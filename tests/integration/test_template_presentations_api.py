"""Mock-Qwen end-to-end examples; approvals here are SYNTHETIC TEST ONLY."""

from copy import deepcopy
import json
from math import factorial

from fastapi.testclient import TestClient
import pytest

from src.ai.template_instantiator import TemplateInstantiator
from src.ai.template_presentations import TemplatePresentations
from src.api.data_adapter import ApiFailure
from src.api.schemas import ExamResponse
from src.orchestration.review_service import validate_regeneration
from tests.integration.test_hybrid_exam_api import application, EchoTemplateClient, HEADERS, hybrid_data
from tests.unit.test_hybrid_sources import template
from tests.unit.test_planner import make_data, profile, request
from tests.unit.test_template_presentations import synthetic_presentation, synthetic_registry


def mixed_data(rows=()):
    data = make_data()
    data._profiles = {"S": profile(rows)}
    data._templates = [template(tid=f"SYNTHETIC_{s}_{lv}", skills=(s,), level=lv)
                       for s in ("A001", "A002", "A003", "A004") for lv in (1, 2)]
    data._presentation_registry = TemplatePresentations(version="synthetic-tests-v1",
        presentations=[synthetic_presentation(t) for t in data.templates])
    return data


@pytest.mark.parametrize("rows", [(), (("A001", 1.0, 1),), (("A001", 3.0, 3),)])
def test_mixed_initial_generation_has_balanced_presentation_for_no_data_partial_and_achieved(tmp_path, rows):
    data = mixed_data(rows)
    app, model = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        body = request(10).model_dump(mode="json")
        preview = client.post("/api/v1/exams/plan", json=body).json()
        result = client.post("/api/v1/exams/generate", json=body)
        assert result.status_code == 200, result.text
        exam = result.json()
        assert exam["planner_summary"]["quota_summary"] == preview["quota_summary"]
        templates = [q for q in exam["questions"] if q["source_ref"]["kind"] == "template"]
        questions = [q for q in exam["questions"] if q["source_ref"]["kind"] == "question"]
        assert templates and questions
        assert {q["generate_type"] for q in templates} == {"direct", "indirect"}
        assert abs(sum(q["generate_type"] == "direct" for q in templates)
                   - sum(q["generate_type"] == "indirect" for q in templates)) <= 1
        assert len(model.calls) == len(templates)
        for q in questions:
            original = next(x for x in data.questions if x.question_id == q["source_ref"]["id"])
            assert q["content_latex"] == original.content and q["answer"] == original.answer.model_dump()
            assert q["template_presentation"] is None
        for q in templates:
            assert q["generate_type"] == q["template_presentation"]["generate_type"]
            assert q["answer"]["correct_answer"] == str(factorial(q["template_instance"]["parameters"]["n"]))
        base = f"/api/v1/exams/{exam['exam_id']}"
        approved = client.post(base + "/approve", json={"expected_revision": 1})
        assert approved.status_code == 200, approved.text
        final = approved.json()
        assert final["status"] == "approved"
        assert all(not q["validation"]["teacher_approved"] for q in final["questions"])
        assert client.get(base).json() == final
    # Persistent presentation metadata can be rechecked after server restart.
    restarted, _ = application(tmp_path, data)
    with TestClient(restarted, headers=HEADERS) as client:
        assert client.get(base).json() == final
    data.validate_exam_references(ExamResponse.model_validate(final))


def test_approved_direct_regenerates_to_verified_indirect_then_back_preserving_other_questions(tmp_path):
    data = hybrid_data()
    data._presentation_registry = synthetic_registry(data.templates[0])
    app, model = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        result = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
        assert result.status_code == 200, result.text
        draft = result.json()
        original = next(q for q in draft["questions"] if q["source_ref"]["kind"] == "template")
        assert original["generate_type"] == "direct"
        base = f"/api/v1/exams/{draft['exam_id']}"
        approved = client.post(base + "/approve", json={"expected_revision": 1}).json()
        url = base + f"/questions/{original['question_id']}/regenerate"
        model.fail = True
        failed = client.post(url, json={"expected_revision": 2})
        assert failed.status_code == 502
        assert client.get(base).json() == approved
        assert all(e.template_context.instance == model.calls[-1][0].template_context.instance for e, _ in model.calls[-4:])
        model.fail = False
        changed = client.post(url, json={"expected_revision": 2})
        assert changed.status_code == 200, changed.text
        regenerated = changed.json()
        assert regenerated["revision"] == 3 and regenerated["status"] == "pending_teacher_review"
        assert regenerated["teacher_review"] is None
        target = regenerated["questions"][original["order_index"] - 1]
        assert target["generate_type"] == "indirect"
        assert target["template_presentation"]["presentation_id"] == "synthetic_shelf"
        assert target["template_instance"]["signature"] != original["template_instance"]["signature"]
        assert target["template_instance"]["parameters"] != original["template_instance"]["parameters"]
        assert target["answer"] != original["answer"]
        definition = data.templates[0]
        instance = TemplateInstantiator().materialize(definition, target["template_instance"]["parameters"])
        assert target["answer"] == instance.answer.model_dump()
        assert [s["explanation"] for s in target["step_solutions"]] == instance.solution_steps
        for field in ("source_ref", "source_digest", "skill_ids", "target_skill_id", "cognitive_level", "order_index", "max_score"):
            assert target[field] == original[field]
        assert all(a == b for a, b in zip(approved["questions"], regenerated["questions"])
                   if a["question_id"] != original["question_id"])
        assert client.post(url, json={"expected_revision": 2}).status_code == 409
        assert client.post(base + "/approve", json={"expected_revision": 3}).status_code == 200
        back = client.post(base + f"/questions/{target['question_id']}/regenerate", json={"expected_revision": 4})
        assert back.status_code == 200, back.text
        assert back.json()["questions"][original["order_index"] - 1]["generate_type"] == "direct"
        immutable = next(q for q in regenerated["questions"] if q["source_ref"]["kind"] == "question")
        assert client.post(base + f"/questions/{immutable['question_id']}/regenerate", json={"expected_revision": 5}).status_code == 409


