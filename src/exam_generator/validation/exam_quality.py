"""Conservative W06 evidence collection; deterministic checks do not earn rubric points.

Unspecified severity thresholds and semantic judgments always require review.
No model is called by default. Optional model assessments are advisory only.
"""

import re
from collections import Counter
from dataclasses import dataclass

from src.exam_generator.validation.quality_contracts import (
    CriterionEvaluation,
    EvaluationReport,
    HumanQualityReview,
    QualityCheck,
    QualityModel,
    exam_fingerprint,
)


@dataclass(frozen=True)
class QualityPolicy:
    # Explicitly approved by the project owner during W06 integration.
    version: str = "w06-approved-integration-v1"
    scoring_approved: bool = True
    structured_redistribution_approved: bool = True
    allow_manual_needs_review: bool = True


DEFAULT_POLICY = QualityPolicy()


class AdvisoryAssessment(QualityModel):
    criterion_id: str
    evidence: str


class ExamQualityEvaluator:
    def __init__(self, policy: QualityPolicy = DEFAULT_POLICY):
        self.policy = policy

    def evaluate(
        self, exam, *, data=None, profile=None, request=None,
        human_review=None, advisory=None,
    ) -> EvaluationReport:
        """Evaluate a complete DTO. Only trusted callers supply source data/reviews."""
        from src.exam_generator.api.schemas import GenerateExamRequest, StudentProfileResponse

        previous = exam.quality_report
        fingerprint = exam_fingerprint(exam)
        if previous is not None and previous.content_fingerprint == fingerprint:
            if profile is not None and previous.profile_snapshot is not None and profile.model_dump(mode="json") != previous.profile_snapshot:
                raise ValueError("Generation-time profile snapshot cannot be replaced on the same exam")
            if request is not None and previous.request_snapshot is not None and request.model_dump(mode="json") != previous.request_snapshot:
                raise ValueError("Generation-time request snapshot cannot be replaced on the same exam")
            if profile is None and previous.profile_snapshot is not None:
                profile = StudentProfileResponse.model_validate(previous.profile_snapshot)
            if request is None and previous.request_snapshot is not None:
                request = GenerateExamRequest.model_validate(previous.request_snapshot)
            if previous.policy_version == self.policy.version:
                human_review = human_review or previous.human_review
        if human_review is not None:
            human_review = HumanQualityReview.model_validate(human_review)
            if human_review.content_fingerprint != fingerprint:
                raise ValueError("Human W06 review refers to different examination content")

        standard = exam.generation_mode in ("default_blueprint", "standard")
        maxima = (
            (45, 35, 20, 0) if self.policy.structured_redistribution_approved else (35, 25, 20, 0)
        ) if standard else (35, 25, 20, 20)
        criteria = {
            f"C{i}": CriterionEvaluation(
                criterion_id=f"C{i}", status="NEEDS_REVIEW", max_score=float(maximum)
            )
            for i, maximum in enumerate(maxima, 1)
        }

        def record(criterion, code, status, evidence, *ids, method="RULE"):
            criteria[criterion].checks.append(QualityCheck(
                code=code, status=status, evidence=evidence, question_ids=list(ids), method=method
            ))

        if profile is not None and (
            profile.student_id != exam.student_id or profile.grade_level != exam.grade_level
        ):
            record("C4" if not standard else "C2", "PROFILE_IDENTITY", "QUALITY_FAIL", "Generation-time profile belongs to a different student or grade.")
        if request is not None and (
            request.student_id != exam.student_id
            or request.generation_mode != exam.generation_mode
            or request.total_questions != exam.total_questions
            or request.duration_minutes != exam.duration_minutes
            or exam.topic_id not in request.selected_topic_ids
        ):
            record("C2", "REQUEST_IDENTITY", "QUALITY_FAIL", "Generation-time request does not describe this exam's identity, scope, mode or size.")

        # Existing Pydantic validators own count/order/scoring checks.
        try:
            type(exam).model_validate(exam.model_dump(exclude={"quality_report"}))
            record("C1", "SOLUTION_STRUCTURE", "PASS", "Existing count, solution-step and marking-score validators passed; logical completeness is not certified.")
        except ValueError as exc:
            record("C1", "EXAM_STRUCTURE", "QUALITY_FAIL", str(exc))

        known, questions, templates = None, {}, {}
        if data is not None:
            from src.exam_generator.api.data_adapter import ApiFailure

            try:
                known = {s.skill_id for s in data.topic.skills}
                questions = {q.question_id: q for q in data.questions}
                templates = {t.template_id: t for t in data.templates}
                try:
                    data.validate_exam_references(exam)
                    record("C1", "SOURCE_PROVENANCE", "PASS", "Existing source/proof/presentation validator passed.")
                except (ValueError, TypeError, KeyError, SyntaxError, ArithmeticError) as exc:
                    record("C1", "SOURCE_PROVENANCE", "QUALITY_FAIL", str(exc))
            except (ApiFailure, OSError, ValueError) as exc:
                record("C1", "SOURCE_UNAVAILABLE", "RETRYABLE_FAIL", str(exc))

        from src.exam_generator.ai.template_instantiator import TemplateInstantiator
        from src.exam_generator.validation.math_validator import (
            near_duplicate, normalize_statement, verified_count,
        )

        for q in exam.questions:
            if exam.grade_level != 10 or exam.topic_id != "combinatorics" or q.topic_tag != "combinatorics":
                record("C2", "CURRICULUM_SCOPE", "HARD_FAIL", "Question is outside the supported grade-10 combinatorics scope.", q.question_id)
            elif known is None:
                record("C2", "SKILL_CATALOGUE", "NEEDS_REVIEW", "Trusted skill catalogue was not available.", q.question_id)
            elif not set(q.skill_ids) <= known or (q.target_skill_id is not None and q.target_skill_id not in q.skill_ids):
                record("C2", "TARGET_SKILL", "QUALITY_FAIL", "Question contains unknown or inconsistent target skills.", q.question_id)
            else:
                record("C2", "CURRICULUM_METADATA", "PASS", "Grade/topic and linked skill identifiers are in the supported catalogue; content alignment still requires human review.", q.question_id)

            source = questions.get(q.source_ref.id) if q.source_ref.kind == "question" else templates.get(q.source_ref.id)
            expected_answer = None
            if source is None:
                record("C1", "MATHEMATICAL_SOURCE", "NEEDS_REVIEW", "No trusted mathematical source was available for independent checking.", q.question_id)
            elif q.source_ref.kind == "question":
                if q.answer != source.answer or [s.explanation for s in q.step_solutions] != source.solution_steps or q.content_latex != source.content:
                    record("C1", "SOURCE_CONSISTENCY", "QUALITY_FAIL", "Content, answer or solution differs from the immutable source.", q.question_id)
                else:
                    record("C1", "SOURCE_CONSISTENCY", "PASS", "Content, answer and solution match the source; this does not establish mathematical correctness.", q.question_id)
                if source.problem_spec is not None:
                    expected_answer = verified_count(source.problem_spec)
                else:
                    record("C1", "BANK_MATHEMATICS", "NEEDS_REVIEW", "Legacy bank prose has no supported mathematical specification.", q.question_id)
                target_valid = q.target_skill_id is None or q.target_skill_id == source.primary_skill_id
            else:
                target_valid = q.target_skill_id in source.skill_ids
                if q.template_instance is None:
                    record("C1", "TEMPLATE_PROOF", "QUALITY_FAIL", "Template instance proof is missing.", q.question_id)
                else:
                    try:
                        instance = TemplateInstantiator().materialize(source, q.template_instance.parameters)
                        expected_answer = int(instance.answer.correct_answer)
                        if instance.record != q.template_instance or [s.explanation for s in q.step_solutions] != instance.solution_steps:
                            record("C1", "TEMPLATE_PROOF", "QUALITY_FAIL", "Template parameters/proof or solution differ from the recomputed source.", q.question_id)
                    except (ValueError, TypeError, KeyError, SyntaxError, ArithmeticError) as exc:
                        record("C1", "TEMPLATE_PROOF", "QUALITY_FAIL", str(exc), q.question_id)
                if q.template_presentation and q.template_presentation.verification_status == "experimental":
                    record("C1", "EXPERIMENTAL_SEMANTICS", "NEEDS_REVIEW", "Backend arithmetic does not verify the meaning of experimental wording.", q.question_id)
            if source is not None:
                if q.skill_ids != source.skill_ids or not target_valid or q.cognitive_level != source.cognitive_level:
                    record("C2", "SOURCE_ALIGNMENT", "QUALITY_FAIL", "Question skills or difficulty label differ from the trusted source.", q.question_id)
            if expected_answer is not None:
                if not re.fullmatch(r"[+-]?\d+", q.answer.correct_answer.strip()):
                    record("C1", "ANSWER_REPRESENTATION", "NEEDS_REVIEW", "Answer is not an unambiguous integer supported by the verifier.", q.question_id)
                else:
                    correct = int(q.answer.correct_answer) == expected_answer
                    record("C1", "COUNTING_ANSWER", "PASS" if correct else "HARD_FAIL", f"Independent supported computation: expected {expected_answer}; recorded {q.answer.correct_answer}. Statement-to-model and solution quality remain separate checks.", q.question_id)
            if q.validation.blocking_errors:
                record("C1", "EXISTING_BLOCKING_ERRORS", "QUALITY_FAIL", "; ".join(q.validation.blocking_errors), q.question_id)

        # Existing wording heuristic plus number-independent shape; neither is an
        # approved threshold for severe duplication. Always send matches to humans.
        def skeleton(text):
            return re.sub(r"\d+(?:[.,]\d+)?", "<number>", normalize_statement(text))

        for index, q in enumerate(exam.questions):
            for other in exam.questions[:index]:
                if near_duplicate(q.content_latex, other.content_latex) or skeleton(q.content_latex) == skeleton(other.content_latex):
                    record("C3", "DUPLICATE_CONTENT", "NEEDS_REVIEW", "Duplicate or number-substituted wording detected; severe-duplication threshold is not approved.", other.question_id, q.question_id)

        actual_levels = dict(Counter(q.cognitive_level for q in exam.questions))
        if request is not None and request.difficulty_distribution is not None:
            from src.exam_generator.api.services import question_slots

            expected = question_slots(request)
            matches = all(actual_levels.get(k, 0) == v for k, v in expected.items())
            record("C2", "LOCKED_DIFFICULTY", "PASS" if matches else "QUALITY_FAIL", f"Teacher-locked levels: expected={expected}, actual={actual_levels}.")
        if exam.planner_summary is not None:
            quota = exam.planner_summary.quota_summary
            counts = {"levels": actual_levels, "skills": dict(Counter(q.target_skill_id for q in exam.questions))}
            for label, actual in counts.items():
                reported = getattr(quota, "achieved_" + label)
                matches = all(actual.get(k, 0) == reported.get(k, 0) for k in set(actual) | set(reported))
                record("C4" if not standard else "C2", "REPORTED_" + label.upper(), "PASS" if matches else "QUALITY_FAIL", f"Reported={reported}; counted={actual}.")
            if any(actual_levels.get(k, 0) != v for k, v in quota.requested_levels.items()):
                record("C2", "AUTOMATIC_DIFFICULTY_DEVIATION", "NEEDS_REVIEW", f"Requested={quota.requested_levels}; actual={actual_levels}; review existing source-shortage diagnostics.")
            if not standard:
                record("C4", "PERSONALIZATION_QUOTAS", "PASS", f"Requested skills/groups={quota.requested_skills}/{quota.requested_groups}; achieved={quota.achieved_skills}/{quota.achieved_groups}; soft deviations require pedagogical judgment.")

        if standard:
            criteria["C4"].status = "NOT_APPLICABLE"
            criteria["C4"].evidence.append("Standard/default blueprint does not request student-specific personalization.")
        elif profile is None:
            record("C4", "PROFILE_MISSING", "NEEDS_REVIEW", "Generation-time student profile snapshot is unavailable.")
        else:
            from src.exam_generator.adaptation.policy import PlannerPolicyConfig

            rows = {s.skill_id: s for s in profile.skill_mastery}
            insufficient = sorted(s for s in (known or rows) if s not in rows or rows[s].evidence_count < PlannerPolicyConfig().min_evidence)
            record("C4", "PROFILE_EVIDENCE", "NEEDS_REVIEW" if insufficient else "PASS", f"Skills without sufficient evidence: {insufficient}. Missing evidence is not evidence of weakness.")
            record("C4", "LEARNING_HISTORY", "NEEDS_REVIEW", f"Available history: {len(profile.learning_history)} tests, containing wrong-question IDs only; completed/mastered-question history and thinking-error labels are not certified.")
            wrong_ids = {qid for test in profile.learning_history for qid in test.wrong_questions}
            selected_ids = {q.source_ref.id for q in exam.questions if q.source_ref.kind == "question"}
            record("C4", "HISTORY_EXPOSURE", "PASS", f"Selected source IDs occurring in available wrong-question history: {sorted(selected_ids & wrong_ids)}. This is not a complete seen/mastered-question check.")
            if known is not None and exam.planner_summary is not None:
                from src.exam_generator.adaptation.planner import RuleBasedPlanner
                from src.exam_generator.api.data_adapter import ApiFailure

                try:
                    planner = RuleBasedPlanner(data)
                    stored_version = exam.planner_summary.policy_version
                    if stored_version != planner.policy.version and not stored_version.startswith(planner.policy.version + "+"):
                        record("C4", "PLANNER_POLICY_CHANGED", "NEEDS_REVIEW", "Stored planner policy differs from the available policy; historical classifications are not reinterpreted.")
                    else:
                        classifications = planner.classify(profile, sorted(known))
                        matches = classifications == exam.planner_summary.skill_classifications
                        record("C4", "PROFILE_CLASSIFICATION", "PASS" if matches else "QUALITY_FAIL", f"Classification from generation-time evidence: {classifications}.")
                except (ApiFailure, ValueError) as exc:
                    record("C4", "ALLOCATION_UNAVAILABLE", "RETRYABLE_FAIL", str(exc))

        mandatory = {
            "C1": "Human assessment required for statement validity, mathematical modelling, solution logic and detailed marking scheme.",
            "C2": "Human assessment required for semantic target-skill alignment and actual cognitive difficulty.",
            "C3": "Human assessment required for Vietnamese language, question independence and rendered mathematical formatting.",
            "C4": "Human assessment required for pedagogical alignment and limitations of the available learning history.",
        }
        for key, warning in mandatory.items():
            if criteria[key].status != "NOT_APPLICABLE":
                criteria[key].warnings.append(warning)

        if advisory is not None:
            try:
                assessment = AdvisoryAssessment.model_validate(advisory(exam.model_dump(mode="json", exclude={"quality_report"})))
                if assessment.criterion_id not in criteria or not assessment.evidence.strip():
                    raise ValueError("Invalid advisory criterion or empty evidence")
                record(assessment.criterion_id, "MODEL_ADVISORY", "NEEDS_REVIEW", assessment.evidence, method="LLM_ASSISTED")
            except (TimeoutError, OSError, ValueError, TypeError) as exc:
                record("C3", "ADVISORY_UNAVAILABLE", "RETRYABLE_FAIL", f"Model evaluation is unavailable or malformed: {exc}", method="LLM_ASSISTED")

        reviews = {r.criterion_id: r for r in human_review.criteria} if human_review else {}
        for key, result in criteria.items():
            if result.status == "NOT_APPLICABLE":
                if key in reviews:
                    raise ValueError("Cannot score a non-applicable W06 criterion")
                continue
            result.evidence.extend(c.evidence for c in result.checks if c.status == "PASS")
            result.warnings.extend(c.evidence for c in result.checks if c.status != "PASS")
            statuses = {c.status for c in result.checks}
            review = reviews.get(key)
            if review and (not self.policy.scoring_approved or (standard and not self.policy.structured_redistribution_approved)):
                raise ValueError("W06 scoring interpretation has not been approved")
            if review and review.score > result.max_score:
                raise ValueError(f"{key} exceeds its approved maximum {result.max_score}")
            if "HARD_FAIL" in statuses:
                result.status = "HARD_FAIL"
            elif "QUALITY_FAIL" in statuses:
                result.status = "QUALITY_FAIL"
            elif any(c.status == "RETRYABLE_FAIL" and c.method == "RULE" for c in result.checks):
                # A human may assess advisory uncertainty, but cannot certify a
                # source/proof check that could not run due to infrastructure.
                result.status = "RETRYABLE_FAIL"
            elif review:
                result.status, result.method, result.score = "PASS", "HUMAN", review.score
                result.warnings.remove(mandatory[key])
                result.evidence.append("Teacher assessment of all mandatory judgments and listed findings: " + review.evidence)
            elif "RETRYABLE_FAIL" in statuses:
                result.status = "RETRYABLE_FAIL"

        applicable = [c for c in criteria.values() if c.status != "NOT_APPLICABLE"]
        complete = all(c.score is not None for c in applicable)
        total = sum(c.score for c in applicable) if complete else None
        statuses = {c.status for c in applicable}
        outcome = next((s for s in ("HARD_FAIL", "QUALITY_FAIL", "RETRYABLE_FAIL", "NEEDS_REVIEW") if s in statuses), "PASS")
        if total is not None and total < 80:
            outcome = "QUALITY_FAIL"
        warnings = []
        if not self.policy.scoring_approved or (standard and not self.policy.structured_redistribution_approved):
            warnings.append("W06 scoring/redistribution policy is pending approval; no total is awarded.")
        return EvaluationReport(
            policy_version=self.policy.version, exam_id=exam.exam_id, revision=exam.revision,
            content_fingerprint=fingerprint, status=outcome, total_score=total,
            approval_blocked=outcome != "PASS" and not (
                outcome == "NEEDS_REVIEW" and self.policy.allow_manual_needs_review
            ),
            criteria=list(criteria.values()), warnings=warnings,
            profile_snapshot=profile.model_dump(mode="json") if profile else None,
            request_snapshot=request.model_dump(mode="json") if request else None,
            human_review=human_review,
        )

    def require_approval_ready(self, exam) -> None:
        from src.exam_generator.api.data_adapter import ApiFailure

        report = exam.quality_report
        if report is not None:
            try:
                report = EvaluationReport.model_validate(report.model_dump())
            except ValueError as exc:
                raise ApiFailure(409, "EXAM_QUALITY_NOT_READY", "Invalid W06 evaluation evidence.") from exc
        if (
            report is None or report.exam_id != exam.exam_id
            or report.revision != exam.revision
            or report.policy_version != self.policy.version
            or report.content_fingerprint != exam_fingerprint(exam)
        ):
            raise ApiFailure(409, "EXAM_QUALITY_NOT_READY", "A current W06 evaluation report is required.")
        if report.status in ("HARD_FAIL", "QUALITY_FAIL", "RETRYABLE_FAIL") or (
            report.status == "NEEDS_REVIEW" and not self.policy.allow_manual_needs_review
        ):
            raise ApiFailure(409, "EXAM_QUALITY_" + report.status, "W06 quality gate: " + report.status)
