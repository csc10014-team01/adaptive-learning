"""Full hybrid pipeline with a local model double; no live Ollama required."""

from collections import Counter
import hashlib
import json
from threading import BoundedSemaphore

from fastapi.testclient import TestClient
import pytest

from src.adaptation.planner import RuleBasedPlanner
from src.ai.contracts import GenerationCandidate
from src.api.data_adapter import ApiFailure
from src.api.data_adapter import DEFAULT_BANK
from src.api.main import create_app
from src.api.m3_adapter import M3DataAdapter
from src.api.real_generator import QwenExamGenerator
from src.api.schemas import LEVELS
from tests.unit.test_planner import make_data, profile, request
from tests.unit.test_hybrid_sources import template

HEADERS = {"Authorization": "Bearer hybrid-test"}


class EchoTemplateClient:
    model = "mock-local-qwen"
    attempts = 2
    exam_timeout = 30

    def __init__(self, *, fail=False, invalid_first=False):
        self.capacity = BoundedSemaphore(1)
        self.calls = []
        self.fail = fail
        self.invalid_first = invalid_first

    def generate_one(self, expression, **kwargs):
        assert expression.template_context is not None, "Immutable Questions must never call Qwen"
        self.calls.append((expression, kwargs))
        text = expression.source_text
        if self.fail or (self.invalid_first and len(self.calls) == 1):
            text += " Thêm 999 đối tượng."
        return GenerationCandidate(model=self.model, raw_response=json.dumps({"question": text}))


def hybrid_data():
    data = make_data()
    data._templates = [template(level=2)]
    data._profiles = {"S": profile()}
    return data


def application(tmp_path, data=None, client=None):
    client = client or EchoTemplateClient()
    app = create_app(backend="qwen", teacher_token="hybrid-test", qwen_client=client, exam_db=tmp_path / "drafts.db")
    app.state.data = data or hybrid_data()
    return app, client


def test_mixed_preview_generation_persistence_and_template_only_model_calls(tmp_path):
    data = hybrid_data()
    app, model = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        body = request(4).model_dump(mode="json")
        preview = client.post("/api/v1/exams/plan", json=body)
        assert preview.status_code == 200, preview.text
        planned = preview.json()
        assert not model.calls
        templates = [q for q in planned["questions"] if q["source_kind"] == "template"]
        assert templates and all(q["source_status"] == "pending_wording" for q in templates)
        generated = client.post("/api/v1/exams/generate", json=body)
        assert generated.status_code == 200, generated.text
        exam = generated.json()
        assert {q["source_ref"]["kind"] for q in exam["questions"]} == {"question", "template"}
        assert len(model.calls) == sum(q["source_ref"]["kind"] == "template" for q in exam["questions"])
        assert exam["planner_summary"]["quota_summary"] == planned["quota_summary"]
        assert [(q["source_ref"]["kind"], q["source_ref"]["id"], q["cognitive_level"]) for q in exam["questions"]] == [
            (q["source_kind"], q["source_id"], q["cognitive_level"]) for q in planned["questions"]]
        for q in exam["questions"]:
            if q["source_ref"]["kind"] == "question":
                source = next(s for s in data.questions if s.question_id == q["source_ref"]["id"])
                assert q["content_latex"] == source.content and q["answer"] == source.answer.model_dump()
                assert [s["explanation"] for s in q["step_solutions"]] == source.solution_steps
        assert client.get("/api/v1/exams/" + exam["exam_id"]).json() == exam
    # A different application instance reads the same durable hybrid records.
    app2, _ = application(tmp_path, data)
    with TestClient(app2, headers=HEADERS) as client:
        assert client.get("/api/v1/exams/" + exam["exam_id"]).json() == exam


def test_question_only_exam_does_not_acquire_qwen_or_allow_regeneration(tmp_path):
    data = make_data()
    data._profiles = {"S": profile()}
    model = EchoTemplateClient()
    model.capacity.acquire()
    app, _ = application(tmp_path, data, model)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
        assert response.status_code == 200, response.text
        exam = response.json()
        assert exam["provenance"] == {"generator": "question_bank", "model": None}
        assert not model.calls
        denied = client.post(f"/api/v1/exams/{exam['exam_id']}/questions/{exam['questions'][0]['question_id']}/regenerate",
                             json={"expected_revision": 1})
        assert denied.status_code == 409 and denied.json()["error"]["code"] == "QUESTION_REGENERATION_FORBIDDEN"


def test_template_retry_keeps_parameters_and_never_asks_the_model_for_answers(tmp_path):
    model = EchoTemplateClient(invalid_first=True)
    app, _ = application(tmp_path, client=model)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
    assert response.status_code == 200, response.text
    assert len(model.calls) == 2
    assert model.calls[0][0].template_context.instance == model.calls[1][0].template_context.instance
    assert model.calls[1][1]["attempt"] == 1
    assert "numeric" in model.calls[1][1]["feedback"].lower()


def test_invalid_template_wording_falls_back_without_saving_a_partial_exam(tmp_path):
    model = EchoTemplateClient(fail=True)
    app, _ = application(tmp_path, client=model)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
        assert response.status_code == 200, response.text
        exam = response.json()
        assert len(model.calls) == model.attempts
        assert all(q["source_ref"]["kind"] == "question" for q in exam["questions"])
        assert any("wording failed" in w for w in exam["planner_summary"]["warnings"])
        assert client.get("/api/v1/exams/" + exam["exam_id"]).json() == exam


