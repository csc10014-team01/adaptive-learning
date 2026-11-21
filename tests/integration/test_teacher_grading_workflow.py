"""Exercise generation, reviewed snapshot grading, retries and restart as one flow."""

import copy
import json
import time

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.schemas import ExamResponse
from src.grading.config import GradingConfig
from src.grading.qwen_client import QwenClient
from src.grading.adapter import normalize_grading_reference

HEADERS = {"Authorization": "Bearer workflow-test"}
REQUEST = {
    "student_id": "DEMO_NEW_001", "generation_mode": "default_blueprint",
    "selected_topic_ids": ["combinatorics"], "total_questions": 2,
    "duration_minutes": 45,
    "difficulty_distribution": {"recognition": 50, "understanding": 50,
                                "application": 0, "advanced_application": 0},
}


def application(tmp_path, calls):
    config = GradingConfig(db_path=tmp_path / "grading.db")

    def transport(path, payload, timeout):
        data = json.loads(payload["prompt"].split("\nDATA:\n")[-1])
        calls.append(data)
        return {"model": payload["model"], "done": True, "done_reason": "stop",
                "response": json.dumps({"steps": [{
                    "evidence": data["student_answer"], "description": "Học sinh kết luận số cách.",
                    "rubric_ids": ["R1"], "decision": "CORRECT", "skill_errors": [],
                }], "final_answer_quote": data["reference_answer"]}, ensure_ascii=False)}

    return create_app(
        backend="fake", profile_source="json", teacher_token="workflow-test",
        exam_db=tmp_path / "exams.db", grading_config=config,
        grading_client=QwenClient(config, transport=transport),
    )


def review(exam):
    return {"expected_revision": exam["revision"], "grading_contexts": [{
        "question_id": q["question_id"], "reference_answer": q["answer"]["correct_answer"],
        "rubric": [{"id": "R1", "description": q["answer"]["explanation"], "skill_ids": q["skill_ids"]}],
    } for q in exam["questions"]]}


