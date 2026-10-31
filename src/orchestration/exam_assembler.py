"""Assemble checked candidates with trusted source answers and scoring."""

from collections import Counter
from uuid import uuid4

from src.adaptation.planner import ExamPlan
from src.ai.contracts import ValidatedQuestion
from src.ai.template_instantiator import InstantiatedTemplate, template_digest
from src.api.data_adapter import ApiFailure, FixtureQuestion
from src.api.schemas import (
    ExamQuestion,
    ExamResponse,
    GenerateExamRequest,
    PlannerSummary,
    StudentProfileResponse,
)
from src.api.services import allocate_units, question_slots
from src.orchestration.source_snapshot import source_digest
from src.validation.math_validator import near_duplicate


class ExamAssembler:
    def assemble(
        self,
        request: GenerateExamRequest,
        profile: StudentProfileResponse,
        plan: ExamPlan,
        sources: dict[str, FixtureQuestion],
        candidates: list[ValidatedQuestion],
        *,
        model: str | None,
        backend: str = "qwen",
    ) -> ExamResponse:
        if (
            len(candidates) != request.total_questions
            or len(plan.questions) != request.total_questions
        ):
            raise ApiFailure(
                500, "EXAM_INTEGRITY_FAILED", "Missing candidates for the complete exam"
            )
        if backend == "fake" or not any(
            q.source_kind == "template" for q in plan.questions
        ):
            model = None
        self._check_blueprint(request, profile, plan, sources)
        questions = []
        for index, (item, candidate, units) in enumerate(
            zip(
                plan.questions,
                candidates,
                allocate_units(40, request.total_questions),
            ),
            1,
        ):
            if (
                candidate.expression.source_id != item.source_key
                or candidate.validation.status == "fail"
                or candidate.validation.question != candidate.content
            ):
                raise ApiFailure(
                    500,
                    "EXAM_INTEGRITY_FAILED",
                    "Candidate does not match an accepted source slot",
                )
            source = sources[item.source_key]
            if item.source_kind == "question":
                if (
                    not isinstance(source, FixtureQuestion)
                    or candidate.content != source.content
                    or candidate.expression.source_text != source.content
                ):
                    raise ApiFailure(
                        500,
                        "EXAM_INTEGRITY_FAILED",
                        "Question Bank content is immutable",
                    )
                skill_ids, level, topic = (
                    source.skill_ids,
                    source.cognitive_level,
                    source.topic_id,
                )
                answer, steps, criteria = (
                    source.answer,
                    source.solution_steps,
                    source.rubric_criteria,
                )
                digest, instance = source_digest(source), None
            else:
                if (
                    not isinstance(source, InstantiatedTemplate)
                    or candidate.expression.template_context is None
                ):
                    raise ApiFailure(
                        500,
                        "EXAM_INTEGRITY_FAILED",
                        "Template instance proof is missing",
                    )
                if candidate.expression.template_context.instance != source.record:
                    raise ApiFailure(
                        500,
                        "EXAM_INTEGRITY_FAILED",
                        "Template instance does not match candidate",
                    )
                skill_ids, level, topic = (
                    source.template.skill_ids,
                    source.template.cognitive_level,
                    source.template.topic_id,
                )
                answer, steps = source.answer, source.solution_steps
                criteria = [
                    "Áp dụng đúng quy tắc và tham số; giải thích và kết luận đúng."
                ]
                digest, instance = template_digest(source.template), source.record
            duplicate_notes = [
                f"Wording resembles question {q.order_index}; teacher must check for duplicate problems."
                for q in questions
                if near_duplicate(q.content_latex, candidate.content)
            ]
            if backend == "fake" and max(len(steps), len(criteria)) > units:
                raise ApiFailure(
                    409,
                    "INSUFFICIENT_QUESTION_BANK",
                    "Scoring fixture cannot fit the requested quarter-point budget",
                )
            step_units = allocate_units(units, len(steps))
            questions.append(
                ExamQuestion(
                    question_id=("FQ_" if backend == "fake" else "QW_") + uuid4().hex,
                    order_index=index,
                    topic_tag=topic,
                    skill_ids=skill_ids,
                    cognitive_level=level,
                    target_skill_id=item.target_skill_id,
                    generate_type=candidate.expression.generate_type,
                    expression_context_id=candidate.expression.context_id,
                    content_latex=candidate.content,
                    max_score=units / 4,
                    source_ref={"kind": item.source_kind, "id": item.source_id},
                    answer=answer,
                    source_digest=digest,
                    template_instance=instance,
                    template_presentation=(
                        candidate.expression.template_context.presentation
                        if candidate.expression.template_context
                        else None
                    ),
                    step_solutions=[
                        {"step_number": i, "explanation": text, "score": score / 4}
                        for i, (text, score) in enumerate(zip(steps, step_units), 1)
                    ],
                    rubric=[
                        {"criteria": text, "sub_score": score / 4}
                        for text, score in zip(
                            criteria, allocate_units(units, len(criteria))
                        )
                    ],
                    validation={
                        "auto_status": "not_evaluated"
                        if backend == "fake"
                        else "needs_review",
                        "teacher_approved": False,
                        "review_notes": [
                            "Source answers and cognitive labels require teacher review.",
                            "Generic scoring rubric requires teacher review.",
                            *candidate.validation.reasons,
                            *duplicate_notes,
                            (
                                f"Planner {plan.policy_version}; personalized={plan.personalized}; "
                                f"priority_count={plan.achieved_target_count}/{plan.target_count}."
                            ),
                            *item.reasons,
                            *plan.warnings,
                        ],
                    },
                )
            )
        return ExamResponse(
            exam_id=("FE_" if backend == "fake" else "EX_") + uuid4().hex,
            student_id=profile.student_id,
            grade_level=profile.grade_level,
            topic_id="combinatorics",
            title=("Demo/Fixture — " if backend == "fake" else "")
            + "Đề ôn tập Đại số tổ hợp — "
            + ("Cá nhân hóa" if plan.personalized else "Khung chuẩn"),
            generation_mode=request.generation_mode,
            total_questions=request.total_questions,
            duration_minutes=request.duration_minutes,
            total_score=10.0,
            status="pending_teacher_review",
            provenance={
                "generator": "fake"
                if backend == "fake"
                else ("qwen" if model else "question_bank"),
                "model": model,
            },
            questions=questions,
            planner_summary=PlannerSummary.model_validate(
                {field: getattr(plan, field) for field in PlannerSummary.model_fields}
            ),
        )

    @staticmethod
    def _check_blueprint(request, profile, plan, sources):
        """Exam-level checks only; mathematical validation has already run."""

        def fail(message):
            raise ApiFailure(500, "EXAM_INTEGRITY_FAILED", message)

        if (
            plan.student_id != profile.student_id
            or plan.requested_mode != request.generation_mode
        ):
            fail("Blueprint identity does not match the exam request")
        if (
            len({(q.source_kind, q.source_key) for q in plan.questions})
            != request.total_questions
        ):
            fail("Blueprint contains duplicate source questions")
        for item in plan.questions:
            source = sources.get(item.source_key)
            if item.source_kind == "question":
                if (
                    source is None
                    or not isinstance(source, FixtureQuestion)
                    or source.question_id != item.source_id
                ):
                    fail("Blueprint source is missing")
                if (
                    source.grade_level != profile.grade_level
                    or source.topic_id not in request.selected_topic_ids
                    or item.target_skill_id != source.primary_skill_id
                    or item.skill_ids != source.skill_ids
                    or item.cognitive_level != source.cognitive_level
                ):
                    fail("Blueprint slot metadata differs from its trusted source")
            else:
                if source is None or not isinstance(source, InstantiatedTemplate):
                    fail("Blueprint template instance is missing")
                definition = source.template
                if (
                    definition.template_id != item.source_id
                    or source.record != item.template_instance
                    or item.target_skill_id not in definition.skill_ids
                    or item.skill_ids != definition.skill_ids
                    or item.cognitive_level != definition.cognitive_level
                    or definition.difficulty not in (1, 2)
                    or definition.grade_level != profile.grade_level
                    or definition.topic_id not in request.selected_topic_ids
                ):
                    fail(
                        "Blueprint template scope or instance metadata is inconsistent"
                    )
        summary = plan.quota_summary
        if plan.difficulty_locked != (
            request.difficulty_distribution is not None
        ) or set(summary.achieved_skill_levels) != set(summary.achieved_skills):
            fail("Blueprint quota metadata is incomplete or inconsistent")
        for counts in (
            summary.requested_groups,
            summary.requested_skills,
            summary.requested_levels,
        ):
            if sum(counts.values()) != request.total_questions or any(
                count < 0 for count in counts.values()
            ):
                fail("Blueprint requested quotas must total the question count")
        for actual, reported in (
            (
                Counter(q.cognitive_level for q in plan.questions),
                summary.achieved_levels,
            ),
            (
                Counter(q.target_skill_id for q in plan.questions),
                summary.achieved_skills,
            ),
            (Counter(q.group for q in plan.questions), summary.achieved_groups),
        ):
            if any(
                actual[k] != reported.get(k, 0) for k in set(actual) | set(reported)
            ):
                fail("Blueprint achieved quotas do not match the selected questions")
        for skill, counts in summary.achieved_skill_levels.items():
            actual = Counter(
                q.cognitive_level for q in plan.questions if q.target_skill_id == skill
            )
            if any(actual[k] != counts.get(k, 0) for k in set(actual) | set(counts)):
                fail("Blueprint per-skill level quotas are inconsistent")
        if request.difficulty_distribution is not None and (
            not plan.difficulty_locked
            or summary.achieved_levels != question_slots(request)
            or summary.requested_levels != question_slots(request)
        ):
            fail("Blueprint violates teacher-locked cognitive levels")
