"""One bounded local worker. No generic inference retry or canonical DB writer."""

import logging
from threading import Event, RLock, Thread

from src.api.data_adapter import ApiFailure
from src.grading.adapter import normalize_request
from src.grading.engine import (
    INCOMPLETE_REASON,
    exam_payload,
    grade_question,
    review_result,
)
from src.grading.schemas import CompactExam, GradingContext
from src.grading.store import GradingStore, ProcessLease, encode, fingerprint

logger = logging.getLogger(__name__)


def blank_row(case):
    result = review_result()
    result.update(
        grading_status="AI_GRADED",
        requires_teacher=False,
        overall_result="INCORRECT",
        errors=[
            {
                "step": 1,
                "error_type": "INCOMPLETE_SOLUTION",
                "skill_ids": [],
                "reason": INCOMPLETE_REASON,
            }
        ],
    )
    return {
        **case,
        "proposal": None,
        "grading_result": result,
        "validation": {},
        "wall_seconds": 0,
        "calls": [],
    }


def compact(context, rows):
    output = exam_payload(rows, 1, len(context.questions))
    # Synthetic benchmark identity/repeat/complete are not business inputs.
    return CompactExam(
        test_id=context.test_id,
        student_id=context.student_id,
        submissions=output["submissions"],
        feedback=output["feedback"],
    ).model_dump(mode="json")


def question_issue(row):
    if row.get("timed_out"):
        return "provider_timeout"
    kind = row.get("validation", {}).get("review_kind")
    if kind == "provider":
        return "provider_failure"
    if row["grading_result"]["overall_result"] != "UNCERTAIN":
        return None
    return "invalid_model_output" if kind == "schema" else "unresolved_judgment"


class GradingService:
    def __init__(self, config, client, snapshots):
        self.config, self.client, self.snapshots = config, client, snapshots
        self.store = GradingStore(config.db_path)
        self.lease = ProcessLease(config.db_path)
        self.lock = RLock()
        self.wake, self.stopping = Event(), Event()
        self.thread = None

    def start(self):
        with self.lock:
            if self.thread is not None:
                if self.stopping.is_set():
                    raise ApiFailure(
                        503,
                        "GRADING_SHUTTING_DOWN",
                        "Worker đang dừng; khởi động lại backend để gửi job mới.",
                    )
                if not self.thread.is_alive():
                    raise ApiFailure(
                        503,
                        "GRADING_WORKER_UNAVAILABLE",
                        "Worker đã dừng do lỗi nội bộ; khởi động lại backend và kiểm tra runtime storage.",
                    )
                return
            self.lease.acquire()
            try:
                self.store.initialize()
                self.store.finish_unfinished()
                self.thread = Thread(target=self._run, name="mira-grading", daemon=True)
                self.thread.start()
            except Exception:
                self.lease.close()
                raise

    def submit(self, payload):
        self.start()
        # Return an identical durable request even if its source is no longer current.
        existing = self.store.existing(payload.idempotency_key, fingerprint(payload))
        if existing:
            return existing
        context = normalize_request(payload, self.snapshots)
        with self.lock:
            if self.stopping.is_set():
                raise ApiFailure(503, "GRADING_SHUTTING_DOWN", "Worker đang dừng.")
            envelope = self.store.admit(payload, context, self.config)
            self.wake.set()
            return envelope

    def get(self, job_id):
        self.start()
        return self.store.get(job_id)

    def stop(self):
        with self.lock:
            if self.thread is None:
                return
            self.stopping.set()
            self.wake.set()
            self.store.finish_unfinished()
        # In-flight HTTP is bounded by the configured timeout. Do not resume jobs.
        # The thread retains the process lease until its outstanding call returns.
        self.thread.join(timeout=0.2)

    def _run(self):
        try:
            while not self.stopping.is_set():
                claimed = self.store.claim()
                if claimed is None:
                    self.wake.wait(0.5)
                    self.wake.clear()
                    continue
                job_id, snapshot = claimed
                try:
                    self._process(job_id, GradingContext.model_validate(snapshot))
                except (
                    Exception
                ):  # Unexpected implementation/storage failure, not a student error.
                    logger.error("Grading job %s failed internally", job_id)
                    self.store.finish_unfinished(
                        "FAILED", "GRADING_PROCESSING_FAILED", job_id
                    )
        except Exception:
            logger.error("Grading worker stopped after an internal storage failure")
            self.store.finish_unfinished("FAILED", "GRADING_WORKER_FAILED")
        finally:
            self.lease.close()

    def _process(self, job_id, context):
        rows = []
        answers = {a.question_id: a.student_answer for a in context.answers}
        for position, question in enumerate(context.questions, 1):
            if self.stopping.is_set():
                return
            case = question.model_dump(exclude={"reference_solution"})
            case["student_answer"] = answers[question.question_id]
            row = (
                blank_row(case)
                if not case["student_answer"].strip()
                else grade_question(
                    case,
                    self.config.model,
                    budget=self.config.num_predict,
                    context=self.config.num_ctx,
                    timeout=self.config.timeout_seconds,
                    max_repairs=self.config.max_repairs,
                    client=self.client,
                )
            )
            rows.append(row)
            output = compact(context, rows)
            if self.stopping.is_set():
                return
            self.store.processed(
                job_id,
                position,
                output["submissions"][-1],
                {
                    "question_id": question.question_id,
                    "seconds": row["wall_seconds"],
                    "inference_calls": len(row["calls"]),
                    "repair_calls": row.get("repair_calls", 0),
                    "verdict": row["grading_result"]["overall_result"],
                    "issue": question_issue(row),
                },
                output["feedback"],
            )
            # In-memory evidence lives through the transaction above. Optional
            # debug files are written only after compact results are durable.
            if self.config.debug_enabled:
                try:
                    folder = self.config.debug_dir / job_id
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f"{position:02d}.json").write_text(
                        encode(row), encoding="utf-8"
                    )
                except OSError:
                    logger.warning(
                        "Could not save optional grading diagnostics for %s", job_id
                    )
