"""Actual SQL sources + mocked Qwen; no canonical/student database writes."""

import hashlib

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from src.ai.template_instantiator import TemplateInstantiator
from src.api.data_adapter import DEFAULT_BANK
from src.api.m3_adapter import M3DataAdapter
from src.api.schemas import ExamQuestion, SkillMastery, StudentProfileResponse
from tests.integration.test_hybrid_exam_api import application, HEADERS
from tests.unit.test_experimental_indirect import ExperimentalClient
from tests.unit.test_planner import make_data, request


def actual_data(evidence=0):
    actual = M3DataAdapter()
    skills = [s.skill_id for s in actual.topic.skills]
    data = make_data(bank=actual.questions, skills=skills)
    data._templates = actual.templates
    # Keep real SQL sources, but never depend on mutable student assessments.
    student = StudentProfileResponse(
        student_id="ST011", name="Synthetic diagnostic student", grade_level=10,
        skill_mastery=[SkillMastery(
            skill_id=skill, mastery_score=None if evidence == 0 else 1.0,
            evidence_count=evidence,
        ) for skill in skills],
        learning_history=[],
    )
    data._profiles = {student.student_id: student}
    return data


@pytest.mark.parametrize("evidence", [0, 1])
def test_real_sql_hybrid_diagnostic_generates_indirect_for_no_data_and_partial_and_approves_without_individual_reviews(tmp_path, monkeypatch, evidence):
    monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", "1")
    before = hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest()
    data, model = actual_data(evidence), ExperimentalClient()
    skills = {f"A{i:03}" for i in range(1, 10)}
    student = data.get_profile("ST011")
    assert {s.skill_id for s in student.skill_mastery} == skills
    assert all(s.evidence_count == evidence and s.mastery_score == (None if evidence == 0 else 1.0)
               for s in student.skill_mastery)
    app, _ = application(tmp_path, data, model)
    with TestClient(app, headers=HEADERS) as client:
        body = request(10, student_id="ST011").model_dump(mode="json")
        planned = client.post("/api/v1/exams/plan", json=body).json()
        assert planned["strategy"] == "diagnostic_review"
        assert planned["skill_classifications"] == {
            skill: "NO_DATA" if evidence == 0 else "PARTIAL" for skill in skills
        }
        assert planned["quota_summary"]["requested_levels"] == dict(
            recognition=3, understanding=3, application=3, advanced_application=1)
        result = client.post("/api/v1/exams/generate", json=body)
        assert result.status_code == 200, result.text
        exam = result.json()
        assert exam["planner_summary"]["quota_summary"] == planned["quota_summary"]
        assert exam["planner_summary"]["quota_summary"]["achieved_levels"] == dict(
            recognition=3, understanding=3, application=3, advanced_application=1)
        templates = [q for q in exam["questions"] if q["source_ref"]["kind"] == "template"]
        assert {q["generate_type"] for q in templates} == {"direct", "indirect"}
        assert abs(sum(q["generate_type"] == "direct" for q in templates)
                   - sum(q["generate_type"] == "indirect" for q in templates)) <= 1
        assert len(model.calls) == len(templates)
        for q in exam["questions"]:
            if q["source_ref"]["kind"] == "question":
                original = next(s for s in data.questions if s.question_id == q["source_ref"]["id"])
                assert q["content_latex"] == original.content and q["answer"] == original.answer.model_dump()
                assert q["generate_type"] == "direct"
            else:
                template = next(t for t in data.templates if t.template_id == q["source_ref"]["id"])
                instance = TemplateInstantiator().materialize(template, q["template_instance"]["parameters"])
                assert q["answer"] == instance.answer.model_dump()
                if q["generate_type"] == "indirect":
                    assert q["template_presentation"]["verification_status"] == "experimental"
                    assert q["template_presentation"]["presentation_id"] == "experimental_indirect"
                    assert q["validation"]["auto_status"] == "needs_review"
                    assert instance.content not in q["content_latex"]
        base = f"/api/v1/exams/{exam['exam_id']}"
        approved = client.post(base + "/approve", json={"expected_revision": 1})
        assert approved.status_code == 200, approved.text
        final = approved.json()
        assert final["status"] == "approved" and final["revision"] == 2
        assert all(not q["validation"]["teacher_approved"] for q in final["questions"])
        assert client.get(base).json() == final
    restarted, _ = application(tmp_path, data, model)
    with TestClient(restarted, headers=HEADERS) as client:
        assert client.get(base).json() == final
    assert hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest() == before


