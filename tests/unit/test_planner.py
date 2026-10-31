"""Policy tests use only small synthetic catalogues; no SQL, model, or network."""

from collections import Counter
from copy import deepcopy

import pytest
from pydantic import ValidationError

from src.adaptation.planner import RuleBasedPlanner, fair_counts
from src.adaptation.policy import PlannerPolicyConfig
from src.api.data_adapter import ApiFailure, FixtureQuestion, StaticDataAdapter
from src.api.schemas import LEVELS, GenerateExamRequest, StudentProfileResponse, Topic
from src.api.services import level_counts

SKILLS = ["A001", "A002", "A003", "A004"]


def question(skill="A001", level="recognition", index=0, **changes):
    record = dict(
        question_id=f"Q_{skill}_{level}_{index:02}", grade_level=10,
        skill_ids=[skill], primary_skill_id=skill, cognitive_level=level,
        generate_type="direct", content="Synthetic question", answer={
            "correct_answer": "Answer", "explanation": "Explanation",
        }, solution_steps=["Solution"], rubric_criteria=["Criterion"],
    )
    record.update(changes)
    return FixtureQuestion.model_validate(record)


def make_data(bank=None, skills=SKILLS):
    data = StaticDataAdapter()
    data._topic = Topic(topic_id="combinatorics", topic_name="Synthetic topic", grade_level=10,
                        skills=[{"skill_id": s, "name": s} for s in skills])
    data._questions = (bank if bank is not None else
                       [question(s, lv, i) for s in skills for lv in LEVELS for i in range(10)])
    return data


def profile(rows=(), **changes):
    record = dict(student_id="S", name="Student", grade_level=10, learning_history=[],
                  skill_mastery=[{"skill_id": s, "mastery_score": m, "evidence_count": e} for s, m, e in rows])
    record.update(changes)
    return StudentProfileResponse.model_validate(record)


def request(n=10, mode="adaptive", **changes):
    record = dict(student_id="S", generation_mode=mode, selected_topic_ids=["combinatorics"],
                  total_questions=n, duration_minutes=45)
    record.update(changes)
    return GenerateExamRequest.model_validate(record)


def plan(rows=(), bank=None, n=10, mode="adaptive", **changes):
    return RuleBasedPlanner(make_data(bank)).plan(request(n, mode, **changes), profile(rows))


def test_all_no_data_is_diagnostic():
    result = plan()
    assert set(result.skill_classifications.values()) == {"NO_DATA"}
    assert result.strategy == "diagnostic_review" and result.priority_skills == []
    assert result.target_count == result.achieved_target_count == 0
    assert Counter(q.group for q in result.questions) == {"diagnostic": 10}
    assert not result.warnings


def test_missing_and_achieved_get_six_diagnostic_four_maintenance():
    result = plan([("A001", 3.2, 3), ("A002", 1, 1)])
    assert result.quota_summary.requested_groups == {"diagnostic": 6, "maintenance": 4}
    assert result.quota_summary.achieved_groups == result.quota_summary.requested_groups
    assert result.skill_classifications["A002"] == "PARTIAL"
    assert result.priority_skills == []


def test_one_weak_gets_four_focus():
    result = plan([("A001", 1, 3), ("A002", 1, 1)])
    assert result.priority_skills == ["A001"]
    assert result.target_count == result.achieved_target_count == 4
    assert result.strategy == "focused_practice" and result.personalized
    assert result.quota_summary.requested_skills == {"A001": 4, "A002": 2, "A003": 2, "A004": 2}


def test_two_lowest_weak_focus_and_third_weak_can_review():
    result = plan([("A003", 1, 3), ("A002", 1, 3), ("A001", 1.8, 5)])
    assert result.priority_skills == ["A002", "A003"]
    assert result.target_count == result.achieved_target_count == 6
    assert result.quota_summary.achieved_skills == {"A002": 3, "A003": 3, "A001": 2, "A004": 2}
    assert any(q.target_skill_id == "A001" and q.group == "review" for q in result.questions)


