"""Shared allocation helpers and Demo presentation of the actual planner output."""

from __future__ import annotations

from math import floor
from threading import Lock
from typing import Protocol

from src.api.data_adapter import ApiFailure, StaticDataAdapter
from src.adaptation.policy import PlannerPolicyConfig
from src.api.schemas import (
    LEVELS, ExamResponse, GenerateExamRequest, StudentProfileResponse,
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
    """Legacy internal quota helper; never plan automatic generation with this."""
    weights = (tuple(getattr(request.difficulty_distribution, level) for level in LEVELS)
               if request.difficulty_distribution is not None else PlannerPolicyConfig().default_levels)
    return level_counts(request.total_questions, weights)


def level_counts(total: int, weights: tuple[float, ...]) -> dict[str, int]:
    """Largest remainder with stable L1 → L4 ties."""
    exact = [weight * total / 100 for weight in weights]
    counts = [floor(value) for value in exact]
    order = sorted(range(len(LEVELS)), key=lambda i: (-(exact[i] - counts[i]), i))
    for index in order[:total - sum(counts)]:
        counts[index] += 1
    return dict(zip(LEVELS, counts))


class FakeExamGenerator:
    def __init__(self, data: StaticDataAdapter, *, planner=None):
        self.data = data
        # Local import avoids the existing planner -> rounding helpers boundary.
        from src.adaptation.planner import RuleBasedPlanner
        self.planner = planner or RuleBasedPlanner(data)

    def generate(self, request: GenerateExamRequest, profile: StudentProfileResponse) -> ExamResponse:
        from src.orchestration.exam_service import ExamService
        return ExamService(self.data, None, planner=self.planner, fake=True).generate(request, profile)

    def regenerate_question(self, exam: ExamResponse, question_id: str) -> ExamResponse:
        from src.orchestration.exam_service import ExamService
        return ExamService(self.data, None, planner=self.planner, fake=True).regenerate_question(exam, question_id)


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

    def replace(self, exam: ExamResponse, *, expected_revision: int) -> None:
        exam = ExamResponse.model_validate(exam)
        if exam.revision != expected_revision + 1:
            raise ValueError("Replacement must advance the revision once")
        with self._lock:
            current = self._exams.get(exam.exam_id)
            if current is None:
                raise ApiFailure(404, "EXAM_NOT_FOUND", "Exam not found")
            if current.revision != expected_revision:
                raise ApiFailure(409, "EXAM_REVISION_CONFLICT", "Reload the latest draft before changing it")
            self._exams[exam.exam_id] = exam.model_copy(deep=True)