def test_real_template_regeneration_changes_math_and_wording_switches_types_and_keeps_atomic_revision(tmp_path, monkeypatch):
    monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", "1")
    data, model = actual_data(), ExperimentalClient()
    app, _ = application(tmp_path, data, model)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(10, student_id="ST011").model_dump(mode="json"))
        assert response.status_code == 200, response.text
        exam = response.json()
        target = next(q for q in exam["questions"] if q["source_ref"]["kind"] == "template" and q["generate_type"] == "direct")
        base = f"/api/v1/exams/{exam['exam_id']}"
        approved = client.post(base + "/approve", json={"expected_revision": 1}).json()
        url = base + f"/questions/{target['question_id']}/regenerate"
        model.mode = "invalid_all"
        failed = client.post(url, json={"expected_revision": 2})
        assert failed.status_code == 502
        assert client.get(base).json() == approved
        failed_calls = model.calls[-4:]
        assert all(e.template_context.instance == failed_calls[0][0].template_context.instance for e, _ in failed_calls)
        model.mode = "valid"
        response = client.post(url, json={"expected_revision": 2})
        assert response.status_code == 200, response.text
        regenerated = response.json()
        changed = regenerated["questions"][target["order_index"] - 1]
        assert changed["generate_type"] == "indirect" and changed["template_presentation"]["verification_status"] == "experimental"
        assert changed["template_instance"]["parameters"] != target["template_instance"]["parameters"]
        assert changed["content_latex"] != target["content_latex"]
        definition = next(t for t in data.templates if t.template_id == changed["source_ref"]["id"])
        correct = TemplateInstantiator().materialize(definition, changed["template_instance"]["parameters"])
        assert changed["answer"] == correct.answer.model_dump()
        assert [s["explanation"] for s in changed["step_solutions"]] == correct.solution_steps
        assert all(a == b for a, b in zip(approved["questions"], regenerated["questions"]) if a["question_id"] != target["question_id"])
        for key in ("source_ref", "source_digest", "target_skill_id", "cognitive_level", "order_index", "max_score"):
            assert changed[key] == target[key]
        assert regenerated["revision"] == 3 and regenerated["status"] == "pending_teacher_review" and regenerated["teacher_review"] is None
        assert client.post(url, json={"expected_revision": 2}).status_code == 409
        assert client.post(base + "/approve", json={"expected_revision": 3}).status_code == 200
        back = client.post(base + f"/questions/{changed['question_id']}/regenerate", json={"expected_revision": 4})
        assert back.status_code == 200, back.text
        assert back.json()["questions"][target["order_index"] - 1]["generate_type"] == "direct"
        immutable = next(q for q in regenerated["questions"] if q["source_ref"]["kind"] == "question")
        assert client.post(base + f"/questions/{immutable['question_id']}/regenerate", json={"expected_revision": 5}).status_code == 409


@pytest.mark.parametrize("tamper", ["answer", "solution", "fingerprint", "wording", "full_validation", "question_label"])
def test_experimental_drafts_cannot_bypass_mathematical_or_structural_integrity(tmp_path, monkeypatch, tamper):
    monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", "1")
    app, _ = application(tmp_path, actual_data(), ExperimentalClient())
    with TestClient(app, headers=HEADERS) as client:
        result = client.post("/api/v1/exams/generate", json=request(10, student_id="ST011").model_dump(mode="json"))
        assert result.status_code == 200, result.text
        exam = app.state.exams.get(result.json()["exam_id"])
        target = next(q for q in exam.questions if q.generate_type == "indirect")
        if tamper == "full_validation":
            value = target.model_dump()
            value["validation"]["auto_status"] = "pass"
            with pytest.raises(ValidationError, match="fully validated"):
                ExamQuestion.model_validate(value)
            return
        if tamper == "answer":
            target.answer.correct_answer = "999999"
        elif tamper == "solution":
            target.step_solutions[0].explanation = "UNTRUSTED MODEL SOLUTION"
        elif tamper == "fingerprint":
            target.template_presentation.fingerprint = "0" * 64
        elif tamper == "question_label":
            next(q for q in exam.questions if q.source_ref.kind == "question").generate_type = "indirect"
        else:
            target.content_latex += " Thêm 999 đối tượng."
        exam.revision = 2
        app.state.exams.replace(exam, expected_revision=1)
        response = client.post(f"/api/v1/exams/{exam.exam_id}/approve", json={"expected_revision": 2})
        assert response.status_code == 409
        assert app.state.exams.get(exam.exam_id) == exam


def test_strict_mode_cannot_approve_experimental_drafts_and_does_not_advance_revision(tmp_path, monkeypatch):
    monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", "1")
    app, _ = application(tmp_path, actual_data(), ExperimentalClient())
    with TestClient(app, headers=HEADERS) as client:
        generated = client.post("/api/v1/exams/generate", json=request(10, student_id="ST011").model_dump(mode="json"))
        assert generated.status_code == 200, generated.text
        exam = generated.json()
        monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", "0")
        base = f"/api/v1/exams/{exam['exam_id']}"
        assert client.get(base).json() == exam
        response = client.post(base + "/approve", json={"expected_revision": 1})
        assert response.status_code == 409
        assert client.get(base).json() == exam
