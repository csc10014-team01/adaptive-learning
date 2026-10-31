"""Read-only profile projections; writes are confined to isolated test databases."""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.adaptation.planner import RuleBasedPlanner
from src.api.data_adapter import DEFAULT_BANK, DEFAULT_FIXTURES, ROOT, ApiFailure
from src.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter
from src.api.main import create_app
from src.api.schemas import SkillMastery, StudentProfileResponse
from tests.unit.test_planner import request

HEADERS = {"Authorization": "Bearer missing-mastery-test"}
CATALOGUE = [f"A{i:03}" for i in range(1, 10)]


def isolated_students(tmp_path, rows=()):
    """Nullable test column permits testing corrupt positive-evidence records."""
    path = tmp_path / "isolated_students.db"
    with sqlite3.connect(path) as c:
        c.executescript("""
            CREATE TABLE Students(student_id TEXT PRIMARY KEY, name TEXT, grade_level INTEGER);
            CREATE TABLE student_skill_mastery(student_id TEXT, skill_id TEXT, mastery_score REAL,
                evidence_count INTEGER, PRIMARY KEY(student_id, skill_id));
            CREATE TABLE Tests(test_id TEXT, student_id TEXT, date TEXT);
            CREATE TABLE test_questions(test_id TEXT, question_id TEXT, is_correct INTEGER, question_order INTEGER);
            INSERT INTO Students VALUES ('MIRA_TEST', 'Isolated profile test', 10);
        """)
        c.executemany(
            "INSERT INTO student_skill_mastery VALUES ('MIRA_TEST', ?, ?, ?)", rows
        )
    return path


def application(tmp_path, path):
    return create_app(
        backend="qwen",
        profile_source="m3",
        student_path=path,
        bank_path=DEFAULT_BANK,
        teacher_token="missing-mastery-test",
        fixture_dir=DEFAULT_FIXTURES,
        exam_db=tmp_path / "drafts.db",
    )


@pytest.mark.parametrize("score", [None, 0.0, 2.0, 4.0])
def test_explicit_zero_evidence_serializes_as_null_without_rewriting_sql(
    tmp_path, score
):
    path = isolated_students(tmp_path, [("A001", score, 0)])
    before = path.read_bytes()
    with TestClient(application(tmp_path, path), headers=HEADERS) as client:
        result = client.get("/api/v1/students/MIRA_TEST/profile")
        assert result.status_code == 200, result.text
        rows = result.json()["skill_mastery"]
        assert [s["skill_id"] for s in rows] == CATALOGUE
        assert all(
            s["mastery_score"] is None and s["evidence_count"] == 0 for s in rows
        )
    assert path.read_bytes() == before
    with sqlite3.connect(path) as c:
        assert c.execute(
            "SELECT mastery_score,evidence_count FROM student_skill_mastery"
        ).fetchall() == [(score, 0)]


def test_missing_rows_become_nine_response_only_no_data_skills_and_diagnostic_blueprint(
    tmp_path,
):
    path = isolated_students(tmp_path)
    before = path.read_bytes()
    with TestClient(application(tmp_path, path), headers=HEADERS) as client:
        response = client.get("/api/v1/students/MIRA_TEST/profile")
        assert response.status_code == 200, response.text
        profile = response.json()
        assert profile["skill_mastery"] == [
            {"skill_id": s, "mastery_score": None, "evidence_count": 0}
            for s in CATALOGUE
        ]
        body = request(10, student_id="MIRA_TEST").model_dump(mode="json")
        result = client.post("/api/v1/exams/plan", json=body)
        assert result.status_code == 200, result.text
        planned = result.json()
        assert planned["strategy"] == "diagnostic_review"
        assert planned["skill_classifications"] == dict.fromkeys(CATALOGUE, "NO_DATA")
        assert (
            planned["priority_skills"] == []
            and not planned["personalized"]
            and planned["target_count"] == 0
        )
        assert planned["quota_summary"]["requested_levels"] == {
            "recognition": 3,
            "understanding": 3,
            "application": 3,
            "advanced_application": 1,
        }
        assert client.get("/api/v1/students/MIRA_TEST/profile").json() == profile
    assert path.read_bytes() == before
    with sqlite3.connect(path) as c:
        assert (
            c.execute("SELECT count(*) FROM student_skill_mastery").fetchone()[0] == 0
        )


