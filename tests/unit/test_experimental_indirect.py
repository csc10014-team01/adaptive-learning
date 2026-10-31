"""Experimental presentation is deliberately NOT author/semantically verified."""

import io
import json
import time

import pytest
from pydantic import ValidationError

from src.ai.contracts import GenerationCandidate
from src.ai.expression_planner import ExpressionPlanner
from src.ai.prompts import build_prompt
from src.ai.qwen_client import QwenClient
from src.ai.template_instantiator import TemplateInstantiator
from src.ai.template_presentations import (
    EXPERIMENTAL_NOTICE,
    TemplatePresentations,
    is_experimental,
)
from src.api.data_adapter import DEFAULT_BANK
from src.api.m3_adapter import M3DataAdapter
from src.api.schemas import TemplatePresentationRecord
from src.api.template_repository import load_templates
from src.orchestration.exam_service import ExamService
from src.validation.question_validator import QuestionValidator
from tests.integration.test_hybrid_exam_api import EchoTemplateClient
from tests.unit.test_hybrid_sources import template
from tests.unit.test_planner import make_data
from tests.unit.test_template_presentations import synthetic_registry


def experimental_expression(level=1, *, ordinal=1, previous_wording=""):
    instance = TemplateInstantiator().materialize(template(level=level), {"n": 5})
    registry = TemplatePresentations(
        version="no-approved-patterns", experimental_indirect=True
    )
    return ExpressionPlanner().plan_template_expression(
        instance,
        registry,
        eligible_index=ordinal,
        variant_index=ordinal // 2,
        previous_wording=previous_wording,
    )


def contextual_wording(expression):
    n = expression.template_context.instance.parameters["n"]
    if expression.template_context.definition.template_id == "EA0004":
        return f"Ban tổ chức có {n} cặp bạn, mỗi cặp gồm một bạn nhóm A và một bạn nhóm B. Mỗi lượt giao lưu ghép một bạn A với một bạn B nhưng không ghép lại cặp đã cho. Danh sách mọi lượt ghép hợp lệ có bao nhiêu mục?"
    return f"Câu lạc bộ có {n} học sinh phân biệt. Mỗi ngày tất cả các bạn xếp thành một hàng theo một cách mới, không dùng lại cách xếp của ngày trước. Câu lạc bộ có thể thực hiện bao nhiêu ngày trước khi phải lặp một cách xếp?"


class ExperimentalClient(EchoTemplateClient):
    def __init__(self, mode="valid"):
        super().__init__()
        self.mode = mode

    def generate_one(self, expression, **kwargs):
        self.calls.append((expression, kwargs))
        text = (
            contextual_wording(expression)
            if is_experimental(expression.template_context.presentation)
            else expression.source_text
        )
        if self.mode == "invalid_all" or (
            self.mode == "invalid_indirect"
            and is_experimental(expression.template_context.presentation)
        ):
            text += " Thêm 999 đối tượng."
        return GenerationCandidate(
            model=self.model, raw_response=json.dumps({"question": text})
        )


@pytest.mark.parametrize("level", [1, 2])
def test_l1_l2_can_select_direct_and_experimental_without_approved_patterns(level):
    direct = experimental_expression(level, ordinal=0)
    indirect = experimental_expression(level)
    assert direct.generate_type == "direct" and indirect.generate_type == "indirect"
    assert indirect.template_context.presentation.verification_status == "experimental"
    assert indirect.template_context.registry.presentations == []
    assert indirect.template_context.instance == direct.template_context.instance
    assert (
        indirect.template_context.definition.cognitive_level
        == direct.template_context.definition.cognitive_level
    )


def test_real_sql_templates_expose_experimental_options_and_strict_mode_stays_available(
    monkeypatch,
):
    monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", "1")
    data = M3DataAdapter()
    for definition in load_templates(DEFAULT_BANK)[0]:
        kinds = [
            p.generate_type for p in data.presentation_registry.options(definition)
        ]
        assert kinds == (
            ["direct", "indirect"] if definition.difficulty in (1, 2) else ["direct"]
        )
        assert all(
            p.verification_status == "proposed"
            for p in data.presentation_registry.presentations
        )
    monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", "0")
    assert all(
        [r.generate_type for r in data.presentation_registry.options(t)] == ["direct"]
        for t in data.templates
    )