@pytest.mark.parametrize("evidence,mastery,status", [
    (0, 0, "NO_DATA"), (1, 1, "PARTIAL"), (2, 0, "PARTIAL"),
    (3, 0, "WEAK"), (5, 1.49, "WEAK"), (5, 1.50, "WEAK"),
    (3, 1.99, "WEAK"), (5, 1.99, "WEAK"), (3, 2.00, "ACHIEVED"),
    (5, 2.00, "ACHIEVED"), (5, 2.50, "ACHIEVED"), (3, 2.99, "ACHIEVED"),
    (3, 3, "ACHIEVED"), (3, 4, "ACHIEVED"), (10, 4, "ACHIEVED"),
])
def test_classification_boundary(evidence, mastery, status):
    result = plan([("A001", mastery, evidence)])
    assert result.skill_classifications["A001"] == status
    assert ("A001" in result.priority_skills) == (status == "WEAK")


def test_all_achieved_uses_advanced_review():
    result = plan([(s, 3.7, 3) for s in SKILLS])
    assert result.strategy == "advanced_review"
    assert result.priority_skills == []
    assert Counter(q.group for q in result.questions) == {"advanced_review": 10}
    assert result.quota_summary.achieved_levels == dict(zip(LEVELS, (1, 3, 4, 2)))
    assert result.personalized


@pytest.mark.parametrize("mode", ["standard", "default_blueprint"])
def test_standard_ignores_weaknesses_and_uses_global_default(mode):
    weak = [("A004", 0.5, 3)]
    result = plan(weak, mode=mode)
    other = plan([(s, 4, 5) for s in SKILLS], mode=mode)
    assert result.strategy == "standard" and not result.personalized
    assert result.priority_skills == []
    assert result.quota_summary.requested_levels == other.quota_summary.requested_levels
    assert all(q.cognitive_level != "advanced_application" for q in result.questions if q.target_skill_id == "A004")
    assert result.quota_summary.requested_skills == {"A001": 3, "A002": 3, "A003": 2, "A004": 2}
    assert result.quota_summary.achieved_levels == level_counts(10, (25, 35, 30, 10))
    assert plan(weak).priority_skills == ["A004"]


def test_multiskill_counts_only_primary_and_preserves_secondary():
    bank = [question(skill_ids=["A002", "A001"], primary_skill_id="A001")]
    result = plan([("A002", 0, 3)], bank=bank, n=1)
    q = result.questions[0]
    assert q.target_skill_id == "A001" and q.skill_ids == ["A002", "A001"]
    assert not q.targeted and result.quota_summary.achieved_skills["A002"] == 0
    assert result.quota_summary.achieved_skills["A001"] == 1


def test_legacy_sole_skill_migration_and_missing_multi_primary_exclusion():
    sole = question(primary_skill_id=None)
    assert sole.primary_skill_id == "A001"
    ambiguous = question(index=1, primary_skill_id=None, skill_ids=["A002", "A001"])
    result = plan(bank=[sole, ambiguous], n=1)
    assert result.questions[0].source_id == sole.question_id
    assert any(ambiguous.question_id in w and "primary_skill_id" in w for w in result.warnings)
    with pytest.raises(ApiFailure, match="primary-annotated") as exc:
        plan(bank=[ambiguous], n=1)
    assert exc.value.code == "INSUFFICIENT_QUESTION_BANK"


@pytest.mark.parametrize("changes", [
    {"primary_skill_id": "A002"}, {"cognitive_level": "L5"},
    {"skill_ids": ["A001", "A001"]}, {"skill_ids": []},
])
def test_invalid_question_fields(changes):
    with pytest.raises(ValidationError):
        question(**changes)


