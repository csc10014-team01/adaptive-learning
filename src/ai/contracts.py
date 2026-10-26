"""Internal model boundaries. Answers and student identities never enter prompts."""

from typing import Literal

from src.api.schemas import ContractModel, Identifier, Text


class ExpressionSpec(ContractModel):
    source_id: Identifier
    source_text: Text
    generate_type: Literal["direct"] = "direct"
    context_policy: Literal["preserve_source"] = "preserve_source"


class GenerationCandidate(ContractModel):
    raw_response: str
    model: Text


class ValidationResult(ContractModel):
    status: Literal["pass", "fail", "needs_review"]
    question: str | None = None
    reasons: list[Text]


class ValidatedQuestion(ContractModel):
    expression: ExpressionSpec
    content: Text
    validation: ValidationResult
