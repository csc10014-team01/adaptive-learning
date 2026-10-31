"""Structured sources exercise the existing endpoints, local transport and store."""

import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.ai.expression_planner import ExpressionPlanner
from src.api.data_adapter import DEFAULT_BANK, StaticDataAdapter
from src.api.m3_adapter import M3DataAdapter
from src.api.main import create_app
from src.orchestration.exam_service import ExamService
from tests.integration.test_real_api import HEADERS
from tests.integration.test_real_api import ollama as _ollama_fixture
from tests.unit.test_planner import make_data, profile, request
from tests.unit.test_structured_problems import structured_source

ollama = _ollama_fixture


@pytest.mark.parametrize(
    "context,kind",
    [("students", "direct"), ("students", "indirect"), ("books", "direct")],
)
def test_structured_generation_approval_and_regeneration_use_existing_contracts(
    tmp_path, ollama, context, kind
):
    qwen, calls, state = ollama
    source = structured_source()
    data = make_data(bank=[source])
    data._profiles = {"S": profile()}
    source_before = source.model_dump_json()
    service = ExamService(
        data,
        qwen,
        expression_planner=ExpressionPlanner(generate_type=kind, context_id=context),
    )
    app = create_app(
        backend="qwen",
        teacher_token="teacher-test",
        generator=service,
        exam_db=tmp_path / "exam.db",
    )
    app.state.data = data
    with TestClient(app, headers=HEADERS) as client:
        planned = client.post(
            "/api/v1/exams/plan", json=request(1).model_dump(mode="json")
        )
        assert planned.status_code == 200 and not calls
        response = client.post(
            "/api/v1/exams/generate", json=request(1).model_dump(mode="json")
        )
        assert response.status_code == 200, response.text
        exam = response.json()
        question = exam["questions"][0]
        assert (
            question["generate_type"] == "direct"
            and question["expression_context_id"] == "students"
        )
        assert question["content_latex"] == source.content
        assert (
            question["answer"]["correct_answer"] == source.problem_spec.verified_answer
        )
        assert [
            s["explanation"] for s in question["step_solutions"]
        ] == source.problem_spec.verified_solution
        assert exam["status"] == "pending_teacher_review" and not calls
        base = f"/api/v1/exams/{exam['exam_id']}"
        approval = client.post(
            base + "/approve",
            json={
                "expected_revision": 1,
                "accepted_question_ids": [question["question_id"]],
            },
        )
        assert approval.status_code == 200 and approval.json()["status"] == "approved"
        # A fresh default service must retain the stored context and presentation.
        app.state.generator = ExamService(data, qwen)
        regenerated = client.post(
            base + f"/questions/{question['question_id']}/regenerate",
            json={"expected_revision": 2},
        )
        assert regenerated.status_code == 409, regenerated.text
        assert regenerated.json()["error"]["code"] == "QUESTION_REGENERATION_FORBIDDEN"
        updated = approval.json()
        assert client.get(base).json() == updated
        state["kind"] = "numbers"
        failed = client.post(
            base + f"/questions/{updated['questions'][0]['question_id']}/regenerate",
            json={"expected_revision": 2},
        )
        assert (
            failed.status_code == 409
            and client.get(base).json() == updated
            and not calls
        )
    assert source.model_dump_json() == source_before
    for call in calls:
        assert (
            '"verified_answer"' not in call["prompt"]
            and '"verified_solution"' not in call["prompt"]
        )


def test_json_adapter_reads_opt_in_structured_metadata(tmp_path):
    source = structured_source()
    (tmp_path / "questions.json").write_text(
        json.dumps(
            {
                "fixture_kind": "synthetic_api_demo",
                "topic_id": "combinatorics",
                "questions": [source.model_dump(mode="json")],
            }
        ),
        encoding="utf-8",
    )
    adapter = StaticDataAdapter(fixture_dir=tmp_path)
    assert adapter.questions == [source]


def test_optional_sql_metadata_is_read_without_canonical_database_changes(tmp_path):
    import shutil

    path = tmp_path / "curated-bank.db"
    before = hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest()
    shutil.copyfile(DEFAULT_BANK, path)
    source = structured_source()
    # Isolated author annotation, not a canonical migration.
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE questions ADD COLUMN problem_spec_json TEXT")
        qid = connection.execute(
            "SELECT q.question_id FROM questions q JOIN question_skills qs USING(question_id) "
            "WHERE question_type='essay' GROUP BY q.question_id HAVING COUNT(*)=1 LIMIT 1"
        ).fetchone()[0]
        spec = source.problem_spec.model_dump(mode="json")
        spec["source_id"] = qid
        spec["verified_solution"] = [source.answer.explanation]
        connection.execute(
            "UPDATE questions SET content=? WHERE question_id=?", (source.content, qid)
        )
        connection.execute(
            "UPDATE answers SET correct_answer=?, explaination=? WHERE question_id=?",
            (source.answer.correct_answer, source.answer.explanation, qid),
        )
        connection.execute(
            "UPDATE questions SET problem_spec_json=? WHERE question_id=?",
            (json.dumps(spec), qid),
        )
    annotated = next(
        q for q in M3DataAdapter(bank_path=path).questions if q.question_id == qid
    )
    assert annotated.problem_spec.source_id == qid
    assert hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest() == before


def test_bad_optional_sql_metadata_fails_clearly(tmp_path):
    import shutil

    path = tmp_path / "bad-bank.db"
    shutil.copyfile(DEFAULT_BANK, path)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE questions ADD COLUMN problem_spec_json TEXT")
        connection.execute("UPDATE questions SET problem_spec_json='{}'")
    data = M3DataAdapter(bank_path=path)
    assert data.questions == []
    assert any(
        "INVALID_QUESTION" in reason
        for item in data.question_diagnostics
        for reason in item["reasons"]
    )