def test_failed_template_without_any_question_fallback_returns_insufficient_bank(tmp_path):
    data = hybrid_data()
    data._questions = []
    # One diagnostic slot is L2; the only compatible source will fail wording.
    app, model = application(tmp_path, data, EchoTemplateClient(fail=True))
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(1).model_dump(mode="json"))
    assert response.status_code == 409 and response.json()["error"]["code"] == "INSUFFICIENT_QUESTION_BANK"
    assert len(model.calls) == model.attempts
    assert not (tmp_path / "drafts.db").exists()


@pytest.mark.parametrize("fail_regeneration", [False, True])
def test_template_regeneration_recomputes_math_preserves_others_and_revision_safety(tmp_path, fail_regeneration):
    data = hybrid_data()
    app, model = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
        assert response.status_code == 200, response.text
        exam = response.json()
        target = next(q for q in exam["questions"] if q["source_ref"]["kind"] == "template")
        base = "/api/v1/exams/" + exam["exam_id"]
        approved_response = client.post(base + "/approve", json={"expected_revision": 1,
            "accepted_question_ids": [q["question_id"] for q in exam["questions"]]})
        assert approved_response.status_code == 200
        approved = approved_response.json()
        url = base + f"/questions/{target['question_id']}/regenerate"
        assert client.post(url, json={"expected_revision": 1}).status_code == 409
        model.fail = fail_regeneration
        response = client.post(url, json={"expected_revision": 2})
        if fail_regeneration:
            assert response.status_code == 502
            assert client.get(base).json() == approved
        else:
            assert response.status_code == 200, response.text
            updated = response.json()
            assert updated["revision"] == 3 and updated["status"] == "pending_teacher_review"
            replacement = next(q for q in updated["questions"] if q["source_ref"]["kind"] == "template")
            assert replacement["template_instance"]["parameters"] != target["template_instance"]["parameters"]
            assert replacement["template_instance"]["signature"] != target["template_instance"]["signature"]
            assert replacement["source_ref"] == target["source_ref"]
            assert replacement["cognitive_level"] == target["cognitive_level"]
            assert replacement["target_skill_id"] == target["target_skill_id"]
            assert replacement["answer"] != target["answer"]
            for old, new in zip(approved["questions"], updated["questions"]):
                if old["question_id"] != target["question_id"]:
                    old["validation"]["teacher_approved"] = False
                    assert old == new
            assert client.get(base).json() == updated


def test_actual_authoritative_bank_produces_a_mixed_exam_without_database_writes(tmp_path):
    from src.adaptation.skill_relationships import SkillRelationships
    from tests.unit.test_skill_relationship_policy import POLICY
    before = hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest()
    data, model = M3DataAdapter(), EchoTemplateClient()
    planner = RuleBasedPlanner(data, relationships=SkillRelationships.load(POLICY))
    req = request(10, student_id="ST001")
    exam = QwenExamGenerator(data, model, planner=planner).generate(req, data.get_profile("ST001"))
    data.validate_exam_references(exam)
    assert set(Counter(q.source_ref.kind for q in exam.questions)) == {"template", "question"}
    assert all(q.source_ref.kind == "question" for q in exam.questions if q.cognitive_level in LEVELS[2:])
    assert len(model.calls) == sum(q.source_ref.kind == "template" for q in exam.questions)
    assert len({q.template_instance.signature for q in exam.questions if q.template_instance}) == len(model.calls)
    assert hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("tamper", ["definition", "parameters", "invalid_parameters", "signature", "answer"])
def test_template_integrity_tampering_blocks_regeneration_before_inference(tamper):
    data, model = hybrid_data(), EchoTemplateClient()
    service = QwenExamGenerator(data, model, instance_seed=42)
    exam = service.generate(request(4), data.get_profile("S"))
    target = next(q for q in exam.questions if q.source_ref.kind == "template")
    if tamper == "definition":
        data._templates[0] = data._templates[0].model_copy(update={"solution_rule": "Changed source rule"})
    elif tamper == "parameters":
        target.template_instance.parameters["n"] = 12 if target.template_instance.parameters["n"] != 12 else 11
    elif tamper == "invalid_parameters":
        target.template_instance.parameters["n"] = -1
    elif tamper == "signature":
        target.template_instance.signature = "0" * 64
    else:
        target.answer.correct_answer = "999999"
    calls = len(model.calls)
    with pytest.raises(ApiFailure) as error:
        service.regenerate_question(exam, target.question_id)
    assert error.value.code == "SOURCE_CHANGED"
    assert len(model.calls) == calls


def test_demo_template_regeneration_uses_new_parameters_without_claiming_inference():
    app = create_app(backend="fake", teacher_token="hybrid-test")
    app.state.data = hybrid_data()
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(4).model_dump(mode="json"))
        assert response.status_code == 200, response.text
        exam = response.json()
        target = next(q for q in exam["questions"] if q["source_ref"]["kind"] == "template")
        response = client.post(f"/api/v1/exams/{exam['exam_id']}/questions/{target['question_id']}/regenerate",
                               json={"expected_revision": 1})
        assert response.status_code == 200, response.text
        updated = response.json()
        replacement = next(q for q in updated["questions"] if q["source_ref"]["kind"] == "template")
        assert replacement["template_instance"]["signature"] != target["template_instance"]["signature"]
        assert updated["provenance"] == {"generator": "fake", "model": None}
        assert all(q["validation"]["auto_status"] == "not_evaluated" for q in updated["questions"])
