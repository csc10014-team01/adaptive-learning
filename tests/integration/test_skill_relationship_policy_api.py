"""Existing policy loader/API against synthetic nine-skill and real legacy data."""

import hashlib
import json
import sqlite3
from threading import BoundedSemaphore

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from src.ai.contracts import GenerationCandidate
from src.api.data_adapter import DEFAULT_BANK, StaticDataAdapter
from src.api.main import create_app
from src.api.m3_adapter import DEFAULT_STUDENTS
from src.api.schemas import LEVELS
from tests.unit.test_planner import make_data, profile, question, request
from tests.unit.test_skill_relationship_policy import CATALOGUE, POLICY, load_policy

HEADERS = {"Authorization": "Bearer relationship-policy-test"}
SKILL_NAMES = {
    "A001": "Quy tắc cộng", "A002": "Quy tắc nhân", "A003": "Hoán vị",
    "A004": "Tổ hợp", "A005": "Sơ đồ cây", "A006": "Chỉnh hợp",
    "A007": "Kết hợp", "A008": "Kỹ năng tính toán", "A009": "Đếm có điều kiện ràng buộc",
}


class EchoTransport:
    """No Ollama: exercise production orchestration with a deterministic double."""
    model = "synthetic-policy-test-only"
    attempts = 1
    exam_timeout = 10

    def __init__(self):
        self.calls = 0
        self.capacity = BoundedSemaphore(1)

    def generate_one(self, content, **kwargs):
        self.calls += 1
        return GenerationCandidate(model=self.model, raw_response=json.dumps({"question": content}))


def synthetic_data(tmp_path):
    # An isolated, explicitly synthetic SQLite catalogue verifies the existing
    # reader accepts all nine approved IDs and exact names. No canonical writes.
    path = tmp_path / "synthetic-nine-skill-catalogue.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE skills (skill_id TEXT PRIMARY KEY, name TEXT, topic TEXT, grade_level INTEGER)")
        connection.executemany("INSERT INTO skills VALUES (?, ?, ?, ?)",
            [(skill, SKILL_NAMES[skill], "Đại số tổ hợp", 10) for skill in CATALOGUE])
    bank = [question(skill, level, index,
        content=f"Đây là câu tự luận kiểm thử cho kỹ năng {skill}, mức {level}, bản {index}.")
        for skill in CATALOGUE for level in LEVELS for index in range(3)]
    data = make_data(bank=bank, skills=CATALOGUE)
    data._topic = StaticDataAdapter(bank_path=path).topic
    data._profiles = {"S": profile([("A004", 1.8, 3), ("A009", 1.9, 3)])}
    return data


def test_environment_policy_loads_for_nine_skill_plan_and_generation_without_api_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_RELATIONSHIPS_FILE", str(POLICY))
    data, transport = synthetic_data(tmp_path), EchoTransport()
    student_before = data.get_profile("S").model_dump_json()
    questions_before = [q.model_dump_json() for q in data.questions]
    store = tmp_path / "drafts.db"
    app = create_app(backend="qwen", teacher_token="relationship-policy-test", qwen_client=transport, exam_db=store)
    app.state.data = data
    assert app.state.relationships == load_policy()
    body = request().model_dump(mode="json")
    with TestClient(app, headers=HEADERS) as client:
        catalogue = client.get("/api/v1/topics").json()["items"][0]["skills"]
        assert {s["skill_id"]: s["name"] for s in catalogue} == SKILL_NAMES
        planned = client.post("/api/v1/exams/plan", json=body)
        assert planned.status_code == 200, planned.text
        plan = planned.json()
        assert client.post("/api/v1/exams/plan", json=body).json() == plan
        assert transport.calls == 0 and not store.exists()
        assert plan["policy_version"].endswith("+a001-a009-relationships-v1")
        assert plan["priority_skills"] == ["A004", "A009"]
        assert plan["quota_summary"]["achieved_groups"] == {"focus": 6, "related_review": 2, "balanced_review": 2}
        expected_levels = plan["quota_summary"]["requested_levels"]
        assert plan["quota_summary"]["achieved_levels"] == expected_levels
        generated = client.post("/api/v1/exams/generate", json=body)
        assert generated.status_code == 200, generated.text
        exam = generated.json()
        assert exam["status"] == "pending_teacher_review" and exam["revision"] == 1
        assert transport.calls == 0  # Synthetic fixtures here contain immutable Questions only.
        assert [q["source_ref"]["id"] for q in exam["questions"]] == [q["source_id"] for q in plan["questions"]]
        assert exam["planner_summary"]["quota_summary"]["achieved_levels"] == expected_levels
        assert client.get(f"/api/v1/exams/{exam['exam_id']}").json() == exam
        assert len(client.get("/openapi.json").json()["paths"]) == 8
    assert data.get_profile("S").model_dump_json() == student_before
    assert [q.model_dump_json() for q in data.questions] == questions_before


def test_explicit_nine_skill_policy_rejects_real_seven_skill_database_before_inference(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_RELATIONSHIPS_FILE", str(POLICY))
    before = {path: hashlib.sha256(path.read_bytes()).digest() for path in (DEFAULT_BANK, DEFAULT_STUDENTS)}
    transport = EchoTransport()
    store = tmp_path / "not-saved.db"
    from src.api.data_adapter import ROOT
    legacy_bank = ROOT / "data/sample/dataset/question_bank.db"
    app = create_app(backend="qwen", bank_path=legacy_bank, teacher_token="relationship-policy-test", qwen_client=transport, exam_db=store)
    body = request(4, student_id="ST001").model_dump(mode="json")
    with TestClient(app, headers=HEADERS) as client:
        topic = client.get("/api/v1/topics").json()["items"][0]
        assert [s["skill_id"] for s in topic["skills"]] == CATALOGUE[:7]
        for route in ("/api/v1/exams/plan", "/api/v1/exams/generate"):
            result = client.post(route, json=body)
            assert result.status_code == 500
            assert result.json()["error"]["code"] == "DATA_SOURCE_ERROR"
            assert "Relationship policy does not match the data catalogue" in result.json()["error"]["message"]
        assert transport.calls == 0 and not store.exists()
    # The same real seven-skill sources still work when the optional policy is unset.
    monkeypatch.delenv("SKILL_RELATIONSHIPS_FILE")
    with TestClient(create_app(backend="fake", profile_source="m3", bank_path=legacy_bank, teacher_token="relationship-policy-test"), headers=HEADERS) as client:
        assert client.post("/api/v1/exams/plan", json=body).status_code == 200
    assert {path: hashlib.sha256(path.read_bytes()).digest() for path in before} == before


@pytest.mark.parametrize("invalid", ["json", "missing_row", "self_reference"])
def test_bad_explicit_policy_fails_clearly_during_existing_app_configuration(tmp_path, monkeypatch, invalid):
    path = tmp_path / "invalid-policy.json"
    if invalid == "json":
        path.write_text("{not-json", encoding="utf-8")
    else:
        value = json.loads(POLICY.read_text(encoding="utf-8"))
        if invalid == "missing_row":
            value["priorities"].pop("A009")
        else:
            value["priorities"]["A009"]["A009"] = 3
        path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setenv("SKILL_RELATIONSHIPS_FILE", str(path))
    with pytest.raises(ValidationError):
        create_app(backend="fake", teacher_token="relationship-policy-test")
