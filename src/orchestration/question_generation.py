"""One bounded wording budget per presentation, under the shared exam deadline."""

import json
import time

from src.ai.contracts import ExpressionSpec, GenerationCandidate, ValidatedQuestion
from src.api.data_adapter import ApiFailure
from src.validation.question_validator import QuestionValidator


class QuestionGenerationService:
    def __init__(self, client, validator: QuestionValidator | None = None):
        self.client = client
        self.validator = validator or QuestionValidator()

    def generate(self, expression: ExpressionSpec, *, deadline: float) -> ValidatedQuestion:
        # Legacy injected clients expose rewrite(); call those only once so an
        # unknown internal retry policy cannot multiply the orchestrator budget.
        single_attempt = hasattr(self.client, "generate_one")
        attempts = self.client.attempts if single_attempt else 1
        feedback = ""
        rejections = []
        for attempt in range(attempts):
            if time.monotonic() >= deadline:
                raise ApiFailure(504, "QWEN_TIMEOUT", "Hết thời gian sinh đề Qwen.")
            try:
                if single_attempt:
                    candidate = self.client.generate_one(
                        expression if expression.problem_spec is not None or expression.template_context is not None else expression.source_text,
                        deadline=deadline, attempt=attempt, feedback=feedback,
                    )
                else:
                    if expression.problem_spec is not None or expression.template_context is not None:
                        raise ApiFailure(500, "STRUCTURED_TRANSPORT_REQUIRED", "Structured expressions require generate_one support")
                    candidate = GenerationCandidate(model=self.client.model, raw_response=json.dumps({
                        "question": self.client.rewrite(expression.source_text, deadline=deadline),
                    }))
                result = self.validator.validate(expression, candidate)
                if time.monotonic() >= deadline:
                    raise ApiFailure(504, "QWEN_TIMEOUT", "Hết thời gian sinh đề Qwen.")
                if result.status != "fail" and result.question:
                    result.reasons.extend(rejections)
                    return ValidatedQuestion(expression=expression, content=result.question, validation=result)
                feedback = "Lần trước không hợp lệ: " + "; ".join(result.reasons)
                rejections.append(f"Wording attempt {attempt + 1} rejected: " + "; ".join(result.reasons))
            except ApiFailure as exc:
                if exc.code != "INVALID_QWEN_OUTPUT":
                    raise
                feedback = "Lần trước trả JSON không hợp lệ; trả đúng schema và giữ nguyên dữ kiện."
                rejections.append(f"Wording attempt {attempt + 1} rejected: invalid model JSON/envelope.")
            if attempt + 1 == attempts:
                raise ApiFailure(502, "INVALID_QWEN_OUTPUT",
                    "Qwen trả câu hỏi không hợp lệ sau các lần thử. " + feedback[:600])
        raise AssertionError("unreachable")
