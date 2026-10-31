"""Approved A-series policy on synthetic data; never migrates canonical M3 data."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.adaptation.planner import RuleBasedPlanner
from src.adaptation.skill_relationships import SkillRelationships
from src.api.data_adapter import ApiFailure
from tests.unit.test_planner import make_data, profile, request

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "config/skill_relationships_a001_a009.json"
FIXTURE = ROOT / "tests/fixtures/nine_skill_relationships.json"
CATALOGUE = [f"A{i:03d}" for i in range(1, 10)]
# Independent transcription of the approved table: P3, P2, P1.
EXPECTED_GROUPS = {
    "A001": (["A005", "A008"], ["A002"], ["A007", "A009"]),
    "A002": (["A005", "A008"], ["A001"], ["A003", "A004", "A006", "A007", "A009"]),
    "A003": (["A002", "A008"], ["A004", "A006"], ["A007", "A009"]),
    "A004": (["A002", "A008"], ["A003", "A006"], ["A007", "A009"]),
    "A005": (["A001", "A002"], ["A009"], ["A007"]),
    "A006": (["A002", "A008"], ["A003", "A004"], ["A007", "A009"]),
    "A007": (["A003", "A004", "A006"], ["A001", "A002", "A005"], ["A008", "A009"]),
    "A008": ([], [], ["A001", "A002", "A003", "A004", "A006"]),
    "A009": (["A001", "A002", "A005"], ["A003", "A004", "A006"], ["A007"]),
}


def load_policy():
    return SkillRelationships.load(POLICY)


def test_production_policy_is_authoritative_and_test_snapshot_cannot_drift():
    production = json.loads(POLICY.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture == production
    policy = load_policy()
    assert policy.version == "a001-a009-relationships-v1"
    assert policy.catalogue_ids == CATALOGUE
    assert set(policy.priorities) == set(CATALOGUE)
    assert all(
        source not in row
        and set(row).issubset(CATALOGUE)
        and all(type(p) is int and p in (1, 2, 3) for p in row.values())
        for source, row in policy.priorities.items()
    )


@pytest.mark.parametrize("focus", CATALOGUE)
def test_each_finalized_relationship_row_including_all_omitted_p0_edges(focus):
    policy = load_policy()
    expected = {
        target: priority
        for priority, group in zip((3, 2, 1), EXPECTED_GROUPS[focus])
        for target in group
    }
    assert policy.priorities[focus] == expected
    for target in CATALOGUE:
        assert policy.priorities[focus].get(target, 0) == expected.get(target, 0)
        assert policy.rank_review_skills([focus], [target]) == (
            [target] if target in expected else []
        )


@pytest.mark.parametrize(
    "focus,expected",
    [
        ("A004", ["A002", "A008", "A003", "A006", "A007", "A009"]),
        ("A007", ["A003", "A004", "A006", "A001", "A002", "A005", "A008", "A009"]),
        ("A009", ["A001", "A002", "A005", "A003", "A004", "A006", "A007"]),
        ("A008", ["A001", "A002", "A003", "A004", "A006"]),
    ],
)
def test_rankings_use_priority_then_id_independent_of_candidate_order(focus, expected):
    policy = load_policy()
    assert policy.rank_review_skills([focus], list(reversed(CATALOGUE))) == expected


def test_relationships_remain_directional_and_unconfigured_edges_are_p0():
    policy = load_policy()
    assert policy.priorities["A004"]["A008"] == 3
    assert policy.priorities["A008"]["A004"] == 1
    assert policy.priorities["A008"].get("A005", 0) == 0
    assert set(policy.priorities["A008"].values()) == {1}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["catalogue_ids"].append("A001"),
        lambda p: p["priorities"].pop("A009"),
        lambda p: p["priorities"].update(A010={}),
        lambda p: p["priorities"]["A004"].update(A010=3),
        lambda p: p["priorities"]["A004"].update(A004=3),
        lambda p: p["priorities"]["A004"].update(A002=0),
        lambda p: p["priorities"]["A004"].update(A002=4),
        lambda p: p["priorities"]["A004"].update(A002=-1),
        lambda p: p["priorities"]["A004"].update(A002="3"),
        lambda p: p["priorities"]["A004"].update(A002=True),
    ],
)
def test_invalid_policy_configuration_fails_at_existing_loader(tmp_path, mutation):
    value = json.loads(POLICY.read_text(encoding="utf-8"))
    mutation(value)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValidationError):
        SkillRelationships.load(path)


@pytest.mark.parametrize(
    "focus_count,expected_focus,expected_related",
    [
        (1, 4, ["A002", "A008", "A003"]),
        (2, 6, ["A001", "A002"]),
    ],
)
def test_one_or_two_focus_quotas_and_read_only_synthetic_profiles(
    focus_count, expected_focus, expected_related
):
    policy = load_policy()
    data = make_data(skills=CATALOGUE)
    # Explicitly synthetic mastery, not inferred/migrated operational profiles.
    rows = [("A004", 1.8, 3), ("A009", 1.9, 3)][:focus_count]
    student = profile(rows)
    before = student.model_dump_json()
    questions_before = [q.model_dump_json() for q in data.questions]
    planner = RuleBasedPlanner(data, relationships=policy)
    allocation = planner.build_allocation_plan(request(), student)
    first = planner.plan(request(), student)
    second = planner.plan(request(), student)
    assert first == second
    assert allocation.group_counts["focus"] == expected_focus
    assert allocation.groups["related_review"] == expected_related
    assert allocation.group_counts["related_review"] <= (10 - expected_focus) // 2
    assert first.quota_summary.achieved_groups == allocation.group_counts
    assert len({q.source_id for q in first.questions}) == 10
    sources = {q.question_id: q for q in data.questions}
    assert all(
        q.target_skill_id == sources[q.source_id].primary_skill_id
        for q in first.questions
    )
    assert student.model_dump_json() == before
    assert [q.model_dump_json() for q in data.questions] == questions_before


def test_insufficient_bank_is_not_fabricated_for_nine_skills():
    data = make_data(bank=[], skills=CATALOGUE)
    with pytest.raises(ApiFailure) as failure:
        RuleBasedPlanner(data, relationships=load_policy()).plan(request(), profile())
    assert failure.value.code == "INSUFFICIENT_QUESTION_BANK"
    assert data.questions == []


def test_seven_skill_catalogue_is_rejected_before_bank_selection_without_remapping():
    legacy = CATALOGUE[:7]
    data = make_data(bank=[], skills=legacy)
    student = profile()
    with pytest.raises(
        ApiFailure, match="Relationship policy does not match the data catalogue"
    ) as failure:
        RuleBasedPlanner(data, relationships=load_policy()).build_allocation_plan(
            request(), student
        )
    assert failure.value.code == "DATA_SOURCE_ERROR"
    assert [s.skill_id for s in data.topic.skills] == legacy
    assert student.skill_mastery == [] and data.questions == []
