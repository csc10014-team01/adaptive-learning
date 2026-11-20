"""W06 checks use synthetic sources and explicitly approved test policies."""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from src.exam_generator.api.data_adapter import ApiFailure, FixtureQuestion
from src.exam_generator.api.schemas import ApproveExamRequest
from src.exam_generator.orchestration.exam_service import ExamService
from src.exam_generator.validation.exam_quality import ExamQualityEvaluator, QualityPolicy
from src.exam_generator.validation.quality_contracts import (
    EvaluationReport, HumanQualityReview, exam_fingerprint,
)
from tests.generator.unit.test_exam_assembly import assemble, inputs
from tests.generator.unit.test_planner import make_data, profile, request
from tests.generator.unit.test_structured_problems import structured_source

APPROVED = QualityPolicy(
    version="explicitly-approved-test-policy", scoring_approved=True,
    structured_redistribution_approved=True, allow_manual_needs_review=True,
)


def fixture():
    values = inputs()
    exam = assemble(values)
    return exam, make_data(bank=list(values[3].values())), values[1], values[0]


def review(exam, scores=(35, 25, 18, 18)):
    return HumanQualityReview(
        content_fingerprint=exam_fingerprint(exam),
        criteria=[
            {"criterion_id": f"C{i}", "score": float(score),
             "evidence": f"Teacher reviewed all C{i} subcriteria, source limitations and flagged findings on this exact exam."}
            for i, score in enumerate(scores, 1)
        ],
    )


def evaluate(exam, data, student, req, **kwargs):
    return ExamQualityEvaluator(APPROVED).evaluate(
        exam, data=data, profile=student, request=req, **kwargs
    )


def checks(report):
    return [c for criterion in report.criteria for c in criterion.checks]


def test_complete_human_evidence_sums_weighted_points_once():
    exam, data, student, req = fixture()
    report = evaluate(exam, data, student, req, human_review=review(exam))
    assert report.status == "PASS" and report.total_score == 96
    assert all(c.method == "HUMAN" and c.evidence for c in report.criteria)
    assert EvaluationReport.model_validate_json(report.model_dump_json()) == report


def test_deterministic_success_never_awards_unreviewed_points():
    exam, data, student, req = fixture()
    report = evaluate(exam, data, student, req)
    assert report.status == "NEEDS_REVIEW" and report.total_score is None
    assert all(c.score is None for c in report.criteria)
    assert any(c.status == "PASS" for c in checks(report))


def test_supported_mathematical_error_is_hard_fail_even_if_source_agrees():
    value = structured_source().model_dump()
    value["answer"]["correct_answer"] = "57"
    value["problem_spec"]["verified_answer"] = "57"
    data = make_data(bank=[FixtureQuestion.model_validate(value)])
    student, req = profile(), request(1)
    exam = ExamService(data, None).generate(req, student)
    report = evaluate(exam, data, student, req, human_review=review(exam))
    assert report.status == "HARD_FAIL" and report.total_score is None
    assert any(c.code == "COUNTING_ANSWER" and "expected 56" in c.evidence for c in checks(report))
    exam.quality_report = report
    with pytest.raises(ApiFailure, match="HARD_FAIL"):
        ExamQualityEvaluator(APPROVED).require_approval_ready(exam)


@pytest.mark.parametrize("change, expected", [
    (lambda e: setattr(e, "grade_level", 11), "HARD_FAIL"),
    (lambda e: setattr(e.questions[0], "skill_ids", ["UNKNOWN"]), "QUALITY_FAIL"),
    (lambda e: setattr(e.questions[0], "target_skill_id", "A004"), "QUALITY_FAIL"),
])
def test_wrong_scope_or_skill_cannot_be_overridden_by_human_score(change, expected):
    exam, data, student, req = fixture()
    change(exam)
    report = evaluate(exam, data, student, req, human_review=review(exam))
    assert report.status == expected and report.total_score is None


def test_duplicates_require_review_without_inventing_severe_threshold():
    exam, data, student, req = fixture()
    # Source fixtures differ only in numerical index, exercising whole-exam
    # number-substitution detection beyond the existing near_duplicate helper.
    report = evaluate(exam, data, student, req)
    assert any(c.code == "DUPLICATE_CONTENT" and c.status == "NEEDS_REVIEW" for c in checks(report))
    assert report.status == "NEEDS_REVIEW"
    assert not any(c.status == "HARD_FAIL" for c in checks(report))


