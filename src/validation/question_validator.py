"""Parse candidates and distinguish definite failures from unresolved semantics."""

import json

from src.ai.contracts import ExpressionSpec, GenerationCandidate, ValidationResult
from src.validation.math_validator import numeric_facts_preserved


class QuestionValidator:
    def validate(self, expression: ExpressionSpec, candidate: GenerationCandidate) -> ValidationResult:
        try:
            result = json.loads(candidate.raw_response)
            if not isinstance(result, dict) or set(result) != {"question"}:
                raise ValueError("Expected only a question field")
            text = result["question"]
            if not isinstance(text, str) or not 20 <= len(text.strip()) <= 16000:
                raise ValueError("Invalid question text")
            if not numeric_facts_preserved(expression.source_text, text):
                raise ValueError("Changed numeric facts")
        except (ValueError, TypeError) as exc:
            return ValidationResult(status="fail", reasons=[str(exc)])
        return ValidationResult(status="needs_review", question=text.strip(), reasons=[
            "JSON and numeric facts checked; mathematical and semantic equivalence require teacher review.",
        ])
