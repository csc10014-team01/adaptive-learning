import copy
import hashlib
import json
import time
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.grading.config import GradingConfig
from src.grading.engine import INCOMPLETE_REASON
from src.grading.qwen_client import QwenClient
from src.grading.schemas import ExperimentalRequest
from src.grading.store import GradingStore
from tests.grading.test_engine import envelope

ROOT = Path(__file__).resolve().parents[2]
HEADERS = {"Authorization": "Bearer grading-test"}


@pytest.fixture
def payload():
    return json.loads(
        (ROOT / "src/ui/static/grading-example.json").read_text(encoding="utf-8")
    )


class Snapshots:
    def __init__(self, snapshot):
        self.snapshot, self.calls = snapshot, []

    def load(self, exam_id, revision):
        self.calls.append((exam_id, revision))
        return copy.deepcopy(self.snapshot)


def setup_app(tmp_path, transport, **kwargs):
    config = GradingConfig(
        db_path=tmp_path / "grading.db", **kwargs.pop("settings", {})
    )
    app = create_app(
        teacher_token="grading-test",
        grading_config=config,
        grading_client=QwenClient(config, transport=transport),
        **kwargs,
    )
    return app


def correct_transport(path, payload, timeout):
    data = json.loads(payload["prompt"].split("\nDATA:\n")[-1])
    return envelope(
        {
            "steps": [
                {
                    "evidence": data["student_answer"],
                    "description": "Học sinh tính số cách chọn.",
                    "rubric_ids": ["R1"],
                    "decision": "CORRECT",
                    "skill_errors": [],
                }
            ],
            "final_answer_quote": data["reference_answer"],
        },
        model=payload["model"],
    )


def wait_job(client, job_id, state="COMPLETED"):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/grading/jobs/{job_id}", headers=HEADERS)
        assert response.status_code == 200, response.text
        body = response.json()
        if body["metadata"]["state"] == state:
            return body
        if body["metadata"]["state"] in ("FAILED", "INTERRUPTED"):
            pytest.fail(str(body))
        time.sleep(0.01)
    pytest.fail("Worker did not reach expected state")


def post(client, payload):
    response = client.post("/api/v1/grading/jobs", headers=HEADERS, json=payload)
    assert response.status_code == 202, response.text
    return response.json()["metadata"]["job_id"]


@pytest.mark.parametrize(
    "headers,status", [({}, 401), ({"Authorization": "Bearer wrong"}, 403)]
)
def test_all_grading_routes_require_existing_auth(tmp_path, payload, headers, status):
    app = setup_app(tmp_path, correct_transport)
    with TestClient(app) as client:
        for method, url in [
            ("post", "/api/v1/grading/jobs"),
            ("get", "/api/v1/grading/jobs/G_missing"),
            ("get", "/api/v1/grading/jobs/G_missing/result"),
        ]:
            response = getattr(client, method)(
                url, headers=headers, **({"json": payload} if method == "post" else {})
            )
            assert response.status_code == status
            assert response.headers["cache-control"] == "no-store"
    assert not app.state.grading.config.db_path.exists()


