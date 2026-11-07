"""Public MVP1 contracts. No Data database columns are added by these models."""

from __future__ import annotations

from math import isclose
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from src.exam_generator.api.schemas import (
    ApproveExamRequest as ApproveExamRequest,  # noqa: PLC0414 -- Public compatibility re-export.
)
from src.exam_generator.api.schemas import (
    LearningHistoryItem,
    PlannerSummary,
    TeacherReview,
    TemplateInstanceRecord,
    TemplatePresentationRecord,
)
from src.exam_generator.api.schemas import (
    RegenerateQuestionRequest as RegenerateQuestionRequest,  # noqa: PLC0414 -- Public compatibility re-export.
)

Identifier = Annotated[
    str, Field(strict=True, min_length=1, max_length=128, pattern=r"^\S+$")
]
Text = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]
GradeLevel = Annotated[int, Field(strict=True, ge=10, le=10)]
Count = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]
Mode = Literal["adaptive", "default_blueprint"]
DataStatus = Literal["no_data", "partial", "sufficient"]
CognitiveLevel = Literal[
    "recognition", "understanding", "application", "advanced_application"
]
LEVELS: tuple[CognitiveLevel, ...] = (
    "recognition",
    "understanding",
    "application",
    "advanced_application",
)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", validate_default=True, revalidate_instances="always"
    )


def evidence_status(count: int) -> DataStatus:
    return "no_data" if count == 0 else "partial" if count < 3 else "sufficient"


def score_units(score: float) -> int:
    units = round(score * 4)
    if not isclose(score * 4, units, abs_tol=1e-8, rel_tol=0):
        raise ValueError("Scores must use 0.25-point increments")
    return units


class SkillMastery(ContractModel):
    skill_id: Identifier
    mastery_score: (
        Annotated[float, Field(strict=True, ge=0, le=4, allow_inf_nan=False)] | None
    ) = None
    evidence_count: Count

    @model_validator(mode="after")
    def evidence_controls_mastery(self) -> Self:
        if self.evidence_count == 0:
            self.mastery_score = None
        elif self.mastery_score is None:
            raise ValueError("Positive evidence requires an actual mastery_score")
        return self


class StudentSummary(ContractModel):
    student_id: Identifier
    student_name: Text
    grade_level: Annotated[int, Field(strict=True, ge=10, le=10)]
    # Legacy JSON supplies root evidence; SQL records evidence per skill only.
    evidence_count: Count | None = None
    data_status: DataStatus | None = None

    @model_validator(mode="after")
    def consistent_evidence(self) -> Self:
        if (self.evidence_count is None) != (self.data_status is None):
            raise ValueError("Root evidence and status must be supplied together")
        if self.evidence_count is not None and self.data_status != evidence_status(
            self.evidence_count
        ):
            raise ValueError("data_status must agree with profile-level evidence_count")
        return self


