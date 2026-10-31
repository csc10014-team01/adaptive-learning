"""Automatic-only teacher API and identical Demo/Qwen source planning."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.schemas import LEVELS
from tests.integration.test_skill_relationship_policy_api import EchoTransport
from tests.unit.test_planner import make_data, profile, question, request
from tests.unit.test_skill_relationship_policy import CATALOGUE, load_policy

HEADERS = {"Authorization": "Bearer automatic-difficulty-test"}
SCENARIOS = [
    [(s, 0, 0) for s in CATALOGUE],
    [(s, 0, i % 3) for i, s in enumerate(CATALOGUE)],
    [("A001", 1.0, 5)],
    [("A004", 1.2, 5), ("A009", 1.8, 5)],
    [("A001", 3.7, 5), ("A002", 0, 1)],
    [(s, 3.7, 5) for s in CATALOGUE],
    [(s, 1.8 if s == "A004" else 3.2, 5) for s in CATALOGUE],
]


def synthetic_data(rows):
    bank = [
        question(
            skill,
            level,
            i,
            content=f"Câu tự luận tổng hợp kiểm thử kỹ năng {skill}, mức {level}, bản {i}.",
        )
        for skill in CATALOGUE
        for level in LEVELS
        for i in range(3)
    ]
    data = make_data(bank=bank, skills=CATALOGUE)
    data._profiles = {"S": profile(rows)}
    return data


@pytest.mark.parametrize("rows", SCENARIOS, ids=list("ABCDEFG"))
def test_preview_demo_and_qwen_use_the_identical_achieved_plan(tmp_path, rows):
    data = synthetic_data(rows)
    student_before = data.get_profile("S").model_dump_json()
    bank_before = [q.model_dump_json() for q in data.questions]
    selections = {}
    for backend in ("fake", "qwen"):
        transport = EchoTransport()
        app = create_app(
            backend=backend,
            teacher_token="automatic-difficulty-test",
            qwen_client=transport,
            relationships=load_policy(),
            exam_db=tmp_path / "drafts.db",
        )
        app.state.data = data
        body = request().model_dump(mode="json", exclude_none=True)
        with TestClient(app, headers=HEADERS) as client:
            preview = client.post("/api/v1/exams/plan", json=body)
            assert preview.status_code == 200, preview.text
            planned = preview.json()
            assert transport.calls == 0
            response = client.post("/api/v1/exams/generate", json=body)
            assert response.status_code == 200, response.text
            exam = response.json()
            actual = [
                (q["source_ref"]["id"], q["target_skill_id"], q["cognitive_level"])
                for q in exam["questions"]
            ]
            expected = [
                (q["source_id"], q["target_skill_id"], q["cognitive_level"])
                for q in planned["questions"]
            ]
            assert actual == expected
            assert exam["planner_summary"]["quota_summary"] == planned["quota_summary"]
            assert not exam["planner_summary"]["difficulty_locked"]
            if rows == SCENARIOS[-1]:
                quota = planned["quota_summary"]
                assert (
                    quota["requested_groups"]
                    == quota["achieved_groups"]
                    == {"focus": 4, "related_review": 3, "balanced_review": 3}
                )
                assert (
                    quota["requested_levels"]
                    == quota["achieved_levels"]
                    == dict(zip(LEVELS, (2, 4, 3, 1)))
                )
                assert quota["requested_skill_levels"]["A004"] == dict(
                    zip(LEVELS, (1, 2, 1, 0))
                )
            assert (
                exam["generation_mode"] == "adaptive"
                and exam["status"] == "pending_teacher_review"
            )
            assert (
                transport.calls == 0
            )  # These fixtures contain immutable Questions only.
            if backend == "fake":
                assert exam["provenance"] == {"generator": "fake", "model": None}
                assert "Demo/Fixture" in exam["title"]
                assert all(
                    q["validation"]["auto_status"] == "not_evaluated"
                    for q in exam["questions"]
                )
            assert client.get(f"/api/v1/exams/{exam['exam_id']}").json() == exam
            selections[backend] = actual
    assert selections["fake"] == selections["qwen"]
    assert data.get_profile("S").model_dump_json() == student_before
    assert [q.model_dump_json() for q in data.questions] == bank_before


@pytest.mark.parametrize("backend", ["fake", "qwen"])
@pytest.mark.parametrize("endpoint", ["plan", "generate"])
@pytest.mark.parametrize(
    "override,field",
    [
        ({"generation_mode": "standard"}, "generation_mode"),
        ({"generation_mode": "default_blueprint"}, "generation_mode"),
        (
            {"difficulty_distribution": dict(zip(LEVELS, (25, 35, 30, 10)))},
            "difficulty_distribution",
        ),
        (
            {"difficulty_distribution": dict(zip(LEVELS, (100, 0, 0, 0)))},
            "difficulty_distribution",
        ),
    ],
)
def test_manual_overrides_are_rejected_explicitly_before_generation(
    tmp_path, backend, endpoint, override, field
):
    transport = EchoTransport()
    app = create_app(
        backend=backend,
        teacher_token="automatic-difficulty-test",
        qwen_client=transport,
        relationships=load_policy(),
        exam_db=tmp_path / "not-created.db",
    )
    app.state.data = synthetic_data([("A001", 0, 5)])
    body = request().model_dump(mode="json") | override
    with TestClient(app, headers=HEADERS) as client:
        response = client.post(f"/api/v1/exams/{endpoint}", json=body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"
        assert any(
            d["field"] == "body." + field for d in response.json()["error"]["details"]
        )
    assert transport.calls == 0
    assert not (tmp_path / "not-created.db").exists()
    if backend == "fake":
        assert not app.state.exams._exams


@pytest.mark.parametrize("difficulty_field", [{}, {"difficulty_distribution": None}])
def test_omitted_mode_defaults_to_adaptive_and_null_or_omitted_difficulty_is_accepted(
    difficulty_field,
):
    app = create_app(
        backend="fake",
        teacher_token="automatic-difficulty-test",
        relationships=load_policy(),
    )
    app.state.data = synthetic_data([("A001", 0, 5)])
    body = {
        "student_id": "S",
        "selected_topic_ids": ["combinatorics"],
        "total_questions": 4,
        "duration_minutes": 45,
    } | difficulty_field
    with TestClient(app, headers=HEADERS) as client:
        preview = client.post("/api/v1/exams/plan", json=body)
        generated = client.post("/api/v1/exams/generate", json=body)
    assert preview.status_code == generated.status_code == 200
    assert preview.json()["priority_skills"] == ["A001"]
    assert generated.json()["generation_mode"] == "adaptive"


def test_previously_stored_standard_draft_keeps_retrieval_review_and_regeneration(
    tmp_path,
):
    from src.orchestration.exam_service import ExamService

    data, transport = synthetic_data([("A001", 1.0, 5)]), EchoTransport()
    service = ExamService(data, transport)
    # Represents an older stored draft; public creation no longer accepts this mode.
    old = service.generate(request(2, mode="standard"), data.get_profile("S"))
    app = create_app(
        backend="qwen",
        teacher_token="automatic-difficulty-test",
        qwen_client=transport,
        exam_db=tmp_path / "older.db",
    )
    app.state.data = data
    app.state.exams.save(old)
    base = "/api/v1/exams/" + old.exam_id
    with TestClient(app, headers=HEADERS) as client:
        assert client.get(base).json()["generation_mode"] == "standard"
        accepted = client.post(
            base + "/approve",
            json={
                "expected_revision": 1,
                "accepted_question_ids": [q.question_id for q in old.questions],
            },
        )
        assert accepted.status_code == 200 and accepted.json()["status"] == "approved"
        regenerated = client.post(
            base + f"/questions/{old.questions[0].question_id}/regenerate",
            json={"expected_revision": 2},
        )
        assert regenerated.status_code == 409, regenerated.text
        assert regenerated.json()["error"]["code"] == "QUESTION_REGENERATION_FORBIDDEN"
        stored = client.get(base).json()
        assert stored["generation_mode"] == "standard" and stored["revision"] == 2
        assert stored["status"] == "approved"


@pytest.mark.parametrize(
    "mastery,status,focus_count,skill_levels",
    [
        (1.49, "WEAK", 4, (2, 2, 0, 0)),
        (1.50, "WEAK", 4, (1, 2, 1, 0)),
        (1.99, "WEAK", 4, (1, 2, 1, 0)),
        (2.00, "ACHIEVED", 0, (1, 2, 1, 0)),
        (4.00, "ACHIEVED", 0, (0, 1, 2, 1)),
    ],
)
def test_final_mastery_boundary_and_per_skill_levels_propagate_to_both_generation_modes(
    tmp_path, mastery, status, focus_count, skill_levels
):
    from src.api.services import level_counts

    data = synthetic_data([("A004", mastery, 5)])
    original = data.get_profile("S").model_dump_json()
    selection = []
    for backend in ("fake", "qwen"):
        transport = EchoTransport()
        app = create_app(
            backend=backend,
            teacher_token="automatic-difficulty-test",
            qwen_client=transport,
            relationships=load_policy(),
            exam_db=tmp_path / "boundary.db",
        )
        app.state.data = data
        with TestClient(app, headers=HEADERS) as client:
            body = request().model_dump(mode="json", exclude_none=True)
            response = client.post("/api/v1/exams/plan", json=body)
            assert response.status_code == 200, response.text
            plan = response.json()
            assert plan["skill_classifications"]["A004"] == status
            assert plan["target_count"] == focus_count
            assert plan["quota_summary"]["requested_skill_levels"]["A004"] == dict(
                zip(LEVELS, skill_levels)
            )
            assert plan["quota_summary"]["requested_levels"] != level_counts(
                10, (25, 35, 30, 10)
            )
            assert plan["policy_version"].startswith(
                "mvp-personalization-v4-coordinated-difficulty+"
            )
            generated = client.post("/api/v1/exams/generate", json=body)
            assert generated.status_code == 200, generated.text
            exam = generated.json()
            selected = [
                (q["source_ref"]["id"], q["cognitive_level"]) for q in exam["questions"]
            ]
            assert selected == [
                (q["source_id"], q["cognitive_level"]) for q in plan["questions"]
            ]
            assert exam["planner_summary"]["skill_classifications"]["A004"] == status
            if status == "WEAK":
                assert all(
                    q["cognitive_level"] != "advanced_application"
                    for q in exam["questions"]
                    if q["target_skill_id"] == "A004"
                )
            assert exam["planner_summary"]["quota_summary"] == plan["quota_summary"]
            assert (
                client.get("/api/v1/students/S/profile").json()["skill_mastery"][0][
                    "mastery_score"
                ]
                == mastery
            )
            selection.append(selected)
    assert selection[0] == selection[1]
    assert data.get_profile("S").model_dump_json() == original


def test_verified_simple_achieved_questions_use_both_presentations_and_keep_levels_on_regeneration(
    tmp_path,
):
    import json

    from src.ai.contracts import ExpressionSpec, GenerationCandidate
    from src.api.data_adapter import FixtureQuestion
    from tests.unit.test_structured_problems import structured_source

    class VerifiedEcho(EchoTransport):
        def generate_one(self, content, **kwargs):
            self.calls += 1
            text = (
                content.source_text if isinstance(content, ExpressionSpec) else content
            )
            return GenerationCandidate(
                model=self.model, raw_response=json.dumps({"question": text})
            )

    bank = []
    for index, level in enumerate(LEVELS[:2]):
        value = structured_source().model_dump()
        value["question_id"] = value["problem_spec"]["source_id"] = (
            f"VERIFIED_SIMPLE_{index}"
        )
        value["cognitive_level"] = level
        bank.append(FixtureQuestion.model_validate(value))
    data = make_data(bank=bank, skills=CATALOGUE)
    data._profiles = {"S": profile([(s, 3.2, 5) for s in CATALOGUE])}
    transport = VerifiedEcho()
    app = create_app(
        backend="qwen",
        teacher_token="automatic-difficulty-test",
        qwen_client=transport,
        relationships=load_policy(),
        exam_db=tmp_path / "expressions.db",
    )
    app.state.data = data
    with TestClient(app, headers=HEADERS) as client:
        body = request(2).model_dump(mode="json")
        planned = client.post("/api/v1/exams/plan", json=body).json()
        response = client.post("/api/v1/exams/generate", json=body)
        assert response.status_code == 200, response.text
        exam = response.json()
        assert {q["generate_type"] for q in exam["questions"]} == {"direct"}
        assert transport.calls == 0
        assert [
            (q["source_ref"]["id"], q["cognitive_level"]) for q in exam["questions"]
        ] == [(q["source_id"], q["cognitive_level"]) for q in planned["questions"]]
        indirect = exam["questions"][
            0
        ]  # Even verified presentation variants cannot rewrite a Question Bank item.
        assert indirect["cognitive_level"] in LEVELS[:2]
        base = "/api/v1/exams/" + exam["exam_id"]
        regenerated = client.post(
            base + f"/questions/{indirect['question_id']}/regenerate",
            json={"expected_revision": 1},
        )
        assert regenerated.status_code == 409, regenerated.text
        assert regenerated.json()["error"]["code"] == "QUESTION_REGENERATION_FORBIDDEN"
        assert client.get(base).json() == exam
        assert (
            client.post(
                base + "/approve",
                json={
                    "expected_revision": 1,
                    "accepted_question_ids": [
                        q["question_id"] for q in exam["questions"]
                    ],
                },
            ).status_code
            == 200
        )