def test_direct_fallback_without_verified_indirect_metadata_is_truthfully_recorded(tmp_path):
    data = hybrid_data()
    data._presentation_registry = synthetic_registry(data.templates[0], verification_status="proposed")
    app, _ = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        result = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
        assert result.status_code == 200, result.text
        exam = result.json()
        target = next(q for q in exam["questions"] if q["source_ref"]["kind"] == "template")
        assert target["generate_type"] == "direct"
        assert "no verified compatible Indirect" in " ".join(target["validation"]["review_notes"])
        result = client.post(f"/api/v1/exams/{exam['exam_id']}/questions/{target['question_id']}/regenerate",
                             json={"expected_revision": 1})
        assert result.status_code == 200
        changed = result.json()["questions"][target["order_index"] - 1]
        assert changed["generate_type"] == "direct"
        assert changed["template_presentation"]["presentation_id"] == "sql_direct"


@pytest.mark.parametrize("tamper", ["revoked", "pattern", "version", "fingerprint", "type", "wording", "answer", "solution"])
def test_approval_revalidates_presentation_and_mathematics_and_preserves_stored_revision_on_failure(tmp_path, tamper):
    data = mixed_data()
    app, _ = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        result = client.post("/api/v1/exams/generate", json=request(10).model_dump(mode="json"))
        assert result.status_code == 200, result.text
        exam = result.json()
        stored = app.state.exams.get(exam["exam_id"])
        target = next(q for q in stored.questions if q.generate_type == "indirect")
        tid = target.source_ref.id
        presentation = next(p for p in data._presentation_registry.presentations if p.template_id == tid)
        if tamper == "revoked":
            presentation.verification_status = "proposed"
        elif tamper == "pattern":
            presentation.pattern += " Added condition."
        elif tamper == "version":
            data._presentation_registry.version = "changed-version"
        elif tamper == "fingerprint":
            target.template_presentation.fingerprint = "0" * 64
        elif tamper == "type":
            target.generate_type = "direct"
            target.template_presentation.generate_type = "direct"
        elif tamper == "wording":
            target.content_latex += " Hai sách phải đứng cạnh nhau."
        elif tamper == "answer":
            target.answer.correct_answer = "999999"
        else:
            target.step_solutions[0].explanation = "UNVERIFIED"
        if tamper not in ("revoked", "pattern", "version"):
            stored.revision = 2
            app.state.exams.replace(stored, expected_revision=1)
        before = app.state.exams.get(exam["exam_id"])
        base = f"/api/v1/exams/{exam['exam_id']}"
        response = client.post(base + "/approve", json={"expected_revision": before.revision})
        assert response.status_code == 409, response.text
        assert app.state.exams.get(exam["exam_id"]) == before
        regen = client.post(base + f"/questions/{target.question_id}/regenerate", json={"expected_revision": before.revision})
        assert regen.status_code == 409, regen.text
        assert app.state.exams.get(exam["exam_id"]) == before


@pytest.mark.parametrize("field,value", [("target_skill_id", "A002"), ("cognitive_level", "recognition"), ("answer", None)])
def test_regeneration_contract_rejects_unauthorized_metadata_and_invalid_math(tmp_path, field, value):
    data = hybrid_data()
    data._presentation_registry = synthetic_registry(data.templates[0])
    app, _ = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        exam = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json")).json()
    original = app.state.exams.get(exam["exam_id"])
    from src.orchestration.exam_service import ExamService
    source = next(q for q in original.questions if q.source_ref.kind == "template")
    changed = ExamService(data, EchoTemplateClient()).regenerate_question(original, source.question_id)
    target = next(q for q in changed.questions if q.source_ref.kind == "template")
    if field == "answer":
        target.answer.correct_answer = "999"
    else:
        setattr(target, field, value)
    with pytest.raises(ApiFailure):
        validate_regeneration(original, changed, source.question_id, data=data)


