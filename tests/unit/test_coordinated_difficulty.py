"""Regression and exhaustive small-instance checks for coordinated allocation."""

from fractions import Fraction
from itertools import permutations, product
from random import Random

import pytest
from pydantic import ValidationError

from src.adaptation.contracts import AllocationPlan
from src.adaptation.difficulty_allocator import coordinated_levels
from src.adaptation.question_selector import QuestionSelector
from src.api.data_adapter import ApiFailure
from src.api.schemas import LEVELS
from src.api.services import level_counts
from tests.unit.test_automatic_difficulty import setup
from tests.unit.test_planner import profile, question, request
from tests.unit.test_skill_relationship_policy import CATALOGUE


def level_dict(counts):
    return dict(zip(LEVELS, counts))


def test_six_single_question_review_skills_do_not_each_round_to_l3():
    counts = {s: 1 for s in CATALOGUE[:6]}
    weights = {s: (15, 30, 40, 15) for s in counts}
    assert all(level_counts(1, w) == level_dict((0, 0, 1, 0)) for w in weights.values())
    result, totals = coordinated_levels(counts, weights, {"review": list(counts)})
    assert totals == level_dict((1, 2, 2, 1))
    assert all(sum(row.values()) == 1 for row in result.values())
    assert coordinated_levels(counts, weights, {"review": list(counts)}) == (
        result,
        totals,
    )


def test_one_weak_eight_achieved_preserves_focus_relationships_and_balances_review():
    planner, student = setup([(s, 1.8 if s == "A004" else 3.2, 5) for s in CATALOGUE])
    allocation = planner.build_allocation_plan(request(), student)
    result = planner.plan(request(), student)
    quota = result.quota_summary
    assert allocation.focus == ["A004"]
    assert (
        quota.requested_groups
        == quota.achieved_groups
        == {"focus": 4, "related_review": 3, "balanced_review": 3}
    )
    assert quota.requested_skill_levels["A004"] == level_dict((1, 2, 1, 0))
    review = {
        lv: sum(row[lv] for s, row in allocation.skill_levels.items() if s != "A004")
        for lv in LEVELS
    }
    assert review == level_dict((1, 2, 2, 1))
    assert quota.requested_levels == quota.achieved_levels == level_dict((2, 4, 3, 1))
    assert quota.requested_skills == quota.achieved_skills
    assert quota.requested_skill_levels == quota.achieved_skill_levels
    assert quota.requested_levels != level_counts(10, (25, 35, 30, 10))
    assert not any("Substituted" in w for w in result.warnings)


@pytest.mark.parametrize("n", [1, 2])
def test_advanced_review_is_personalized_without_a_mandatory_l4(n):
    planner, student = setup([(s, 4, 5) for s in CATALOGUE])
    result = planner.plan(request(n), student)
    assert result.personalized and result.strategy == "advanced_review"
    assert result.quota_summary.requested_levels["advanced_application"] == 0
    assert result.quota_summary.achieved_levels == level_counts(n, (10, 25, 45, 20))


@pytest.mark.parametrize("n", range(1, 11))
def test_mixed_profile_allocations_preserve_all_totals_and_prohibited_cells(n):
    random = Random(n)
    planner, _ = setup()
    for _ in range(12):
        student = profile(
            [
                (
                    s,
                    random.choice([0, 1.49, 1.5, 1.99, 2, 2.5, 3, 3.5, 4]),
                    random.randrange(6),
                )
                for s in CATALOGUE
                if random.randrange(5)
            ]
        )
        allocation = planner.build_allocation_plan(request(n), student)
        statuses = planner.classify(student, CATALOGUE)
        assert allocation == planner.build_allocation_plan(request(n), student)
        assert (
            sum(allocation.group_counts.values())
            == sum(allocation.skill_counts.values())
            == n
        )
        assert sum(allocation.levels.values()) == n
        for group, members in allocation.groups.items():
            assert (
                sum(allocation.skill_counts[s] for s in members)
                == allocation.group_counts[group]
            )
        for skill, row in allocation.skill_levels.items():
            assert sum(row.values()) == allocation.skill_counts[skill]
            assert all(type(count) is int and count >= 0 for count in row.values())
            if statuses[skill] == "WEAK":
                assert row["advanced_application"] == 0
            if statuses[skill] in ("NO_DATA", "PARTIAL"):
                assert allocation.weights[skill] == (25, 35, 30, 10)
        for level in LEVELS:
            assert (
                sum(row[level] for row in allocation.skill_levels.values())
                == allocation.levels[level]
            )


def distributions(total):
    return [row for row in product(range(total + 1), repeat=4) if sum(row) == total]


def test_group_then_skill_rounding_minimizes_error_against_exhaustive_oracle():
    counts = {"a": 2, "b": 1, "c": 1}
    weights = {"a": (35, 45, 20, 0), "b": (15, 30, 40, 15), "c": (25, 35, 30, 10)}
    groups = {"focus": ["a"], "review": ["b", "c"]}
    actual, totals = coordinated_levels(counts, weights, groups)
    ideals = {s: [Fraction(w * counts[s], 100) for w in weights[s]] for s in counts}

    def objective(rows):
        group_error = sum(
            (sum(rows[s][i] for s in members) - sum(ideals[s][i] for s in members)) ** 2
            for members in groups.values()
            for i in range(4)
        )
        skill_error = sum(
            (rows[s][i] - ideals[s][i]) ** 2 for s in counts for i in range(4)
        )
        return group_error, skill_error

    feasible = []
    for values in product(*(distributions(n) for n in counts.values())):
        rows = dict(zip(counts, values))
        if rows["a"][3] or any(
            sum(row[i] for row in rows.values()) != totals[lv]
            for i, lv in enumerate(LEVELS)
        ):
            continue
        feasible.append(objective(rows))
    assert objective({s: list(row.values()) for s, row in actual.items()}) == min(
        feasible
    )