@pytest.mark.parametrize("change", ["duplicate_id", "unknown_skill", "invalid_level", "bad_primary"])
def test_invalid_bank_fails_clearly(change):
    bank = [question()]
    if change == "duplicate_id":
        bank.append(question())
    elif change == "unknown_skill":
        bank[0] = question("UNKNOWN")
    elif change == "invalid_level":
        bank[0].cognitive_level = "L5"
    else:
        bank[0].primary_skill_id = "A002"
    with pytest.raises(ApiFailure) as exc:
        plan(bank=bank, n=1)
    assert exc.value.status == 500 and exc.value.code == "DATA_SOURCE_ERROR"


@pytest.mark.parametrize("mastery", [None, -1, 4.1, float("nan"), float("inf"), "1"])
def test_invalid_mastery_with_sufficient_evidence_is_rejected(mastery):
    with pytest.raises(ValidationError):
        profile([("A001", mastery, 3)])


def test_missing_mastery_with_sufficient_evidence_is_rejected():
    with pytest.raises(ValidationError):
        StudentProfileResponse(student_id="S", name="Student", grade_level=10, learning_history=[],
                               skill_mastery=[{"skill_id": "A001", "evidence_count": 3}])


def test_mutated_invalid_profile_is_revalidated_at_planning_boundary():
    student = profile([("A001", 1, 3)])
    student.skill_mastery[0].mastery_score = None
    with pytest.raises(ApiFailure) as exc:
        RuleBasedPlanner(make_data()).plan(request(), student)
    assert exc.value.code == "INVALID_PROFILE_DATA"


def test_locked_teacher_levels_override_soft_skill_quotas():
    bank = [question("A004", "advanced_application", i) for i in range(10)]
    dist = dict(zip(LEVELS, (0, 0, 0, 100)))
    result = plan([("A001", 0.5, 3)], bank=bank, difficulty_distribution=dist)
    assert result.difficulty_locked
    assert result.quota_summary.achieved_levels == dist | {"advanced_application": 10}
    assert result.quota_summary.requested_skill_levels == {}
    assert result.achieved_target_count == 0 and result.warnings
    assert len({q.source_id for q in result.questions}) == 10


@pytest.mark.parametrize("n", [1, 3, 7, 10])
def test_locked_mixed_global_totals_remain_exact_for_short_exams(n):
    req = request(n, difficulty_distribution=dict(zip(LEVELS, (25, 35, 30, 10))))
    from src.api.services import question_slots

    result = RuleBasedPlanner(make_data()).plan(req, profile([("A001", 0, 3), ("A002", 1, 3)]))
    assert result.quota_summary.achieved_levels == question_slots(req)
    assert len({q.source_id for q in result.questions}) == n


def test_infeasible_locked_level_pool_is_shortage():
    bank = [question(index=i) for i in range(10)]
    with pytest.raises(ApiFailure) as exc:
        plan(bank=bank, difficulty_distribution=dict(zip(LEVELS, (0, 0, 0, 100))))
    assert exc.value.status == 409 and exc.value.code == "INSUFFICIENT_QUESTION_BANK"


def test_locked_selection_reserves_scarce_skill_levels():
    bank = [question("A001", "recognition"), question("A002", "understanding"),
            question("A002", "recognition")]
    data = make_data(bank, skills=SKILLS[:2])
    result = RuleBasedPlanner(data).plan(request(2, "standard", difficulty_distribution=dict(zip(LEVELS, (50, 50, 0, 0)))), profile())
    assert result.quota_summary.achieved_skills == {"A001": 1, "A002": 1}
    assert result.quota_summary.achieved_levels == dict(zip(LEVELS, (1, 1, 0, 0)))


@pytest.mark.parametrize("n", [1, 3, 7, 10])
@pytest.mark.parametrize("rows", [[], [("A001", 0.5, 3)], [("A002", 1, 3), ("A001", 0.5, 3)]])
def test_short_exams_have_exact_integer_totals(n, rows):
    result = plan(rows, n=n)
    quota = result.quota_summary
    assert len(result.questions) == len({q.source_id for q in result.questions}) == n
    for counts in (quota.requested_groups, quota.achieved_groups, quota.requested_skills,
                   quota.achieved_skills, quota.requested_levels, quota.achieved_levels):
        assert sum(counts.values()) == n
        assert all(type(count) is int for count in counts.values())
    if len(result.priority_skills) == 2:
        first, second = result.priority_skills
        assert quota.requested_skills[first] >= quota.requested_skills[second]


