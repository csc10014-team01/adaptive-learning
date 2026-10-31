"""Public MVP1 contracts. No Data database columns are added by these models."""

from __future__ import annotations

from datetime import datetime
from math import isclose
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, model_validator

Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=128, pattern=r"^\S+$")]
Text = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]
GradeLevel = Annotated[int, Field(strict=True, ge=10, le=10)]
Count = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]
Mode = Literal["adaptive", "default_blueprint", "standard"]
CognitiveLevel = Literal["recognition", "understanding", "application", "advanced_application"]
LEVELS: tuple[CognitiveLevel, ...] = (
    "recognition", "understanding", "application", "advanced_application",
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True, revalidate_instances="always")


def score_units(score: float) -> int:
    units = round(score * 4)
    if not isclose(score * 4, units, abs_tol=1e-8, rel_tol=0):
        raise ValueError("Scores must use 0.25-point increments")
    return units


class SkillMastery(ContractModel):
    skill_id: Identifier
    mastery_score: Annotated[float, Field(strict=True, ge=0, le=4, allow_inf_nan=False)] | None = None
    evidence_count: Count

    @model_validator(mode="after")
    def evidence_controls_mastery(self) -> Self:
        if self.evidence_count == 0:
            # SQL may contain a legacy numeric placeholder. It is not an
            # assessment and must never be exposed as a measured score.
            self.mastery_score = None
        elif self.mastery_score is None:
            raise ValueError("Positive evidence requires an actual mastery_score; evidence cannot be discarded")
        return self


class StudentSummary(ContractModel):
    student_id: Identifier
    name: Text
    grade_level: PositiveInt


class LearningHistoryItem(ContractModel):
    test_id: Identifier
    wrong_questions: list[Identifier]


class StudentProfileResponse(StudentSummary):
    """MVP student format; evidence is recorded independently for each skill."""

    skill_mastery: list[SkillMastery]
    learning_history: list[LearningHistoryItem]

    @model_validator(mode="after")
    def consistent_skills(self) -> Self:
        ids = [skill.skill_id for skill in self.skill_mastery]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate skill IDs")
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
    include_real_world_context: Annotated[Literal[True], BeforeValidator(strict_context_flag)] = True
    step_scoring_granularity: Literal[0.25] = 0.25


class GenerateExamRequest(ContractModel):
    student_id: Identifier
    generation_mode: Mode = Field(default="adaptive", description="Teacher endpoints accept only adaptive; legacy modes are internal compatibility only.",
        json_schema_extra={"enum": ["adaptive"]})
    selected_topic_ids: Annotated[list[Literal["combinatorics"]], Field(min_length=1, max_length=1)]
    total_questions: Annotated[int, Field(strict=True, ge=1, le=10)]
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=180)]
    # Retained for old internal integrations. Teacher HTTP endpoints reject non-null values.
    difficulty_distribution: DifficultyDistribution | None = Field(default=None,
        description="Deprecated manual override. Teacher endpoints require null or omission.", json_schema_extra={"deprecated": True, "enum": [None]})
    advanced_options: AdvancedOptions = Field(default_factory=AdvancedOptions)


class SourceReference(ContractModel):
    kind: Literal["question", "template"]
    id: Identifier


class TemplateInstanceRecord(ContractModel):
    instance_id: Identifier
    parameters: dict[str, JsonValue]
    signature: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    template_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class TemplatePresentationRecord(ContractModel):
    presentation_id: Identifier
    generate_type: Literal["direct", "indirect"]
    config_version: Identifier
    fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    verification_status: Literal["source_direct", "verified", "experimental"] | None = None
    context_id: Identifier | None = None

    @model_validator(mode="after")
    def experimental_label(self):
        if self.presentation_id == "experimental_indirect":
            if self.generate_type != "indirect" or self.verification_status != "experimental" or not self.context_id:
                raise ValueError("Experimental Indirect must retain explicit experimental provenance")
        elif self.verification_status == "experimental":
            raise ValueError("Experimental status requires the experimental presentation pathway")
        return self


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
            raise ValueError("Only template questions can contain template instances")
        if self.template_presentation is not None and (
            self.source_ref.kind != "template" or self.template_presentation.generate_type != self.generate_type
        ):
            raise ValueError("Template presentation provenance must match source kind and generate_type")
        if (self.template_presentation and self.template_presentation.verification_status == "experimental"
                and self.validation.auto_status == "pass"):
            raise ValueError("Experimental wording cannot be labeled fully validated")
        if self.target_skill_id is not None and self.target_skill_id not in self.skill_ids:
            raise ValueError("Target skill must belong to skill_ids")
        units = score_units(self.max_score)
        if sum(score_units(s.score) for s in self.step_solutions) != units:
            raise ValueError("Solution scores must sum to max_score")
        if sum(score_units(r.sub_score) for r in self.rubric) != units:
            raise ValueError("Rubric scores must sum to max_score")
        if [s.step_number for s in self.step_solutions] != list(range(1, len(self.step_solutions) + 1)):
            raise ValueError("Solution steps must be numbered consecutively")
        return self