class StudentProfileResponse(StudentSummary):
    skill_mastery: list[SkillMastery]
    recommended_blueprint_mode: Mode
    learning_history: list[LearningHistoryItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_skills(self) -> Self:
        ids = [skill.skill_id for skill in self.skill_mastery]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate skill IDs")
        if self.evidence_count is None:
            return self
        if any(
            skill.evidence_count > self.evidence_count for skill in self.skill_mastery
        ):
            raise ValueError("Per-skill evidence cannot exceed the profile count")
        expected = "adaptive" if self.evidence_count >= 3 else "default_blueprint"
        if self.recommended_blueprint_mode != expected:
            raise ValueError("Recommended mode must agree with evidence eligibility")
        if self.evidence_count >= 3 and not any(
            s.evidence_count for s in self.skill_mastery
        ):
            raise ValueError("Sufficient profile requires observed skill information")
        return self


class StudentListResponse(ContractModel):
    items: list[StudentSummary]


class SkillLabel(ContractModel):
    skill_id: Identifier
    name: Text


class Topic(ContractModel):
    topic_id: Literal["combinatorics"]
    topic_name: Text
    grade_level: Annotated[int, Field(strict=True, ge=10, le=10)]
    skills: list[SkillLabel]


class TopicListResponse(ContractModel):
    items: list[Topic]


Percentage = Annotated[float, Field(strict=True, ge=0, le=100, allow_inf_nan=False)]


class DifficultyDistribution(ContractModel):
    recognition: Percentage
    understanding: Percentage
    application: Percentage
    advanced_application: Percentage

    @model_validator(mode="after")
    def totals_one_hundred(self) -> Self:
        if not isclose(sum(self.model_dump().values()), 100, abs_tol=1e-8, rel_tol=0):
            raise ValueError("Difficulty percentages must sum to 100")
        return self


def strict_context_flag(value: object) -> bool:
    # Literal[True] alone also accepts integer 1; preserve the strict JSON boolean contract.
    if type(value) is not bool:
        raise ValueError("include_real_world_context must be a boolean")
    return value


class AdvancedOptions(ContractModel):
    include_real_world_context: Annotated[
        Literal[True], BeforeValidator(strict_context_flag)
    ] = True
    step_scoring_granularity: Literal[0.25] = 0.25


class GenerateExamRequest(ContractModel):
    student_id: Identifier
    generation_mode: Mode = "adaptive"
    selected_topic_ids: Annotated[
        list[Literal["combinatorics"]], Field(min_length=1, max_length=1)
    ]
    total_questions: Annotated[int, Field(strict=True, ge=1, le=10)]
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=180)]
    difficulty_distribution: DifficultyDistribution | None = None
    advanced_options: AdvancedOptions = Field(default_factory=AdvancedOptions)

    @model_validator(mode="after")
    def distribution_policy(self) -> Self:
        if (
            self.generation_mode == "adaptive"
            and self.difficulty_distribution is not None
        ):
            raise ValueError("Adaptive difficulty is controlled by the Planner")
        if self.generation_mode != "adaptive" and self.difficulty_distribution is None:
            raise ValueError("Non-adaptive generation requires difficulty_distribution")
        return self


class SourceReference(ContractModel):
    kind: Literal["question", "template"]
    id: Identifier


class Answer(ContractModel):
    correct_answer: Text
    explanation: Text


class SolutionStep(ContractModel):
    step_number: PositiveInt
    explanation: Text
    score: Number


class RubricCriterion(ContractModel):
    criteria: Text
    sub_score: Number


class ValidationSummary(ContractModel):
    auto_status: Literal["pass", "needs_review", "not_evaluated"]
    teacher_approved: Annotated[bool, Field(strict=True)]
    review_notes: list[str]
    blocking_errors: list[Text] = Field(default_factory=list)


class StudentQuestion(ContractModel):
    """Allowlist for future student delivery; never inherits teacher-only fields."""

    question_id: Identifier
    order_index: PositiveInt
    topic_tag: Literal["combinatorics"]
    skill_ids: Annotated[list[Identifier], Field(min_length=1)]
    cognitive_level: CognitiveLevel
    generate_type: Literal["direct", "indirect"]
    content_latex: Text
    max_score: Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]


class ExamQuestion(StudentQuestion):
    source_ref: SourceReference
    template_instance: TemplateInstanceRecord | None = None
    template_presentation: TemplatePresentationRecord | None = None
    source_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    target_skill_id: Identifier | None = None
    expression_context_id: Identifier | None = None
    answer: Answer
    step_solutions: Annotated[list[SolutionStep], Field(min_length=1)]
    rubric: Annotated[list[RubricCriterion], Field(min_length=1)]
    validation: ValidationSummary

    @model_validator(mode="after")
    def consistent_scoring(self) -> Self:
        if self.template_instance is not None and self.source_ref.kind != "template":
            raise ValueError("Only Template questions can contain instances")
        if self.template_presentation is not None and (
            self.source_ref.kind != "template"
            or self.template_presentation.generate_type != self.generate_type
        ):
            raise ValueError(
                "Presentation must match Template source and generate_type"
            )
        if (
            self.template_presentation
            and self.template_presentation.verification_status == "experimental"
            and self.validation.auto_status == "pass"
        ):
            raise ValueError("Experimental wording cannot be labeled fully validated")
        if (
            self.target_skill_id is not None
            and self.target_skill_id not in self.skill_ids
        ):
            raise ValueError("Target skill must belong to skill_ids")
        units = score_units(self.max_score)
        if sum(score_units(s.score) for s in self.step_solutions) != units:
            raise ValueError("Solution scores must sum to max_score")
        if sum(score_units(r.sub_score) for r in self.rubric) != units:
            raise ValueError("Rubric scores must sum to max_score")
        if [s.step_number for s in self.step_solutions] != list(
            range(1, len(self.step_solutions) + 1)
        ):
            raise ValueError("Solution steps must be numbered consecutively")
        return self


