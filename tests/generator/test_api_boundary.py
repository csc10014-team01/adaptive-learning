"""The shared API validates adaptive output against trusted planning inputs."""

import pytest
from fastapi.testclient import TestClient

from src.api.adaptive_generator import AdaptiveExamGenerator
from tests.generator.api_helpers import HEADERS, application
from tests.generator.test_indirect_api import actual_data
from tests.generator.test_sql_boundary import app_for, request, student_database


@pytest.mark.parametrize(
    "mutation", ["requested_levels", "achieved_levels", "classifications", "answer"]
)
def test_provider_cannot_forge_blueprint_or_source_answer(tmp_path, mutation):
    data = actual_data()
    app, _ = application(tmp_path, data)
    service = AdaptiveExamGenerator(data, fake=True, instance_seed=42)

    class InvalidProvider:
        def generate(self, payload, profile):
            exam = service.generate(payload, profile)
            summary = exam.planner_summary
            if mutation == "requested_levels":
                summary.quota_summary.requested_levels["recognition"] += 1
            elif mutation == "achieved_levels":
                summary.quota_summary.achieved_levels["recognition"] += 1
            elif mutation == "classifications":
                summary.skill_classifications["A001"] = "ACHIEVED"
            else:
                exam.questions[0].answer.correct_answer = "UNTRUSTED"
            return exam

    app.state.generator = InvalidProvider()
    with TestClient(app, headers=HEADERS) as client:
        body = {**request(), "student_id": "ST011"}
        response = client.post("/api/v1/exams/generate", json=body)
        assert response.status_code == 500, response.text
        assert response.json()["error"]["code"] == "INVALID_EXAM_OUTPUT"
    assert not (tmp_path / "drafts.db").exists()


@pytest.mark.parametrize(
    "rows,strategy,groups",
    [
        ([("A001", 0.0, 6)], "focused_practice", {"focus": 4, "review": 6}),
        (
            [("A001", 0.5, 6), ("A002", 1.75, 4)],
            "focused_practice",
            {"focus": 6, "review": 4},
        ),
        (
            [(f"A{i:03}", 4.0, 5) for i in range(1, 10)],
            "advanced_review",
            {"advanced_review": 10},
        ),
    ],
)
def test_assessed_profiles_keep_personalized_plan_through_shared_api(
    tmp_path, rows, strategy, groups
):
    path = student_database(tmp_path, rows)
    with TestClient(
        app_for(tmp_path, path), headers={"Authorization": "Bearer sql-test"}
    ) as client:
        planned = client.post("/api/v1/exams/plan", json=request())
        assert planned.status_code == 200, planned.text
        plan = planned.json()
        assert plan["strategy"] == strategy
        assert plan["quota_summary"]["requested_groups"] == groups
        generated = client.post("/api/v1/exams/generate", json=request())
        assert generated.status_code == 200, generated.text
        assert (
            generated.json()["planner_summary"]["quota_summary"]
            == plan["quota_summary"]
        )


def test_preview_and_generation_both_reject_manual_adaptive_override(tmp_path):
    app, _ = application(tmp_path, actual_data())
    with TestClient(app, headers=HEADERS) as client:
        body = {
            **request(),
            "student_id": "ST011",
            "difficulty_distribution": {
                "recognition": 100,
                "understanding": 0,
                "application": 0,
                "advanced_application": 0,
            },
        }
        for endpoint in ("/api/v1/exams/plan", "/api/v1/exams/generate"):
            response = client.post(endpoint, json=body)
            assert response.status_code == 422, response.text
            assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"
