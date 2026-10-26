"""Durable teacher review and regeneration using a local HTTP provider double."""

import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from src.api.data_adapter import ApiFailure
from src.api.exam_store import SQLiteExamStore
from src.api.main import create_app
from src.api.schemas import ApproveExamRequest, ExamResponse
from src.orchestration.review_service import approve_exam
from tests.integration.test_real_api import HEADERS, ollama, payload


def approve_payload(exam):
    return {"expected_revision": exam["revision"],
            "accepted_question_ids": [q["question_id"] for q in exam["questions"]], "notes": "Checked all questions."}


def test_approval_regeneration_and_revision_history_survive_restart(tmp_path, ollama):
    qwen, calls, state = ollama
    path = tmp_path / "exams.db"
    app = create_app(backend="qwen", teacher_token="teacher-test", qwen_client=qwen, exam_db=path)
    with TestClient(app, headers=HEADERS) as c:
        exam = c.post("/api/v1/exams/generate", json=payload()).json()
        base = "/api/v1/exams/" + exam["exam_id"]
        accepted = c.post(base + "/approve", json=approve_payload(exam))
        assert accepted.status_code == 200, accepted.text
        approved = accepted.json()
        assert approved["status"] == "approved" and approved["revision"] == 2
        assert all(q["validation"]["teacher_approved"] for q in approved["questions"])
        assert len(calls) == len(exam["questions"])
        assert c.post(base + "/approve", json=approve_payload(exam)).status_code == 409
        qid = exam["questions"][0]["question_id"]
        url = base + f"/questions/{qid}/regenerate"
        assert c.post(url, json={"expected_revision": 1}).status_code == 409
        regenerated = c.post(url, json={"expected_revision": 2})
        assert regenerated.status_code == 200, regenerated.text
        updated = regenerated.json()
        assert updated["revision"] == 3 and updated["status"] == "pending_teacher_review"
        assert updated["teacher_review"] is None
        assert all(not q["validation"]["teacher_approved"] for q in updated["questions"])
        assert updated["questions"][0]["question_id"] != qid
        assert updated["questions"][0]["answer"] == exam["questions"][0]["answer"]
        assert [q["source_ref"] for q in updated["questions"]] == [q["source_ref"] for q in exam["questions"]]
        assert len(calls) == len(exam["questions"]) + 1
    with TestClient(create_app(backend="qwen", teacher_token="teacher-test", exam_db=path), headers=HEADERS) as c:
        assert c.get(base).json() == updated
    with sqlite3.connect(path) as connection:
        versions = connection.execute("SELECT revision, body FROM exam_revisions ORDER BY revision").fetchall()
    assert [v[0] for v in versions] == [1, 2, 3]
    assert json.loads(versions[1][1])["teacher_review"]["notes"] == "Checked all questions."


def test_failed_regeneration_preserves_approved_draft(tmp_path, ollama):
    qwen, calls, state = ollama
    app = create_app(backend="qwen", teacher_token="teacher-test", qwen_client=qwen, exam_db=tmp_path / "e.db")
    with TestClient(app, headers=HEADERS) as c:
        exam = c.post("/api/v1/exams/generate", json=payload()).json()
        base = "/api/v1/exams/" + exam["exam_id"]
        approved = c.post(base + "/approve", json=approve_payload(exam)).json()
        state["kind"] = "numbers"
        result = c.post(base + f"/questions/{exam['questions'][0]['question_id']}/regenerate",
                        json={"expected_revision": 2})
        assert result.status_code == 502
        assert c.get(base).json() == approved


def test_review_requires_access_and_explicit_complete_acceptance():
    app = create_app(backend="fake", teacher_token="teacher-test")
    with TestClient(app) as c:
        req = payload("DEMO_NEW_001", generation_mode="standard")
        exam = c.post("/api/v1/exams/generate", json=req, headers=HEADERS).json()
        url = f"/api/v1/exams/{exam['exam_id']}/approve"
        assert c.post(url, json=approve_payload(exam)).status_code == 401
        body = approve_payload(exam)
        body["accepted_question_ids"] = body["accepted_question_ids"][:1]
        assert c.post(url, json=body, headers=HEADERS).status_code == 422
        assert c.post(url, json=approve_payload(exam), headers=HEADERS).status_code == 200


def test_store_rejects_stale_write(tmp_path, ollama):
    qwen, _, _ = ollama
    path = tmp_path / "e.db"
    with TestClient(create_app(backend="qwen", teacher_token="teacher-test", qwen_client=qwen, exam_db=path), headers=HEADERS) as c:
        draft = c.post("/api/v1/exams/generate", json=payload()).json()
    original = ExamResponse.model_validate(draft)
    accepted = approve_exam(original, ApproveExamRequest.model_validate(approve_payload(draft)))
    first, second = SQLiteExamStore(path), SQLiteExamStore(path)
    first.replace(accepted, expected_revision=1)
    with pytest.raises(ApiFailure) as failure:
        second.replace(accepted, expected_revision=1)
    assert failure.value.code == "EXAM_REVISION_CONFLICT"


def test_changed_source_text_blocks_regeneration_before_model_call(tmp_path, ollama):
    qwen, calls, _ = ollama
    app = create_app(backend="qwen", teacher_token="teacher-test", qwen_client=qwen, exam_db=tmp_path / "e.db")
    with TestClient(app, headers=HEADERS) as c:
        draft = c.post("/api/v1/exams/generate", json=payload()).json()
        first = draft["questions"][0]
        source = next(q for q in app.state.data.questions if q.question_id == first["source_ref"]["id"])
        source.content += " Điều kiện nguồn đã thay đổi."
        before = len(calls)
        url = f"/api/v1/exams/{draft['exam_id']}/questions/{first['question_id']}/regenerate"
        result = c.post(url, json={"expected_revision": 1})
        assert result.status_code == 409 and result.json()["error"]["code"] == "SOURCE_CHANGED"
        assert len(calls) == before


def test_generator_cannot_self_approve():
    from src.api.data_adapter import StaticDataAdapter
    from src.api.services import FakeExamGenerator

    class SelfApproving:
        def generate(self, req, student):
            draft = FakeExamGenerator(StaticDataAdapter()).generate(req, student)
            return approve_exam(draft, ApproveExamRequest(expected_revision=1,
                accepted_question_ids=[q.question_id for q in draft.questions]))

    app = create_app(backend="fake", teacher_token="teacher-test", generator=SelfApproving())
    with TestClient(app, headers=HEADERS) as c:
        result = c.post("/api/v1/exams/generate", json=payload("DEMO_NEW_001", generation_mode="standard"))
        assert result.status_code == 500 and result.json()["error"]["code"] == "INVALID_EXAM_OUTPUT"
