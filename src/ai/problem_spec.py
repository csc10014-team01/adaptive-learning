"""Author-supplied mathematics, never inferred from legacy question prose.

Verification references are provenance supplied by the data author, not proof
produced by a model. The MVP verifier supports only bounded counting problems.
"""

from string import Formatter
from typing import Annotated, Literal

from pydantic import Field, model_validator

from src.api.schemas import ContractModel, Identifier, Text

Presentation = Literal["direct", "indirect"]
Structure = Literal["combination", "arrangement", "permutation"]
Parameter = Annotated[int, Field(strict=True, ge=0, le=100)]


class ProblemParameters(ContractModel):
    n: Annotated[int, Field(strict=True, ge=1, le=100)]
    k: Parameter | None = None


class ProblemConstraints(ContractModel):
    order_matters: Annotated[bool, Field(strict=True)]
    replacement_allowed: Annotated[bool, Field(strict=True)]


def render_template(template: str, parameters: ProblemParameters) -> str:
    """Only n/k substitutions; no expressions, attributes or format directives."""
    values = parameters.model_dump(exclude_none=True)
    for _, field, spec, conversion in Formatter().parse(template):
        if field is not None and (field not in values or spec or conversion):
            raise ValueError("Templates permit only plain {n} and available {k} placeholders")
    return template.format_map(values)


class VerifiedPresentation(ContractModel):
    generate_type: Presentation
    template: Text
    # Authored guards deliberately constrain paraphrasing. Missing a guard is
    # rejected rather than guessed to be semantically equivalent.
    required_phrases: Annotated[list[Text], Field(min_length=1)]
    forbidden_phrases: list[Text] = Field(default_factory=list)


class ProblemContext(ContractModel):
    context_id: Identifier
    presentations: Annotated[list[VerifiedPresentation], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_presentations(self):
        kinds = [p.generate_type for p in self.presentations]
        if len(kinds) != len(set(kinds)):
            raise ValueError("Each context may have only one presentation of each type")
        return self


class ProblemSpec(ContractModel):
    source_id: Identifier
    data_kind: Literal["synthetic_fixture", "approved_data"]
    verification_status: Literal["verified"]
    verification_reference: Text
    mathematical_structure: Structure
    parameters: ProblemParameters
    constraints: ProblemConstraints
    verified_answer: Annotated[str, Field(strict=True, pattern=r"^(0|[1-9][0-9]{0,200})$")]
    verified_solution: Annotated[list[Text], Field(min_length=1)]
    source_context_id: Identifier
    supported_contexts: Annotated[list[ProblemContext], Field(min_length=1)]

    @model_validator(mode="after")
    def consistent_specification(self):
        n, k = self.parameters.n, self.parameters.k
        order, replacement = self.constraints.order_matters, self.constraints.replacement_allowed
        if self.mathematical_structure == "permutation":
            if k is not None or not order or replacement:
                raise ValueError("Permutation requires n only, order and no replacement")
        elif k is None or (not replacement and k > n):
            raise ValueError("Selection requires k, with k <= n without replacement")
        if self.mathematical_structure == "combination" and (order or replacement):
            raise ValueError("MVP combinations require no order and no replacement")
        if self.mathematical_structure == "arrangement" and not order:
            raise ValueError("Arrangements require order")
        ids = [c.context_id for c in self.supported_contexts]
        if len(ids) != len(set(ids)) or self.source_context_id not in ids:
            raise ValueError("Contexts must be unique and include the source context")
        for context in self.supported_contexts:
            for presentation in context.presentations:
                fields = {field for _, field, _, _ in Formatter().parse(presentation.template) if field}
                if fields != set(self.parameters.model_dump(exclude_none=True)):
                    raise ValueError("Every statement must explicitly represent each mathematical parameter")
                text = render_template(presentation.template, self.parameters).casefold()
                required = [render_template(p, self.parameters).casefold() for p in presentation.required_phrases]
                forbidden = [render_template(p, self.parameters).casefold() for p in presentation.forbidden_phrases]
                if any(p not in text for p in required) or any(p in text for p in forbidden):
                    raise ValueError("Authored statement contradicts its expression guards")
        source = next(c for c in self.supported_contexts if c.context_id == self.source_context_id)
        if not any(p.generate_type == "direct" for p in source.presentations):
            raise ValueError("Source context requires a direct presentation")
        return self
