"""Historical N=10 regression, frozen independently of Data Lead bank updates."""

import hashlib
from collections import Counter

import pytest

from data.sample.memory.seed_sample_profiles import DEFAULT_DATABASE as SEEDED_PROFILES
from src.adaptation.planner import RuleBasedPlanner
from src.adaptation.question_selector import QuestionSelector
from src.adaptation.source_selector import SourceSelector
from src.api.data_adapter import DEFAULT_BANK, ApiFailure
from src.api.m3_adapter import M3DataAdapter
from src.api.schemas import LEVELS
from src.orchestration.exam_service import ExamService
from tests.unit.test_hybrid_sources import allocation, template
from tests.unit.test_planner import make_data, question, request

EXPECTED = dict(zip(LEVELS, (3, 3, 3, 1)))
MISSING_CELLS = {
    ("A001", LEVELS[1]),
    ("A001", LEVELS[2]),
    ("A004", LEVELS[2]),
    ("A005", LEVELS[1]),
    ("A007", LEVELS[2]),
    ("A008", LEVELS[3]),
}


@pytest.fixture
def diagnostic():
    before = hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest()
    actual = M3DataAdapter(bank_path=DEFAULT_BANK, student_path=SEEDED_PROFILES)
    # Preserve the original 83-source capacity matrix as a synthetic fixture.
    # The updated main-skill mappings correctly enable more canonical sources.
    capacities = {
        "A001": (9, 0, 0, 0),
        "A002": (18, 16, 7, 2),
        "A003": (6, 5, 0, 0),
        "A004": (0, 0, 0, 0),
        "A005": (0, 0, 0, 0),
        "A006": (0, 0, 0, 0),
        "A007": (0, 0, 0, 0),
        "A008": (1, 0, 1, 0),
        "A009": (1, 14, 3, 0),
    }
    bank = [
        question(s, lv, i)
        for s, counts in capacities.items()
        for lv, count in zip(LEVELS, counts)
        for i in range(count)
    ]
    data = make_data(bank, list(capacities))
    data._templates = actual.templates
    student = actual.get_profile("ST011")
    req = request(student_id=student.student_id)
    yield data, student, req
    assert hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("seed", [0, 17, 42])
def test_exact_actual_diagnostic_preserves_difficulty_and_reports_all_six_substitutions(
    diagnostic, seed
):
    data, student, req = diagnostic
    plan = RuleBasedPlanner(data).plan(req, student, seed=seed)
    assert plan.strategy == "diagnostic_review" and not plan.personalized
    assert len(plan.skill_classifications) == 9
    assert set(plan.skill_classifications.values()) == {"NO_DATA"}
    quota, audit = plan.quota_summary, plan.selection_diagnostics
    assert quota.requested_levels == quota.achieved_levels == EXPECTED
    assert audit.exact_exam_levels_feasible
    assert not audit.exact_skill_level_matrix_feasible
    assert not audit.level_shortages
    assert {(x.skill_id, x.level) for x in audit.cell_shortages} == MISSING_CELLS
    assert all(x.shortage == 1 and x.available == 0 for x in audit.cell_shortages)
    assert len(audit.substitutions) == 6
    for sub in audit.substitutions:
        assert sub.requested_level == sub.actual_level
        assert "same difficulty preserved" in sub.reason
        assert any(sub.source_id in w and sub.reason in w for w in plan.warnings)
    assert audit.eligible_question_levels == dict(zip(LEVELS, (35, 35, 11, 2)))
    assert audit.eligible_template_instance_levels == dict(zip(LEVELS, (20, 20, 0, 0)))
    assert len({q.source_key for q in plan.questions}) == 10
    assert {
        (q.source_id, q.target_skill_id)
        for q in plan.questions
        if q.source_kind == "template"
    } == {("EA0004", "A002"), ("EA0017", "A003"), ("EA0015", "A006")}
    assert all(
        q.source_kind == "question"
        for q in plan.questions
        if q.cognitive_level in LEVELS[2:]
    )


def test_question_only_path_also_preserves_actual_diagnostic_blueprint(diagnostic):
    data, student, req = diagnostic
    planner = RuleBasedPlanner(data)
    alloc = planner.build_allocation_plan(req, student)
    _, bank, _, warnings = planner._validate(req, student)
    audit = {}
    chosen, _ = QuestionSelector().select(
        bank, alloc, False, set(), warnings, audit=audit
    )
    assert {
        lv: sum(q.cognitive_level == lv for q in chosen) for lv in LEVELS
    } == EXPECTED
    assert audit["exact_exam_levels_feasible"]
    data._templates = []
    plan = planner.plan(req, student)
    assert plan.quota_summary.achieved_levels == EXPECTED
    assert (
        plan.selection_diagnostics.eligible_template_instance_levels
        == dict.fromkeys(LEVELS, 0)
    )


