"""Independent SQL/API checks; only temporary test databases may be written."""

import hashlib
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.adaptive_generator import SQLDataAdapter
from src.api.data_adapter import DEFAULT_BANK, ROOT
from src.api.main import create_app
from src.api.schemas import SkillMastery
from src.exam_generator.api.m3_adapter import DEFAULT_STUDENTS

SKILLS = [f"A{i:03}" for i in range(1, 10)]
HEADERS = {"Authorization": "Bearer sql-test"}


def student_database(tmp_path, rows=()):
    path = tmp_path / "students.db"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript("""
            CREATE TABLE Students(student_id TEXT PRIMARY KEY, name TEXT, grade_level INTEGER);
            CREATE TABLE student_skill_mastery(student_id TEXT, skill_id TEXT, mastery_score REAL,
                evidence_count INTEGER, PRIMARY KEY(student_id, skill_id));
            CREATE TABLE Tests(test_id TEXT, student_id TEXT, date TEXT);
            CREATE TABLE test_questions(test_id TEXT, question_id TEXT, is_correct INTEGER, question_order INTEGER);
            INSERT INTO Students VALUES ('TEST', 'Isolated SQL student', 10);
        """)
        connection.executemany(
            "INSERT INTO student_skill_mastery VALUES ('TEST', ?, ?, ?)", rows
        )
    return path


def app_for(tmp_path, path):
    return create_app(
        backend="fake",
        profile_source="m3",
        student_path=path,
        teacher_token="sql-test",
        instance_seed=42,
    )


def request():
    return {
        "student_id": "TEST",
        "selected_topic_ids": ["combinatorics"],
        "total_questions": 10,
        "duration_minutes": 45,
    }


@pytest.mark.parametrize("score", [None, 0.0, 2.0, 4.0])
def test_missing_and_zero_evidence_are_null_without_database_writes(tmp_path, score):
    path = student_database(tmp_path, [("A001", score, 0)])
    before = path.read_bytes()
    with TestClient(app_for(tmp_path, path), headers=HEADERS) as client:
        profile = client.get("/api/v1/students/TEST/profile").json()
        assert profile["skill_mastery"] == [
            {"skill_id": skill, "mastery_score": None, "evidence_count": 0}
            for skill in SKILLS
        ]
        assert profile["student_name"] == "Isolated SQL student"
        assert profile["evidence_count"] is None and profile["data_status"] is None
        planned = client.post("/api/v1/exams/plan", json=request()).json()
        assert planned["strategy"] == "diagnostic_review"
        assert planned["skill_classifications"] == dict.fromkeys(SKILLS, "NO_DATA")
        generated = client.post("/api/v1/exams/generate", json=request())
        assert generated.status_code == 200, generated.text
        quotas = generated.json()["planner_summary"]["quota_summary"]
        assert quotas == planned["quota_summary"]
        assert list(quotas["achieved_levels"].values()) == [3, 3, 3, 1]
    assert path.read_bytes() == before


def test_mixed_assessed_zero_and_unassessed_values_agree_across_sql_api_and_planner(
    tmp_path,
):
    path = student_database(
        tmp_path,
        [("A001", 0.0, 6), ("A002", 3.25, 7), ("A003", 1.125, 2), ("A004", 4.0, 0)],
    )
    with TestClient(app_for(tmp_path, path), headers=HEADERS) as client:
        response = client.get("/api/v1/students/TEST/profile")
        assert response.status_code == 200, response.text
        rows = response.json()["skill_mastery"]
        assert [(s["mastery_score"], s["evidence_count"]) for s in rows[:3]] == [
            (0.0, 6),
            (3.25, 7),
            (1.125, 2),
        ]
        assert all(
            s["mastery_score"] is None and s["evidence_count"] == 0 for s in rows[3:]
        )
        planned = client.post("/api/v1/exams/plan", json=request()).json()
        assert planned["skill_classifications"] == {
            "A001": "WEAK",
            "A002": "ACHIEVED",
            "A003": "PARTIAL",
            **dict.fromkeys(SKILLS[3:], "NO_DATA"),
        }
        assert planned["quota_summary"]["requested_groups"] == {"focus": 4, "review": 6}


