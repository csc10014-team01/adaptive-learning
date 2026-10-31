"""Meaningful module-boundary tests, independent of a running model."""

import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.adaptation.planner import RuleBasedPlanner
from src.adaptation.skill_relationships import SkillRelationships
from src.ai.contracts import ExpressionSpec, GenerationCandidate
from src.ai.expression_planner import ExpressionPlanner
from src.api.data_adapter import ApiFailure
from src.orchestration.question_generation import QuestionGenerationService
from src.validation.question_validator import QuestionValidator
from tests.unit.test_planner import make_data, profile, question, request

RELATIONS = (
    Path(__file__).resolve().parents[1] / "fixtures/nine_skill_relationships.json"
)
SOURCE = "Có 3 bút đỏ và 5 bút xanh phân biệt. Có bao nhiêu cách chọn một bút?"


def test_allocation_precedes_question_access():
    data = make_data(bank=[])
    allocation = RuleBasedPlanner(data).build_allocation_plan(request(), profile())
    assert sum(allocation.skill_counts.values()) == 10
    assert "source_id" not in allocation.model_dump_json()
    with pytest.raises(ApiFailure) as failure:
        RuleBasedPlanner(data).plan(request(), profile())
    assert failure.value.code == "INSUFFICIENT_QUESTION_BANK"


def test_expression_preserves_source_without_guessing_context():
    source = question(content=SOURCE)
    expression = ExpressionPlanner().plan_expression(source)
    assert expression.source_text == SOURCE
    assert expression.context_policy == "preserve_source"
    assert "answer" not in expression.model_dump()
    with pytest.raises(ValidationError):
        ExpressionSpec(source_id="Q", source_text=SOURCE, generate_type="indirect")


@pytest.mark.parametrize(
    "raw",
    [
        "broken",
        "[]",
        '{"question":1}',
        '{"question":"short"}',
        json.dumps({"question": SOURCE, "answer": "8"}),
        json.dumps({"question": SOURCE + " Thêm 99 bút."}),
    ],
)
def test_definite_failure_is_not_teacher_review(raw):
    result = QuestionValidator().validate(
        ExpressionSpec(source_id="Q", source_text=SOURCE),
        GenerationCandidate(raw_response=raw, model="test"),
    )
    assert result.status == "fail" and result.question is None


def test_preserving_numbers_is_not_semantic_proof():
    candidate = SOURCE.replace("chọn một bút", "sắp xếp các bút")
    result = QuestionValidator().validate(
        ExpressionSpec(source_id="Q", source_text=SOURCE),
        GenerationCandidate(
            raw_response=json.dumps({"question": candidate}), model="test"
        ),
    )
    assert result.status == "needs_review"


class CandidateClient:
    model = "test"
    attempts = 3

    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []

    def generate_one(self, content, **kwargs):
        self.calls.append(kwargs)
        return GenerationCandidate(
            raw_response=self.outputs[len(self.calls) - 1], model=self.model
        )


def test_retry_budget_and_feedback_are_owned_by_one_service():
    client = CandidateClient(["broken", json.dumps({"question": SOURCE})])
    result = QuestionGenerationService(client).generate(
        ExpressionSpec(source_id="Q", source_text=SOURCE),
        deadline=time.monotonic() + 10,
    )
    assert len(client.calls) == 2 and client.calls[1]["feedback"]
    assert result.validation.status == "needs_review"


def test_exhausted_failures_never_become_needs_review():
    client = CandidateClient(["broken"] * 3)
    with pytest.raises(ApiFailure) as failure:
        QuestionGenerationService(client).generate(
            ExpressionSpec(source_id="Q", source_text=SOURCE),
            deadline=time.monotonic() + 10,
        )
    assert failure.value.code == "INVALID_QWEN_OUTPUT" and len(client.calls) == 3


def test_expired_deadline_makes_no_attempt():
    client = CandidateClient([])
    with pytest.raises(ApiFailure) as failure:
        QuestionGenerationService(client).generate(
            ExpressionSpec(source_id="Q", source_text=SOURCE), deadline=0
        )
    assert failure.value.status == 504 and not client.calls


def test_nine_skill_relationships_are_not_applied_to_legacy_catalogue():
    relations = SkillRelationships.load(RELATIONS)
    with pytest.raises(ApiFailure, match="catalogue"):
        RuleBasedPlanner(make_data(), relationships=relations).plan(
            request(), profile()
        )