@pytest.mark.parametrize(
    "evidence,status", [(1, "PARTIAL"), (2, "PARTIAL"), (3, "WEAK"), (6, "WEAK")]
)
def test_legitimate_zero_mastery_with_real_evidence_is_preserved_and_not_no_data(
    tmp_path, evidence, status
):
    path = isolated_students(tmp_path, [("A001", 0.0, evidence)])
    data = M3DataAdapter(student_path=path)
    student = data.get_profile("MIRA_TEST")
    assert student.skill_mastery[0].mastery_score == 0.0
    assert student.skill_mastery[0].evidence_count == evidence
    planner = RuleBasedPlanner(data)
    assert planner.classify(student, CATALOGUE)["A001"] == status
    allocation = planner.build_allocation_plan(
        request(10, student_id="MIRA_TEST"), student
    )
    assert allocation.focus == (["A001"] if status == "WEAK" else [])
    if status == "WEAK":
        assert allocation.group_counts == {"focus": 4, "review": 6}
        assert allocation.weights["A001"] == (50, 40, 10, 0)


def test_mixed_profile_reads_exact_assessed_sql_values_and_preserves_focus_review_policy(
    tmp_path,
):
    path = isolated_students(
        tmp_path,
        [("A001", 0.0, 6), ("A002", 3.25, 7), ("A003", 1.125, 2), ("A004", 2.0, 0)],
    )
    with TestClient(application(tmp_path, path), headers=HEADERS) as client:
        response = client.get("/api/v1/students/MIRA_TEST/profile")
        assert response.status_code == 200, response.text
        fixture = Path(__file__).parents[1] / "fixtures/missing_mastery_profile.json"
        assert response.json() == json.loads(fixture.read_text(encoding="utf-8"))
        student = StudentProfileResponse.model_validate(response.json())
        rows = {s.skill_id: s for s in student.skill_mastery}
        assert [
            (rows[s].mastery_score, rows[s].evidence_count) for s in CATALOGUE[:3]
        ] == [(0.0, 6), (3.25, 7), (1.125, 2)]
        assert all(
            rows[s].mastery_score is None and rows[s].evidence_count == 0
            for s in CATALOGUE[3:]
        )
        data = M3DataAdapter(student_path=path)
        planner = RuleBasedPlanner(data)
        assert planner.classify(student, CATALOGUE) == dict(
            A001="WEAK",
            A002="ACHIEVED",
            A003="PARTIAL",
            **dict.fromkeys(CATALOGUE[3:], "NO_DATA"),
        )
        allocation = planner.build_allocation_plan(
            request(10, student_id="MIRA_TEST"), student
        )
        assert allocation.group_counts == {"focus": 4, "review": 6}
        assert allocation.weights["A002"] == (15, 30, 40, 15)


@pytest.mark.parametrize("evidence", [1, 3, 7])
def test_positive_evidence_with_null_mastery_is_an_integrity_error_not_no_data(
    tmp_path, evidence
):
    path = isolated_students(tmp_path, [("A001", None, evidence)])
    before = path.read_bytes()
    with TestClient(application(tmp_path, path), headers=HEADERS) as client:
        response = client.get("/api/v1/students/MIRA_TEST/profile")
        assert response.status_code == 500, response.text
        assert response.json()["error"]["code"] == "INVALID_PROFILE_DATA"
        assert "Positive evidence" in response.json()["error"]["message"]
        assert (
            client.post(
                "/api/v1/exams/plan",
                json=request(10, student_id="MIRA_TEST").model_dump(),
            ).status_code
            == 500
        )
    assert path.read_bytes() == before
    with sqlite3.connect(path) as c:
        assert c.execute(
            "SELECT mastery_score,evidence_count FROM student_skill_mastery"
        ).fetchone() == (None, evidence)