def test_teacher_locked_difficulty_mismatch_is_quality_failure():
    exam, data, student, _ = fixture()
    req = request(4, difficulty_distribution={
        "recognition": 0, "understanding": 0,
        "application": 0, "advanced_application": 100,
    })
    report = evaluate(exam, data, student, req)
    assert report.status == "QUALITY_FAIL"
    assert any(c.code == "LOCKED_DIFFICULTY" and c.status == "QUALITY_FAIL" for c in checks(report))


def test_insufficient_profile_evidence_is_not_weakness_or_pass():
    exam, data, student, req = fixture()
    report = evaluate(exam, data, student, req)
    finding = next(c for c in checks(report) if c.code == "PROFILE_EVIDENCE")
    assert finding.status == "NEEDS_REVIEW" and "A001" in finding.evidence
    assert report.criteria[3].score is None and report.total_score is None
    assert report.profile_snapshot == student.model_dump(mode="json")


def test_structured_assessment_without_c4_uses_only_approved_redistribution():
    exam, data, student, req = fixture()
    exam.generation_mode = "default_blueprint"
    req.generation_mode = "default_blueprint"
    report = evaluate(exam, data, student, req, human_review=review(exam, (45, 35, 20)))
    assert report.status == "PASS" and report.total_score == 100
    assert report.criteria[3].status == "NOT_APPLICABLE" and report.criteria[3].score is None
    pending = ExamQualityEvaluator(QualityPolicy(
        scoring_approved=False, structured_redistribution_approved=False,
    )).evaluate(exam, data=data)
    assert pending.total_score is None and pending.warnings


@pytest.mark.parametrize("advisory", [
    lambda exam: (_ for _ in ()).throw(TimeoutError("local evaluation timed out")),
    lambda exam: {"criterion_id": "C3", "score": 20, "evidence": "untrusted score"},
    lambda exam: "malformed JSON",
])
def test_model_timeout_or_malformed_assessment_is_retryable_not_pass(advisory):
    exam, data, student, req = fixture()
    report = evaluate(exam, data, student, req, advisory=advisory)
    assert report.status == "RETRYABLE_FAIL" and report.total_score is None
    assert any(c.method == "LLM_ASSISTED" and c.status == "RETRYABLE_FAIL" for c in checks(report))


def test_model_advice_cannot_award_points_or_complete_human_judgments():
    exam, data, student, req = fixture()
    report = evaluate(exam, data, student, req, advisory=lambda e: {
        "criterion_id": "C3", "evidence": "Wording appears clear; advisory only."
    })
    assert report.status == "NEEDS_REVIEW"
    assert all(c.score is None for c in report.criteria)


def test_no_approved_scoring_interpretation_means_no_numeric_scoring():
    exam, data, _, _ = fixture()
    with pytest.raises(ValueError, match="not been approved"):
        ExamQualityEvaluator(QualityPolicy(scoring_approved=False)).evaluate(exam, data=data, human_review=review(exam))


def test_below_80_is_quality_fail_and_partial_human_scores_are_not_totalled():
    exam, data, student, req = fixture()
    low = evaluate(exam, data, student, req, human_review=review(exam, (20, 20, 15, 15)))
    assert low.status == "QUALITY_FAIL" and low.total_score == 70
    partial = review(exam)
    partial.criteria.pop()
    report = evaluate(exam, data, student, req, human_review=partial)
    assert report.status == "NEEDS_REVIEW" and report.total_score is None


def test_stale_review_and_stale_report_are_rejected():
    exam, data, student, req = fixture()
    human = review(exam)
    exam.quality_report = evaluate(exam, data, student, req)
    exam.questions[0].content_latex += " Altered statement."
    with pytest.raises(ValueError, match="different"):
        evaluate(exam, data, student, req, human_review=human)
    with pytest.raises(ApiFailure, match="current W06"):
        ExamQualityEvaluator(APPROVED).require_approval_ready(exam)


