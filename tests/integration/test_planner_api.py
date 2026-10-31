"""Planner contracts through the existing API with synthetic banks."""

import json

from fastapi.testclient import TestClient
import pytest

from src.api.main import create_app
from src.api.schemas import LEVELS
from tests.unit.test_planner import make_data, profile, question, request

HEADERS = {"Authorization": "Bearer teacher-test"}
CATALOGUE = [f"A00{i}" for i in range(1, 10)]


def fixtures(path, student, bank=None):
    path.mkdir()
    envelope = {"fixture_kind": "synthetic_api_demo", "topic_id": "combinatorics"}
    (path / "student_profiles.json").write_text(json.dumps(envelope | {"students": [student.model_dump()]}), encoding="utf-8")
    if bank is None:
        bank = make_data(skills=CATALOGUE).questions
    (path / "questions.json").write_text(json.dumps(envelope | {"questions": [q.model_dump() for q in bank]}), encoding="utf-8")
    return path


@pytest.mark.parametrize("rows,strategy,groups", [
    ([], "diagnostic_review", {"diagnostic": 10, "maintenance": 0}),
    ([("A001", 1, 3)], "focused_practice", {"focus": 4, "review": 6}),
    ([("A001", 4, 3)], "diagnostic_review", {"diagnostic": 6, "maintenance": 4}),
    ([(s, 4, 3) for s in CATALOGUE], "advanced_review", {"advanced_review": 10}),
])
def test_plan_endpoint_strategies_without_model_or_draft(tmp_path, rows, strategy, groups):
    directory = fixtures(tmp_path / "fixtures", profile(rows))
    app = create_app(backend="fake", teacher_token="teacher-test", fixture_dir=directory)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/plan", json=request().model_dump(mode="json"))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["strategy"] == strategy and result["difficulty_locked"] is False
    assert result["quota_summary"]["requested_groups"] == groups
    assert result["quota_summary"]["achieved_groups"] == groups
    assert not app.state.exams._exams


def test_teacher_quota_shortage_returns_typed_409_and_no_partial_plan(tmp_path):
    directory = fixtures(tmp_path / "fixtures", profile([("A001", 1, 5)]),
                         [question(level="advanced_application", index=i) for i in range(10)])
    app = create_app(backend="fake", teacher_token="teacher-test", fixture_dir=directory)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/plan", json=request().model_dump(mode="json"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_QUESTION_BANK"
    assert "questions" not in response.json() and not app.state.exams._exams


@pytest.mark.parametrize("mutation", ["primary", "level", "duplicate", "skills"])
def test_invalid_bank_has_data_source_error(tmp_path, mutation):
    directory = fixtures(tmp_path / "fixtures", profile(), [question()])
    path = directory / "questions.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    q = content["questions"][0]
    if mutation == "primary":
        q["primary_skill_id"] = "A002"
    elif mutation == "level":
        q["cognitive_level"] = "L9"
    elif mutation == "skills":
        q["skill_ids"] = ["A001", "A001"]
    else:
        content["questions"].append(q.copy())
    path.write_text(json.dumps(content), encoding="utf-8")
    app = create_app(backend="fake", teacher_token="teacher-test", fixture_dir=directory)
    with TestClient(app, headers=HEADERS) as client:
        result = client.post("/api/v1/exams/plan", json=request(1).model_dump(mode="json"))
    assert result.status_code == 500
    assert result.json()["error"]["code"] == "DATA_SOURCE_ERROR"


def test_ambiguous_multi_skill_is_excluded_with_warning(tmp_path):
    bank = [question(), question(index=1, primary_skill_id=None, skill_ids=["A001", "A002"])]
    directory = fixtures(tmp_path / "fixtures", profile(), bank)
    app = create_app(backend="fake", teacher_token="teacher-test", fixture_dir=directory)
    with TestClient(app, headers=HEADERS) as client:
        result = client.post("/api/v1/exams/plan", json=request(1).model_dump(mode="json"))
    assert result.status_code == 200
    assert any("primary_skill_id" in warning for warning in result.json()["warnings"])
    assert result.json()["questions"][0]["source_id"] == bank[0].question_id