def test_context_rotation_is_reproducible_and_previous_wording_is_transient_prompt_data():
    first = experimental_expression(
        previous_wording="Một bối cảnh cũ không nên sao chép."
    )
    second = experimental_expression(ordinal=3, previous_wording=first.source_text)
    assert first == experimental_expression(
        previous_wording="Một bối cảnh cũ không nên sao chép."
    )
    assert (
        first.template_context.presentation.context_id
        != second.template_context.presentation.context_id
    )
    prompt = build_prompt(first)
    assert (
        "Vietnamese grade-10 story question" in prompt and "decorative story" in prompt
    )
    assert (
        "copy the original Direct question" in prompt
        and "All parameters are FIXED" in prompt
    )
    assert "do not calculate or return an answer or solution" in prompt
    assert "required_statement" not in prompt
    assert "Một bối cảnh cũ" in prompt
    assert build_prompt(first, attempt=1) != prompt
    for secret in (
        "answer_rule",
        "solution_rule",
        "correct_answer",
        "student_id",
        "verification_reference",
    ):
        assert secret not in prompt


def test_legitimate_contextual_output_needs_review_without_original_direct_sentence():
    expr = experimental_expression()
    text = contextual_wording(expr)
    result = QuestionValidator().validate(
        expr,
        GenerationCandidate(model="mock", raw_response=json.dumps({"question": text})),
    )
    assert expr.source_text not in text
    assert result.status == "needs_review" and result.question == text
    assert EXPERIMENTAL_NOTICE in result.reasons
    assert "NOT verified" in " ".join(result.reasons)


@pytest.mark.parametrize(
    "mode",
    [
        "number",
        "missing_number",
        "contradiction",
        "placeholder",
        "copy",
        "decorative",
        "shallow",
        "formula",
        "bad_json",
        "extra_answer",
        "short",
    ],
)
def test_basic_blocking_checks_still_reject_corruption(mode):
    expr = experimental_expression()
    text = contextual_wording(expr)
    if mode == "number":
        text = text.replace("5", "6")
    elif mode == "missing_number":
        text = text.replace("5", "năm")
    elif mode == "contradiction":
        text = text.replace("phân biệt", "giống nhau")
    elif mode == "placeholder":
        text += " {unresolved}"
    elif mode == "copy":
        text = expr.source_text
    elif mode == "decorative":
        text = "Trong một sự kiện thú vị. " + expr.source_text
    elif mode == "shallow":
        text = "Có 5 loại cây phân biệt. Hỏi có bao nhiêu cách sắp xếp tất cả các loại cây thành một hàng?"
    elif mode == "formula":
        text += " Áp dụng công thức hoán vị."
    elif mode == "short":
        text = "5 người"
    raw = json.dumps({"question": text})
    if mode == "bad_json":
        raw = "not json"
    elif mode == "extra_answer":
        raw = json.dumps({"question": text, "answer": "120"})
    assert (
        QuestionValidator()
        .validate(expr, GenerationCandidate(model="mock", raw_response=raw))
        .status
        == "fail"
    )


def test_experimental_uncertainty_is_accepted_honestly_but_verified_path_remains_exact():
    expr = experimental_expression()
    # A changed contextual goal without known contradictory tokens may pass the
    # MVP checks. Explicitly exercise the accepted limitation; never call it proof.
    text = contextual_wording(expr).replace(
        "trước khi phải lặp một cách xếp", "để tìm ra cách xếp đẹp nhất"
    )
    result = QuestionValidator().validate(
        expr,
        GenerationCandidate(model="mock", raw_response=json.dumps({"question": text})),
    )
    assert result.status == "needs_review"
    instance = TemplateInstantiator().materialize(template(), {"n": 5})
    verified = ExpressionPlanner().plan_template_expression(
        instance, synthetic_registry(), eligible_index=1
    )
    result = QuestionValidator().validate(
        verified,
        GenerationCandidate(
            model="mock",
            raw_response=json.dumps({"question": contextual_wording(expr)}),
        ),
    )
    assert result.status == "fail"


def test_invalid_indirect_retries_keep_math_then_direct_fallback_records_rejection_reason():
    data = make_data()
    data._presentation_registry = TemplatePresentations(
        version="test", experimental_indirect=True
    )
    model = ExperimentalClient("invalid_indirect")
    service = ExamService(data, model)
    instance = TemplateInstantiator().materialize(template(), {"n": 5})
    candidate = service._word_template(
        instance, time.monotonic() + 30, expression=experimental_expression()
    )
    assert [e.generate_type for e, _ in model.calls] == [
        "indirect",
        "indirect",
        "direct",
    ]
    assert all(e.template_context.instance == instance.record for e, _ in model.calls)
    assert candidate.expression.generate_type == "direct"
    assert (
        candidate.expression.template_context.presentation.verification_status
        == "source_direct"
    )
    assert "numeric" in " ".join(candidate.validation.reasons)