def test_missing_cell_and_group_fallback_warns_without_partial_plan():
    bank = [question("A001", "understanding", i) for i in range(10)]
    result = plan([("A001", 4, 4)], bank=bank)
    assert len(result.questions) == 10
    assert result.quota_summary.requested_groups["diagnostic"] == 6
    assert result.quota_summary.achieved_groups["diagnostic"] == 0
    assert any("Substituted" in w for w in result.warnings)


def test_overall_shortage_and_grade_scope():
    with pytest.raises(ApiFailure) as exc:
        plan(bank=[question()], n=3)
    assert exc.value.code == "INSUFFICIENT_QUESTION_BANK"
    with pytest.raises(ApiFailure) as exc:
        RuleBasedPlanner(make_data()).plan(request(), profile(grade_level=11))
    assert exc.value.code == "INSUFFICIENT_QUESTION_BANK"


def test_same_inputs_and_bank_reordering_are_deterministic_and_immutable():
    data = make_data()
    req, student = request(), profile([("A001", 1, 3)])
    before = deepcopy((req.model_dump(), student.model_dump(), [q.model_dump() for q in data.questions]))
    planner = RuleBasedPlanner(data)
    first = planner.plan(req, student)
    assert planner.plan(req, student) == first
    assert before == (req.model_dump(), student.model_dump(), [q.model_dump() for q in data.questions])
    data._questions.reverse()
    assert planner.plan(req, student) == first


def test_seen_questions_lose_ties_and_history_never_changes_classification():
    data = make_data([question(index=0), question(index=1)])
    student = profile([("A001", 4, 1)], learning_history=[{"test_id": "T", "wrong_questions": [question().question_id, "UNKNOWN"]}])
    result = RuleBasedPlanner(data).plan(request(1), student)
    assert result.questions[0].source_id == question(index=1).question_id
    assert result.skill_classifications["A001"] == "PARTIAL" and not result.priority_skills
    assert any("UNKNOWN" in w for w in result.warnings)


def test_default_distribution_remains_unlocked_after_round_trip():
    req = request()
    restored = GenerateExamRequest.model_validate_json(req.model_dump_json())
    assert restored.difficulty_distribution is None
    explicit = request(difficulty_distribution=dict(zip(LEVELS, (25, 35, 30, 10))))
    assert plan(difficulty_distribution=explicit.difficulty_distribution).difficulty_locked


@pytest.mark.parametrize("mastery,expected", [
    (1.49, (50, 40, 10, 0)), (1.5, (35, 45, 20, 0)), (1.99, (35, 45, 20, 0)),
    (2.00, (25, 40, 30, 5)), (2.49, (25, 40, 30, 5)), (2.5, (20, 35, 35, 10)),
    (3, (15, 30, 40, 15)), (3.5, (10, 25, 45, 20)), (4, (10, 25, 45, 20)),
])
def test_mastery_band_boundaries(mastery, expected):
    planner = RuleBasedPlanner(make_data())
    student = profile([("A001", mastery, 3)])
    statuses = planner.classify(student, SKILLS)
    allocation = planner._allocate(request(), student, statuses)
    assert allocation.weights["A001"] == expected


def test_policy_is_configurable_and_rounding_is_stable():
    policy = PlannerPolicyConfig(min_evidence=5, default_levels=(100, 0, 0, 0))
    result = RuleBasedPlanner(make_data(), policy).plan(request(), profile([("A001", 1, 3)]))
    assert result.skill_classifications["A001"] == "PARTIAL" and not result.priority_skills
    assert result.quota_summary.achieved_levels["recognition"] == 10
    assert level_counts(1, (25, 25, 25, 25)) == dict(zip(LEVELS, (1, 0, 0, 0)))
    assert fair_counts(3, ["A002", "A001"]) == {"A002": 2, "A001": 1}