class Provenance(ContractModel):
    generator: Literal["fake", "qwen", "question_bank"]
    model: str | None

    @model_validator(mode="after")
    def truthful_model(self) -> Self:
        if self.generator in ("fake", "question_bank") and self.model is not None:
            raise ValueError("Fake generation cannot claim a model invocation")
        if self.generator == "qwen" and (not self.model or not self.model.strip()):
            raise ValueError("Qwen generation must identify its model")
        return self


class ExamResponse(ContractModel):
    exam_id: Identifier
    student_id: Identifier
    grade_level: Annotated[int, Field(strict=True, ge=10, le=10)]
    topic_id: Literal["combinatorics"]
    title: Text
    generation_mode: Mode
    # Legacy JSON supplies root evidence; SQL records evidence per skill only.
    evidence_count: Count | None = None
    data_status: DataStatus | None = None
    total_questions: Annotated[int, Field(strict=True, ge=1, le=10)]
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=180)]
    total_score: Annotated[float, Field(strict=True, ge=10, le=10, allow_inf_nan=False)]
    status: Literal["pending_teacher_review", "approved"]
    revision: PositiveInt = 1
    teacher_review: TeacherReview | None = None
    planner_summary: PlannerSummary | None = None
    provenance: Provenance
    questions: Annotated[list[ExamQuestion], Field(min_length=1)]

    @model_validator(mode="after")
    def complete_exam(self) -> Self:
        if (self.evidence_count is None) != (self.data_status is None):
            raise ValueError("Root evidence and status must be supplied together")
        if self.evidence_count is not None and self.data_status != evidence_status(
            self.evidence_count
        ):
            raise ValueError("Exam evidence status mismatch")
        if self.status == "approved" and self.teacher_review is None:
            raise ValueError(
                "Approved exams require a whole-exam teacher review record"
            )
        if self.status == "pending_teacher_review" and self.teacher_review is not None:
            raise ValueError("Pending drafts cannot carry whole-exam approval")
        if len(self.questions) != self.total_questions:
            raise ValueError("Question count mismatch")
        if [q.order_index for q in self.questions] != list(
            range(1, self.total_questions + 1)
        ):
            raise ValueError("Question order must be consecutive")
        if len({q.question_id for q in self.questions}) != self.total_questions:
            raise ValueError("Duplicate generated question IDs")
        if (
            len(
                {
                    (
                        q.source_ref.kind,
                        q.template_instance.signature
                        if q.template_instance
                        else q.source_ref.id,
                    )
                    for q in self.questions
                }
            )
            != self.total_questions
        ):
            raise ValueError("Duplicate source questions")
        if sum(score_units(q.max_score) for q in self.questions) != score_units(
            self.total_score
        ):
            raise ValueError("Question scores must sum to total_score")
        if self.provenance.generator == "fake" and any(
            q.validation.auto_status != "not_evaluated" for q in self.questions
        ):
            raise ValueError("Fake output must not claim automated semantic validation")
        return self

    def student_view(self) -> StudentExamResponse:
        """Explicit allowlist; no answers, solutions, rubric, source or review notes."""
        return StudentExamResponse(
            exam_id=self.exam_id,
            title=self.title,
            grade_level=self.grade_level,
            topic_id=self.topic_id,
            total_questions=self.total_questions,
            duration_minutes=self.duration_minutes,
            total_score=self.total_score,
            questions=[
                StudentQuestion.model_validate(
                    {
                        field: getattr(question, field)
                        for field in StudentQuestion.model_fields
                    }
                )
                for question in self.questions
            ],
        )


class StudentExamResponse(ContractModel):
    exam_id: Identifier
    title: Text
    grade_level: Annotated[int, Field(strict=True, ge=10, le=10)]
    topic_id: Literal["combinatorics"]
    total_questions: PositiveInt
    duration_minutes: PositiveInt
    total_score: Number
    questions: list[StudentQuestion]


class ErrorDetail(ContractModel):
    field: str
    reason: str


class ApiError(ContractModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ApiErrorResponse(ContractModel):
    error: ApiError
