"""Quality reports follow the existing authenticated, atomic exam lifecycle."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.api.adaptive_generator import SQLDataAdapter
from src.api.main import create_app
from src.exam_generator.api.data_adapter import FixtureQuestion
from src.exam_generator.validation.exam_quality import QualityPolicy
from tests.generator.api_helpers import HEADERS, application
from tests.generator.test_indirect_api import actual_data
from tests.generator.unit.test_experimental_indirect import ExperimentalClient
from tests.generator.unit.test_planner import make_data, profile, request
from tests.generator.unit.test_structured_problems import structured_source


def human_review(exam, scores):
    return {
        "content_fingerprint": exam["quality_report"]["content_fingerprint"],
        "criteria": [
            {"criterion_id": f"C{i}", "score": score,
             "evidence": f"Teacher assessed all C{i} subcriteria and resolved the listed uncertainties for this revision."}
            for i, score in enumerate(scores, 1)
        ],
    }


def test_manual_approval_preserves_inconclusive_report_across_sql_revisions(tmp_path):
    app, _ = application(tmp_path, actual_data())
    with TestClient(app, headers=HEADERS) as client:
        generated = client.post("/api/v1/exams/generate", json=request(4, student_id="ST011").model_dump(mode="json"))
        assert generated.status_code == 200, generated.text
        exam = generated.json()
        report = exam["quality_report"]
        assert report["revision"] == 1 and report["status"] == "NEEDS_REVIEW"
        assert report["total_score"] is None and not report["approval_blocked"]
        base = f"/api/v1/exams/{exam['exam_id']}"
        response = client.post(base + "/approve", json={"expected_revision": 1})
        assert response.status_code == 200, response.text
        approved = response.json()
        assert approved["status"] == "approved" and approved["revision"] == 2
        assert approved["quality_report"]["status"] == "NEEDS_REVIEW"
        assert approved["quality_report"]["revision"] == 2
        assert approved["quality_report"]["content_fingerprint"] == report["content_fingerprint"]
        assert client.post(base + "/approve", json={"expected_revision": 1}).status_code == 409
        assert client.get(base).json() == approved
    with sqlite3.connect(tmp_path / "drafts.db") as connection:
        rows = connection.execute("SELECT revision, body FROM exam_revisions ORDER BY revision").fetchall()
    assert [r[0] for r in rows] == [1, 2]
    assert all(json.loads(body)["quality_report"]["revision"] == revision for revision, body in rows)
    restarted, _ = application(tmp_path, actual_data())
    with TestClient(restarted, headers=HEADERS) as client:
        assert client.get(base).json() == approved


def test_structured_teacher_scoring_is_additive_and_student_view_excludes_report():
    app = create_app(teacher_token="hybrid-test", backend="fake", profile_source="json")
    with TestClient(app, headers=HEADERS) as client:
        generated = client.post("/api/v1/exams/generate", json={
            "student_id": "DEMO_NEW_001", "generation_mode": "default_blueprint",
            "selected_topic_ids": ["combinatorics"], "total_questions": 4,
            "duration_minutes": 45,
            "difficulty_distribution": {"recognition": 25, "understanding": 25,
                                        "application": 25, "advanced_application": 25},
        })
        assert generated.status_code == 200, generated.text
        exam = generated.json()
        assert exam["quality_report"]["criteria"][3]["status"] == "NOT_APPLICABLE"
        response = client.post(f"/api/v1/exams/{exam['exam_id']}/approve", json={
            "expected_revision": 1, "quality_review": human_review(exam, [43, 34, 19]),
        })
        assert response.status_code == 200, response.text
        approved = response.json()
        assert approved["quality_report"]["total_score"] == 96
        assert approved["quality_report"]["status"] == "PASS"
        assert approved["quality_report"]["revision"] == 2
        assert "quality_report" not in app.state.exams.get(exam["exam_id"]).student_view().model_dump()


def test_confirmed_wrong_bank_answer_blocks_teacher_approval_without_advancing_revision(tmp_path):
    value = structured_source().model_dump()
    value["answer"]["correct_answer"] = "57"
    value["problem_spec"]["verified_answer"] = "57"
    data = SQLDataAdapter()
    data.core = make_data(bank=[FixtureQuestion.model_validate(value)])
    data.core._profiles = {"S": profile()}
    app, _ = application(tmp_path, data)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(1).model_dump(mode="json"))
        assert response.status_code == 200, response.text
        exam = response.json()
        assert exam["quality_report"]["status"] == "HARD_FAIL"
        base = f"/api/v1/exams/{exam['exam_id']}"
        denied = client.post(base + "/approve", json={
            "expected_revision": 1, "quality_review": human_review(exam, [35, 25, 20, 20]),
        })
        assert denied.status_code == 409, denied.text
        assert denied.json()["error"]["code"] == "EXAM_QUALITY_HARD_FAIL"
        assert client.get(base).json() == exam


def test_regeneration_rechecks_whole_exam_resets_human_scores_and_preserves_input_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", "1")
    model = ExperimentalClient()
    app, _ = application(tmp_path, actual_data(), model)
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(4, student_id="ST011").model_dump(mode="json"))
        assert response.status_code == 200, response.text
        exam = response.json()
        base = f"/api/v1/exams/{exam['exam_id']}"
        reviewed = client.post(base + "/approve", json={
            "expected_revision": 1, "quality_review": human_review(exam, [35, 25, 20, 20]),
        })
        assert reviewed.status_code == 200, reviewed.text
        target = next(q for q in exam["questions"] if q["source_ref"]["kind"] == "template")
        url = base + f"/questions/{target['question_id']}/regenerate"
        regenerated = client.post(url, json={"expected_revision": 2})
        assert regenerated.status_code == 200, regenerated.text
        changed = regenerated.json()
        report = changed["quality_report"]
        assert changed["status"] == "pending_teacher_review" and report["revision"] == 3
        assert report["human_review"] is None and report["total_score"] is None
        assert report["status"] == "NEEDS_REVIEW"
        assert report["profile_snapshot"] == exam["quality_report"]["profile_snapshot"]
        assert report["content_fingerprint"] != exam["quality_report"]["content_fingerprint"]
        stale = client.post(base + "/approve", json={
            "expected_revision": 3, "quality_review": human_review(exam, [35, 25, 20, 20]),
        })
        assert stale.status_code == 422 and client.get(base).json() == changed
        model.mode = "invalid_all"
        target = changed["questions"][target["order_index"] - 1]
        failed = client.post(base + f"/questions/{target['question_id']}/regenerate", json={"expected_revision": 3})
        assert failed.status_code == 502 and client.get(base).json() == changed


def test_strict_configuration_requires_scores_and_old_drafts_are_evaluated_on_approval(tmp_path):
    app, _ = application(tmp_path, actual_data(), quality_policy=QualityPolicy(allow_manual_needs_review=False))
    with TestClient(app, headers=HEADERS) as client:
        exam = client.post("/api/v1/exams/generate", json=request(4, student_id="ST011").model_dump(mode="json")).json()
        base = f"/api/v1/exams/{exam['exam_id']}"
        assert client.post(base + "/approve", json={"expected_revision": 1}).status_code == 409
        # Simulate a pre-W06 draft using a separate new exam ID, without changing
        # the current draft or bypassing store compare-and-swap semantics.
        legacy = app.state.exams.get(exam["exam_id"])
        legacy.exam_id += "_legacy"
        legacy.quality_report = None
        app.state.exams.save(legacy)
        response = client.post(f"/api/v1/exams/{legacy.exam_id}/approve", json={"expected_revision": 1})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "EXAM_QUALITY_NEEDS_REVIEW"


@pytest.mark.parametrize("scores", [[100, 25, 20, 20], [0, 0, 0, 0]])
def test_invalid_or_failing_scores_do_not_save_a_review(tmp_path, scores):
    app, _ = application(tmp_path, actual_data())
    with TestClient(app, headers=HEADERS) as client:
        exam = client.post("/api/v1/exams/generate", json=request(4, student_id="ST011").model_dump(mode="json")).json()
        base = f"/api/v1/exams/{exam['exam_id']}"
        response = client.post(base + "/approve", json={
            "expected_revision": 1, "quality_review": human_review(exam, scores),
        })
        assert response.status_code == (422 if scores[0] > 35 else 409)
        assert client.get(base).json() == exam


def test_concurrent_approvals_preserve_one_atomic_quality_revision(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from src.api.adaptive_generator import core_exam, public_exam
    from src.api.data_adapter import ApiFailure
    from src.api.exam_store import SQLiteExamStore
    from src.exam_generator.api.schemas import ApproveExamRequest
    from src.exam_generator.orchestration.review_service import approve_exam

    app, _ = application(tmp_path, actual_data())
    with TestClient(app, headers=HEADERS) as client:
        response = client.post("/api/v1/exams/generate", json=request(4, student_id="ST011").model_dump(mode="json"))
        assert response.status_code == 200, response.text
        current = app.state.exams.get(response.json()["exam_id"])
    barrier = Barrier(2)

    def submit(index):
        reviewed = public_exam(approve_exam(
            core_exam(current), ApproveExamRequest(expected_revision=1, notes=f"reviewer {index}"),
            evaluator=app.state.quality_evaluator,
        ), current)
        store = SQLiteExamStore(tmp_path / "drafts.db")
        barrier.wait(timeout=5)
        try:
            store.replace(reviewed, expected_revision=1)
            return "SAVED"
        except ApiFailure as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(submit, [1, 2]))
    assert sorted(outcomes) == ["EXAM_REVISION_CONFLICT", "SAVED"]
    stored = app.state.exams.get(current.exam_id)
    assert stored.revision == stored.quality_report.revision == 2
    with sqlite3.connect(tmp_path / "drafts.db") as connection:
        revisions = connection.execute("SELECT revision, body FROM exam_revisions ORDER BY revision").fetchall()
    assert [r[0] for r in revisions] == [1, 2]
    assert all(json.loads(body)["quality_report"]["revision"] == version for version, body in revisions)