def test_unconfigured_auth_fails_closed(tmp_path, payload):
    app = setup_app(tmp_path, correct_transport)
    app.state.teacher_token = None
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/grading/jobs", json=payload, headers=HEADERS
            ).status_code
            == 503
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "unknown",
        "duplicate_answer",
        "duplicate_question",
        "duplicate_rubric",
        "skill",
        "rubric_skill",
        "reference",
        "absent_text",
        "unknown_field",
    ],
)
def test_invalid_context_rejected_before_inference(tmp_path, payload, mutation):
    calls = []

    def transport(*args):
        calls.append(args)
        return correct_transport(*args)

    if mutation == "missing":
        payload["answers"].pop()
    elif mutation == "unknown":
        payload["answers"][0]["question_id"] = "UNKNOWN"
    elif mutation == "duplicate_answer":
        payload["answers"].append(payload["answers"][0])
    elif mutation == "duplicate_question":
        payload["questions"][1] = payload["questions"][0]
    elif mutation == "duplicate_rubric":
        payload["questions"][0]["rubric"].append(payload["questions"][0]["rubric"][0])
    elif mutation == "skill":
        payload["questions"][0]["skill_ids"] = ["A010"]
    elif mutation == "rubric_skill":
        payload["questions"][0]["rubric"][0]["skill_ids"] = ["A009"]
    elif mutation == "reference":
        payload["questions"][0]["reference_answer"] = "not supported"
    elif mutation == "absent_text":
        del payload["answers"][0]["student_answer"]
    else:
        payload["manual_grade"] = "CORRECT"
    with TestClient(setup_app(tmp_path, transport)) as client:
        response = client.post("/api/v1/grading/jobs", json=payload, headers=HEADERS)
        assert response.status_code == 422
        assert 'student_answer":"' not in response.text
    assert not calls


def test_progress_full_feedback_and_frozen_results(tmp_path, payload):
    second_started, release_second = Event(), Event()

    def transport(path, data, timeout):
        if "SYN_PRODUCT" not in data["prompt"] and "3 áo" in data["prompt"]:
            second_started.set()
            assert release_second.wait(5)
        return correct_transport(path, data, timeout)

    app = setup_app(tmp_path, transport)
    try:
        with TestClient(app) as client:
            start = time.monotonic()
            job_id = post(client, payload)
            assert time.monotonic() - start < 2
            assert second_started.wait(5)
            partial = client.get(
                f"/api/v1/grading/jobs/{job_id}", headers=HEADERS
            ).json()
            assert partial["metadata"]["completed_questions"] == 1
            assert partial["result"]["feedback"] is None
            assert (
                client.get(
                    f"/api/v1/grading/jobs/{job_id}/result", headers=HEADERS
                ).status_code
                == 409
            )
            release_second.set()
            done = wait_job(client, job_id)
            assert done["metadata"]["experimental"] is True
            assert done["metadata"]["exam_revision"] is None
            assert done["metadata"]["completed_questions"] == 2
            assert done["result"]["feedback"]
            assert done["result"]["test_id"] == payload["test_id"]
            assert [
                s["grading_result"]["overall_result"]
                for s in done["result"]["submissions"]
            ] == ["CORRECT", "INCORRECT"]
            assert (
                done["result"]["submissions"][1]["grading_result"][
                    "final_answer_correct"
                ]
                is None
            )
            for _ in range(2):
                assert (
                    client.get(
                        f"/api/v1/grading/jobs/{job_id}/result", headers=HEADERS
                    ).json()
                    == done
                )
            compact = json.dumps(done["result"])
            for field in (
                "calls",
                "raw_response",
                "validation",
                "observed_level",
                "score",
                "repeat",
                "job_id",
            ):
                assert f'"{field}"' not in compact
            with app.state.grading.store.connection() as db:
                stored = db.execute(
                    "SELECT request_json,context_json FROM grading_jobs"
                ).fetchone()
                assert json.loads(stored[0])["answers"] == payload["answers"]
                assert json.loads(stored[1])["approved_snapshot"] is None
                assert (
                    db.execute("SELECT COUNT(*) FROM grading_questions").fetchone()[0]
                    == 2
                )
    finally:
        release_second.set()


def test_blank_is_incorrect_with_no_model_call_or_invented_skill(tmp_path, payload):
    calls = []

    def transport(*args):
        calls.append(args)
        raise AssertionError("No inference for blank answers")

    for answer in payload["answers"]:
        answer["student_answer"] = " \n\t "
    with TestClient(setup_app(tmp_path, transport)) as client:
        done = wait_job(client, post(client, payload))
    assert not calls
    for question in done["result"]["submissions"]:
        grade = question["grading_result"]
        assert (
            grade["overall_result"] == "INCORRECT"
            and grade["final_answer_correct"] is None
        )
        assert grade["errors"][0]["reason"] == INCOMPLETE_REASON
        assert grade["errors"][0]["skill_ids"] == []
        assert question["answer"] == []


