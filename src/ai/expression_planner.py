"""Conservative expression policy for existing, unstructured M3 questions."""

from src.ai.contracts import ExpressionSpec
from src.ai.problem_spec import Presentation, render_template
from src.ai.template_presentations import (
    EXPERIMENTAL_CONTEXTS,
    TemplatePresentations,
    is_experimental,
)
from src.api.data_adapter import FixtureQuestion


class ExpressionPlanner:
    def __init__(
        self, *, generate_type: Presentation = "direct", context_id: str | None = None
    ):
        self.generate_type, self.context_id = generate_type, context_id

    def plan_template_expression(
        self,
        instance,
        registry: TemplatePresentations,
        *,
        eligible_index=0,
        variant_index=None,
        previous=None,
        previous_wording="",
    ):
        """Alternate types across eligible slots, then rotate available variants.

        No mastery/difficulty gate: NO_DATA/PARTIAL and L1/L2 share this policy.
        Regeneration prefers another allowed presentation before rotating back.
        """
        options = registry.options(instance.template)
        if previous is not None:
            alternatives = [
                p for p in options if p.presentation_id != previous.presentation_id
            ]
            opposite = [
                p for p in alternatives if p.generate_type != previous.generate_type
            ]
            choices = opposite or alternatives or options
        else:
            desired = "indirect" if eligible_index % 2 else "direct"
            choices = [p for p in options if p.generate_type == desired] or options
        ordinal = eligible_index // 2 if variant_index is None else variant_index
        chosen = choices[ordinal % len(choices)]
        if is_experimental(chosen):
            contexts = list(EXPERIMENTAL_CONTEXTS)
            offset = int(instance.record.signature[:8], 16) + ordinal
            context_id = contexts[offset % len(contexts)]
            if previous and context_id == previous.context_id:
                context_id = contexts[(offset + 1) % len(contexts)]
            chosen = registry.experimental_record(instance.template, context_id)
        presentation = registry.resolve(instance.template, chosen, chosen.generate_type)
        text = (
            presentation.render(instance.record.parameters)
            if presentation
            else instance.content
        )
        return ExpressionSpec(
            source_id=instance.record.instance_id,
            source_text=text,
            generate_type=chosen.generate_type,
            template_context={
                "definition": instance.template,
                "instance": instance.record,
                "presentation": chosen,
                "registry": registry,
                "previous_wording": previous_wording,
                "variation_seed": (
                    int(instance.record.signature[:8], 16) + ordinal * 97
                )
                % 2147483000,
            },
        )

    def plan_adaptive_expression(
        self, source: FixtureQuestion, *, status: str, achieved_index: int
    ) -> ExpressionSpec:
        """Alternate achieved-skill presentations only where authors verified both.

        Cognitive level never enters this decision. Legacy prose and weak or
        diagnostic skills retain direct/preserve-source wording. Explicit internal
        presentation/context configurations retain their existing behavior.
        """
        if self.generate_type != "direct" or self.context_id is not None:
            return self.plan_expression(source)
        spec = source.problem_spec
        if status == "ACHIEVED" and achieved_index % 2 and spec is not None:
            context = next(
                c
                for c in spec.supported_contexts
                if c.context_id == spec.source_context_id
            )
            if any(p.generate_type == "indirect" for p in context.presentations):
                return self.plan_expression(source, generate_type="indirect")
        return self.plan_expression(source)

    def plan_expression(
        self,
        source: FixtureQuestion,
        *,
        generate_type: Presentation | None = None,
        context_id: str | None = None,
    ) -> ExpressionSpec:
        # New contexts and indirect wording require author-supplied mathematical
        # specifications. Never infer n/k/order/replacement from arbitrary prose.
        source = FixtureQuestion.model_validate(source)
        generate_type = generate_type or self.generate_type
        context_id = context_id if context_id is not None else self.context_id
        spec = source.problem_spec
        if spec is None:
            if generate_type != "direct" or context_id is not None:
                raise ValueError(
                    "Context changes and indirect wording require a verified ProblemSpec"
                )
            return ExpressionSpec(
                source_id=source.question_id, source_text=source.content
            )
        context_id = context_id or spec.source_context_id
        context = next(
            (c for c in spec.supported_contexts if c.context_id == context_id), None
        )
        presentation = (
            next(
                (p for p in context.presentations if p.generate_type == generate_type),
                None,
            )
            if context
            else None
        )
        if presentation is None:
            raise ValueError(
                "Requested context/presentation is not compatible with this ProblemSpec"
            )
        return ExpressionSpec(
            source_id=source.question_id,
            source_text=render_template(presentation.template, spec.parameters),
            generate_type=generate_type,
            context_policy="preserve_source"
            if context_id == spec.source_context_id
            else "verified_context",
            problem_spec=spec,
            context_id=context_id,
        )