def test_review_relationship_uses_max_not_sum():
    relations = SkillRelationships.load(RELATIONS)
    # All have max P3, but sums are A008=6, A002=5, A005=3.
    # The correct result follows the existing skill-ID tie-break, not sums.
    assert relations.rank_review_skills(["A001", "A003"], ["A008", "A005", "A002"]) == [
        "A002",
        "A005",
        "A008",
    ]


@pytest.mark.parametrize("n", [1, 2, 3, 5, 10])
def test_nine_skill_focus_related_cap_and_teacher_levels(n):
    relations = SkillRelationships.load(RELATIONS)
    data = make_data(skills=relations.catalogue_ids)
    student = profile([("A004", 1.8, 3), ("A009", 1.9, 3)])
    planner = RuleBasedPlanner(data, relationships=relations)
    req = request(n)
    allocation = planner.build_allocation_plan(req, student)
    result = planner.plan(req, student)
    assert result.priority_skills == ["A004", "A009"]
    assert len(result.questions) == len({q.source_id for q in result.questions}) == n
    review = n - allocation.group_counts["focus"]
    assert allocation.group_counts["related_review"] <= review // 2
    assert sum(q.group == "related_review" for q in result.questions) <= review // 2
    if n == 10:
        assert allocation.groups["related_review"] == ["A001", "A002"]
        assert result.quota_summary.achieved_groups == {
            "focus": 6,
            "related_review": 2,
            "balanced_review": 2,
        }


def test_hard_teacher_levels_survive_relationship_policy():
    relations = SkillRelationships.load(RELATIONS)
    req = request(
        difficulty_distribution={
            "recognition": 20,
            "understanding": 40,
            "application": 30,
            "advanced_application": 10,
        }
    )
    result = RuleBasedPlanner(
        make_data(skills=relations.catalogue_ids), relationships=relations
    ).plan(req, profile([("A004", 1.8, 3), ("A009", 1.9, 3)]))
    assert result.quota_summary.achieved_levels == {
        "recognition": 2,
        "understanding": 4,
        "application": 3,
        "advanced_application": 1,
    }


def test_related_cap_reserves_scarce_teacher_level():
    from src.adaptation.contracts import AllocationPlan
    from src.adaptation.question_selector import QuestionSelector

    allocation = AllocationPlan(
        strategy="focused_practice",
        focus=["A001"],
        groups={
            "focus": ["A001"],
            "related_review": ["A002"],
            "balanced_review": ["A003"],
        },
        group_counts={"focus": 0, "related_review": 1, "balanced_review": 1},
        skill_counts={"A001": 0, "A002": 1, "A003": 1},
        # This test exercises level capacity and the related cap on unassessed
        # skills, not a reliably weak skill's zero-L4 safety constraint.
        weights={s: (25, 35, 30, 10) for s in ["A001", "A002", "A003"]},
        skill_levels={},
        levels={
            "recognition": 1,
            "understanding": 0,
            "application": 0,
            "advanced_application": 1,
        },
    )
    bank = [
        question("A002", "recognition"),
        question("A002", "advanced_application"),
        question("A003", "recognition"),
    ]
    selected, _ = QuestionSelector().select(bank, allocation, True, set(), [])
    assert {(q.primary_skill_id, q.cognitive_level) for q in selected} == {
        ("A002", "advanced_application"),
        ("A003", "recognition"),
    }


def test_nine_skill_fixture_runs_complete_modular_pipeline():
    from threading import BoundedSemaphore

    from src.orchestration.exam_service import ExamService

    relations = SkillRelationships.load(RELATIONS)
    data = make_data(skills=relations.catalogue_ids)
    for source in data.questions:
        source.content = SOURCE
    student = profile([("A004", 1.8, 3), ("A009", 1.9, 3)])

    class EchoTransport:
        model = "synthetic-test-model"
        attempts = 2
        exam_timeout = 10
        capacity = BoundedSemaphore(1)

        def __init__(self):
            self.calls = 0

        def generate_one(self, content, **kwargs):
            self.calls += 1
            return GenerationCandidate(
                raw_response=json.dumps({"question": content}), model=self.model
            )

    transport = EchoTransport()
    exam = ExamService(
        data, transport, planner=RuleBasedPlanner(data, relationships=relations)
    ).generate(request(), student)
    assert exam.status == "pending_teacher_review" and len(exam.questions) == 10
    assert transport.calls == 0  # Immutable Question Bank items do not invoke Qwen.
    assert len(exam.planner_summary.skill_classifications) == 9
    assert exam.planner_summary.quota_summary.achieved_groups == {
        "focus": 6,
        "related_review": 2,
        "balanced_review": 2,
    }
    assert all(
        q.source_digest and q.validation.auto_status == "needs_review"
        for q in exam.questions
    )