def test_live_sql_update_is_read_without_estimation_cache_or_demo_fallback(tmp_path):
    path = isolated_students(tmp_path, [("A001", 3.125, 5)])
    data = M3DataAdapter(student_path=path)
    assert data.get_profile("MIRA_TEST").skill_mastery[0].mastery_score == 3.125
    with sqlite3.connect(path) as c:
        c.execute("UPDATE student_skill_mastery SET mastery_score=0.0,evidence_count=8")
    row = data.get_profile("MIRA_TEST").skill_mastery[0]
    assert (row.mastery_score, row.evidence_count) == (0.0, 8)
    with sqlite3.connect(path) as c:
        c.execute("UPDATE student_skill_mastery SET mastery_score=NULL")
    with pytest.raises(ApiFailure) as error:
        data.get_profile("MIRA_TEST")
    assert error.value.code == "INVALID_PROFILE_DATA"


@pytest.mark.parametrize("unavailable", ["missing", "corrupt", "missing_table"])
def test_unavailable_authoritative_sql_never_creates_a_database_or_uses_demo_profiles(
    tmp_path, unavailable
):
    path = tmp_path / "unavailable.db"
    if unavailable == "corrupt":
        path.write_bytes(b"not a sqlite database")
    elif unavailable == "missing_table":
        with sqlite3.connect(path) as c:
            c.execute("CREATE TABLE unrelated(value TEXT)")
    before = path.read_bytes() if path.exists() else None
    with TestClient(application(tmp_path, path), headers=HEADERS) as client:
        for endpoint in ("/api/v1/students", "/api/v1/students/DEMO_NEW_001/profile"):
            response = client.get(endpoint)
            assert response.status_code == 500
            assert response.json()["error"]["code"] == "INVALID_PROFILE_DATA"
    assert (path.read_bytes() if path.exists() else None) == before


def test_absent_student_is_not_an_invented_or_demo_profile(tmp_path):
    path = isolated_students(tmp_path)
    with TestClient(application(tmp_path, path), headers=HEADERS) as client:
        response = client.get("/api/v1/students/DEMO_NEW_001/profile")
        assert (
            response.status_code == 404
            and response.json()["error"]["code"] == "STUDENT_NOT_FOUND"
        )


def test_current_canonical_projection_preserves_all_assessed_values_and_does_not_write_either_database():
    paths = (DEFAULT_STUDENTS, DEFAULT_BANK)
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    data = M3DataAdapter()
    with sqlite3.connect(
        DEFAULT_STUDENTS.resolve().as_uri() + "?mode=ro", uri=True
    ) as c:
        source = {
            (sid, skill): (score, count)
            for sid, skill, score, count in c.execute(
                "SELECT student_id,skill_id,mastery_score,evidence_count FROM student_skill_mastery"
            )
        }
    profiles = data.profiles
    assessed, unknown = 0, 0
    for sid, student in profiles.items():
        assert [s.skill_id for s in student.skill_mastery] == CATALOGUE
        for row in student.skill_mastery:
            score, evidence = source.get((sid, row.skill_id), (None, 0))
            assert row.evidence_count == evidence
            if evidence > 0:
                assert row.mastery_score == score
                assessed += 1
            else:
                assert row.mastery_score is None
                unknown += 1
    expected_assessed = sum(count > 0 for _, count in source.values())
    assert (assessed, unknown) == (
        expected_assessed,
        len(profiles) * len(CATALOGUE) - expected_assessed,
    )
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


@pytest.mark.parametrize("evidence", [1, 3])
def test_schema_and_planner_reject_positive_evidence_missing_mastery_even_if_model_validation_was_bypassed(
    evidence,
):
    with pytest.raises(ValidationError, match="Positive evidence"):
        SkillMastery(skill_id="A001", mastery_score=None, evidence_count=evidence)
    with pytest.raises(ValidationError, match="Positive evidence"):
        SkillMastery(skill_id="A001", evidence_count=evidence)
    row = SkillMastery(skill_id="A001", mastery_score=None, evidence_count=0)
    row.evidence_count = evidence
    invalid = StudentProfileResponse.model_construct(
        student_id="MIRA_TEST",
        name="Invalid test",
        grade_level=10,
        skill_mastery=[row],
        learning_history=[],
    )
    with pytest.raises(ApiFailure) as error:
        RuleBasedPlanner(M3DataAdapter()).classify(invalid, CATALOGUE)
    assert error.value.code == "INVALID_PROFILE_DATA"


