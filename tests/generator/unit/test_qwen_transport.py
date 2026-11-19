"""Provider protocol and resource limits, without a running model."""

import io
import json
import time

import pytest

from src.exam_generator.ai.qwen_client import QwenClient
from src.exam_generator.api.data_adapter import ApiFailure


@pytest.mark.parametrize("field", ["timeout", "exam_timeout"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, True, "45"])
def test_invalid_time_budgets_fail_before_inference(field, value):
    with pytest.raises(ValueError, match="finite positive"):
        QwenClient(**{field: value})


@pytest.mark.parametrize("attempts", [True, 1.0, 0, 4])
def test_attempt_budget_is_a_bounded_integer(attempts):
    with pytest.raises(ValueError, match="integer"):
        QwenClient(attempts=attempts)


@pytest.mark.parametrize("reason", ["length", "load", "unload", "unknown"])
def test_non_normal_completion_is_rejected_even_with_parseable_text(monkeypatch, reason):
    client = QwenClient()
    payload = {
        "model": client.model, "done": True, "done_reason": reason,
        "response": json.dumps({"question": "A superficially valid but unfinished question."}),
    }
    monkeypatch.setattr(
        "src.exam_generator.ai.qwen_client.urlopen",
        lambda *a, **kw: io.BytesIO(json.dumps(payload).encode()),
    )
    with pytest.raises(ApiFailure) as error:
        client.generate_one("A source statement", deadline=time.monotonic() + 5)
    assert error.value.code == "INVALID_QWEN_OUTPUT"


@pytest.mark.parametrize("reason", [None, "stop"])
def test_normal_and_legacy_completion_envelopes_remain_supported(monkeypatch, reason):
    client = QwenClient()
    payload = {"model": client.model, "done": True, "response": '{"question":"Valid transport text."}'}
    if reason is not None:
        payload["done_reason"] = reason
    monkeypatch.setattr(
        "src.exam_generator.ai.qwen_client.urlopen",
        lambda *a, **kw: io.BytesIO(json.dumps(payload).encode()),
    )
    candidate = client.generate_one("A source statement", deadline=time.monotonic() + 5)
    assert candidate.raw_response == payload["response"]
