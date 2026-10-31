"""Profile-driven difficulty scenarios A–G on the official synthetic catalogue."""

from copy import deepcopy

import pytest

from src.adaptation.contracts import AllocationPlan
from src.adaptation.planner import RuleBasedPlanner
from src.adaptation.policy import PlannerPolicyConfig
from src.adaptation.question_selector import QuestionSelector
from src.api.data_adapter import ApiFailure
from src.api.schemas import LEVELS
from src.api.services import level_counts
from tests.unit.test_planner import make_data, profile, question, request
from tests.unit.test_skill_relationship_policy import CATALOGUE, load_policy


def setup(rows=(), bank=None):
    data = make_data(skills=CATALOGUE, bank=bank)
    student = profile(rows)
    return RuleBasedPlanner(data, relationships=load_policy()), student


@pytest.mark.parametrize("evidence", [0, 1, 2])
@pytest.mark.parametrize("n", [1, 2, 3, 5, 9, 10])
def test_no_reliable_evidence_uses_coherent_exam_wide_diagnostic_target(evidence, n):
    planner, student = setup([(s, 0, evidence) for s in CATALOGUE])
    before = student.model_dump_json()
    allocation = planner.build_allocation_plan(request(n), student)
    result = planner.plan(request(n), student)
    expected = level_counts(n, PlannerPolicyConfig().default_levels)
    assert allocation.strategy == result.strategy == "diagnostic_review"
    assert allocation.focus == result.priority_skills == []
    assert set(result.skill_classifications.values()) == ({"NO_DATA"} if evidence == 0 else {"PARTIAL"})
    assert allocation.levels == result.quota_summary.achieved_levels == expected
    assert all(sum(counts.values()) == allocation.skill_counts[s] for s, counts in allocation.skill_levels.items())
    if n == 10:
        assert list(expected.values()) == [3, 3, 3, 1]
    assert student.model_dump_json() == before


@pytest.mark.parametrize("mastery", [0, 1.0])
def test_one_reliably_weak_skill_never_reverts_the_exam_to_default(mastery):
    planner, student = setup([("A001", mastery, 5)])
    allocation = planner.build_allocation_plan(request(), student)
    plan = planner.plan(request(), student)
    assert plan.skill_classifications["A001"] == "WEAK"
    assert allocation.focus == ["A001"] and allocation.group_counts["focus"] == 4
    assert allocation.weights["A001"] == (50, 40, 10, 0)
    assert list(allocation.skill_levels["A001"].values()) == [2, 2, 0, 0]
    assert allocation.levels != level_counts(10, PlannerPolicyConfig().default_levels)
    assert plan.quota_summary.achieved_levels == allocation.levels
    assert all(q.cognitive_level != "advanced_application" for q in plan.questions if q.target_skill_id == "A001")


def test_two_focus_skills_keep_their_own_difficulty_and_relationships():
    planner, student = setup([("A004", 1.2, 5), ("A009", 1.8, 5)])
    allocation = planner.build_allocation_plan(request(), student)
    plan = planner.plan(request(), student)
    assert allocation.group_counts == {"focus": 6, "related_review": 2, "balanced_review": 2}
    assert allocation.groups["related_review"] == ["A001", "A002"]
    assert allocation.weights["A004"] == (50, 40, 10, 0)
    assert allocation.weights["A009"] == (35, 45, 20, 0)
    assert allocation.weights["A001"] == PlannerPolicyConfig().default_levels
    assert allocation.skill_levels["A004"] != allocation.skill_levels["A009"]
    assert list(allocation.levels.values()) == [4, 4, 2, 0]
    assert plan.quota_summary.achieved_levels == allocation.levels


