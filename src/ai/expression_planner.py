"""Conservative expression policy for existing, unstructured M3 questions."""

from src.ai.contracts import ExpressionSpec
from src.api.data_adapter import FixtureQuestion


class ExpressionPlanner:
    def plan_expression(self, source: FixtureQuestion) -> ExpressionSpec:
        # New contexts and indirect wording require author-supplied mathematical
        # specifications. Never infer n/k/order/replacement from arbitrary prose.
        return ExpressionSpec(source_id=source.question_id, source_text=source.content)
