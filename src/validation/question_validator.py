"""Parse candidates and distinguish definite failures from unresolved semantics."""

import json

from src.ai.contracts import ExpressionSpec, GenerationCandidate, ValidationResult
from src.ai.problem_spec import render_template
from src.ai.template_instantiator import TemplateInstantiator
from src.ai.template_presentations import EXPERIMENTAL_NOTICE, is_experimental, validate_template_wording
from src.validation.math_validator import (
    changed_constraints, constraint_signatures, normalize_statement, numeric_facts_preserved, verified_count,
)


class QuestionValidator:
    def validate(self, expression: ExpressionSpec, candidate: GenerationCandidate) -> ValidationResult:
        try:
            result = json.loads(candidate.raw_response)
            if not isinstance(result, dict) or set(result) != {"question"}:
                raise ValueError("Expected only a question field")
            text = result["question"]
            if not isinstance(text, str) or not 20 <= len(text.strip()) <= 16000:
                raise ValueError("Invalid question text")
            experimental = expression.template_context is not None and is_experimental(expression.template_context.presentation)
            if not experimental and not numeric_facts_preserved(expression.source_text, text):
                raise ValueError("Changed numeric facts")
            if not experimental and changed_constraints(expression.source_text, text, structured=expression.problem_spec is not None or expression.template_context is not None):
                raise ValueError("Changed known mathematical constraints")
            if expression.template_context is not None:
                context = expression.template_context
                materialized = TemplateInstantiator().materialize(context.definition, context.instance.parameters)
                if context.instance != materialized.record:
                    raise ValueError("Template rules/parameters do not reproduce the verified instance")
                expected = validate_template_wording(materialized, text, expression.generate_type,
                    context.presentation, context.registry)
                if expression.source_text != expected:
                    raise ValueError("Template expression differs from its approved presentation")
                if experimental:
                    return ValidationResult(status="needs_review", question=text.strip(), reasons=[
                        EXPERIMENTAL_NOTICE,
                        "Basic JSON, source/numeric and detectable constraint checks only; semantic and cognitive equivalence are NOT verified.",
                        "Answer and solution remain computed by the backend, not Qwen.",
                    ])
            if expression.problem_spec is not None:
                spec, presentation = expression.problem_spec, expression.presentation()
                normalized = normalize_statement(text)
                markers = constraint_signatures(text)
                if (markers["order"]["no" if spec.constraints.order_matters else "yes"]
                        or markers["replacement"]["no" if spec.constraints.replacement_allowed else "yes"]):
                    raise ValueError("Statement contradicts the verified order/replacement constraints")
                if any(normalize_statement(render_template(p, spec.parameters)) not in normalized
                       for p in presentation.required_phrases):
                    raise ValueError("Missing required expression or mathematical constraint")
                if any(normalize_statement(render_template(p, spec.parameters)) in normalized
                       for p in presentation.forbidden_phrases):
                    raise ValueError("Forbidden expression or mathematical constraint")
                if verified_count(spec) != int(spec.verified_answer):
                    raise ValueError("Verified answer disagrees with the deterministic mathematical check")
        except (ValueError, TypeError) as exc:
            return ValidationResult(status="fail", reasons=[str(exc)])
        if (expression.problem_spec is not None or expression.template_context is not None) and normalize_statement(text) == normalize_statement(expression.source_text):
            return ValidationResult(status="pass", question=text.strip(), reasons=[
                "Matches the author-approved presentation; supported counting answer independently checked.",
                "Author verification of the statement and solution remains the trust boundary; teacher approval is separate.",
            ])
        return ValidationResult(status="needs_review", question=text.strip(), reasons=[
            "JSON and numeric facts checked; mathematical and semantic equivalence require teacher review.",
        ])