def test_mixed_achieved_and_unknown_keeps_diagnostic_and_maintenance_difficulties():
    planner, student = setup([("A001", 3.7, 5), ("A002", 0, 2)])
    allocation = planner.build_allocation_plan(request(), student)
    plan = planner.plan(request(), student)
    assert allocation.focus == []
    assert allocation.group_counts == {"diagnostic": 6, "maintenance": 4}
    assert plan.personalized
    assert allocation.weights["A001"] == (10, 25, 45, 20)
    assert allocation.weights["A002"] == PlannerPolicyConfig().default_levels
    assert list(allocation.levels.values()) == [2, 3, 4, 1]
    assert plan.quota_summary.achieved_levels == allocation.levels


def test_all_achieved_skills_use_advanced_review_without_default_override():
    planner, student = setup([(s, 3.7, 5) for s in CATALOGUE])
    allocation = planner.build_allocation_plan(request(), student)
    plan = planner.plan(request(), student)
    assert plan.strategy == "advanced_review"
    assert all(w == (10, 25, 45, 20) for w in allocation.weights.values())
    assert allocation.levels != level_counts(10, PlannerPolicyConfig().default_levels)
    assert plan.quota_summary.achieved_levels == dict(zip(LEVELS, (1, 3, 4, 2)))


@pytest.mark.parametrize("safe_alternatives", [False, True])
@pytest.mark.parametrize("mastery", [1.0, 1.50, 1.99])
def test_very_weak_skill_l4_is_never_used_to_fill_bank_shortages(safe_alternatives, mastery):
    unsafe = [question("A001", "advanced_application", i) for i in range(10)]
    bank = unsafe + ([question("A003", "understanding", i) for i in range(10)] if safe_alternatives else [])
    planner, student = setup([("A001", mastery, 5)], bank)
    before = [q.model_dump_json() for q in planner.data.questions]
    if safe_alternatives:
        plan = planner.plan(request(), student)
        assert len(plan.questions) == 10
        assert all(q.target_skill_id == "A003" and q.cognitive_level == "understanding" for q in plan.questions)
        assert any("Substituted" in w for w in plan.warnings)
        assert any("L4 is forbidden" in w for w in plan.warnings)
    else:
        with pytest.raises(ApiFailure) as failure:
            planner.plan(request(), student)
        assert failure.value.code == "INSUFFICIENT_QUESTION_BANK"
    assert [q.model_dump_json() for q in planner.data.questions] == before


def test_nearest_fallback_prefers_easier_tie_and_rejects_large_upward_jumps():
    planner, student = setup(bank=[question("A001", "recognition"), question("A001", "application")])
    plan = planner.plan(request(1), student)  # Default one-slot target is L2.
    assert plan.questions[0].cognitive_level == "recognition"
    assert any("Substituted" in w for w in plan.warnings)
    planner, student = setup(bank=[question("A001", "advanced_application")])
    with pytest.raises(ApiFailure) as failure:
        planner.plan(request(1), student)
    assert failure.value.code == "INSUFFICIENT_QUESTION_BANK"


def test_capacity_lookahead_reserves_the_only_easy_source_for_a_later_slot():
    allocation = AllocationPlan(strategy="diagnostic_review", focus=[],
        groups={"diagnostic": ["A001", "A002"]}, group_counts={"diagnostic": 2},
        skill_counts={"A001": 1, "A002": 1}, weights={s: (25, 35, 30, 10) for s in ("A001", "A002")},
        skill_levels={"A001": dict(zip(LEVELS, (0, 1, 0, 0))), "A002": dict(zip(LEVELS, (1, 0, 0, 0)))},
        levels=dict(zip(LEVELS, (1, 1, 0, 0))))
    bank = [question("A001", "recognition"), question("A002", "application")]
    selected, _ = QuestionSelector().select(bank, allocation, False, set(), [])
    assert [q.cognitive_level for q in selected] == ["application", "recognition"]


def test_profile_and_policy_are_unchanged_by_difficulty_planning():
    planner, student = setup([("A004", 1.2, 5), ("A009", 1.8, 5)])
    before = deepcopy((student.model_dump(), planner.relationships.model_dump()))
    first = planner.plan(request(), student)
    planner.data._questions.reverse()
    assert planner.plan(request(), student) == first
    assert (student.model_dump(), planner.relationships.model_dump()) == before