def test_experimental_status_cannot_be_forged_as_verified_and_is_source_bound():
    expression = experimental_expression()
    record = expression.template_context.presentation
    value = record.model_dump()
    value["verification_status"] = "verified"
    with pytest.raises(ValidationError):
        TemplatePresentationRecord.model_validate(value)
    wrong = record.model_copy(update={"fingerprint": "0" * 64})
    with pytest.raises(ValueError):
        expression.template_context.registry.resolve(template(), wrong, "indirect")
    strict = TemplatePresentations(version="strict")
    with pytest.raises(ValueError, match="disabled"):
        strict.resolve(template(), record, "indirect")


@pytest.mark.parametrize("experimental", [False, True])
def test_qwen_nonzero_sampling_only_applies_to_experimental_path(
    monkeypatch, experimental
):
    captured = []
    model = QwenClient()
    expression = experimental_expression(ordinal=int(experimental))

    def fake_urlopen(request, **kwargs):
        captured.append(json.loads(request.data))
        return io.BytesIO(
            json.dumps(
                {
                    "done": True,
                    "model": model.model,
                    "response": json.dumps({"question": "Transport schema only"}),
                }
            ).encode()
        )

    monkeypatch.setattr("src.ai.qwen_client.urlopen", fake_urlopen)
    model.generate_one(expression, deadline=time.monotonic() + 5)
    assert captured[0]["options"]["temperature"] == (0.7 if experimental else 0)
    assert captured[0]["format"]["properties"] == {"question": {"type": "string"}}
    if experimental:
        assert captured[0]["options"]["seed"] != 42


@pytest.mark.parametrize("flag,expected", [(None, "1"), ("0", "0")])
def test_local_launcher_enables_experimental_by_default_and_respects_explicit_strict(
    monkeypatch, flag, expected
):
    from src.ui import __main__ as ui

    # Register cleanup even when the flag was initially absent: main() mutates
    # process environment through setdefault(), outside monkeypatch itself.
    monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", "0")
    monkeypatch.delenv("KORO_EXPERIMENTAL_INDIRECT", raising=False)
    if flag is not None:
        monkeypatch.setenv("KORO_EXPERIMENTAL_INDIRECT", flag)
    monkeypatch.setenv("API_TEACHER_TOKEN", "synthetic-test-token")
    monkeypatch.setattr("sys.argv", ["src.ui", "--no-browser"])
    captured = []
    monkeypatch.setattr(
        ui, "create_app", lambda **kwargs: captured.append(kwargs) or object()
    )

    class NoServer:
        def __init__(self, config):
            pass

        def run(self):
            pass

    monkeypatch.setattr(ui.uvicorn, "Server", NoServer)
    ui.main()
    import os

    assert os.environ["KORO_EXPERIMENTAL_INDIRECT"] == expected
    assert captured[0]["backend"] == "qwen"


def test_fake_demo_never_labels_unrewritten_direct_as_experimental_indirect():
    data = make_data()
    data._presentation_registry = TemplatePresentations(
        version="test", experimental_indirect=True
    )
    instance = TemplateInstantiator().materialize(template(), {"n": 5})
    expression = ExamService(data, None, fake=True)._expression(
        instance, eligible_index=1
    )
    assert expression.generate_type == "direct"


def test_legacy_verified_presentation_records_without_new_status_fields_still_resolve():
    definition = template()
    registry = synthetic_registry()
    for record in registry.options(definition):
        old = record.model_dump()
        old.pop("verification_status")
        old.pop("context_id")
        registry.resolve(
            definition,
            TemplatePresentationRecord.model_validate(old),
            record.generate_type,
        )


def test_successful_indirect_retry_retains_rejection_reason_and_same_parameters():
    from src.orchestration.question_generation import QuestionGenerationService

    class FirstWrong(ExperimentalClient):
        def generate_one(self, expression, **kwargs):
            candidate = super().generate_one(expression, **kwargs)
            if len(self.calls) == 1:
                candidate.raw_response = json.dumps(
                    {"question": contextual_wording(expression) + " Thêm 999 vật."}
                )
            return candidate

    model = FirstWrong()
    result = QuestionGenerationService(model).generate(
        experimental_expression(), deadline=time.monotonic() + 10
    )
    assert (
        result.expression.generate_type == "indirect"
        and result.validation.status == "needs_review"
    )
    assert "Wording attempt 1 rejected" in " ".join(result.validation.reasons)
    assert (
        model.calls[0][0].template_context.instance
        == model.calls[1][0].template_context.instance
    )