class Provenance(ContractModel):
    generator: Literal["fake", "qwen", "question_bank"]
    model: str | None

    @model_validator(mode="after")
    def truthful_model(self) -> Self:
        if self.generator in ("fake", "question_bank") and self.model is not None:
            raise ValueError("Generation without inference cannot claim a model invocation")
        if self.generator == "qwen" and (not self.model or not self.model.strip()):
            raise ValueError("Qwen generation must identify its model")
        return self


class QuotaSummary(ContractModel):
    requested_groups: dict[str, int]
    achieved_groups: dict[str, int]
    requested_skills: dict[str, int]
    achieved_skills: dict[str, int]
    requested_levels: dict[str, int]
    achieved_levels: dict[str, int]
    requested_skill_levels: dict[str, dict[str, int]]
    achieved_skill_levels: dict[str, dict[str, int]]


class CellShortage(ContractModel):
    skill_id: Identifier
    level: CognitiveLevel
    requested: int
    available: int
    shortage: int


class LevelShortage(ContractModel):
    level: CognitiveLevel
    requested: int
    available: int
    achieved: int
    shortage: int
    reason: str


class SourceSubstitution(ContractModel):
    slot: int
    requested_skill: Identifier
    requested_level: CognitiveLevel
    actual_skill: Identifier
    actual_level: CognitiveLevel
    source_kind: Literal["question", "template"]
    source_id: Identifier
    reason: str


class SelectionDiagnostics(ContractModel):
    exact_skill_level_matrix_feasible: bool
    exact_exam_levels_feasible: bool
    eligible_question_levels: dict[str, int]
    eligible_template_instance_levels: dict[str, int]
    cell_shortages: list[CellShortage]
    level_shortages: list[LevelShortage]
    substitutions: list[SourceSubstitution]
    fallback_policy: str


class PlannerSummary(ContractModel):
    policy_version: str
    strategy: Literal["focused_practice", "diagnostic_review", "advanced_review", "standard"]
    difficulty_locked: bool
    skill_classifications: dict[str, Literal["NO_DATA", "PARTIAL", "WEAK", "ACHIEVED"]]
    quota_summary: QuotaSummary
    warnings: list[str]
    # Optional for persisted drafts created before source diagnostics existed.
    selection_diagnostics: SelectionDiagnostics | None = None


class TeacherReview(ContractModel):
    approved_at: datetime
    # The current shared teacher token does not identify an individual teacher.
    access_method: Literal["teacher_token"] = "teacher_token"
    notes: Annotated[str, Field(max_length=2000)] = ""


class ApproveExamRequest(ContractModel):
    expected_revision: PositiveInt
    # Optional individual review acknowledgements, independent of whole-exam approval.
    accepted_question_ids: list[Identifier] = Field(default_factory=list)
    notes: Annotated[str, Field(max_length=2000)] = ""


class RegenerateQuestionRequest(ContractModel):
    expected_revision: PositiveInt


class ExamResponse(ContractModel):
    exam_id: Identifier
    student_id: Identifier
    grade_level: PositiveInt
    topic_id: Literal["combinatorics"]
    title: Text
    generation_mode: Mode
    total_questions: Annotated[int, Field(strict=True, ge=1, le=10)]
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=180)]
    total_score: Annotated[float, Field(strict=True, ge=10, le=10, allow_inf_nan=False)]
    status: Literal["pending_teacher_review", "approved"]
    revision: PositiveInt = 1
    teacher_review: TeacherReview | None = None
    provenance: Provenance
    questions: Annotated[list[ExamQuestion], Field(min_length=1)]
    planner_summary: PlannerSummary | None = None

    @model_validator(mode="after")
    def complete_exam(self) -> Self:
        if self.status == "approved" and self.teacher_review is None:
            raise ValueError("Approved exams require a whole-exam teacher review record")
        if self.status == "pending_teacher_review" and self.teacher_review is not None:
            raise ValueError("Pending drafts cannot carry whole-exam approval")
        if len(self.questions) != self.total_questions:
            raise ValueError("Question count mismatch")
        if [q.order_index for q in self.questions] != list(range(1, self.total_questions + 1)):
            raise ValueError("Question order must be consecutive")
        if len({q.question_id for q in self.questions}) != self.total_questions:
            raise ValueError("Duplicate generated question IDs")
        if len({(q.source_ref.kind, q.template_instance.signature if q.template_instance else q.source_ref.id)
                for q in self.questions}) != self.total_questions:
            raise ValueError("Duplicate source questions")
        if sum(score_units(q.max_score) for q in self.questions) != score_units(self.total_score):
            raise ValueError("Question scores must sum to total_score")
        if self.provenance.generator == "fake" and any(
            q.validation.auto_status != "not_evaluated" for q in self.questions
        ):
            raise ValueError("Fake output must not claim automated semantic validation")
        return self

    def student_view(self) -> StudentExamResponse:
        """Explicit allowlist; no answers, solutions, rubric, source or review notes."""
        return StudentExamResponse(
            exam_id=self.exam_id, title=self.title, grade_level=self.grade_level,
            topic_id=self.topic_id, total_questions=self.total_questions,
            duration_minutes=self.duration_minutes, total_score=self.total_score,
            questions=[
                StudentQuestion.model_validate({
                    field: getattr(question, field) for field in StudentQuestion.model_fields
                }) for question in self.questions
            ],
        )


class StudentExamResponse(ContractModel):
    exam_id: Identifier
    title: Text
    grade_level: PositiveInt
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