def test_single_fixed_instance_can_regenerate_presentation_without_inventing_parameters(tmp_path):
    data = hybrid_data()
    data._templates = [template(level=2, parameter_rules={"n": {"type": "integer", "value": 5, "min": 5, "max": 5}})]
    data._presentation_registry = synthetic_registry(data.templates[0])
    app, _ = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        result = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
        assert result.status_code == 200, result.text
        original = result.json()
        target = next(q for q in original["questions"] if q["source_ref"]["kind"] == "template")
        result = client.post(f"/api/v1/exams/{original['exam_id']}/questions/{target['question_id']}/regenerate",
                             json={"expected_revision": 1})
        assert result.status_code == 200, result.text
        changed = result.json()["questions"][target["order_index"] - 1]
        assert changed["template_instance"] == target["template_instance"]
        assert changed["answer"] == target["answer"]
        assert changed["generate_type"] == "indirect" and target["generate_type"] == "direct"


def test_legacy_direct_draft_is_readable_but_cannot_claim_indirect_without_provenance(tmp_path):
    app, _ = application(tmp_path)
    with TestClient(app, headers=HEADERS) as client:
        exam = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json")).json()
    for q in exam["questions"]:
        q.pop("template_presentation")
    legacy = ExamResponse.model_validate(exam)
    app.state.data.validate_exam_references(legacy)
    broken = deepcopy(legacy)
    next(q for q in broken.questions if q.source_ref.kind == "template").generate_type = "indirect"
    with pytest.raises(ValueError, match="provenance"):
        app.state.data.validate_exam_references(broken)


def test_invalid_indirect_output_falls_back_to_direct_with_persisted_truthful_metadata(tmp_path):
    class InvalidIndirect(EchoTemplateClient):
        def generate_one(self, expression, **kwargs):
            candidate = super().generate_one(expression, **kwargs)
            if expression.generate_type == "indirect":
                candidate.raw_response = json.dumps({"question": expression.source_text + " Hai sách phải đứng cạnh nhau."})
            return candidate

    app, model = application(tmp_path, mixed_data(), InvalidIndirect())
    with TestClient(app, headers=HEADERS) as client:
        result = client.post("/api/v1/exams/generate", json=request(10).model_dump(mode="json"))
        assert result.status_code == 200, result.text
        exam = result.json()
        templates = [q for q in exam["questions"] if q["source_ref"]["kind"] == "template"]
        assert all(q["generate_type"] == q["template_presentation"]["generate_type"] == "direct" for q in templates)
        assert any("safe SQL Direct fallback" in " ".join(q["validation"]["review_notes"]) for q in templates)
        for i, (expr, _) in enumerate(model.calls):
            if expr.generate_type == "indirect":
                successor = model.calls[i + 1][0]
                assert successor.template_context.instance == expr.template_context.instance
        base = f"/api/v1/exams/{exam['exam_id']}"
        assert client.get(base).json() == exam
        assert client.post(base + "/approve", json={"expected_revision": 1}).status_code == 200


@pytest.mark.parametrize("missing", [True, False])
def test_explicit_missing_or_malformed_presentation_config_fails_closed(tmp_path, monkeypatch, missing):
    path = tmp_path / "presentations.json"
    if not missing:
        path.write_text('{"version": "bad", "presentations": [{"bad": "entry"}]}', encoding="utf-8")
    monkeypatch.setenv("TEMPLATE_PRESENTATIONS_FILE", str(path))
    data = hybrid_data()
    with pytest.raises(ApiFailure) as failure:
        _ = data.presentation_registry
    assert failure.value.code == "PRESENTATION_CONFIG_ERROR"


def test_regeneration_rejects_changes_to_unrelated_questions_and_same_instance_metadata_only_upgrade(tmp_path):
    data = hybrid_data()
    data._presentation_registry = synthetic_registry(data.templates[0])
    app, _ = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        generated = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json")).json()
    original = app.state.exams.get(generated["exam_id"])
    target = next(q for q in original.questions if q.source_ref.kind == "template")
    from src.orchestration.exam_service import ExamService
    changed = ExamService(data, EchoTemplateClient()).regenerate_question(original, target.question_id)
    next(q for q in changed.questions if q.source_ref.kind == "question").content_latex += " Changed."
    with pytest.raises(ApiFailure):
        validate_regeneration(original, changed, target.question_id, data=data)
    legacy = original.model_copy(deep=True)
    next(q for q in legacy.questions if q.source_ref.kind == "template").template_presentation = None
    upgrade = original.model_copy(deep=True)
    upgrade.revision += 1
    next(q for q in upgrade.questions if q.source_ref.kind == "template").question_id = "NEW_ID"
    with pytest.raises(ApiFailure, match="new mathematical instance"):
        validate_regeneration(legacy, upgrade, target.question_id, data=data)
