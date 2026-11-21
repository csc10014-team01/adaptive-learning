"""Explicit experimental inputs and server-owned exact approved revisions.

Canonical submission access is intentionally an unimplemented Protocol boundary.
"""

import json
import sqlite3
from typing import Protocol

from pydantic import ValidationError

from src.api.data_adapter import ApiFailure
from src.grading.schemas import (
    ExperimentalRequest,
    GradingContext,
    QuestionContext,
    validate_membership,
)


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
            # No criteria/sub_score -> ID/skill fabrication. Current public
            # generated exams deliberately fail here until Data/API supplies IDs.
            contexts.append(
                QuestionContext(
                    question_id=question["question_id"],
                    question_text=question["content_latex"],
                    reference_answer=question["answer"]["correct_answer"],
                    reference_solution=question["answer"]["explanation"],
                    rubric=question["rubric"],
                    skill_ids=question["skill_ids"],
                )
            )
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