@pytest.mark.parametrize("missing", [LEVELS[1], LEVELS[3]])
def test_actual_diagnostic_true_level_shortage_is_quantified_and_every_level_change_explained(
    diagnostic, missing
):
    data, student, req = diagnostic
    data._questions = [q for q in data.questions if q.cognitive_level != missing]
    data._templates = [t for t in data.templates if t.cognitive_level != missing]
    plan = RuleBasedPlanner(data).plan(req, student)
    audit = plan.selection_diagnostics
    assert not audit.exact_exam_levels_feasible
    shortage = next(x for x in audit.level_shortages if x.level == missing)
    assert shortage.requested == shortage.shortage == EXPECTED[missing]
    assert shortage.available == shortage.achieved == 0
    assert "capacity exhausted" in shortage.reason
    changes = [s for s in audit.substitutions if s.requested_level != s.actual_level]
    assert len(changes) == EXPECTED[missing]
    assert all("exact exam difficulty infeasible" in s.reason for s in changes)
    assert all(
        LEVELS.index(s.actual_level) <= LEVELS.index(s.requested_level) + 1
        for s in changes
    )
    assert any(f"Difficulty shortage {missing}" in w for w in plan.warnings)


@pytest.mark.parametrize("hybrid", [False, True])
def test_l4_to_l1_fallback_is_declared_when_no_closer_level_exists(hybrid):
    alloc = allocation({"A001": (0, 0, 0, 1)})
    warnings, audit = [], {}
    bank = [question()]
    if hybrid:
        selected, _ = SourceSelector().select(
            bank, [template()], alloc, False, set(), warnings, audit=audit
        )
    else:
        selected, _ = QuestionSelector().select(
            bank, alloc, False, set(), warnings, audit=audit
        )
    assert selected[0].cognitive_level == LEVELS[0]
    assert audit["level_shortages"] == [
        {
            "level": LEVELS[3],
            "requested": 1,
            "available": 0,
            "achieved": 0,
            "shortage": 1,
            "reason": "eligible source capacity exhausted",
        }
    ]
    assert audit["substitutions"][0]["requested_level"] == LEVELS[3]
    assert audit["substitutions"][0]["actual_level"] == LEVELS[0]
    assert "downward allowed" in audit["fallback_policy"]
    assert any("advanced_application" in w and "recognition" in w for w in warnings)


def test_shared_template_is_reserved_jointly_even_during_skill_fallback():
    fixed = template(
        skills=("A001", "A002"),
        parameter_rules={"n": {"type": "integer", "min": 2, "max": 2, "value": 2}},
    )
    alloc = allocation(
        {"A001": (1, 0, 0, 0), "A002": (1, 0, 0, 0), "A003": (0, 1, 0, 0)}
    )
    selected, _ = SourceSelector().select(
        [question(), question(level=LEVELS[1])], [fixed], alloc, False, set(), []
    )
    assert Counter(q.cognitive_level for q in selected) == {LEVELS[0]: 2, LEVELS[1]: 1}
    assert [(q.source_kind, q.primary_skill_id) for q in selected[:2]] == [
        ("question", "A001"),
        ("template", "A002"),
    ]


def test_difficulty_fallback_never_permits_two_level_upward_jump():
    with pytest.raises(ApiFailure) as failure:
        QuestionSelector().select(
            [question(level=LEVELS[2])],
            allocation({"A001": (1, 0, 0, 0)}),
            False,
            set(),
            [],
        )
    assert (
        "recognition requested=1, eligible=0, capacity_shortage=1"
        in failure.value.message
    )


def test_generated_exam_retains_diagnostic_quotas_and_audit(diagnostic):
    data, student, req = diagnostic
    exam = ExamService(data, None, fake=True, instance_seed=0).generate(req, student)
    assert exam.planner_summary.quota_summary.achieved_levels == EXPECTED
    assert len(exam.planner_summary.selection_diagnostics.substitutions) == 6
    assert Counter(q.cognitive_level for q in exam.questions) == EXPECTED
