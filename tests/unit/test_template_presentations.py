"""Synthetic author approvals exercise infrastructure, never approve SQL data."""

from copy import deepcopy
import json
import time

import pytest
from pydantic import ValidationError

from src.ai.contracts import ExpressionSpec, GenerationCandidate
from src.ai.expression_planner import ExpressionPlanner
from src.ai.prompts import build_prompt
from src.ai.template_instantiator import TemplateInstantiator, template_digest
from src.ai.template_presentations import TemplatePresentation, TemplatePresentations, validate_template_wording
from src.api.data_adapter import DEFAULT_BANK
from src.api.template_repository import load_templates
from src.orchestration.exam_service import ExamService
from src.validation.question_validator import QuestionValidator
from tests.integration.test_hybrid_exam_api import EchoTemplateClient
from tests.unit.test_hybrid_sources import template
from tests.unit.test_planner import make_data


def synthetic_presentation(definition, **changes):
    """TEST-ONLY mathematical/cognitive approval of a synthetic n! example."""
    value = dict(template_id=definition.template_id, presentation_id="synthetic_shelf",
        generate_type="indirect", pattern="Một thư viện có {n} quyển sách phân biệt. Người phụ trách đặt tất cả sách thành một hàng và lập danh sách mọi cách bố trí. Danh sách có bao nhiêu cách bố trí?",
        required_placeholders=["n"], permitted_context="Synthetic book display, one row, all books distinct.",
        mathematical_invariants=["All n distinct objects, all used, one ordered row; n!; no added restriction."],
        required_result="Number of arrangements of all n distinct objects.", source_digest=template_digest(definition),
        cognitive_level=definition.cognitive_level, verification_status="verified",
        verification_reference="SYNTHETIC TEST ONLY: bijection between object orders and shelf arrangements.",
        cognitive_level_preserved=True, cognitive_review_reference="SYNTHETIC TEST ONLY: same explicitly stated task.")
    value.update(changes)
    return TemplatePresentation.model_validate(value)


def synthetic_registry(definition=None, **changes):
    definition = definition or template()
    return TemplatePresentations(version="synthetic-tests-v1", presentations=[synthetic_presentation(definition, **changes)])


def expression(kind="indirect", definition=None, registry=None, n=5):
    definition = definition or template()
    registry = registry or synthetic_registry(definition)
    instance = TemplateInstantiator().materialize(definition, {"n": n})
    return ExpressionPlanner().plan_template_expression(instance, registry, eligible_index=int(kind == "indirect"))


def validate(expr, text=None):
    return QuestionValidator().validate(expr, GenerationCandidate(model="mock-local-qwen",
        raw_response=json.dumps({"question": expr.source_text if text is None else text})))


@pytest.mark.parametrize("level", [1, 2])
def test_both_levels_have_a_safe_explicit_direct_option_and_verified_indirect(level):
    definition = template(level=level)
    direct, indirect = expression("direct", definition), expression("indirect", definition)
    assert direct.generate_type == "direct" and indirect.generate_type == "indirect"
    assert direct.template_context.instance == indirect.template_context.instance
    assert direct.template_context.presentation.presentation_id == "sql_direct"
    assert direct.template_context.definition.cognitive_level == indirect.template_context.definition.cognitive_level


def test_direct_only_and_proposed_indirect_never_select_indirect():
    definition = template()
    registry = synthetic_registry(definition, verification_status="proposed")
    instance = TemplateInstantiator().materialize(definition, {"n": 5})
    for i in range(4):
        assert ExpressionPlanner().plan_template_expression(instance, registry, eligible_index=i).generate_type == "direct"
    with pytest.raises(ValueError, match="unverified"):
        registry.record(definition, registry.presentations[0])
    forged = expression().model_dump()
    forged["template_context"]["registry"]["presentations"][0]["verification_status"] = "proposed"
    with pytest.raises(ValidationError):
        ExpressionSpec.model_validate(forged)


@pytest.mark.parametrize("change", [
    {"verification_reference": None}, {"cognitive_review_reference": None}, {"cognitive_level_preserved": False},
    {"required_placeholders": []}, {"pattern": "Unsafe {n.__class__}"}, {"pattern": "Unsafe {n!r}"},
])
def test_verified_contract_requires_review_references_and_plain_complete_placeholders(change):
    with pytest.raises(ValidationError):
        synthetic_presentation(template(), **change)


@pytest.mark.parametrize("change", [
    {"source_digest": "0" * 64}, {"template_id": "OTHER"}, {"cognitive_level": "understanding"},
])
def test_other_source_rules_or_cognitive_review_cannot_be_reused(change):
    definition = template()
    registry = synthetic_registry(definition, **change)
    assert len(registry.options(definition)) == 1


def test_balanced_deterministic_mixture_rotates_multiple_verified_variants():
    definition = template()
    registry = synthetic_registry(definition)
    registry.presentations.append(synthetic_presentation(definition, presentation_id="synthetic_shelf_alternative",
        pattern="Có {n} cuốn sách phân biệt trong kho. Nhân viên trưng bày tất cả thành một hàng. Danh mục mọi cách trưng bày có bao nhiêu mục?"))
    instance = TemplateInstantiator().materialize(definition, {"n": 5})
    def choose():
        return [ExpressionPlanner().plan_template_expression(instance, registry, eligible_index=i) for i in range(8)]
    first = choose()
    assert [e.generate_type for e in first] == ["direct", "indirect"] * 4
    assert first == choose()
    assert {e.template_context.presentation.presentation_id for e in first if e.generate_type == "indirect"} == {
        "synthetic_shelf", "synthetic_shelf_alternative"}


