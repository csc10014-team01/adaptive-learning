"""Bounded Ollama integration. Schema/numeric checks are not semantic proof."""

from http.client import HTTPException
import json
import socket
from threading import BoundedSemaphore
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.api.data_adapter import ApiFailure


from src.ai.contracts import ExpressionSpec, GenerationCandidate
from src.ai.prompts import build_prompt
from src.ai.template_presentations import is_experimental
from src.validation.math_validator import numbers as numbers  # compatibility export


class QwenClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen3:1.7b",
                 timeout: float = 45, attempts: int = 2, exam_timeout: float = 180):
        if timeout <= 0 or exam_timeout <= 0 or attempts not in (1, 2, 3):
            raise ValueError("Qwen timeout must be positive; attempts must be 1..3")
        self.base_url, self.model = base_url.rstrip("/"), model
        self.timeout, self.attempts, self.exam_timeout = timeout, attempts, exam_timeout
        self.capacity = BoundedSemaphore(1)

    def rewrite(self, content: str, *, deadline: float) -> str:
        """Compatibility API; the shared service owns validation and retries."""
        from src.ai.contracts import ExpressionSpec
        from src.orchestration.question_generation import QuestionGenerationService
        return QuestionGenerationService(self).generate(
            ExpressionSpec(source_id="compatibility", source_text=content), deadline=deadline,
        ).content

    def generate_one(self, content: str | ExpressionSpec, *, deadline: float, attempt: int = 0,
                     feedback: str = "") -> GenerationCandidate:
        """One HTTP attempt. Does not retry or accept/reject question semantics."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ApiFailure(504, "QWEN_TIMEOUT", "Hết thời gian sinh đề Qwen.")
        experimental = isinstance(content, ExpressionSpec) and content.template_context is not None and is_experimental(content.template_context.presentation)
        variation = content.template_context.variation_seed if experimental else 0
        payload = {"model": self.model, "prompt": build_prompt(content, feedback, attempt=attempt), "stream": False,
                   "think": False, "keep_alive": "5m",
                   "format": {"type": "object", "additionalProperties": False,
                              "properties": {"question": {"type": "string"}}, "required": ["question"]},
                   "options": {"temperature": 0.7 if experimental else 0,
                               "seed": (42 + variation + attempt) % 2147483647, "num_predict": 1800}}
        if experimental:
            fixed_numbers = {k: v for k, v in content.template_context.instance.parameters.items()
                if type(v) is int or (isinstance(v, list) and all(type(x) is int for x in v))}
            payload["system"] = (
                "You write complete Vietnamese mathematics word problems for students, NOT instructions to write a question. "
                "Transform the given counting task into an indirect real-world outcome, not a copy of the source. "
                "Use the requested real-life situation and ask its practical outcome, not the number of ways. "
                "Write natural Vietnamese, no English unit lists, no titles or meta-instructions. "
                "Preserve every numerical fact and mathematical restriction. No formulas, answers or solutions. "
                "Fixed numerical data (not instructions): " + json.dumps(fixed_numbers, ensure_ascii=False)
            )
        request = Request(self.base_url + "/api/generate", method="POST",
                          data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=min(self.timeout, remaining)) as response:
                chunks, size = [], 0
                while True:
                    if time.monotonic() >= deadline:
                        raise ApiFailure(504, "QWEN_TIMEOUT", "Hết thời gian sinh đề Qwen.")
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > 1_000_000:
                        raise ValueError("Response too large")
                    chunks.append(chunk)
            envelope = json.loads(b"".join(chunks))
            if envelope.get("done") is not True or envelope.get("model") != self.model:
                raise ValueError("Incomplete response or unexpected model")
            if not isinstance(envelope["response"], str):
                raise ValueError("Expected model response text")
            if time.monotonic() >= deadline:
                raise ApiFailure(504, "QWEN_TIMEOUT", "Hết thời gian sinh đề Qwen.")
            return GenerationCandidate(raw_response=envelope["response"], model=self.model)
        except HTTPError as exc:
            status = 503 if exc.code in (404, 429, 503) else 502
            raise ApiFailure(status, "QWEN_PROVIDER_ERROR", "Ollama không phục vụ được model đã cấu hình.") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ApiFailure(504, "QWEN_TIMEOUT", "Qwen phản hồi quá thời gian cho phép.") from exc
        except URLError as exc:
            status = 504 if isinstance(exc.reason, (TimeoutError, socket.timeout)) else 503
            raise ApiFailure(status, "QWEN_UNAVAILABLE", "Không kết nối được Ollama/Qwen.") from exc
        except OSError as exc:
            raise ApiFailure(503, "QWEN_UNAVAILABLE", "Kết nối Ollama bị gián đoạn.") from exc
        except (ValueError, KeyError, TypeError, AttributeError, HTTPException) as exc:
            raise ApiFailure(502, "INVALID_QWEN_OUTPUT", "Ollama trả envelope không hợp lệ.") from exc