def test_profile_snapshot_is_reused_not_current_database_mastery():
    exam, data, student, req = fixture()
    exam.quality_report = evaluate(exam, data, student, req)
    updated = ExamQualityEvaluator(APPROVED).evaluate(exam, data=data)
    assert updated.profile_snapshot == student.model_dump(mode="json")
    assert updated.request_snapshot == req.model_dump(mode="json")


def test_strict_policy_blocks_inconclusive_evidence():
    exam, data, student, req = fixture()
    exam.quality_report = evaluate(exam, data, student, req)
    with pytest.raises(ApiFailure, match="NEEDS_REVIEW"):
        ExamQualityEvaluator(replace(APPROVED, allow_manual_needs_review=False)).require_approval_ready(exam)


def test_report_cannot_claim_pass_without_sufficient_scoring_evidence():
    exam, data, student, req = fixture()
    value = evaluate(exam, data, student, req).model_dump()
    value["status"] = "PASS"
    with pytest.raises(ValidationError, match="PASS requires"):
        EvaluationReport.model_validate(value)


def test_generation_snapshot_and_human_scores_cannot_silently_change_policy():
    exam, data, student, req = fixture()
    exam.quality_report = evaluate(exam, data, student, req, human_review=review(exam))
    changed_profile = profile([("A001", 0.0, 3)])
    with pytest.raises(ValueError, match="snapshot cannot be replaced"):
        evaluate(exam, data, changed_profile, req)
    new_policy = replace(APPROVED, version="new-rubric-policy")
    report = ExamQualityEvaluator(new_policy).evaluate(exam, data=data)
    assert report.human_review is None and report.total_score is None
    assert report.status == "NEEDS_REVIEW"


def test_exact_duplicate_sources_are_reviewed_without_losing_source_proof():
    from src.exam_generator.orchestration.source_snapshot import source_digest

    exam, data, student, req = fixture()
    first, second = exam.questions[:2]
    source = next(q for q in data.questions if q.question_id == second.source_ref.id)
    source.content = second.content_latex = first.content_latex
    second.source_digest = source_digest(source)
    report = evaluate(exam, data, student, req)
    assert report.status == "NEEDS_REVIEW"
    assert any(c.code == "DUPLICATE_CONTENT" and c.question_ids == [first.question_id, second.question_id] for c in checks(report))


def test_gate_revalidates_evidence_instead_of_trusting_a_mutated_status():
    exam, data, student, req = fixture()
    exam.quality_report = evaluate(exam, data, student, req)
    exam.quality_report.status = "PASS"
    with pytest.raises(ApiFailure, match="Invalid W06"):
        ExamQualityEvaluator(APPROVED).require_approval_ready(exam)


def test_unavailable_mandatory_source_checks_cannot_be_overridden_by_human_points():
    class MissingSource:
        @property
        def topic(self):
            raise OSError("source temporarily unavailable")

    exam, _, student, req = fixture()
    report = evaluate(exam, MissingSource(), student, req, human_review=review(exam))
    assert report.status == "RETRYABLE_FAIL" and report.total_score is None
    assert report.criteria[0].score is None and report.approval_blocked
    exam.quality_report = report
    with pytest.raises(ApiFailure, match="RETRYABLE_FAIL"):
        ExamQualityEvaluator(APPROVED).require_approval_ready(exam)
    value = report.model_dump()
    value.update(status="NEEDS_REVIEW", approval_blocked=False)
    with pytest.raises(ValidationError, match="mandatory rule checks"):
        EvaluationReport.model_validate(value)


@pytest.mark.parametrize("target", ["profile", "request"])
def test_wrong_generation_context_identity_is_not_accepted_with_human_scores(target):
    exam, data, student, req = fixture()
    if target == "profile":
        student.student_id = "OTHER_STUDENT"
    else:
        req.student_id = "OTHER_STUDENT"
    report = evaluate(exam, data, student, req, human_review=review(exam))
    assert report.status == "QUALITY_FAIL" and report.total_score is None


def test_similarly_named_planner_policy_is_not_treated_as_the_current_version():
    exam, data, student, req = fixture()
    exam.planner_summary.policy_version += "-different-policy"
    report = evaluate(exam, data, student, req)
    assert any(c.code == "PLANNER_POLICY_CHANGED" for c in checks(report))
    assert not any(c.code == "PROFILE_CLASSIFICATION" for c in checks(report))
