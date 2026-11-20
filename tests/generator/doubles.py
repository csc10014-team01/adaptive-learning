import json
from threading import BoundedSemaphore

from src.exam_generator.ai.contracts import GenerationCandidate


class EchoTemplateClient:
    model = "mock-local-qwen"
    attempts = 2
    exam_timeout = 30

    def __init__(self, *, fail=False, invalid_first=False):
        self.capacity = BoundedSemaphore(1)
        self.calls = []
        self.fail = fail
        self.invalid_first = invalid_first

    def generate_one(self, expression, **kwargs):
        assert expression.template_context is not None, (
            "Immutable Questions must never call Qwen"
        )
        self.calls.append((expression, kwargs))
        text = expression.source_text
        if self.fail or (self.invalid_first and len(self.calls) == 1):
            text += " Thêm 999 đối tượng."
        return GenerationCandidate(
            model=self.model, raw_response=json.dumps({"question": text})
        )
