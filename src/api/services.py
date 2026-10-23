"""Replaceable synchronous fake service; this is not the team's real AI Planner."""

from __future__ import annotations

from math import floor
from threading import Lock
from typing import Protocol
from uuid import uuid4

from src.api.data_adapter import ApiFailure, StaticDataAdapter
from src.api.schemas import (
    LEVELS, ExamQuestion, ExamResponse, GenerateExamRequest, Provenance,
    RubricCriterion, SolutionStep, SourceReference, StudentProfileResponse,
    ValidationSummary,
)


class ExamGenerator(Protocol):
    def generate(
        self, request: GenerateExamRequest, profile: StudentProfileResponse,
    ) -> ExamResponse:
        """Return a complete teacher draft synchronously, or raise ApiFailure."""
        ...


def allocate_units(total: int, slots: int) -> list[int]:
    base, remainder = divmod(total, slots)
    return [base + (index < remainder) for index in range(slots)]


def question_slots(request: GenerateExamRequest) -> dict[str, int]:
    exact = [getattr(request.difficulty_distribution, level) * request.total_questions / 100 for level in LEVELS]
    counts = [floor(value) for value in exact]
    order = sorted(range(len(LEVELS)), key=lambda i: (-(exact[i] - counts[i]), i))
    for index in order[:request.total_questions - sum(counts)]:
        counts[index] += 1
    return dict(zip(LEVELS, counts))


class FakeExamGenerator:
    def __init__(self, data: StaticDataAdapter):
        self.data = data

    def generate(self, request: GenerateExamRequest, profile: StudentProfileResponse) -> ExamResponse:
        # Only deterministic fixture assembly. Real skill-priority/expression policies
        # belong to the replacement AI service, not an invented fake algorithm.
        selected = []
        for level, count in question_slots(request).items():
            candidates = [q for q in self.data.questions if q.cognitive_level == level]
            if len(candidates) < count:
                raise ApiFailure(
                    409, "INSUFFICIENT_QUESTION_BANK",
                    f"Fixture không đủ câu mức {level}: cần {count}, có {len(candidates)}.",
                )
            selected.extend(candidates[:count])

        questions = []
        for index, (source, units) in enumerate(zip(selected, allocate_units(40, len(selected))), 1):
            if max(len(source.solution_steps), len(source.rubric_criteria)) > units:
                raise ApiFailure(409, "INSUFFICIENT_QUESTION_BANK", "Scoring fixture không đáp ứng số câu yêu cầu.")
            questions.append(ExamQuestion(
                question_id="FQ_" + uuid4().hex, order_index=index,
                source_ref=SourceReference(kind="question", id=source.question_id),
                topic_tag="combinatorics", skill_ids=source.skill_ids,
                cognitive_level=source.cognitive_level, generate_type=source.generate_type,
                content_latex=source.content, answer=source.answer, max_score=units / 4,
                step_solutions=[SolutionStep(
                    step_number=step, explanation=text, score=part / 4,
                ) for step, (text, part) in enumerate(zip(
                    source.solution_steps, allocate_units(units, len(source.solution_steps)),
                ), 1)],
                rubric=[RubricCriterion(criteria=text, sub_score=part / 4)
                        for text, part in zip(source.rubric_criteria, allocate_units(units, len(source.rubric_criteria)))],
                validation=ValidationSummary(
                    auto_status="not_evaluated", teacher_approved=False,
                    review_notes=["Synthetic fake fixture; không gọi Qwen hoặc thực hiện semantic validation."],
                ),
            ))
        return ExamResponse(
            exam_id="FE_" + uuid4().hex, student_id=profile.student_id,
            grade_level=profile.grade_level, topic_id="combinatorics",
            title="Đề ôn tập Đại số tổ hợp — Fake MVP1",
            generation_mode=request.generation_mode,
            evidence_count=profile.evidence_count, data_status=profile.data_status,
            total_questions=request.total_questions, duration_minutes=request.duration_minutes,
            total_score=10.0, status="pending_teacher_review",
            provenance=Provenance(generator="fake", model=None), questions=questions,
        )


class InMemoryExamStore:
    """Single-process draft storage; restarting the API discards all drafts."""

    def __init__(self):
        self._exams: dict[str, ExamResponse] = {}
        self._lock = Lock()

    def save(self, exam: ExamResponse) -> None:
        with self._lock:
            self._exams[exam.exam_id] = exam.model_copy(deep=True)

    def get(self, exam_id: str) -> ExamResponse:
        with self._lock:
            if exam_id not in self._exams:
                raise ApiFailure(404, "EXAM_NOT_FOUND", "Không tìm thấy exam draft.")
            return self._exams[exam_id].model_copy(deep=True)
