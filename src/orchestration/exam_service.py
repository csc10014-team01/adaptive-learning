"""Synchronous plan/select/expression/generation/validation/assembly pipeline."""

import time
from uuid import uuid4

from src.adaptation.planner import RuleBasedPlanner
from src.ai.expression_planner import ExpressionPlanner
from src.api.data_adapter import ApiFailure
from src.api.schemas import ExamResponse, GenerateExamRequest, StudentProfileResponse
from src.orchestration.exam_assembler import ExamAssembler
from src.orchestration.question_generation import QuestionGenerationService
from src.orchestration.source_snapshot import source_digest


class ExamService:
    def __init__(self, data, client, *, planner=None, expression_planner=None, validator=None, assembler=None):
        self.data, self.client = data, client
        self.planner = planner or RuleBasedPlanner(data)
        self.expression_planner = expression_planner or ExpressionPlanner()
        self.question_service = QuestionGenerationService(client, validator)
        self.assembler = assembler or ExamAssembler()

    def generate(self, request: GenerateExamRequest, profile: StudentProfileResponse) -> ExamResponse:
        plan = self.planner.plan(request, profile)
        sources = {q.question_id: q for q in self.data.questions}
        if not self.client.capacity.acquire(blocking=False):
            raise ApiFailure(503, "QWEN_BUSY", "Qwen đang sinh đề khác; vui lòng thử lại.")
        try:
            deadline = time.monotonic() + self.client.exam_timeout
            candidates = [self.question_service.generate(
                self.expression_planner.plan_expression(sources[item.source_id]), deadline=deadline,
            ) for item in plan.questions]
            return self.assembler.assemble(request, profile, plan, sources, candidates, model=self.client.model)
        finally:
            self.client.capacity.release()

    def regenerate_question(self, exam: ExamResponse, question_id: str) -> ExamResponse:
        question = next((q for q in exam.questions if q.question_id == question_id), None)
        if question is None:
            raise ApiFailure(404, "QUESTION_NOT_FOUND", "Question is not in this exam")
        source = next((s for s in self.data.questions if s.question_id == question.source_ref.id), None)
        if source is None or question.source_ref.kind != "question":
            raise ApiFailure(409, "SOURCE_NOT_AVAILABLE", "The original question source is unavailable")
        if question.source_digest is None:
            raise ApiFailure(409, "SOURCE_SNAPSHOT_REQUIRED", "This older draft has no source fingerprint; generate a new exam")
        if question.source_digest != source_digest(source):
            raise ApiFailure(409, "SOURCE_CHANGED", "Source content changed; generate a new exam")
        if (source.answer != question.answer or source.skill_ids != question.skill_ids
                or source.cognitive_level != question.cognitive_level
                or source.grade_level != exam.grade_level or source.topic_id != exam.topic_id
                or (question.target_skill_id is not None and source.primary_skill_id != question.target_skill_id)):
            raise ApiFailure(409, "SOURCE_CHANGED", "Source metadata or answer changed; generate a new exam")
        if not self.client.capacity.acquire(blocking=False):
            raise ApiFailure(503, "QWEN_BUSY", "Qwen is serving another generation request")
        try:
            candidate = self.question_service.generate(self.expression_planner.plan_expression(source),
                deadline=time.monotonic() + self.client.exam_timeout)
            value = exam.model_dump(mode="python")
            value.update(status="pending_teacher_review", teacher_review=None, revision=exam.revision + 1)
            for item in value["questions"]:
                item["validation"]["teacher_approved"] = False
                if item["question_id"] == question_id:
                    item.update(question_id="QW_" + uuid4().hex, content_latex=candidate.content)
                    item["validation"] = {"auto_status": "needs_review", "teacher_approved": False,
                        "review_notes": [*candidate.validation.reasons, "Regenerated wording; teacher review required."]}
            value["provenance"] = {"generator": "qwen", "model": self.client.model}
            return ExamResponse.model_validate(value)
        finally:
            self.client.capacity.release()
