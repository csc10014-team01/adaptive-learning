import hashlib
import json
import shutil
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.data_adapter import ApiFailure, DEFAULT_BANK, DEFAULT_FIXTURES, StaticDataAdapter
from src.api.main import create_app
from src.api.schemas import AdvancedOptions, ExamResponse, GenerateExamRequest, StudentExamResponse, StudentProfileResponse
from src.api.services import FakeExamGenerator


TOKEN = "test-teacher-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def payload(student_id="DEMO_NEW_001", **changes):
    result = {
        "student_id": student_id,
        "generation_mode": "default_blueprint",
        "selected_topic_ids": ["combinatorics"],
        "total_questions": 4,
        "duration_minutes": 45,
        "difficulty_distribution": {
            "recognition": 20, "understanding": 40,
            "application": 30, "advanced_application": 10,
        },
    }
    result.update(changes)
    return result


@pytest.fixture
def client():
    with TestClient(create_app(teacher_token=TOKEN), headers=HEADERS) as test_client:
        yield test_client


def generated(client, **changes):
    response = client.post("/api/v1/exams/generate", json=payload(**changes))
    assert response.status_code == 200, response.text
    return response.json()


def test_student_profile_and_catalogue(client):
    response = client.get("/api/v1/students/DEMO_SUFFICIENT_001/profile")
    assert response.status_code == 200
    profile = StudentProfileResponse.model_validate(response.json())
    assert profile.grade_level == 10
    assert profile.evidence_count == 3
    assert profile.skill_mastery[0].evidence_count == 1
    assert profile.data_status == "sufficient"
    assert profile.recommended_blueprint_mode == "adaptive"
    assert "name" not in response.json()
    assert "birthday" not in response.json()
    students = client.get("/api/v1/students").json()["items"]
    assert len(students) == 4
    topics = client.get("/api/v1/topics").json()["items"]
    assert topics[0]["topic_id"] == "combinatorics"
    assert {s["skill_id"] for s in topics[0]["skills"]} == {f"A00{i}" for i in range(1, 10)}


@pytest.mark.parametrize("path", [
    "/api/v1/students/UNKNOWN/profile", "/api/v1/exams/UNKNOWN",
])
def test_unknown_resource(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] in {"STUDENT_NOT_FOUND", "EXAM_NOT_FOUND"}


