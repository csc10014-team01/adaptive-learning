"""Teacher decisions are explicit; model output cannot approve an exam."""

from datetime import datetime, timezone

from pydantic import ValidationError

from src.api.data_adapter import ApiFailure
from src.api.schemas import ApproveExamRequest, ExamResponse


def check_revision(exam: ExamResponse, expected_revision: int) -> None:
    if exam.revision != expected_revision:
        raise ApiFailure(409, "EXAM_REVISION_CONFLICT", "Reload the latest draft before changing it")


def require_template_regeneration(exam, question_id):
    question = next((q for q in exam.questions if q.question_id == question_id), None)
    if question is None:
        raise ApiFailure(404, "QUESTION_NOT_FOUND", "Question is not in this exam")
    if question.source_ref.kind == "question":
        raise ApiFailure(409, "QUESTION_REGENERATION_FORBIDDEN", "Question Bank items are immutable; only Template instances can be regenerated")
    if question.template_instance is None:
        raise ApiFailure(409, "TEMPLATE_INSTANCE_REQUIRED", "This older draft lacks verified template instance provenance")
    return question


def approve_exam(exam: ExamResponse, request: ApproveExamRequest) -> ExamResponse:
    check_revision(exam, request.expected_revision)
    if exam.status != "pending_teacher_review":
        raise ApiFailure(409, "EXAM_ALREADY_APPROVED", "Exam has already been approved")
    try:
        exam = ExamResponse.model_validate(exam.model_dump(mode="python"))
    except (ValueError, ValidationError) as exc:
        raise ApiFailure(409, "EXAM_NOT_READY", "A complete valid draft is required for approval") from exc
    if any(q.validation.blocking_errors or (
        exam.provenance.generator != "fake" and q.validation.auto_status == "not_evaluated"
    ) for q in exam.questions):
        raise ApiFailure(409, "EXAM_NOT_READY", "Required automated validation is incomplete or has blocking errors")
    expected = {q.question_id for q in exam.questions}
    accepted = set(request.accepted_question_ids)
    if len(accepted) != len(request.accepted_question_ids) or not accepted.issubset(expected):
        raise ApiFailure(422, "INVALID_QUESTION_REVIEW", "Individual review IDs must be distinct questions in this draft")
    value = exam.model_dump(mode="python")
    value.update(status="approved", revision=exam.revision + 1, teacher_review={
        "approved_at": datetime.now(timezone.utc), "notes": request.notes,
    })
    for question in value["questions"]:
        if question["question_id"] in accepted:
            question["validation"]["teacher_approved"] = True
    return ExamResponse.model_validate(value)


def validate_regeneration(original: ExamResponse, updated: ExamResponse, question_id: str, *, data=None) -> None:
    """Template math/presentation may change; source, quotas and scoring stay fixed."""
    old_target = require_template_regeneration(original, question_id)
    allowed = {"questions", "status", "revision", "teacher_review", "provenance"}
    if (updated.status != "pending_teacher_review" or updated.revision != original.revision + 1
            or any(getattr(updated, f) != getattr(original, f) for f in ExamResponse.model_fields if f not in allowed)):
        raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Regeneration changed the exam contract")
    if question_id not in {q.question_id for q in original.questions}:
        raise ApiFailure(404, "QUESTION_NOT_FOUND", "Question is not in this exam")
    if len(original.questions) != len(updated.questions):
        raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Regeneration changed question count")
    for old, new in zip(original.questions, updated.questions):
        expected = old.model_dump(mode="python")
        expected["validation"]["teacher_approved"] = False
        if old.question_id == question_id:
            if new.question_id == old.question_id:
                raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Regeneration requires a new question revision ID")
            expected.update(question_id=new.question_id, content_latex=new.content_latex,
                            validation=new.validation.model_dump(mode="python"),
                            template_instance=new.template_instance.model_dump(mode="python") if new.template_instance else None,
                            answer=new.answer.model_dump(mode="python"),
                            step_solutions=[s.model_dump(mode="python") for s in new.step_solutions],
                            rubric=[r.model_dump(mode="python") for r in new.rubric])
            presentation_changed = (new.generate_type != old.generate_type or new.template_presentation != old.template_presentation)
            if presentation_changed:
                if data is None:
                    raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Presentation changes require trusted source validation")
                try:
                    data.validate_exam_references(updated)
                except ValueError as exc:
                    raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Invalid Template presentation provenance or mathematics") from exc
                expected.update(generate_type=new.generate_type,
                    template_presentation=new.template_presentation.model_dump(mode="python") if new.template_presentation else None)
            old_pid = old.template_presentation.presentation_id if old.template_presentation else "sql_direct"
            new_pid = new.template_presentation.presentation_id if new.template_presentation else "sql_direct"
            different_presentation = new.generate_type != old.generate_type or new_pid != old_pid
            if (new.template_instance is None or (
                new.template_instance.signature == old_target.template_instance.signature and not different_presentation
            )):
                raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Regeneration requires a new mathematical instance or compatible presentation")
        if expected != new.model_dump(mode="python"):
            raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Regeneration changed source metadata or scoring")
