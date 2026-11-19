"""Teacher-only W06 evidence, separate from the student's marking scheme."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Outcome = Literal["PASS", "QUALITY_FAIL", "HARD_FAIL", "NEEDS_REVIEW", "RETRYABLE_FAIL"]
CriterionID = Literal["C1", "C2", "C3", "C4"]
Method = Literal["RULE", "LLM_ASSISTED", "HUMAN"]
Evidence = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]
Points = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class QualityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")


class QualityCheck(QualityModel):
    code: str
    status: Outcome
    evidence: Evidence
    question_ids: list[str] = Field(default_factory=list)
    method: Method = "RULE"


class HumanCriterionReview(QualityModel):
    criterion_id: CriterionID
    score: Points
    evidence: Evidence


class HumanQualityReview(QualityModel):
    content_fingerprint: Fingerprint
    criteria: list[HumanCriterionReview] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def distinct_criteria(self):
        if len({c.criterion_id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Human review must contain distinct W06 criteria")
        return self


class CriterionEvaluation(QualityModel):
    criterion_id: CriterionID
    status: Literal[
        "PASS", "QUALITY_FAIL", "HARD_FAIL", "NEEDS_REVIEW", "RETRYABLE_FAIL", "NOT_APPLICABLE"
    ]
    score: Points | None = None
    max_score: Points
    method: Method = "RULE"
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[Evidence] = Field(default_factory=list)
    checks: list[QualityCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def supported_score(self):
        if self.score is not None and (
            self.score > self.max_score
            or self.method != "HUMAN"
            or not self.evidence
            or self.status not in ("PASS", "QUALITY_FAIL")
        ):
            raise ValueError("W06 scores require supported human assessment within the criterion maximum")
        return self


class EvaluationReport(QualityModel):
    rubric_version: str = "w06-draft-evidence-v1"
    policy_version: str
    exam_id: str
    revision: int = Field(strict=True, ge=1)
    content_fingerprint: Fingerprint
    status: Outcome
    approval_blocked: bool = True
    total_score: Points | None = None
    criteria: list[CriterionEvaluation] = Field(min_length=4, max_length=4)
    warnings: list[Evidence] = Field(default_factory=list)
    profile_snapshot: dict[str, JsonValue] | None = None
    request_snapshot: dict[str, JsonValue] | None = None
    human_review: HumanQualityReview | None = None

    @model_validator(mode="after")
    def consistent_summary(self):
        if {c.criterion_id for c in self.criteria} != {"C1", "C2", "C3", "C4"}:
            raise ValueError("A W06 report must contain exactly C1-C4")
        applicable = [c for c in self.criteria if c.status != "NOT_APPLICABLE"]
        if any(c.status == "NOT_APPLICABLE" and c.criterion_id != "C4" for c in self.criteria):
            raise ValueError("Only C4 may be non-applicable in the W06 rubric")
        if any(
            c.status == "HARD_FAIL" or any(k.status == "HARD_FAIL" for k in c.checks)
            for c in self.criteria
        ) and self.status != "HARD_FAIL":
            raise ValueError("Confirmed hard failures cannot be downgraded")
        if any(
            c.status == "QUALITY_FAIL" or any(k.status == "QUALITY_FAIL" for k in c.checks)
            for c in self.criteria
        ) and self.status not in ("HARD_FAIL", "QUALITY_FAIL"):
            raise ValueError("Confirmed quality failures cannot be downgraded")
        if any(
            k.status == "RETRYABLE_FAIL" and k.method == "RULE"
            for c in self.criteria for k in c.checks
        ) and self.status not in ("HARD_FAIL", "QUALITY_FAIL", "RETRYABLE_FAIL"):
            raise ValueError("Unavailable mandatory rule checks cannot be replaced by human scores")
        if self.total_score is not None and (
            self.total_score > 100
            or any(c.score is None for c in applicable)
            or abs(sum(c.score for c in applicable) - self.total_score) > 1e-8
        ):
            raise ValueError("W06 total must sum supported, already-weighted criterion points once")
        if self.status == "PASS" and (
            self.total_score is None
            or self.total_score < 80
            or any(c.status != "PASS" for c in applicable)
        ):
            raise ValueError("W06 PASS requires complete passing evidence and at least 80/100")
        if self.status in ("HARD_FAIL", "QUALITY_FAIL", "RETRYABLE_FAIL") and not self.approval_blocked:
            raise ValueError("Failed evaluations must block approval")
        return self


def exam_fingerprint(exam) -> str:
    """Same in core/public DTOs; approval metadata is not examination content."""
    fields = (
        "exam_id", "student_id", "grade_level", "topic_id", "title", "generation_mode",
        "total_questions", "duration_minutes", "total_score", "provenance", "planner_summary",
    )
    value = exam.model_dump(mode="json", include=set(fields))
    value["questions"] = [
        q.model_dump(mode="json", exclude={"validation": {"teacher_approved"}})
        for q in exam.questions
    ]
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