def wait(client, job_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(f"/api/v1/grading/jobs/{job_id}").json()
        if body["metadata"]["state"] == "COMPLETED":
            return body
        assert body["metadata"]["state"] in ("QUEUED", "RUNNING"), body
        time.sleep(.01)
    pytest.fail("Grading job did not complete")


def test_generate_approve_grade_retry_and_reopen_after_restart(tmp_path):
    calls = []
    with TestClient(application(tmp_path, calls), headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=REQUEST)
        assert response.status_code == 200, response.text
        exam = response.json()
        base = f"/api/v1/exams/{exam['exam_id']}"
        assert client.get(base + "/grading-context?revision=1").json()["error"]["code"] == "GRADING_EXAM_NOT_APPROVED"
        response = client.post(base + "/approve", json=review(exam))
        assert response.status_code == 200, response.text
        approved = response.json()
        assert approved["revision"] == 2
        assert approved["quality_report"]["status"] == "NEEDS_REVIEW"
        prepared = client.get(base + "/grading-context?revision=2")
        assert prepared.status_code == 200, prepared.text
        prepared = prepared.json()
        assert prepared["student_id"] == REQUEST["student_id"]
        assert len(prepared["questions"]) == 2
        assert all(a["student_answer"] == "" for a in prepared["answers"])
        assert client.get(base + "/grading-context?revision=99").status_code == 404

        # Keep the original approved revision gradeable after a later draft exists.
        newer = copy.deepcopy(approved)
        newer.update(revision=3, status="pending_teacher_review", teacher_review=None, quality_report=None)
        for q in newer["questions"]:
            q["grading_context"] = None
            q["validation"]["teacher_approved"] = False
        client.app.state.exams.replace(ExamResponse.model_validate(newer), expected_revision=2)
        assert client.get(base + "/grading-context?revision=2").status_code == 200
        assert client.get(base + "/grading-context?revision=3").status_code == 409

        request = {
            "mode": "approved_snapshot", "idempotency_key": "workflow-submission-1",
            "exam_id": exam["exam_id"], "exam_revision": 2, "student_id": exam["student_id"],
            "answers": [{"question_id": q["question_id"],
                         "student_answer": f"Vậy kết quả là {q['grading_context']['reference_answer']}." if i == 0 else ""}
                        for i, q in enumerate(approved["questions"])],
        }
        response = client.post("/api/v1/grading/jobs", json=request)
        assert response.status_code == 202, response.text
        job_id = response.json()["metadata"]["job_id"]
        completed = wait(client, job_id)
        assert [s["grading_result"]["overall_result"] for s in completed["result"]["submissions"]] == ["CORRECT", "INCORRECT"]
        assert len(calls) == 1  # Explicit blank is handled without inference.
        assert calls[0]["reference_answer"] == approved["questions"][0]["grading_context"]["reference_answer"]
        assert client.post("/api/v1/grading/jobs", json=request).json() == completed
        assert len(calls) == 1
        changed = copy.deepcopy(request)
        changed["answers"][0]["student_answer"] += " Thay đổi."
        assert client.post("/api/v1/grading/jobs", json=changed).status_code == 409
        assert client.get(f"/api/v1/grading/jobs?exam_id={exam['exam_id']}").json()["items"][0]["job_id"] == job_id

    with TestClient(application(tmp_path, calls), headers=HEADERS) as client:
        assert client.get(base).json()["revision"] == 3
        assert client.get(base + "/grading-context?revision=2").status_code == 200
        assert client.get(f"/api/v1/grading/jobs/{job_id}/result").json() == completed
        assert client.post("/api/v1/grading/jobs", json=request).json() == completed
        assert len(calls) == 1


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "skill", "reference", "wrong_answer", "rubric_id"])
def test_invalid_grading_review_does_not_approve_or_change_snapshot(tmp_path, mutation):
    with TestClient(application(tmp_path, []), headers=HEADERS) as client:
        exam = client.post("/api/v1/exams/generate", json=REQUEST).json()
        body = review(exam)
        if mutation == "missing":
            body["grading_contexts"].pop()
        elif mutation == "duplicate":
            body["grading_contexts"][1] = copy.deepcopy(body["grading_contexts"][0])
        elif mutation == "skill":
            body["grading_contexts"][0]["rubric"][0]["skill_ids"] = ["A009"]
        elif mutation == "reference":
            body["grading_contexts"][0]["reference_answer"] = "not a mathematical expression"
        elif mutation == "wrong_answer":
            body["grading_contexts"][0]["reference_answer"] = "999999"
        else:
            body["grading_contexts"][0]["rubric"] *= 2
        base = f"/api/v1/exams/{exam['exam_id']}"
        response = client.post(base + "/approve", json=body)
        assert response.status_code == 422, response.text
        assert client.get(base).json() == exam


def test_new_read_endpoints_require_teacher_auth(tmp_path):
    with TestClient(application(tmp_path, [])) as client:
        assert client.get("/api/v1/exams/EX/grading-context?revision=2").status_code == 401
        assert client.get("/api/v1/grading/jobs").status_code == 401


@pytest.mark.parametrize("text,expected", [
    ("53 cách chọn", "53"), ("43200 cách", "43200"), ("C(20,2) = 190", "190"),
    ("1/2", "1/2"), ("Có 3 trường hợp và 5 cách chọn", None),
    ("A_5^3 = 60", None),
])
def test_reference_formatting_does_not_guess_from_prose(text, expected):
    assert normalize_grading_reference(text) == expected


def test_reference_equation_must_be_true():
    with pytest.raises(ValueError, match="không đúng"):
        normalize_grading_reference("C(20,2) = 191")


def test_teacher_review_saves_normalized_reference_and_preserves_original_answer(tmp_path):
    with TestClient(application(tmp_path, []), headers=HEADERS) as client:
        exam = client.post("/api/v1/exams/generate", json=REQUEST).json()
        body = review(exam)
        for item in body["grading_contexts"]:
            item["reference_answer"] += " cách chọn"
        response = client.post(f"/api/v1/exams/{exam['exam_id']}/approve", json=body)
        assert response.status_code == 200, response.text
        for old, new in zip(exam["questions"], response.json()["questions"]):
            assert new["answer"] == old["answer"]
            assert new["grading_context"]["reference_answer"] == old["answer"]["correct_answer"]