def test_nullable_mastery_is_declared_in_api_openapi_schema(tmp_path):
    app = application(tmp_path, isolated_students(tmp_path))
    mastery = app.openapi()["components"]["schemas"]["SkillMastery"]["properties"][
        "mastery_score"
    ]
    assert {s.get("type") for s in mastery["anyOf"]} == {"number", "null"}


def test_default_api_uses_data_lead_sql_instead_of_the_offline_seeded_copy(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("M3_STUDENT_DB", raising=False)
    expected = (
        ROOT.parents[1] / "pre-work/data/sample/memory/student_profiles_sample.db"
    )
    assert DEFAULT_STUDENTS == expected
    offline = ROOT / "data/sample/memory/student_profiles_sample.db"
    # Independent SQL expectations, not adapter output or mutable score snapshots.
    with closing(
        sqlite3.connect(expected.resolve().as_uri() + "?mode=ro", uri=True)
    ) as c:
        c.execute("PRAGMA query_only=ON")
        students = [
            row[0]
            for row in c.execute("SELECT student_id FROM Students ORDER BY student_id")
        ]
        source = {
            (sid, skill): (score, evidence)
            for sid, skill, score, evidence in c.execute(
                "SELECT student_id,skill_id,mastery_score,evidence_count FROM student_skill_mastery"
            )
        }
    assert students
    app = create_app(
        backend="qwen",
        profile_source="m3",
        teacher_token="missing-mastery-test",
        exam_db=tmp_path / "drafts.db",
    )
    assert app.state.student_path.resolve() == expected.resolve()
    assert app.state.student_path.resolve() != offline.resolve()
    with TestClient(app, headers=HEADERS) as client:
        for sid in students:
            response = client.get(f"/api/v1/students/{sid}/profile")
            assert response.status_code == 200, response.text
            expected_skills = []
            for skill in CATALOGUE:
                score, evidence = source.get((sid, skill), (None, 0))
                expected_skills.append(
                    {
                        "skill_id": skill,
                        "mastery_score": score if evidence > 0 else None,
                        "evidence_count": evidence,
                    }
                )
            assert response.json()["skill_mastery"] == expected_skills, sid
            # No fixed student ID is guaranteed to remain unassessed after a pull.
            if all(row["evidence_count"] == 0 for row in expected_skills):
                planned = client.post(
                    "/api/v1/exams/plan", json=request(10, student_id=sid).model_dump()
                )
                assert planned.status_code == 200, planned.text
                assert planned.json()["skill_classifications"] == dict.fromkeys(
                    CATALOGUE, "NO_DATA"
                )
                assert (
                    planned.json()["strategy"] == "diagnostic_review"
                    and not planned.json()["personalized"]
                )
        assert isinstance(app.state.data, M3DataAdapter)
        assert not app.state.data.profile_json
        assert app.state.data.student_path.resolve() == expected.resolve()


def test_explicit_relative_student_sql_override_is_resolved_from_app_root(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "M3_STUDENT_DB", "../../pre-work/data/sample/memory/student_profiles_sample.db"
    )
    monkeypatch.chdir(tmp_path)
    app = create_app(
        backend="qwen",
        profile_source="m3",
        teacher_token="missing-mastery-test",
        exam_db=tmp_path / "drafts.db",
    )
    assert app.state.student_path.resolve() == DEFAULT_STUDENTS.resolve()
    with TestClient(app, headers=HEADERS) as client:
        row = client.get("/api/v1/students/ST001/profile").json()["skill_mastery"][0]
        assert (row["mastery_score"], row["evidence_count"]) == (2.3, 1)
