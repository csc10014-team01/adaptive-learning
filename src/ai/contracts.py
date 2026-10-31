"""Internal model boundaries. Answers and student identities never enter prompts."""

from typing import Literal

from pydantic import Field, model_validator

from src.ai.problem_spec import ProblemSpec, render_template
from src.ai.template_instantiator import TemplateDefinition
from src.ai.template_presentations import TemplatePresentations
from src.api.schemas import (
    ContractModel,
    Identifier,
    TemplateInstanceRecord,
    TemplatePresentationRecord,
    Text,
)


class TemplateWordingContext(ContractModel):
    definition: TemplateDefinition
    instance: TemplateInstanceRecord
    presentation: TemplatePresentationRecord | None = None
    registry: TemplatePresentations = Field(
        default_factory=lambda: TemplatePresentations(version="legacy")
    )
    previous_wording: str = Field(default="", max_length=16000)
    variation_seed: int = Field(default=0, ge=0, le=2147483000)


class ExpressionSpec(ContractModel):
    source_id: Identifier
    source_text: Text
    generate_type: Literal["direct", "indirect"] = "direct"
    context_policy: Literal["preserve_source", "verified_context"] = "preserve_source"
    problem_spec: ProblemSpec | None = None
    context_id: Identifier | None = None
    template_context: TemplateWordingContext | None = None

    @model_validator(mode="after")
    def safe_presentation(self):
        if self.template_context is not None:
            from src.ai.template_instantiator import TemplateInstantiator

            context = self.template_context
            materialized = TemplateInstantiator().materialize(
                context.definition, context.instance.parameters
            )
            presentation = context.registry.resolve(
                context.definition, context.presentation, self.generate_type
            )
            expected = (
                presentation.render(context.instance.parameters)
                if presentation
                else materialized.content
            )
            from src.validation.math_validator import numeric_facts_preserved

            if not numeric_facts_preserved(materialized.content, expected):
                raise ValueError(
                    "Presentation pattern changed the source numerical facts"
                )
            if (
                self.problem_spec is not None
                or self.context_id is not None
                or self.context_policy != "preserve_source"
                or self.source_id != context.instance.instance_id
                or self.source_text != expected
                or context.instance != materialized.record
            ):
                raise ValueError(
                    "Template expression must match its verified mathematical instance and presentation"
                )
            return self
        if self.problem_spec is None:
            if (
                self.generate_type != "direct"
                or self.context_policy != "preserve_source"
                or self.context_id is not None
            ):
                raise ValueError(
                    "Legacy sources require direct/preserve_source presentation"
                )
            return self
        spec = self.problem_spec
        if spec.source_id != self.source_id:
            raise ValueError("ProblemSpec source mismatch")
        context = next(
            (c for c in spec.supported_contexts if c.context_id == self.context_id),
            None,
        )
        presentation = (
            next(
                (
                    p
                    for p in context.presentations
                    if p.generate_type == self.generate_type
                ),
                None,
            )
            if context
            else None
        )
        if presentation is None:
            raise ValueError("Context or presentation is not author-approved")
        if (
            self.context_policy == "preserve_source"
            and self.context_id != spec.source_context_id
        ):
            raise ValueError("Context changes require verified_context policy")
        if self.source_text != render_template(presentation.template, spec.parameters):
            raise ValueError("Structured expression must use its approved statement")
        return self

    def presentation(self):
        if self.problem_spec is None:
            return None
        context = next(
            c
            for c in self.problem_spec.supported_contexts
            if c.context_id == self.context_id
        )
        return next(
            p for p in context.presentations if p.generate_type == self.generate_type
        )


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
