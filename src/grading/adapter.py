"""Explicit experimental inputs and server-owned exact approved revisions.

Canonical submission access is intentionally an unimplemented Protocol boundary.
"""

import json
import re
import sqlite3
from typing import Protocol

from pydantic import ValidationError

from src.api.data_adapter import ApiFailure
from src.grading.schemas import (
    ApprovedRequest,
    AnswerRecord,
    ExperimentalRequest,
    GradingContext,
    QuestionContext,
    validate_membership,
)


def normalize_grading_reference(text):
    """Lossless numeric formatting only; never select an arbitrary number from prose."""
    from src.grading.engine import parse, value

    def atomic(part):
        part = part.strip()
        try:
            value(parse(part))
            return part
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError):
            match = re.fullmatch(
                r"([+-]?\d+(?:\s*/\s*\d+)?)\s+(?:cách(?:\s+(?:chọn|sắp xếp|đi|lập))?|số|bộ|phương án|lựa chọn)\.?",
                part, flags=re.IGNORECASE,
            )
            if match:
                expression = match[1]
                try:
                    value(parse(expression))
                    return expression
                except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError):
                    pass
            return None

    direct = atomic(text)
    if direct is not None:
        return direct
    sides = text.split("=")
    if len(sides) == 2:
        left, right = (atomic(side) for side in sides)
        if left is not None and right is not None:
            if value(parse(left)) != value(parse(right)):
                raise ValueError("Đẳng thức trong đáp án tham chiếu không đúng.")
            return right
    return None


def prepare_grading_review(exam, reviews):
    """Bind explicitly reviewed grading data to the server-owned question text."""
    from src.grading.engine import parse, value

    if reviews is None:
        return
    ids = [review.question_id for review in reviews]
    if len(ids) != len(set(ids)) or set(ids) != {q.question_id for q in exam.questions}:
        raise ApiFailure(422, "INVALID_GRADING_REVIEW", "Cần rubric chấm cho đúng mỗi câu trong đề, không thiếu hoặc trùng câu.")
    by_id = {review.question_id: review for review in reviews}
    contexts = {}
    try:
        for question in exam.questions:
            review = by_id[question.question_id]
            reference = normalize_grading_reference(review.reference_answer)
            if reference is None:
                raise ValueError(f"Nhập đáp án chấm của {question.question_id} dưới dạng số hoặc biểu thức được hỗ trợ.")
            contexts[question.question_id] = QuestionContext(
                question_id=question.question_id,
                question_text=question.content_latex,
                reference_answer=reference,
                reference_solution=question.answer.explanation,
                rubric=review.rubric,
                skill_ids=question.skill_ids,
            )
            original = normalize_grading_reference(question.answer.correct_answer)
            if original is not None and value(parse(original)) != value(parse(reference)):
                raise ValueError(f"Đáp án chấm của {question.question_id} không khớp đáp án nguồn đã tính được.")
    except (ValueError, ValidationError) as exc:
        raise ApiFailure(422, "INVALID_GRADING_REVIEW", "Rubric chấm hoặc đáp án biểu thức không hợp lệ: " + str(exc)) from exc
    for question in exam.questions:
        question.grading_context = contexts[question.question_id]