@pytest.mark.parametrize(
    "failure,issue",
    [
        (TimeoutError("SENSITIVE"), "provider_timeout"),
        (OSError("SENSITIVE"), "provider_failure"),
    ],
)
def test_provider_failures_complete_and_continue_other_questions(
    tmp_path, payload, failure, issue
):
    calls = []

    def transport(*args):
        calls.append(args)
        if len(calls) == 1:
            raise failure
        return correct_transport(*args)

    with TestClient(setup_app(tmp_path, transport)) as client:
        done = wait_job(client, post(client, payload))
    assert len(calls) == 2
    assert done["metadata"]["state"] == "COMPLETED"
    assert (
        done["metadata"]["uncertain_questions"]
        == done["metadata"]["provider_failures"]
        == 1
    )
    assert done["metadata"]["questions"][0]["issue"] == issue
    assert done["result"]["submissions"][0]["grading_result"]["errors"] == []
    assert "SENSITIVE" not in json.dumps(done)
    assert done["result"]["feedback"]


def test_durable_idempotency_and_conflicting_payload(tmp_path, payload):
    calls = []

    def transport(*args):
        calls.append(args)
        return correct_transport(*args)

    app = setup_app(tmp_path, transport)
    with TestClient(app) as client:
        job_id = post(client, payload)
        done = wait_job(client, job_id)
        assert post(client, payload) == job_id
        changed = copy.deepcopy(payload)
        changed["answers"][0]["student_answer"] += " "
        response = client.post("/api/v1/grading/jobs", headers=HEADERS, json=changed)
        assert (
            response.status_code == 409
            and response.json()["error"]["code"] == "GRADING_IDEMPOTENCY_CONFLICT"
        )
    app.state.grading.thread.join(2)
    with TestClient(setup_app(tmp_path, transport)) as client:
        assert (
            client.get(f"/api/v1/grading/jobs/{job_id}/result", headers=HEADERS).json()
            == done
        )
        assert post(client, payload) == job_id
    assert len(calls) == 2


def test_queue_capacity_and_process_lease(tmp_path, payload):
    entered, release = Event(), Event()

    def transport(*args):
        entered.set()
        assert release.wait(5)
        return correct_transport(*args)

    app = setup_app(tmp_path, transport, settings={"capacity": 1})
    try:
        with TestClient(app) as client:
            job_id = post(client, payload)
            assert entered.wait(3)
            assert post(client, payload) == job_id
            payload["idempotency_key"] = "another"
            assert (
                client.post(
                    "/api/v1/grading/jobs", headers=HEADERS, json=payload
                ).json()["error"]["code"]
                == "GRADING_QUEUE_FULL"
            )
            other = setup_app(tmp_path, correct_transport)
            with TestClient(other) as competing:
                assert (
                    competing.get(
                        f"/api/v1/grading/jobs/{job_id}", headers=HEADERS
                    ).json()["error"]["code"]
                    == "GRADING_WORKER_ALREADY_ACTIVE"
                )
            release.set()
            wait_job(client, job_id)
    finally:
        release.set()


def test_restart_marks_queued_and_running_jobs_interrupted_without_inference(
    tmp_path, payload
):
    app = setup_app(tmp_path, lambda *a: pytest.fail("No automatic resume"))
    store = GradingStore(app.state.grading.config.db_path)
    store.initialize()
    from src.grading.adapter import normalize_request

    parsed = ExperimentalRequest.model_validate(payload)
    first = store.admit(
        parsed, normalize_request(parsed, None), app.state.grading.config
    )
    store.claim()
    parsed.idempotency_key = "queued-second"
    second = store.admit(
        parsed, normalize_request(parsed, None), app.state.grading.config
    )
    with TestClient(app) as client:
        for job in (first, second):
            result = client.get(
                f'/api/v1/grading/jobs/{job["metadata"]["job_id"]}', headers=HEADERS
            ).json()
            assert result["metadata"]["state"] == "INTERRUPTED"
            assert result["result"]["feedback"] is None