def test_incompatible_custom_supports_relax_columns_without_assigning_a_zero_preference():
    # Unconstrained largest remainder chooses L1/L2, but skill b only allows L3/L4.
    counts = {"a": 1, "b": 1}
    weights = {"a": (50, 50, 0, 0), "b": (0, 0, 50, 50)}
    rows, totals = coordinated_levels(counts, weights, {"review": list(counts)})
    assert sum(totals.values()) == 2
    assert rows["a"]["application"] == rows["a"]["advanced_application"] == 0
    assert rows["b"]["recognition"] == rows["b"]["understanding"] == 0


def allocation_for_matching():
    return AllocationPlan(
        strategy="advanced_review",
        focus=[],
        groups={"advanced_review": ["A001", "A002"]},
        group_counts={"advanced_review": 3},
        skill_counts={"A001": 2, "A002": 1},
        weights={s: (15, 30, 40, 15) for s in ("A001", "A002")},
        skill_levels={
            "A001": level_dict((1, 1, 0, 0)),
            "A002": level_dict((0, 0, 1, 0)),
        },
        levels=level_dict((1, 1, 1, 0)),
    )


def test_selection_matches_exhaustive_feasible_assignments_and_reports_every_deviation():
    allocation = allocation_for_matching()
    bank = [
        question("A001", "understanding"),
        question("A001", "application"),
        question("A002", "recognition"),
        question("A002", "understanding"),
    ]
    # Selector traverses skills round-robin, with levels ascending per skill.
    slots = [
        ("A001", "recognition"),
        ("A002", "application"),
        ("A001", "understanding"),
    ]

    def objective(chosen):
        return tuple(
            sum(values)
            for values in zip(
                *[
                    (
                        int(q.cognitive_level != lv),
                        abs(LEVELS.index(q.cognitive_level) - LEVELS.index(lv)),
                        int(q.primary_skill_id != s),
                        int(LEVELS.index(q.cognitive_level) > LEVELS.index(lv)),
                    )
                    for (s, lv), q in zip(slots, chosen)
                ]
            )
        )

    feasible = [
        qs
        for qs in permutations(bank, 3)
        if all(
            LEVELS.index(q.cognitive_level) <= LEVELS.index(lv) + 1
            for (_, lv), q in zip(slots, qs)
        )
    ]
    warnings = []
    chosen, _ = QuestionSelector().select(bank, allocation, False, set(), warnings)
    assert objective(chosen) == min(map(objective, feasible))
    assert len({q.question_id for q in chosen}) == 3
    assert len(warnings) == sum(
        (q.primary_skill_id, q.cognitive_level) != slot
        for slot, q in zip(slots, chosen)
    )
    assert QuestionSelector().select(
        list(reversed(bank)), allocation, False, set(), []
    ) == (chosen, {"A001": "advanced_review", "A002": "advanced_review"})


def test_scarce_easy_sources_are_reserved_and_insufficient_safe_bank_is_explicit():
    allocation = allocation_for_matching()
    bank = [
        question("A002", "recognition"),
        question("A001", "understanding"),
        question("A001", "advanced_application"),
    ]
    chosen, _ = QuestionSelector().select(bank, allocation, False, set(), [])
    assert [q.cognitive_level for q in chosen] == [
        "recognition",
        "advanced_application",
        "understanding",
    ]
    planner, student = setup(
        [("A004", 1.8, 5)],
        [question("A004", "advanced_application", i) for i in range(10)],
    )
    with pytest.raises(ApiFailure) as failure:
        planner.plan(request(), student)
    assert failure.value.code == "INSUFFICIENT_QUESTION_BANK"


def test_enough_unique_sources_without_balanced_review_capacity_can_still_be_infeasible():
    bank = [question("A004", level, i) for level in LEVELS[:3] for i in range(3)]
    bank += [question("A002", "recognition", i) for i in range(3)]
    planner, student = setup([("A004", 1.8, 5)], bank)
    # Nine Focus sources cannot fill N=10. Any Related Review source requires
    # Balanced Review coverage, which this bank cannot supply at any level.
    with pytest.raises(ApiFailure) as failure:
        planner.plan(request(), student)
    assert failure.value.code == "INSUFFICIENT_QUESTION_BANK"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["levels"].update(recognition=0, understanding=2),
        lambda value: value["skill_levels"]["A001"].pop("advanced_application"),
        lambda value: value.update(forbidden_levels={"A001": ["recognition"]}),
    ],
)
def test_allocation_contract_rejects_inconsistent_columns_and_prohibited_cells(
    mutation,
):
    value = allocation_for_matching().model_dump()
    mutation(value)
    with pytest.raises(ValidationError):
        AllocationPlan.model_validate(value)
