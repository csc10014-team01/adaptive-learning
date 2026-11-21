"""Application-owned transactional jobs, preserved inputs and compact results."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.api.data_adapter import ApiFailure
from src.grading.engine import GRADING_REVISION

INTEGRATION_REVISION = "W08-2026-11-21-teacher-workflow-v2"


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint(payload):
    return hashlib.sha256(
        encode(payload.model_dump(mode="json")).encode("utf-8")
    ).hexdigest()


class GradingStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS grading_jobs (
                job_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL, request_json TEXT NOT NULL,
                context_json TEXT NOT NULL, state TEXT NOT NULL,
                metadata_json TEXT NOT NULL, result_json TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS grading_questions (
                job_id TEXT NOT NULL, position INTEGER NOT NULL,
                question_id TEXT NOT NULL, compact_json TEXT NOT NULL,
                progress_json TEXT NOT NULL, PRIMARY KEY(job_id, question_id),
                UNIQUE(job_id, position))""")

    def list_jobs(self, exam_id=None, limit=20):
        where = " WHERE json_extract(metadata_json, '$.mode')='approved_snapshot' AND json_extract(metadata_json, '$.test_id')=?" if exam_id else ""
        parameters = (exam_id, limit) if exam_id else (limit,)
        with self.connection() as db:
            rows = db.execute(
                "SELECT metadata_json FROM grading_jobs" + where + " ORDER BY rowid DESC LIMIT ?",
                parameters,
            ).fetchall()
        return [json.loads(row["metadata_json"]) for row in rows]

    def existing(self, key, request_hash):
        with self.connection() as db:
            row = db.execute(
                "SELECT job_id, request_hash FROM grading_jobs WHERE idempotency_key=?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise ApiFailure(
                409,
                "GRADING_IDEMPOTENCY_CONFLICT",
                "Idempotency key đã dùng cho nội dung khác; dùng key mới cho bài làm mới.",
            )
        return self.get(row["job_id"])

    def admit(self, payload, context, config):
        body_hash = fingerprint(payload)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT job_id, request_hash FROM grading_jobs WHERE idempotency_key=?",
                (payload.idempotency_key,),
            ).fetchone()
            if previous:
                if previous["request_hash"] != body_hash:
                    raise ApiFailure(
                        409,
                        "GRADING_IDEMPOTENCY_CONFLICT",
                        "Idempotency key đã dùng cho nội dung khác.",
                    )
                job_id = previous["job_id"]
            else:
                active = db.execute(
                    "SELECT COUNT(*) FROM grading_jobs WHERE state IN ('QUEUED','RUNNING')"
                ).fetchone()[0]
                if active >= config.capacity:
                    raise ApiFailure(
                        503,
                        "GRADING_QUEUE_FULL",
                        "Hàng đợi chấm đã đầy; chờ job đang chạy hoàn tất rồi gửi lại cùng key.",
                    )
                job_id = "G_" + uuid4().hex
                metadata = {
                    "job_id": job_id,
                    "state": "QUEUED",
                    "mode": context.mode,
                    "experimental": context.mode == "experimental",
                    "test_id": context.test_id,
                    "student_id": context.student_id,
                    "exam_revision": context.exam_revision,
                    "engine_revision": GRADING_REVISION,
                    "integration_revision": INTEGRATION_REVISION,
                    "configuration": {
                        **config.model_dump(
                            mode="json",
                            include={
                                "model",
                                "base_url",
                                "timeout_seconds",
                                "num_predict",
                                "num_ctx",
                                "max_repairs",
                            },
                        ),
                        "think": False,
                        "temperature": 0,
                        "seed": 42,
                    },
                    "created_at": now(),
                    "started_at": None,
                    "finished_at": None,
                    "elapsed_seconds": 0,
                    "completed_questions": 0,
                    "total_questions": len(context.questions),
                    "definite_questions": 0,
                    "uncertain_questions": 0,
                    "provider_failures": 0,
                    "error_code": None,
                    "questions": [],
                }
                result = {
                    "test_id": context.test_id,
                    "student_id": context.student_id,
                    "submissions": [],
                    "feedback": None,
                }
                db.execute(
                    "INSERT INTO grading_jobs VALUES (?,?,?,?,?,?,?,?)",
                    (
                        job_id,
                        payload.idempotency_key,
                        body_hash,
                        payload.model_dump_json(),
                        context.model_dump_json(),
                        "QUEUED",
                        encode(metadata),
                        encode(result),
                    ),
                )
        return self.get(job_id)

    def get(self, job_id):
        with self.connection() as db:
            row = db.execute(
                "SELECT metadata_json, result_json FROM grading_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise ApiFailure(404, "GRADING_JOB_NOT_FOUND", "Không tìm thấy job chấm.")
        # Fresh decoded objects; retrieving never rewrites or regenerates feedback.
        return {"metadata": json.loads(row[0]), "result": json.loads(row[1])}

    def claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM grading_jobs WHERE state='QUEUED' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            metadata = json.loads(row["metadata_json"])
            metadata.update(state="RUNNING", started_at=now())
            db.execute(
                "UPDATE grading_jobs SET state='RUNNING',metadata_json=? WHERE job_id=?",
                (encode(metadata), row["job_id"]),
            )
            return row["job_id"], json.loads(row["context_json"])

    def processed(self, job_id, position, submission, progress, feedback=None):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT metadata_json,result_json,state FROM grading_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row["state"] != "RUNNING":
                return
            metadata, result = json.loads(row[0]), json.loads(row[1])
            db.execute(
                "INSERT INTO grading_questions VALUES (?,?,?,?,?)",
                (
                    job_id,
                    position,
                    submission["question_id"],
                    encode(submission),
                    encode(progress),
                ),
            )
            result["submissions"].append(submission)
            metadata["questions"].append(progress)
            metadata["completed_questions"] += 1
            metadata["elapsed_seconds"] = sum(
                p["seconds"] for p in metadata["questions"]
            )
            uncertain = progress["verdict"] == "UNCERTAIN"
            metadata["uncertain_questions"] += int(uncertain)
            metadata["definite_questions"] += int(not uncertain)
            metadata["provider_failures"] += int(
                progress["issue"] in ("provider_timeout", "provider_failure")
            )
            if metadata["completed_questions"] == metadata["total_questions"]:
                if feedback is None:
                    raise ValueError(
                        "Full-exam feedback must be persisted with the last processed question"
                    )
                result["feedback"] = feedback
                metadata.update(state="COMPLETED", finished_at=now())
            elif feedback is not None:
                raise ValueError("Feedback cannot be attached to a partial exam")
            db.execute(
                "UPDATE grading_jobs SET state=?, metadata_json=?, result_json=? WHERE job_id=?",
                (
                    metadata["state"],
                    encode(metadata),
                    encode(result),
                    job_id,
                ),
            )

    def finish_unfinished(
        self, state="INTERRUPTED", code="GRADING_INTERRUPTED", job_id=None
    ):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            query = "SELECT job_id,metadata_json FROM grading_jobs WHERE state IN ('QUEUED','RUNNING')"
            rows = db.execute(
                query + (" AND job_id=?" if job_id else ""), (job_id,) if job_id else ()
            ).fetchall()
            for row in rows:
                metadata = json.loads(row[1])
                metadata.update(state=state, error_code=code, finished_at=now())
                db.execute(
                    "UPDATE grading_jobs SET state=?,metadata_json=? WHERE job_id=?",
                    (state, encode(metadata), row[0]),
                )


class ProcessLease:
    """Fail closed when two local processes try to own the same grading store."""

    def __init__(self, path):
        self.path = path.with_suffix(path.suffix + ".worker.lock")
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        try:
            if __import__("os").name == "nt":
                import msvcrt

                self.handle.seek(0)
                if not self.handle.read(1):
                    self.handle.write(b"0")
                    self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            self.handle = None
            raise ApiFailure(
                503,
                "GRADING_WORKER_ALREADY_ACTIVE",
                "Chỉ chạy một process/worker cho cùng GRADING_DB.",
            ) from None

    def close(self):
        if self.handle:
            self.handle.close()
            self.handle = None