def approved_request(payload):
    return {
        "mode": "approved_snapshot",
        "idempotency_key": "approved-case",
        "exam_id": "EX_SYN",
        "exam_revision": 3,
        "student_id": payload["student_id"],
        "answers": payload["answers"],
    }


def approved_snapshot(payload):
    return {
        "exam_id": "EX_SYN",
        "revision": 3,
        "status": "approved",
        "teacher_review": {"notes": "Synthetic adapter test"},
        "student_id": payload["student_id"],
        "questions": [
            {
                "question_id": q["question_id"],
                "content_latex": q["question_text"],
                "answer": {
                    "correct_answer": q["reference_answer"],
                    "explanation": q["reference_solution"],
                },
                "rubric": q["rubric"],
                "skill_ids": q["skill_ids"],
            }
            for q in payload["questions"]
        ],
    }


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("rubric", "GRADING_CONTEXT_NOT_READY"),
        ("student", "GRADING_STUDENT_MISMATCH"),
        ("revision", "GRADING_REVISION_MISMATCH"),
        ("pending", "GRADING_EXAM_NOT_APPROVED"),
        ("membership", "GRADING_QUESTION_MEMBERSHIP"),
    ],
)
def test_approved_errors_before_inference(tmp_path, payload, mutation, code):
    snapshot = approved_snapshot(payload)
    request = approved_request(payload)
    if mutation == "rubric":
        snapshot["questions"][0]["rubric"] = [{"criteria": "Legacy", "sub_score": 1}]
    elif mutation == "student":
        snapshot["student_id"] = "OTHER"
    elif mutation == "revision":
        snapshot["revision"] = 4
    elif mutation == "pending":
        snapshot["status"] = "pending_teacher_review"
    else:
        request["answers"].pop()
    snapshots = Snapshots(snapshot)

    def no_call(*args):
        pytest.fail("Invalid context must not call Qwen")

    with TestClient(
        setup_app(tmp_path, no_call, grading_snapshots=snapshots)
    ) as client:
        response = client.post("/api/v1/grading/jobs", headers=HEADERS, json=request)
        assert response.status_code in (409, 422)
        assert response.json()["error"]["code"] == code
    assert snapshots.calls == [("EX_SYN", 3)]


def test_complete_approved_adapter_uses_only_server_snapshot(tmp_path, payload):
    snapshots = Snapshots(approved_snapshot(payload))
    app = setup_app(tmp_path, correct_transport, grading_snapshots=snapshots)
    with TestClient(app) as client:
        request = approved_request(payload)
        forged = {**request, "questions": payload["questions"]}
        assert (
            client.post(
                "/api/v1/grading/jobs", headers=HEADERS, json=forged
            ).status_code
            == 422
        )
        done = wait_job(client, post(client, request))
        assert (
            done["metadata"]["experimental"] is False
            and done["metadata"]["exam_revision"] == 3
        )
        with app.state.grading.store.connection() as db:
            context = json.loads(
                db.execute("SELECT context_json FROM grading_jobs").fetchone()[0]
            )
            assert context["approved_snapshot"] == snapshots.snapshot