@pytest.mark.parametrize("locked", [False, True])
def test_teacher_endpoint_rejects_legacy_standard_and_manual_overrides(tmp_path, locked):
    directory = fixtures(tmp_path / "fixtures", profile())
    app = create_app(backend="fake", teacher_token="teacher-test", fixture_dir=directory)
    req = request(4, "standard", **({"difficulty_distribution": dict(zip(LEVELS, (25, 25, 25, 25)))} if locked else {}))
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=req.model_dump(mode="json"))
    assert response.status_code == 422, response.text
    result = response.json()
    assert result["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert any("generation_mode" in detail["field"] for detail in result["error"]["details"])
    assert not app.state.exams._exams


def test_primary_metadata_preserved_in_openapi():
    with TestClient(create_app(backend="fake", teacher_token="teacher-test")) as client:
        schema = client.get("/openapi.json").json()["components"]["schemas"]
    assert "difficulty_distribution" not in schema["GenerateExamRequest"]["required"]
    assert schema["GenerateExamRequest"]["properties"]["generation_mode"]["enum"] == ["adaptive"]
    assert schema["GenerateExamRequest"]["properties"]["difficulty_distribution"]["enum"] == [None]
    assert "target_skill_id" in schema["PlannedQuestion"]["required"]
    assert "planner_summary" in schema["ExamResponse"]["properties"]


def test_qwen_generation_accepts_mastery_levels_without_teacher_lock(tmp_path):
    # A local client double proves integration accepts adaptive L3/L4 totals and
    # preserves a multi-skill source; it performs no model call or math changes.
    from threading import BoundedSemaphore
    from src.api.data_adapter import StaticDataAdapter
    from src.api.real_generator import QwenExamGenerator

    bank = [question(s, level, i, content="Synthetic mathematical question for pipeline validation.",
                     skill_ids=[s, "A007"] if s != "A007" else [s])
            for s in CATALOGUE for level in LEVELS for i in range(3)]
    directory = fixtures(tmp_path / "fixtures", profile([(s, 4, 3) for s in CATALOGUE]), bank)
    data = StaticDataAdapter(fixture_dir=directory)

    class LocalClient:
        capacity = BoundedSemaphore(1)
        exam_timeout = 10
        model = "local-test-double"

        def rewrite(self, content, *, deadline):
            return content

    generator = QwenExamGenerator(data, LocalClient())
    app = create_app(backend="fake", teacher_token="teacher-test", fixture_dir=directory, generator=generator)
    req = request().model_dump(mode="json")
    with TestClient(app, headers=HEADERS) as client:
        planned = client.post("/api/v1/exams/plan", json=req)
        response = client.post("/api/v1/exams/generate", json=req)
    assert response.status_code == planned.status_code == 200, response.text
    exam = response.json()
    assert exam["planner_summary"]["strategy"] == "advanced_review"
    assert not exam["planner_summary"]["difficulty_locked"]
    assert not exam["planner_summary"]["warnings"]
    assert exam["planner_summary"]["quota_summary"]["achieved_levels"] == dict(zip(LEVELS, (1, 3, 4, 2)))
    assert [q["source_ref"]["id"] for q in exam["questions"]] == [q["source_id"] for q in planned.json()["questions"]]
    for q in exam["questions"]:
        original = next(item for item in bank if item.question_id == q["source_ref"]["id"])
        assert q["target_skill_id"] == original.primary_skill_id and q["skill_ids"] == original.skill_ids


def test_invalid_mastery_returns_profile_error(tmp_path):
    directory = fixtures(tmp_path / "fixtures", profile([("A001", 1, 3)]))
    path = directory / "student_profiles.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    content["students"][0]["skill_mastery"][0].pop("mastery_score")
    path.write_text(json.dumps(content), encoding="utf-8")
    with TestClient(create_app(backend="fake", teacher_token="teacher-test", fixture_dir=directory), headers=HEADERS) as client:
        response = client.post("/api/v1/exams/plan", json=request().model_dump(mode="json"))
    assert response.status_code == 500 and response.json()["error"]["code"] == "INVALID_PROFILE_DATA"