def approved_input(exam_id, revision, snapshots):
    """Prepare answer editors from the exact approved snapshot, never client context."""
    snapshot = snapshots.load(exam_id, revision)
    try:
        payload = ApprovedRequest(
            mode="approved_snapshot", idempotency_key="context-preview",
            exam_id=exam_id, exam_revision=revision, student_id=snapshot["student_id"],
            answers=[AnswerRecord(question_id=q["question_id"], student_answer="") for q in snapshot["questions"]],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiFailure(409, "GRADING_CONTEXT_NOT_READY", "Snapshot chưa có thông tin học sinh/câu hỏi hợp lệ.") from exc
    context = normalize_request(payload, snapshots)
    return {
        "exam_id": exam_id, "exam_revision": revision, "student_id": context.student_id,
        "questions": [{"question_id": q.question_id, "question_text": q.question_text} for q in context.questions],
        "answers": [a.model_dump() for a in context.answers],
    }


class SubmissionRepository(Protocol):
    """Future Data adapter must preserve raw text and explicit blank records."""

    def load_answers(
        self, submission_id: str, exam_id: str, revision: int, student_id: str
    ) -> list: ...


class ApprovedSnapshotRepository(Protocol):
    def load(self, exam_id: str, revision: int) -> dict: ...


class ExamStoreSnapshots:
    """Read only the requested existing revision, never silently use latest."""

    def __init__(self, exam_store):
        self.store = exam_store

    def load(self, exam_id, revision):
        if hasattr(self.store, "get_revision"):
            try:
                return self.store.get_revision(exam_id, revision).model_dump(mode="json")
            except ApiFailure as exc:
                if exc.code in ("EXAM_NOT_FOUND", "EXAM_REVISION_NOT_FOUND"):
                    raise ApiFailure(404, "GRADING_SNAPSHOT_NOT_FOUND", "Không tìm thấy snapshot đề và revision đã yêu cầu.") from exc
                raise
        if hasattr(self.store, "path"):
            path = self.store.path.resolve()
            if not path.exists():
                raise ApiFailure(
                    404,
                    "GRADING_SNAPSHOT_NOT_FOUND",
                    "Không tìm thấy snapshot đề và revision đã yêu cầu.",
                )
            connection = None
            try:
                connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                connection.execute("PRAGMA query_only=ON")
                row = connection.execute(
                    "SELECT body FROM exam_revisions WHERE exam_id=? AND revision=?",
                    (exam_id, revision),
                ).fetchone()
            except sqlite3.Error as exc:
                raise ApiFailure(
                    409,
                    "GRADING_CONTEXT_NOT_READY",
                    "Kho snapshot chưa có exam_revisions đọc được; cần khôi phục đúng snapshot đã duyệt trước khi chấm.",
                ) from exc
            finally:
                if connection is not None:
                    connection.close()
            if row is None:
                raise ApiFailure(
                    404,
                    "GRADING_SNAPSHOT_NOT_FOUND",
                    "Không tìm thấy snapshot đề và revision đã yêu cầu.",
                )
            try:
                snapshot = json.loads(row[0])
                if not isinstance(snapshot, dict):
                    raise ValueError("Snapshot must be an object")
                return snapshot
            except (ValueError, TypeError) as exc:
                raise ApiFailure(
                    409,
                    "GRADING_CONTEXT_NOT_READY",
                    "Snapshot lưu trên server không hợp lệ; cần sửa dữ liệu nguồn trước khi chấm.",
                ) from exc
        snapshot = self.store.get(exam_id).model_dump(mode="json")
        if snapshot["revision"] != revision:
            raise ApiFailure(
                409,
                "GRADING_REVISION_UNAVAILABLE",
                "Kho fake chỉ giữ revision hiện tại; revision yêu cầu không còn trong memory.",
            )
        return snapshot


def normalize_request(payload, snapshots: ApprovedSnapshotRepository):
    if isinstance(payload, ExperimentalRequest):
        return GradingContext(
            mode="experimental",
            test_id=payload.test_id,
            student_id=payload.student_id,
            questions=payload.questions,
            answers=payload.answers,
        )
    snapshot = snapshots.load(payload.exam_id, payload.exam_revision)
    if (
        snapshot.get("exam_id") != payload.exam_id
        or snapshot.get("revision") != payload.exam_revision
    ):
        raise ApiFailure(
            409,
            "GRADING_REVISION_MISMATCH",
            "Snapshot không khớp chính xác exam/revision yêu cầu.",
        )
    if snapshot.get("status") != "approved" or not snapshot.get("teacher_review"):
        raise ApiFailure(
            409, "GRADING_EXAM_NOT_APPROVED", "Revision này chưa được duyệt đề."
        )
    if snapshot.get("student_id") != payload.student_id:
        raise ApiFailure(
            409,
            "GRADING_STUDENT_MISMATCH",
            "Bài làm không thuộc học sinh được gắn với snapshot.",
        )
    try:
        questions = snapshot["questions"]
        validate_membership([q["question_id"] for q in questions], payload.answers)
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiFailure(
            422,
            "GRADING_QUESTION_MEMBERSHIP",
            "Phải gửi đúng một bản ghi bài làm cho mỗi câu của revision đã chọn.",
        ) from exc
    contexts = []
    for question in questions:
        try:
            reviewed = question.get("grading_context")
            context = (
                QuestionContext.model_validate(reviewed) if reviewed is not None else QuestionContext(
                    question_id=question["question_id"],
                    question_text=question["content_latex"],
                    reference_answer=question["answer"]["correct_answer"],
                    reference_solution=question["answer"]["explanation"],
                    rubric=question["rubric"],
                    skill_ids=question["skill_ids"],
                )
            )
            if (context.question_id != question["question_id"]
                or context.question_text != question["content_latex"]
                or context.skill_ids != question["skill_ids"]):
                raise ValueError("Reviewed grading context does not bind to this snapshot")
            contexts.append(context)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise ApiFailure(
                409,
                "GRADING_CONTEXT_NOT_READY",
                "Snapshot chưa có grading context được hỗ trợ. Cần rubric [{id, description, skill_ids}], "
                "mapping kỹ năng từng tiêu chí và đáp án tham chiếu thuộc tập biểu thức được hỗ trợ; "
                "criteria/sub_score hoặc step/description không đủ. Dùng chế độ thử nghiệm với context tường minh.",
            ) from exc
    return GradingContext(
        mode="approved_snapshot",
        test_id=payload.exam_id,
        student_id=payload.student_id,
        exam_revision=payload.exam_revision,
        questions=contexts,
        answers=payload.answers,
        approved_snapshot=snapshot,
    )
