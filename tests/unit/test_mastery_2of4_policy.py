"""Final 0–4 policy: reliable weakness ends at 2.0, not at 3.0."""

import pytest
from pydantic import ValidationError

from src.adaptation.policy import PlannerPolicyConfig
from src.api.data_adapter import ApiFailure
from src.api.schemas import SkillMastery
from src.api.services import level_counts
from tests.unit.test_automatic_difficulty import setup
from tests.unit.test_planner import question, request
from tests.unit.test_skill_relationship_policy import CATALOGUE


def test_policy_version_and_threshold_identify_the_2of4_policy():
    policy = PlannerPolicyConfig()
    assert policy.mastery_target == 2.0 and policy.min_evidence == 3
    assert policy.version == "mvp-personalization-v4-coordinated-difficulty"
    assert policy.default_levels == (25, 35, 30, 10)


@pytest.mark.parametrize("weights", [
    (25, 35, 40), (-1, 36, 30, 35), (25, 35, 30, 9),
    (101, 0, 0, -1), (float("nan"), 35, 30, 10), (float("inf"), 35, 30, 10),
])
@pytest.mark.parametrize("field", ["default_levels", "mastery_levels"])
def test_difficulty_percentages_must_remain_four_finite_nonnegative_values_totaling_100(weights, field):
    value = weights if field == "default_levels" else ((1.5, weights), (float("inf"), (25, 35, 30, 10)))
    with pytest.raises(ValueError, match="four nonnegative percentages totaling 100"):
        PlannerPolicyConfig(**{field: value})


@pytest.mark.parametrize("mastery", [-0.01, 4.01, 10.0, float("inf"), float("nan")])
@pytest.mark.parametrize("evidence", [0, 5])
def test_scores_outside_0_to_4_are_rejected_even_without_evidence(mastery, evidence):
    with pytest.raises(ValidationError):
        SkillMastery(skill_id="A001", mastery_score=mastery, evidence_count=evidence)


@pytest.mark.parametrize("evidence", [0, 1, 2])
def test_high_scores_without_sufficient_evidence_still_use_default_diagnostic(evidence):
    planner, student = setup([(s, 4.0, evidence) for s in CATALOGUE])
    result = planner.plan(request(), student)
    assert set(result.skill_classifications.values()) == ({"NO_DATA"} if evidence == 0 else {"PARTIAL"})
    assert result.priority_skills == [] and result.strategy == "diagnostic_review"
    assert list(result.quota_summary.requested_levels.values()) == [3, 3, 3, 1]
    assert result.quota_summary.achieved_levels == result.quota_summary.requested_levels


def test_one_reliable_score_at_2_is_maintenance_not_weak_or_a_whole_exam_default():
    planner, student = setup([("A004", 2.0, 3), ("A009", 4.0, 2)])
    allocation = planner.build_allocation_plan(request(), student)
    result = planner.plan(request(), student)
    assert result.skill_classifications["A004"] == "ACHIEVED"
    assert result.skill_classifications["A009"] == "PARTIAL"
    assert allocation.focus == []
    assert allocation.group_counts == {"diagnostic": 6, "maintenance": 4}
    assert allocation.weights["A004"] == (25, 40, 30, 5)
    assert allocation.weights["A009"] == (25, 35, 30, 10)
    assert allocation.skill_levels["A004"] == level_counts(4, (25, 40, 30, 5))
    assert list(allocation.levels.values()) == [2, 4, 3, 1]
    assert result.quota_summary.achieved_levels == allocation.levels


def test_reliable_profiles_across_2_boundary_have_different_strategies_and_allocations():
    plans = []
    for mastery in (1.99, 2.00, 4.00):
        planner, student = setup([(s, mastery, 5) for s in CATALOGUE])
        plans.append(planner.plan(request(), student))
    assert plans[0].strategy == "focused_practice"
    assert plans[0].priority_skills == ["A001", "A002"]
    assert plans[0].target_count == 6
    assert plans[0].quota_summary.achieved_levels["advanced_application"] == 0
    assert plans[1].strategy == plans[2].strategy == "advanced_review"
    assert plans[1].priority_skills == plans[2].priority_skills == []
    assert plans[1].quota_summary.requested_levels != plans[2].quota_summary.requested_levels
    assert plans[2].quota_summary.achieved_levels["advanced_application"] > 0


@pytest.mark.parametrize("mastery", [1.49, 1.50, 1.99])
def test_weak_primary_is_never_l4_while_strong_skills_can_supply_l4_fallbacks(mastery):
    # Synthetic bank deliberately offers only L4 for strong review skills. It
    # also contains tempting L4 sources for the weak primary, which must be excluded.
    bank = [question("A004", level, i) for level in ("recognition", "understanding", "application", "advanced_application") for i in range(3)]
    bank += [question(s, "advanced_application", i) for s in CATALOGUE if s != "A004" for i in range(3)]
    rows = [(s, mastery if s == "A004" else 4.0, 5) for s in CATALOGUE]
    planner, student = setup(rows, bank)
    before = [q.model_dump_json() for q in bank]
    result = planner.plan(request(), student)
    assert result.priority_skills == ["A004"] and result.target_count == 4
    # Review L1/L2 slots cannot safely jump to the only available review L4s.
    # Report additional foundational focus questions instead of forcing L4.
    assert result.achieved_target_count > 4
    assert any("Soft group quotas deviated" in warning for warning in result.warnings)
    assert all(q.cognitive_level != "advanced_application" for q in result.questions if q.target_skill_id == "A004")
    advanced = [q for q in result.questions if q.cognitive_level == "advanced_application"]
    assert advanced and all(q.target_skill_id != "A004" for q in advanced)
    assert result.quota_summary.achieved_groups["related_review"] <= 3
    assert result.quota_summary.achieved_groups["related_review"] <= result.quota_summary.achieved_groups["balanced_review"]
    assert any("Substituted" in w for w in result.warnings)
    assert [q.model_dump_json() for q in bank] == before


@pytest.mark.parametrize("mastery", [1.50, 1.99])
def test_legacy_internal_locked_quota_cannot_bypass_a_weak_primary_zero_l4_policy(mastery):
    bank = [question("A004", "advanced_application", i) for i in range(10)]
    planner, student = setup([("A004", mastery, 5)], bank)
    legacy_request = request(difficulty_distribution={"recognition": 0, "understanding": 0,
        "application": 0, "advanced_application": 100})
    with pytest.raises(ApiFailure) as failure:
        planner.plan(legacy_request, student)
    assert failure.value.code == "INSUFFICIENT_QUESTION_BANK"
    assert "L4 is forbidden" in failure.value.message
