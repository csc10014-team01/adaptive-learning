"""Assemble checked candidates with trusted source answers and scoring."""

from uuid import uuid4

from src.adaptation.planner import ExamPlan
from src.ai.contracts import ValidatedQuestion
from src.api.data_adapter import ApiFailure, FixtureQuestion
from src.api.schemas import ExamQuestion, ExamResponse, GenerateExamRequest, PlannerSummary, StudentProfileResponse
from src.api.services import allocate_units
from src.orchestration.source_snapshot import source_digest


class ExamAssembler:
    def assemble(self, request: GenerateExamRequest, profile: StudentProfileResponse,
                 plan: ExamPlan, sources: dict[str, FixtureQuestion],
                 candidates: list[ValidatedQuestion], *, model: str) -> ExamResponse:
        if len(candidates) != request.total_questions or len(plan.questions) != request.total_questions:
            raise ApiFailure(500, "EXAM_INTEGRITY_FAILED", "Missing candidates for the complete exam")
        questions = []
        for index, (item, candidate, units) in enumerate(zip(
            plan.questions, candidates, allocate_units(40, request.total_questions),
        ), 1):
            if candidate.expression.source_id != item.source_id or candidate.validation.status == "fail":
                raise ApiFailure(500, "EXAM_INTEGRITY_FAILED", "Candidate does not match an accepted source slot")
            source = sources[item.source_id]
            questions.append(ExamQuestion(
                question_id="QW_" + uuid4().hex, order_index=index, topic_tag=source.topic_id,
                skill_ids=source.skill_ids, cognitive_level=source.cognitive_level,
                target_skill_id=item.target_skill_id, generate_type=candidate.expression.generate_type,
                content_latex=candidate.content, max_score=units / 4,
                source_ref={"kind": "question", "id": source.question_id}, answer=source.answer,
                source_digest=source_digest(source),
                step_solutions=[{"step_number": 1, "explanation": source.answer.explanation, "score": units / 4}],
                rubric=[{"criteria": source.rubric_criteria[0], "sub_score": units / 4}],
                validation={"auto_status": "needs_review", "teacher_approved": False,
                    "review_notes": [
                        "Source answers and cognitive labels require teacher review.",
                        "Generic scoring rubric requires teacher review.",
                        *candidate.validation.reasons,
                        f"Planner {plan.policy_version}; personalized={plan.personalized}; "
                        f"priority_count={plan.achieved_target_count}/{plan.target_count}.",
                        *item.reasons, *plan.warnings,
                    ]},
            ))
        return ExamResponse(
            exam_id="EX_" + uuid4().hex, student_id=profile.student_id, grade_level=profile.grade_level,
            topic_id="combinatorics", title="Đề ôn tập Đại số tổ hợp — " + (
                "Cá nhân hóa" if plan.personalized else "Khung chuẩn"),
            generation_mode=request.generation_mode, total_questions=request.total_questions,
            duration_minutes=request.duration_minutes, total_score=10.0, status="pending_teacher_review",
            provenance={"generator": "qwen", "model": model}, questions=questions,
            planner_summary=PlannerSummary.model_validate({
                field: getattr(plan, field) for field in PlannerSummary.model_fields
            }),
        )