def test_canonical_databases_unmodified_and_ui_accessible(tmp_path, payload):
    paths = [
        ROOT / "data/sample/dataset/question_bank.db",
        ROOT / "data/sample/memory/student_profiles_sample.db",
    ]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    for answer in payload["answers"]:
        answer["student_answer"] = ""
    with TestClient(setup_app(tmp_path, correct_transport)) as client:
        wait_job(client, post(client, payload))
        for page in ("/", "/grading"):
            response = client.get(page)
            assert response.status_code == 200
            assert (
                "frame-ancestors 'none'" in response.headers["content-security-policy"]
            )
        for asset in ("grading.js", "grading.css", "grading-example.json", "app.js"):
            assert client.get("/ui/assets/" + asset).status_code == 200
        assert (
            client.get("/api/v1/grading/jobs/unknown", headers=HEADERS).status_code
            == 404
        )
    assert before == [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]


def test_sqlite_adapter_binds_old_revision_without_writing_snapshot(tmp_path, payload):
    import sqlite3
    from types import SimpleNamespace
    from src.grading.adapter import ExamStoreSnapshots

    path = tmp_path / "exams.db"
    old = approved_snapshot(payload)
    latest = copy.deepcopy(old)
    latest["revision"] = 4
    latest["status"] = "pending_teacher_review"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE exam_revisions(exam_id TEXT,revision INTEGER,body TEXT)"
        )
        for value in (old, latest):
            db.execute(
                "INSERT INTO exam_revisions VALUES (?,?,?)",
                ("EX_SYN", value["revision"], json.dumps(value)),
            )
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    snapshots = ExamStoreSnapshots(SimpleNamespace(path=path))
    with TestClient(
        setup_app(tmp_path, correct_transport, grading_snapshots=snapshots)
    ) as client:
        done = wait_job(client, post(client, approved_request(payload)))
        assert done["metadata"]["exam_revision"] == 3
        request = approved_request(payload)
        request["exam_revision"] = 5
        request["idempotency_key"] = "missing-revision"
        response = client.post("/api/v1/grading/jobs", headers=HEADERS, json=request)
        assert response.status_code == 404
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_optional_debug_cleanup_cannot_delete_submissions_or_results(tmp_path, payload):
    import os
    from src.grading.cleanup import cleanup_debug

    app = setup_app(
        tmp_path,
        correct_transport,
        settings={"debug_enabled": True, "debug_dir": tmp_path / "debug"},
    )
    with TestClient(app) as client:
        job_id = post(client, payload)
        done = wait_job(client, job_id)
        debug_dir = app.state.grading.config.debug_dir
        deadline = time.monotonic() + 3
        while (
            len(list(debug_dir.glob("G_*/*.json"))) < 2 and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        traces = list(debug_dir.glob("G_*/*.json"))
        assert len(traces) == 2
        assert json.loads(traces[0].read_text(encoding="utf-8"))["student_answer"]
        unrelated = debug_dir / "keep.json"
        unrelated.write_text("{}")
        for trace in traces:
            os.utime(trace, (time.time() - 9 * 86400,) * 2)
        assert cleanup_debug(app.state.grading.config, 7) == 2
        assert unrelated.exists()
        assert (
            client.get(f"/api/v1/grading/jobs/{job_id}/result", headers=HEADERS).json()
            == done
        )
        with app.state.grading.store.connection() as db:
            assert (
                json.loads(
                    db.execute("SELECT request_json FROM grading_jobs").fetchone()[0]
                )["answers"]
                == payload["answers"]
            )


def test_interruption_preserves_processed_question_without_full_feedback(
    tmp_path, payload
):
    from src.grading.adapter import normalize_request
    from src.grading.service import blank_row, compact

    app = setup_app(tmp_path, correct_transport)
    store = app.state.grading.store
    store.initialize()
    parsed = ExperimentalRequest.model_validate(payload)
    context = normalize_request(parsed, None)
    envelope = store.admit(parsed, context, app.state.grading.config)
    job_id = envelope["metadata"]["job_id"]
    store.claim()
    case = {**context.questions[0].model_dump(), "student_answer": ""}
    row = blank_row(case)
    partial = compact(context, [row])
    store.processed(
        job_id,
        1,
        partial["submissions"][0],
        {
            "question_id": case["question_id"],
            "seconds": 0,
            "verdict": "INCORRECT",
            "issue": None,
        },
    )
    with TestClient(app) as client:
        result = client.get(f"/api/v1/grading/jobs/{job_id}", headers=HEADERS).json()
        assert result["metadata"]["state"] == "INTERRUPTED"
        assert result["metadata"]["completed_questions"] == 1
        assert result["result"] == partial


def test_unexpected_processing_failure_is_failed_job_not_student_mistake(
    tmp_path, payload, monkeypatch
):
    import src.grading.service as service

    def broken(*args, **kwargs):
        raise RuntimeError("SENSITIVE_INTERNAL_DATA")

    monkeypatch.setattr(service, "grade_question", broken)
    with TestClient(setup_app(tmp_path, correct_transport)) as client:
        job_id = post(client, payload)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            response = client.get(f"/api/v1/grading/jobs/{job_id}", headers=HEADERS)
            result = response.json()
            if result["metadata"]["state"] == "FAILED":
                break
            time.sleep(0.01)
        assert result["metadata"]["state"] == "FAILED"
        assert result["result"]["submissions"] == []
        assert result["result"]["feedback"] is None
        assert "SENSITIVE" not in response.text


def test_concurrent_identical_submissions_admit_only_one_job(tmp_path, payload):
    from concurrent.futures import ThreadPoolExecutor

    calls = []

    def transport(*args):
        calls.append(args)
        return correct_transport(*args)

    app = setup_app(tmp_path, transport)
    try:
        with ThreadPoolExecutor(max_workers=6) as executor:
            jobs = list(
                executor.map(
                    lambda _: app.state.grading.submit(
                        ExperimentalRequest.model_validate(payload)
                    ),
                    range(8),
                )
            )
        assert len({job["metadata"]["job_id"] for job in jobs}) == 1
        with TestClient(app) as client:
            wait_job(client, jobs[0]["metadata"]["job_id"])
        with app.state.grading.store.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM grading_jobs").fetchone()[0] == 1
        assert len(calls) == 2
    finally:
        app.state.grading.stop()


def test_question_progress_and_completion_writes_are_atomic(tmp_path, payload):
    from src.grading.adapter import normalize_request
    from src.grading.service import blank_row, compact

    parsed = ExperimentalRequest.model_validate(payload)
    context = normalize_request(parsed, None)
    config = GradingConfig(db_path=tmp_path / "grading.db")
    store = GradingStore(config.db_path)
    store.initialize()
    job_id = store.admit(parsed, context, config)["metadata"]["job_id"]
    store.claim()
    rows = [
        blank_row({**q.model_dump(), "student_answer": ""}) for q in context.questions
    ]
    partial, full = compact(context, rows[:1]), compact(context, rows)

    def progress(index):
        return {
            "question_id": context.questions[index].question_id,
            "seconds": 0,
            "verdict": "INCORRECT",
            "issue": None,
        }

    with pytest.raises(ValueError, match="partial exam"):
        store.processed(
            job_id, 1, partial["submissions"][0], progress(0), "Premature feedback"
        )
    assert store.get(job_id)["metadata"]["completed_questions"] == 0
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM grading_questions").fetchone()[0] == 0
    store.processed(job_id, 1, partial["submissions"][0], progress(0))
    with pytest.raises(ValueError, match="Full-exam feedback"):
        store.processed(job_id, 2, full["submissions"][1], progress(1))
    assert store.get(job_id)["result"] == partial
    assert store.get(job_id)["metadata"]["state"] == "RUNNING"
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM grading_questions").fetchone()[0] == 1
    store.processed(job_id, 2, full["submissions"][1], progress(1), full["feedback"])
    assert store.get(job_id)["metadata"]["state"] == "COMPLETED"
    assert store.get(job_id)["result"] == full
