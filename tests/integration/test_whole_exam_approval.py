"""Whole-exam approval is independent of optional individual acknowledgements."""

from copy import deepcopy
import hashlib

from fastapi.testclient import TestClient
import pytest

from src.api.data_adapter import ApiFailure, DEFAULT_BANK
from src.api.m3_adapter import M3DataAdapter
from src.api.schemas import ApproveExamRequest
from src.orchestration.review_service import approve_exam
from tests.integration.test_hybrid_exam_api import application, EchoTemplateClient, HEADERS
from tests.unit.test_planner import request


def test_latest_bank_mixed_exam_approve_with_zero_individual_reviews_persists_and_can_be_reapproved(tmp_path):
    before = hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest()
    data, model = M3DataAdapter(bank_path=DEFAULT_BANK), EchoTemplateClient()
    app, _ = application(tmp_path, data, model)
    expected = dict(recognition=3, understanding=3, application=3, advanced_application=1)
    with TestClient(app, headers=HEADERS) as client:
        body = request(10, student_id="ST011").model_dump(mode="json")
        preview = client.post("/api/v1/exams/plan", json=body).json()
        result = client.post("/api/v1/exams/generate", json=body)
        assert result.status_code == 200, result.text
        draft = result.json()
        assert draft["status"] == "pending_teacher_review" and draft["revision"] == 1
        assert {q["source_ref"]["kind"] for q in draft["questions"]} == {"question", "template"}
        assert all(not q["validation"]["teacher_approved"] for q in draft["questions"])
        assert preview["quota_summary"] == draft["planner_summary"]["quota_summary"]
        assert preview["quota_summary"]["achieved_levels"] == expected
        assert len(preview["selection_diagnostics"]["substitutions"]) == 4
        url = f"/api/v1/exams/{draft['exam_id']}"
        response = client.post(url + "/approve", json={"expected_revision": 1, "notes": "Reviewed whole exam visually."})
        assert response.status_code == 200, response.text
        approved = response.json()
        assert approved["status"] == "approved" and approved["revision"] == 2
        assert approved["teacher_review"]["notes"] == "Reviewed whole exam visually."
        assert approved["questions"] == draft["questions"]
        assert all(not q["validation"]["teacher_approved"] for q in approved["questions"])
        assert client.get(url).json() == approved
        assert client.post(url + "/approve", json={"expected_revision": 1}).status_code == 409
        immutable = next(q for q in approved["questions"] if q["source_ref"]["kind"] == "question")
        assert client.post(url + f"/questions/{immutable['question_id']}/regenerate",
                           json={"expected_revision": 2}).status_code == 409
        target = next(q for q in approved["questions"] if q["source_ref"]["kind"] == "template")
        regen_url = url + f"/questions/{target['question_id']}/regenerate"
        model.fail = True
        assert client.post(regen_url, json={"expected_revision": 2}).status_code == 502
        assert client.get(url).json() == approved
        model.fail = False
        regenerated = client.post(regen_url, json={"expected_revision": 2})
        assert regenerated.status_code == 200, regenerated.text
        changed = regenerated.json()
        assert changed["revision"] == 3 and changed["status"] == "pending_teacher_review"
        assert changed["teacher_review"] is None
        assert all(not q["validation"]["teacher_approved"] for q in changed["questions"])
        reapproved = client.post(url + "/approve", json={"expected_revision": 3})
        assert reapproved.status_code == 200
        final = reapproved.json()
        assert final["status"] == "approved" and final["revision"] == 4
        assert all(not q["validation"]["teacher_approved"] for q in final["questions"])
    restarted, _ = application(tmp_path, M3DataAdapter(bank_path=DEFAULT_BANK))
    with TestClient(restarted, headers=HEADERS) as client:
        assert client.get(url).json() == final
    assert hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("invalid", ["blocking_error", "not_evaluated", "changed_answer", "changed_template_answer"])
def test_invalid_or_unvalidated_drafts_cannot_be_approved_and_no_change_is_persisted(tmp_path, invalid):
    app, _ = application(tmp_path)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
        assert response.status_code == 200
        draft = app.state.exams.get(response.json()["exam_id"])
        broken = deepcopy(draft)
        if invalid == "blocking_error":
            broken.questions[0].validation.blocking_errors = ["Required mathematical validation failed"]
        elif invalid == "not_evaluated":
            broken.questions[0].validation.auto_status = "not_evaluated"
        else:
            kind = "template" if invalid == "changed_template_answer" else "question"
            next(q for q in broken.questions if q.source_ref.kind == kind).answer.correct_answer = "UNVERIFIED"
        broken.revision = 2
        app.state.exams.replace(broken, expected_revision=1)
        result = client.post(f"/api/v1/exams/{draft.exam_id}/approve", json={"expected_revision": 2})
        assert result.status_code == 409 and result.json()["error"]["code"] == "EXAM_NOT_READY"
        assert app.state.exams.get(draft.exam_id) == broken


def test_incomplete_draft_is_rejected_even_if_created_by_bypassing_model_validation(tmp_path):
    app, _ = application(tmp_path)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
        draft = app.state.exams.get(response.json()["exam_id"])
    draft.questions.pop()
    with pytest.raises(ApiFailure) as error:
        approve_exam(draft, ApproveExamRequest(expected_revision=1))
    assert error.value.code == "EXAM_NOT_READY"


@pytest.mark.parametrize("review_ids", [["UNKNOWN"], ["DUPLICATE", "DUPLICATE"]])
def test_optional_individual_review_ids_must_belong_to_current_draft(tmp_path, review_ids):
    app, _ = application(tmp_path)
    with TestClient(app, headers=HEADERS) as client:
        draft = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json")).json()
        if review_ids[0] == "DUPLICATE":
            review_ids = [draft["questions"][0]["question_id"]] * 2
        result = client.post(f"/api/v1/exams/{draft['exam_id']}/approve",
                             json={"expected_revision": 1, "accepted_question_ids": review_ids})
        assert result.status_code == 422
        assert app.state.exams.get(draft["exam_id"]).revision == 1