@pytest.mark.parametrize("kind", ["direct", "indirect"])
def test_prompt_uses_selected_presentation_and_never_delegates_math(kind):
    expr = expression(kind)
    prompt = build_prompt(expr)
    assert f'"generate_type": "{kind}"' in prompt and f"Trình bày {kind}" in prompt
    assert "không đổi tham số" in prompt
    assert "không tính hay trả đáp án, lời giải" in prompt
    for secret in ["answer_rule", "solution_rule", "correct_answer", "verified_answer", "student_id", "verification_reference"]:
        assert secret not in prompt
    if kind == "indirect":
        assert "bối cảnh" in prompt and "mathematical_invariants" in prompt
        assert expr.template_context.definition.template_content not in prompt


@pytest.mark.parametrize("kind", ["direct", "indirect"])
def test_exact_verified_output_passes_without_requiring_original_direct_wording(kind):
    expr = expression(kind)
    assert validate(expr).status == "pass"
    if kind == "indirect":
        original = TemplateInstantiator().materialize(expr.template_context.definition, {"n": 5})
        assert original.content not in expr.source_text
        validate_template_wording(original, expr.source_text, kind, expr.template_context.presentation, expr.template_context.registry)


@pytest.mark.parametrize("mutate", [
    lambda s: s.replace("5", "6"),
    lambda s: s + " Hai sách phải đứng cạnh nhau.",  # Unknown keywords are STILL rejected.
    lambda s: s + " Chọn ít nhất một quyển.",
    lambda s: s.replace("phân biệt", "giống nhau"),
    lambda s: s.replace("tất cả sách", "sách"),
    lambda s: s.replace("một hàng", "hai hàng"),
    lambda s: s.replace("5", "{n}"),
    lambda s: s.replace("thư viện", "cửa hàng"),  # Plausible but NOT author-approved equivalence.
])
def test_detectable_changes_missing_conditions_and_uncertain_paraphrases_fail(mutate):
    expr = expression()
    assert validate(expr, mutate(expr.source_text)).status == "fail"


def test_unapproved_new_numeric_fact_in_pattern_is_rejected_before_model_call():
    registry = synthetic_registry(pattern="Có {n} quyển sách phân biệt và 99 ngăn. Có bao nhiêu cách đặt sách?")
    with pytest.raises(ValidationError, match="numerical"):
        expression(registry=registry)


@pytest.mark.parametrize("tamper", ["fingerprint", "type", "version", "revoke"])
def test_presentation_provenance_is_checked_against_current_registry(tamper):
    expr = expression()
    record = expr.template_context.presentation.model_copy(deep=True)
    registry = expr.template_context.registry.model_copy(deep=True)
    if tamper == "fingerprint":
        record.fingerprint = "0" * 64
    elif tamper == "type":
        record.generate_type = "direct"
    elif tamper == "version":
        registry.version = "new-review-version"
    else:
        registry.presentations[0].verification_status = "proposed"
    with pytest.raises(ValueError):
        registry.resolve(expr.template_context.definition, record, "indirect")


def test_indirect_retry_and_explicit_direct_fallback_keep_same_math_and_final_label():
    data = make_data()
    data._presentation_registry = synthetic_registry()

    class FailIndirect(EchoTemplateClient):
        def generate_one(self, expr, **kwargs):
            candidate = super().generate_one(expr, **kwargs)
            if expr.generate_type == "indirect":
                candidate.raw_response = json.dumps({"question": expr.source_text + " Hai sách phải đứng cạnh nhau."})
            return candidate

    model = FailIndirect()
    service = ExamService(data, model)
    expr = expression()
    instance = TemplateInstantiator().materialize(template(), {"n": 5})
    candidate = service._word_template(instance, time.monotonic() + 30, expression=expr)
    assert candidate.expression.generate_type == "direct"
    assert candidate.expression.template_context.presentation.generate_type == "direct"
    assert [e.generate_type for e, _ in model.calls] == ["indirect", "indirect", "direct"]
    assert all(e.template_context.instance == expr.template_context.instance for e, _ in model.calls)
    assert "fallback" in " ".join(candidate.validation.reasons)
    assert "semantic equivalence" in model.calls[1][1]["feedback"]


def test_actual_bank_has_no_fabricated_approved_indirect_and_only_inactive_proposals():
    registry = TemplatePresentations.load()
    assert len(registry.presentations) == 8
    assert all(p.verification_status == "proposed" for p in registry.presentations)
    assert all(p.verification_reference is None and not p.cognitive_level_preserved for p in registry.presentations)
    for definition in load_templates(DEFAULT_BANK)[0]:
        assert [r.generate_type for r in registry.options(definition)] == ["direct"]


def test_duplicate_ids_and_cross_template_or_indirect_legacy_claims_are_rejected():
    registry = synthetic_registry()
    value = registry.model_dump()
    value["presentations"].append(deepcopy(value["presentations"][0]))
    with pytest.raises(ValidationError, match="Duplicate"):
        TemplatePresentations.model_validate(value)
    with pytest.raises(ValueError, match="provenance"):
        registry.resolve(template(), None, "indirect")


def test_multiple_direct_variants_can_rotate_without_requiring_indirect():
    definition = template()
    registry = synthetic_registry(definition, generate_type="direct")
    instance = TemplateInstantiator().materialize(definition, {"n": 5})
    expressions = [ExpressionPlanner().plan_template_expression(instance, registry, variant_index=i) for i in range(2)]
    assert [e.generate_type for e in expressions] == ["direct", "direct"]
    assert len({e.template_context.presentation.presentation_id for e in expressions}) == 2