@pytest.mark.parametrize("evidence", [1, 3, 7])
def test_positive_evidence_missing_mastery_remains_an_integrity_error(
    tmp_path, evidence
):
    with pytest.raises(ValidationError, match="Positive evidence"):
        SkillMastery(skill_id="A001", evidence_count=evidence)
    path = student_database(tmp_path, [("A001", None, evidence)])
    before = path.read_bytes()
    with TestClient(app_for(tmp_path, path), headers=HEADERS) as client:
        for endpoint in ("/api/v1/students", "/api/v1/students/TEST/profile"):
            response = client.get(endpoint)
            assert response.status_code == 500, response.text
            assert response.json()["error"]["code"] == "INVALID_PROFILE_DATA"
    assert path.read_bytes() == before


def test_all_canonical_profiles_match_independent_read_only_sql(tmp_path):
    paths = (DEFAULT_STUDENTS, DEFAULT_BANK)
    before = {p: hashlib.sha256(p.read_bytes()).digest() for p in paths}
    assert DEFAULT_STUDENTS == ROOT / "data/sample/memory/student_profiles_sample.db"
    with closing(
        sqlite3.connect(DEFAULT_STUDENTS.resolve().as_uri() + "?mode=ro", uri=True)
    ) as connection:
        connection.execute("PRAGMA query_only=ON")
        source = {
            (sid, skill): (score, count)
            for sid, skill, score, count in connection.execute(
                "SELECT student_id,skill_id,mastery_score,evidence_count FROM student_skill_mastery"
            )
        }
        students = [
            row[0]
            for row in connection.execute(
                "SELECT student_id FROM Students ORDER BY student_id"
            )
        ]
    app = app_for(tmp_path, DEFAULT_STUDENTS)
    assert app.state.student_path.resolve() == DEFAULT_STUDENTS.resolve()
    with TestClient(app, headers=HEADERS) as client:
        for sid in students:
            response = client.get(f"/api/v1/students/{sid}/profile")
            assert response.status_code == 200, response.text
            expected = []
            for skill in SKILLS:
                score, count = source.get((sid, skill), (None, 0))
                expected.append(
                    {
                        "skill_id": skill,
                        "mastery_score": score if count else None,
                        "evidence_count": count,
                    }
                )
            assert response.json()["skill_mastery"] == expected
    assert isinstance(app.state.data, SQLDataAdapter)
    assert app.state.data.core.student_path.resolve() == DEFAULT_STUDENTS.resolve()
    assert before == {p: hashlib.sha256(p.read_bytes()).digest() for p in paths}


def test_missing_canonical_database_never_falls_back_to_demo(tmp_path):
    path = tmp_path / "missing.db"
    with TestClient(app_for(tmp_path, path), headers=HEADERS) as client:
        response = client.get("/api/v1/students")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INVALID_PROFILE_DATA"
    assert not path.exists()


@pytest.mark.parametrize("database", [DEFAULT_BANK, DEFAULT_STUDENTS])
def test_exam_store_cannot_write_into_a_canonical_database(database):
    with pytest.raises(ValueError, match="separate"):
        create_app(backend="qwen", exam_db=database)


def test_sql_override_resolves_from_project_root_and_nullable_mastery_is_documented(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("M3_STUDENT_DB", "data/sample/memory/student_profiles_sample.db")
    monkeypatch.chdir(tmp_path)
    app = create_app(profile_source="m3", teacher_token="sql-test")
    assert app.state.student_path.resolve() == DEFAULT_STUDENTS.resolve()
    field = app.openapi()["components"]["schemas"]["SkillMastery"]["properties"][
        "mastery_score"
    ]
    assert {s.get("type") for s in field["anyOf"]} == {"number", "null"}
