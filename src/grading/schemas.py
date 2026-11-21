"""Distinct request, trusted context, processing metadata and compact contracts."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ID = Annotated[
    str, Field(strict=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
]
Text = Annotated[str, Field(strict=True, min_length=1, max_length=16000, pattern=r"\S")]
Skill = Annotated[str, Field(strict=True, pattern=r"^A00[1-9]$")]
Skills = Annotated[list[Skill], Field(min_length=1, max_length=9)]
Verdict = Literal["CORRECT", "INCORRECT", "UNCERTAIN"]
State = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "INTERRUPTED"]


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", validate_default=True, revalidate_instances="always"
    )


def unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError("Duplicate " + label)


class RubricStep(Contract):
    id: ID
    description: Text
    skill_ids: Skills

    @model_validator(mode="after")
    def unique_skills(self) -> Self:
        unique(self.skill_ids, "rubric skills")
        return self


class QuestionContext(Contract):
    question_id: ID
    question_text: Text
    reference_answer: Annotated[str, Field(strict=True, min_length=1, max_length=180)]
    # The frozen prompt consumes reference reasoning through rubric descriptions.
    # Preserve a supplied solution, but do not add it to the frozen prompt.
    reference_solution: Text | None = None
    rubric: Annotated[list[RubricStep], Field(min_length=1, max_length=32)]
    skill_ids: Skills

    @model_validator(mode="after")
    def valid_context(self) -> Self:
        from src.grading.engine import parse, value

        unique(self.skill_ids, "question skills")
        unique([r.id for r in self.rubric], "rubric IDs")
        # Frozen v11 always permits A008 for verified false source arithmetic.
        if any(set(r.skill_ids) - set(self.skill_ids) - {"A008"} for r in self.rubric):
            raise ValueError(
                "Rubric skills must belong to question skill_ids (A008 is implicit in v11)"
            )
        try:
            value(parse(self.reference_answer))
        except (
            ValueError,
            SyntaxError,
            ZeroDivisionError,
            OverflowError,
            RecursionError,
        ) as exc:
            raise ValueError(
                "Reference answer must use the frozen supported integer/Fraction expression subset"
            ) from exc
        return self


class QuestionGradingReview(Contract):
    """Teacher-supplied grading reference and mappings, approved with the exam."""

    question_id: ID
    reference_answer: Annotated[str, Field(strict=True, min_length=1, max_length=180)]
    rubric: Annotated[list[RubricStep], Field(min_length=1, max_length=32)]


class AnswerRecord(Contract):
    question_id: ID
    student_answer: Annotated[str, Field(strict=True, max_length=16000)]


class ExperimentalRequest(Contract):
    mode: Literal["experimental"]
    idempotency_key: ID
    test_id: ID
    student_id: ID
    questions: Annotated[list[QuestionContext], Field(min_length=1, max_length=10)]
    answers: Annotated[list[AnswerRecord], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def membership(self) -> Self:
        validate_membership([q.question_id for q in self.questions], self.answers)
        return self


class ApprovedRequest(Contract):
    mode: Literal["approved_snapshot"]
    idempotency_key: ID
    exam_id: ID
    exam_revision: Annotated[int, Field(strict=True, ge=1)]
    student_id: ID
    answers: Annotated[list[AnswerRecord], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def unique_answers(self) -> Self:
        unique([a.question_id for a in self.answers], "answer IDs")
        return self


JobRequest = Annotated[
    ExperimentalRequest | ApprovedRequest, Field(discriminator="mode")
]


def validate_membership(question_ids, answers):
    unique(question_ids, "question IDs")
    ids = [a.question_id for a in answers]
    unique(ids, "answer IDs")
    if set(ids) != set(question_ids):
        raise ValueError(
            "Exactly one answer record is required for every question; unknown/missing IDs are rejected"
        )


class GradingContext(Contract):
    mode: Literal["experimental", "approved_snapshot"]
    test_id: ID
    student_id: ID
    exam_revision: int | None = None
    questions: list[QuestionContext]
    answers: list[AnswerRecord]
    # Only server-loaded authoritative data may populate this field.
    approved_snapshot: dict | None = None


class StepResult(Contract):
    step: int
    result: Verdict
    start: int
    end: int


class GradingError(Contract):
    step: int
    error_type: Literal[
        "ARITHMETIC_ERROR", "METHOD_OR_CONDITION_ERROR", "INCOMPLETE_SOLUTION"
    ]
    skill_ids: list[Skill]
    reason: str


class GradingResult(Contract):
    grading_status: Literal["AI_GRADED", "NEEDS_REVIEW"]
    requires_teacher: bool
    overall_result: Verdict
    final_answer_correct: bool | None
    step_results: list[StepResult]
    errors: list[GradingError]
    missing_steps: list
    teacher_comment: str | None


class AssessedAction(Contract):
    step: int
    description: str
    start: int
    end: int


class CompactSubmission(Contract):
    question_id: ID
    answer: list[AssessedAction]
    grading_result: GradingResult


class CompactExam(Contract):
    test_id: ID
    student_id: ID
    submissions: list[CompactSubmission]
    feedback: str | None


class QuestionProgress(Contract):
    question_id: ID
    seconds: float
    inference_calls: int | None = None
    repair_calls: int | None = None
    verdict: Verdict
    issue: (
        Literal[
            "provider_timeout",
            "provider_failure",
            "invalid_model_output",
            "unresolved_judgment",
        ]
        | None
    )


class JobMetadata(Contract):
    job_id: str
    state: State
    mode: Literal["experimental", "approved_snapshot"]
    experimental: bool
    test_id: str
    student_id: str
    exam_revision: int | None
    engine_revision: str
    integration_revision: str
    configuration: dict
    created_at: str
    started_at: str | None
    finished_at: str | None
    elapsed_seconds: float
    completed_questions: int
    total_questions: int
    definite_questions: int
    uncertain_questions: int
    provider_failures: int
    error_code: str | None
    questions: list[QuestionProgress]


class JobEnvelope(Contract):
    metadata: JobMetadata
    result: CompactExam
