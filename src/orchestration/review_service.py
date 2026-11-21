"""Teacher decisions are explicit; model output cannot approve an exam."""

from datetime import datetime, timezone

from src.api.data_adapter import ApiFailure
from src.api.schemas import ApproveExamRequest, ExamResponse


def check_revision(exam: ExamResponse, expected_revision: int) -> None:
    if exam.revision != expected_revision:
        raise ApiFailure(409, "EXAM_REVISION_CONFLICT", "Reload the latest draft before changing it")


def approve_exam(exam: ExamResponse, request: ApproveExamRequest) -> ExamResponse:
    check_revision(exam, request.expected_revision)
    if exam.status != "pending_teacher_review":
        raise ApiFailure(409, "EXAM_ALREADY_APPROVED", "Exam has already been approved")
    expected = {q.question_id for q in exam.questions}
    if len(request.accepted_question_ids) != len(expected) or set(request.accepted_question_ids) != expected:
        raise ApiFailure(422, "INCOMPLETE_TEACHER_REVIEW", "Explicitly accept every current question before approval")
    value = exam.model_dump(mode="python")
    value.update(status="approved", revision=exam.revision + 1, teacher_review={
        "approved_at": datetime.now(timezone.utc), "notes": request.notes,
    })
    for question in value["questions"]:
        question["validation"]["teacher_approved"] = True
    return ExamResponse.model_validate(value)


def validate_regeneration(original: ExamResponse, updated: ExamResponse, question_id: str) -> None:
    """A replacement generator may change wording, not trusted exam identity or scoring."""
    allowed = {"questions", "status", "revision", "teacher_review", "provenance"}
    if (updated.status != "pending_teacher_review" or updated.revision != original.revision + 1
            or any(getattr(updated, f) != getattr(original, f) for f in ExamResponse.model_fields if f not in allowed)):
        raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Regeneration changed the exam contract")
    if question_id not in {q.question_id for q in original.questions}:
        raise ApiFailure(404, "QUESTION_NOT_FOUND", "Question is not in this exam")
    for old, new in zip(original.questions, updated.questions):
        expected = old.model_dump(mode="python")
        expected["validation"]["teacher_approved"] = False
        if old.question_id == question_id:
            if new.question_id == old.question_id:
                raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Regeneration requires a new question revision ID")
            expected.update(question_id=new.question_id, content_latex=new.content_latex,
                            validation=new.validation.model_dump(mode="python"))
        if expected != new.model_dump(mode="python"):
            raise ApiFailure(500, "INVALID_EXAM_OUTPUT", "Regeneration changed source metadata or scoring")