def test_unknown_student_cannot_generate(client):
    response = client.post("/api/v1/exams/generate", json=payload("UNKNOWN"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STUDENT_NOT_FOUND"


def test_default_generation_is_complete_and_retrievable(client):
    body = generated(client)
    exam = ExamResponse.model_validate(body)
    assert len(exam.questions) == exam.total_questions == 4
    assert exam.total_score == 10
    assert [q.order_index for q in exam.questions] == [1, 2, 3, 4]
    assert [q.cognitive_level for q in exam.questions] == [
        "recognition", "understanding", "understanding", "application",
    ]
    assert exam.status == "pending_teacher_review"
    assert exam.provenance.generator == "fake" and exam.provenance.model is None
    assert all(q.answer.correct_answer and q.rubric and q.step_solutions for q in exam.questions)
    assert all(not q.validation.teacher_approved for q in exam.questions)
    assert all(q.validation.auto_status == "not_evaluated" for q in exam.questions)
    assert "job_id" not in json.dumps(body)
    stored = client.get(f"/api/v1/exams/{exam.exam_id}")
    assert stored.status_code == 200 and stored.json() == body
    assert stored.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("student_id", ["DEMO_NEW_001", "DEMO_PARTIAL_001", "DEMO_PARTIAL_002"])
def test_adaptive_rejected_at_evidence_zero_one_two(client, student_id):
    response = client.post("/api/v1/exams/generate", json=payload(student_id, generation_mode="adaptive"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ADAPTIVE_NOT_ALLOWED"


@pytest.mark.parametrize("mode", ["adaptive", "default_blueprint"])
def test_sufficient_profile_allows_explicit_mode(client, mode):
    body = generated(client, student_id="DEMO_SUFFICIENT_001", generation_mode=mode)
    assert body["generation_mode"] == mode
    assert body["evidence_count"] == 3


@pytest.mark.parametrize("count", [1, 3, 4, 5, 8, 10])
def test_requested_count_is_exact_or_explicit_failure(client, count):
    distribution = (
        {"recognition": 25, "understanding": 25, "application": 25, "advanced_application": 25}
        if count == 8 else payload()["difficulty_distribution"]
    )
    response = client.post("/api/v1/exams/generate", json=payload(
        total_questions=count, difficulty_distribution=distribution,
    ))
    if count == 10:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INSUFFICIENT_QUESTION_BANK"
    else:
        assert response.status_code == 200, response.text
        exam = ExamResponse.model_validate(response.json())
        assert len(exam.questions) == count
        assert sum(q.max_score for q in exam.questions) == 10


@pytest.mark.parametrize("change", [
    {"total_questions": True}, {"total_questions": "4"}, {"total_questions": 2.5},
    {"total_questions": 0}, {"total_questions": 11}, {"duration_minutes": -1},
    {"selected_topic_ids": []}, {"selected_topic_ids": ["calculus"]},
    {"selected_topic_ids": ["combinatorics", "combinatorics"]},
    {"generation_mode": "personalized"}, {"class_name": "10A1"},
    {"total_tests_taken": 3}, {"job_id": "wrong-boundary"},
    {"evidence_count": 99}, {"studentId": "legacy"},
    {"difficulty_distribution": {"recognition": 100}},
    {"difficulty_distribution": {"recognition": 25, "understanding": 25, "application": 25, "advanced_application": 20}},
    {"advanced_options": {"step_scoring_granularity": 0.5}},
    {"advanced_options": {"include_real_world_context": False}},
])
def test_invalid_payload_has_typed_422(client, change):
    response = client.post("/api/v1/exams/generate", json=payload(**change))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert response.json()["error"]["details"]


def test_missing_and_malformed_payload(client):
    for kwargs in ({"json": {}}, {"content": "{", "headers": {"Content-Type": "application/json"}}):
        assert client.post("/api/v1/exams/generate", **kwargs).status_code == 422


def test_pydantic_round_trip_and_invalid_response(client):
    request = GenerateExamRequest.model_validate(payload())
    assert GenerateExamRequest.model_validate_json(request.model_dump_json()) == request
    body = generated(client)
    exam = ExamResponse.model_validate(body)
    assert ExamResponse.model_validate_json(exam.model_dump_json()) == exam
    body["total_questions"] += 1
    with pytest.raises(ValidationError):
        ExamResponse.model_validate(body)
    body = exam.model_dump(mode="json")
    body["questions"][0]["rubric"][0]["sub_score"] += 0.25
    with pytest.raises(ValidationError):
        ExamResponse.model_validate(body)


def test_student_projection_cannot_expose_solutions(client):
    exam = ExamResponse.model_validate(generated(client))
    safe = exam.student_view()
    assert StudentExamResponse.model_validate_json(safe.model_dump_json()) == safe
    forbidden = {"answer", "correct_answer", "explanation", "step_solutions", "rubric", "validation", "source_ref"}

    def walk(value):
        if isinstance(value, dict):
            assert forbidden.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(safe.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        StudentExamResponse.model_validate(exam.model_dump(mode="json"))


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/students"), ("GET", "/api/v1/students/DEMO_NEW_001/profile"),
    ("GET", "/api/v1/topics"), ("POST", "/api/v1/exams/generate"),
    ("GET", "/api/v1/exams/ANY?audience=student"),
])
def test_teacher_routes_deny_anonymous_and_student_tokens(method, path):
    with TestClient(create_app(teacher_token=TOKEN)) as unauthenticated:
        kwargs = {"json": payload()} if method == "POST" else {}
        assert unauthenticated.request(method, path, **kwargs).status_code == 401
        denied = unauthenticated.request(method, path, headers={"Authorization": "Bearer student-token"}, **kwargs)
        assert denied.status_code == 403
        assert "correct_answer" not in denied.text


def test_no_configured_teacher_token_fails_closed(monkeypatch):
    monkeypatch.delenv("FAKE_API_TEACHER_TOKEN", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/students")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "TEACHER_ACCESS_NOT_CONFIGURED"


@pytest.mark.parametrize("value", [None, -1, True, "3"])
def test_malformed_profile_is_not_silently_defaulted(tmp_path, value):
    shutil.copytree(DEFAULT_FIXTURES, tmp_path / "data")
    path = tmp_path / "data" / "student_profiles.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if value is None:
        fixture["students"][0].pop("evidence_count")
    else:
        fixture["students"][0]["evidence_count"] = value
    path.write_text(json.dumps(fixture), encoding="utf-8")
    with TestClient(create_app(teacher_token=TOKEN, fixture_dir=path.parent), headers=HEADERS) as client:
        response = client.get("/api/v1/students/DEMO_NEW_001/profile")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INVALID_PROFILE_DATA"


def test_missing_fixture_and_database_do_not_create_files(tmp_path):
    missing = tmp_path / "missing.db"
    with TestClient(create_app(teacher_token=TOKEN, bank_path=missing), headers=HEADERS) as client:
        assert client.get("/api/v1/topics").status_code == 500
    assert not missing.exists()
    with TestClient(create_app(teacher_token=TOKEN, fixture_dir=tmp_path), headers=HEADERS) as client:
        assert client.get("/api/v1/students").status_code == 500


def test_generator_can_be_replaced_and_bad_output_is_not_stored():
    real_fake = FakeExamGenerator(StaticDataAdapter())

    class Replacement:
        calls = 0

        def generate(self, request, profile):
            self.calls += 1
            result = real_fake.generate(request, profile).model_dump(mode="json")
            result["student_id"] = "SOMEONE_ELSE"
            return result

    replacement = Replacement()
    app = create_app(teacher_token=TOKEN, generator=replacement)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=payload())
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INVALID_EXAM_OUTPUT"
        assert replacement.calls == 1
        assert not app.state.exams._exams


def test_valid_service_replacement_uses_same_http_contract():
    fixture_generator = FakeExamGenerator(StaticDataAdapter())

    class Replacement:
        def generate(self, request, profile):
            result = fixture_generator.generate(request, profile).model_dump(mode="json")
            result["title"] = "Replacement service draft"
            return result

    with TestClient(create_app(teacher_token=TOKEN, generator=Replacement()), headers=HEADERS) as client:
        body = generated(client)
        assert body["title"] == "Replacement service draft"
        ExamResponse.model_validate(body)


def test_replacement_cannot_ignore_requested_distribution():
    fixture_generator = FakeExamGenerator(StaticDataAdapter())

    class WrongDistribution:
        def generate(self, request, profile):
            result = fixture_generator.generate(request, profile).model_dump(mode="json")
            result["questions"][0]["cognitive_level"] = "advanced_application"
            return result

    with TestClient(create_app(teacher_token=TOKEN, generator=WrongDistribution()), headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=payload())
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INVALID_EXAM_OUTPUT"


@pytest.mark.parametrize("status,code", [(502, "INVALID_MODEL_OUTPUT"), (503, "MODEL_UNAVAILABLE"), (504, "GENERATION_TIMEOUT")])
def test_replacement_provider_failures_are_errors_not_partial_exams(status, code):
    class FailingService:
        def generate(self, request, profile):
            raise ApiFailure(status, code, "Provider failure")

    with TestClient(create_app(teacher_token=TOKEN, generator=FailingService()), headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=payload())
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert "questions" not in response.json()
        assert response.headers["cache-control"] == "no-store"


def test_cors_allows_only_configured_ui_origin(monkeypatch):
    monkeypatch.setenv("FAKE_API_CORS_ORIGINS", "http://localhost:5173")
    with TestClient(create_app(teacher_token=TOKEN)) as client:
        headers = {
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        response = client.options("/api/v1/exams/generate", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        headers["Origin"] = "http://untrusted.example"
        assert client.options("/api/v1/exams/generate", headers=headers).status_code == 400


def test_new_process_store_has_no_previous_exam(client):
    exam = generated(client)
    with TestClient(create_app(teacher_token=TOKEN), headers=HEADERS) as restarted:
        assert restarted.get(f"/api/v1/exams/{exam['exam_id']}").status_code == 404


def test_generate_does_not_write_data_or_call_qwen(client, monkeypatch):
    paths = [DEFAULT_BANK, DEFAULT_BANK.parent.parent / "memory" / "student_profiles_sample.db"]
    paths.extend(DEFAULT_FIXTURES.glob("*.json"))
    before = {p: hashlib.sha256(p.read_bytes()).digest() for p in paths}

    def no_network(*args, **kwargs):
        pytest.fail("Fake generation must not call inference HTTP")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    generated(client)
    assert before == {p: hashlib.sha256(p.read_bytes()).digest() for p in paths}


def test_openapi_documents_five_teacher_endpoints(client):
    schema = client.get("/openapi.json").json()
    assert len(schema["paths"]) == 5
    for path in schema["paths"].values():
        for operation in path.values():
            assert operation["security"] == [{"HTTPBearer": []}]
            assert "200" in operation["responses"]


@pytest.mark.parametrize("mutation", ["evidence", "identity", "duration", "distribution"])
def test_generator_cannot_rewrite_trusted_context(mutation):
    fixture_generator = FakeExamGenerator(StaticDataAdapter())

    class MutatingService:
        def generate(self, request, profile):
            if mutation == "evidence":
                request.generation_mode = "adaptive"
                profile.evidence_count = 3
                profile.data_status = "sufficient"
            elif mutation == "identity":
                profile.student_id = "SOMEONE_ELSE"
            elif mutation == "duration":
                request.duration_minutes = 60
            else:
                for level in ("recognition", "understanding", "application", "advanced_application"):
                    setattr(request.difficulty_distribution, level, 100 if level == "recognition" else 0)
            return fixture_generator.generate(request, profile)

    app = create_app(teacher_token=TOKEN, generator=MutatingService())
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=payload(total_questions=1))
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INVALID_EXAM_OUTPUT"
        assert not app.state.exams._exams
        assert client.get("/api/v1/students/DEMO_NEW_001/profile").json()["evidence_count"] == 0


def test_generator_nested_working_mutations_do_not_change_original_inputs():
    fixture_generator = FakeExamGenerator(StaticDataAdapter())

    class WorkingCopyService:
        def generate(self, request, profile):
            result = fixture_generator.generate(request, profile)
            request.selected_topic_ids.clear()
            request.difficulty_distribution.recognition = 999
            profile.skill_mastery[0].mastery_score = 4
            profile.skill_mastery.clear()
            return result

    with TestClient(create_app(teacher_token=TOKEN, generator=WorkingCopyService()), headers=HEADERS) as client:
        url = "/api/v1/students/DEMO_SUFFICIENT_001/profile"
        before = client.get(url).json()
        exam = generated(client, student_id="DEMO_SUFFICIENT_001", generation_mode="adaptive")
        assert exam["generation_mode"] == "adaptive" and exam["evidence_count"] == 3
        assert client.get(url).json() == before


@pytest.mark.parametrize("change", [
    {"skill_ids": ["DOES_NOT_EXIST"]},
    {"skill_ids": ["A001", "A001"]},
    {"source_ref": {"kind": "question", "id": "DOES_NOT_EXIST"}},
    {"source_ref": {"kind": "template", "id": "DOES_NOT_EXIST"}},
    {"source_ref": {"kind": "question", "id": "EA0001"}},
    {"source_ref": {"kind": "template", "id": "QA0001"}},
    {"skill_ids": ["A003"]},  # Known skill, but DEMO_Q01 is linked to A001.
    {"source_ref": {"kind": "question", "id": "QA0001"}, "skill_ids": ["A003"]},
])
def test_generator_invalid_catalogue_references_are_not_stored(change):
    fixture_generator = FakeExamGenerator(StaticDataAdapter())

    class BadReferences:
        def generate(self, request, profile):
            result = fixture_generator.generate(request, profile).model_dump(mode="json")
            result["questions"][0].update(change)
            return result

    app = create_app(teacher_token=TOKEN, generator=BadReferences())
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=payload(
            total_questions=1, difficulty_distribution={
                "recognition": 100, "understanding": 0, "application": 0, "advanced_application": 0,
            },
        ))
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INVALID_EXAM_OUTPUT"
        assert not app.state.exams._exams


@pytest.mark.parametrize("kind,source_id", [("question", "QA0001"), ("template", "EA0001")])
def test_reference_validator_recognizes_existing_repository_sources(kind, source_id):
    # Identity/link checks only; this does not claim semantic approval of a draft.
    data = StaticDataAdapter()
    request = GenerateExamRequest.model_validate(payload(
        total_questions=1, difficulty_distribution={
            "recognition": 100, "understanding": 0, "application": 0, "advanced_application": 0,
        },
    ))
    exam = FakeExamGenerator(data).generate(request, data.get_profile(request.student_id))
    exam.questions[0].source_ref.kind = kind
    exam.questions[0].source_ref.id = source_id
    data.validate_exam_references(exam)


@pytest.mark.parametrize("failure", ["missing", "invalid_json", "invalid_schema"])
def test_broken_question_fixture_does_not_break_profile_or_topics(tmp_path, failure):
    fixture_dir = tmp_path / "fixtures"
    shutil.copytree(DEFAULT_FIXTURES, fixture_dir)
    question_path = fixture_dir / "questions.json"
    if failure == "missing":
        question_path.unlink()
    elif failure == "invalid_json":
        question_path.write_text("{", encoding="utf-8")
    else:
        fixture = json.loads(question_path.read_text(encoding="utf-8"))
        fixture["questions"][0].pop("answer")
        question_path.write_text(json.dumps(fixture), encoding="utf-8")
    app = create_app(teacher_token=TOKEN, fixture_dir=fixture_dir)
    with TestClient(app, headers=HEADERS) as client:
        for path in ("/api/v1/students", "/api/v1/students/DEMO_NEW_001/profile", "/api/v1/topics"):
            assert client.get(path).status_code == 200
        response = client.post("/api/v1/exams/generate", json=payload())
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "DATA_SOURCE_ERROR"
        assert not app.state.exams._exams
        assert client.get("/api/v1/students/DEMO_NEW_001/profile").status_code == 200
        assert client.get("/api/v1/topics").status_code == 200


def test_topics_do_not_depend_on_profile_fixtures(tmp_path):
    with TestClient(create_app(teacher_token=TOKEN, fixture_dir=tmp_path), headers=HEADERS) as client:
        assert client.get("/api/v1/topics").status_code == 200
        response = client.get("/api/v1/students")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INVALID_PROFILE_DATA"


@pytest.mark.parametrize("origin", [None, "http://localhost:5173", "http://untrusted.example"])
def test_unexpected_500_preserves_cors_only_for_allowed_origins(monkeypatch, origin):
    monkeypatch.setenv("FAKE_API_CORS_ORIGINS", "http://localhost:5173")

    class CrashingService:
        def generate(self, request, profile):
            raise RuntimeError("Internal provider details must stay private")

    app = create_app(teacher_token=TOKEN, generator=CrashingService())
    with TestClient(app, headers=HEADERS, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/exams/generate", json=payload(),
            headers={"Origin": origin} if origin else {},
        )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "provider details" not in response.text
        assert response.headers["cache-control"] == "no-store"
        if origin == "http://localhost:5173":
            assert response.headers["access-control-allow-origin"] == origin
            assert "Origin" in response.headers["vary"]
        else:
            assert "access-control-allow-origin" not in response.headers


def test_advanced_options_openapi_matches_supported_values(client):
    properties = client.get("/openapi.json").json()["components"]["schemas"]["AdvancedOptions"]["properties"]
    assert properties["include_real_world_context"]["const"] is True
    assert properties["include_real_world_context"]["type"] == "boolean"
    assert properties["step_scoring_granularity"]["const"] == 0.25
    assert properties["step_scoring_granularity"]["type"] == "number"
    valid = {"include_real_world_context": True, "step_scoring_granularity": 0.25}
    assert AdvancedOptions.model_validate(valid).model_dump() == valid
    assert AdvancedOptions().model_dump() == valid
    assert client.post("/api/v1/exams/generate", json=payload(advanced_options=valid)).status_code == 200


@pytest.mark.parametrize("options", [
    {"include_real_world_context": False}, {"include_real_world_context": 1},
    {"include_real_world_context": "true"}, {"step_scoring_granularity": 0.5},
    {"step_scoring_granularity": "0.25"},
])
def test_advanced_options_reject_values_outside_published_constants(client, options):
    with pytest.raises(ValidationError):
        AdvancedOptions.model_validate(options)
    response = client.post("/api/v1/exams/generate", json=payload(advanced_options=options))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"
