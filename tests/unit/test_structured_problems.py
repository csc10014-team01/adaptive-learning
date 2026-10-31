"""Synthetic, author-supplied metadata; no facts inferred from the M3 bank."""

import hashlib
import json
import time
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.ai.contracts import ExpressionSpec, GenerationCandidate
from src.ai.expression_planner import ExpressionPlanner
from src.ai.problem_spec import ProblemSpec, render_template
from src.ai.prompts import build_prompt
from src.api.data_adapter import FixtureQuestion
from src.orchestration.question_generation import QuestionGenerationService
from src.orchestration.source_snapshot import source_digest
from src.validation.math_validator import near_duplicate, verified_count
from src.validation.question_validator import QuestionValidator
from tests.unit.test_planner import question

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/structured_problem.json"


def structured_source():
    spec = ProblemSpec.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    return question(
        question_id=spec.source_id,
        problem_spec=spec,
        content=render_template(
            spec.supported_contexts[0].presentations[0].template, spec.parameters
        ),
        answer={
            "correct_answer": spec.verified_answer,
            "explanation": " ".join(spec.verified_solution),
        },
        solution_steps=spec.verified_solution,
    )


def validate(expression, text):
    return QuestionValidator().validate(
        expression,
        GenerationCandidate(raw_response=json.dumps({"question": text}), model="mock"),
    )


def test_legacy_path_and_old_source_fingerprints_are_preserved():
    source = question()
    expression = ExpressionPlanner().plan_expression(source)
    assert expression.generate_type == "direct" and expression.problem_spec is None
    old = source.model_dump(mode="json", exclude={"problem_spec"})
    digest = hashlib.sha256(
        json.dumps(old, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert digest == source_digest(source)
    for kwargs in [{"generate_type": "indirect"}, {"context_id": "books"}]:
        with pytest.raises(ValueError, match="verified"):
            ExpressionPlanner().plan_expression(source, **kwargs)


@pytest.mark.parametrize("status", ["NO_DATA", "PARTIAL", "WEAK", "ACHIEVED"])
def test_adaptive_legacy_wording_never_infers_mathematics_or_indirect_equivalence(
    status,
):
    source = question(level="recognition")
    expression = ExpressionPlanner().plan_adaptive_expression(
        source, status=status, achieved_index=1
    )
    assert (
        expression.generate_type == "direct"
        and expression.context_policy == "preserve_source"
    )
    assert expression.source_text == source.content and expression.problem_spec is None


@pytest.mark.parametrize(
    "level", ["recognition", "understanding", "application", "advanced_application"]
)
def test_verified_achieved_presentations_alternate_independently_of_cognitive_level(
    level,
):
    source = structured_source()
    source.cognitive_level = level
    before = source.model_dump_json()
    planner = ExpressionPlanner()
    expressions = [
        planner.plan_adaptive_expression(source, status="ACHIEVED", achieved_index=i)
        for i in range(2)
    ]
    assert [e.generate_type for e in expressions] == ["direct", "indirect"]
    assert all(
        e.problem_spec == source.problem_spec
        and e.context_id == source.problem_spec.source_context_id
        for e in expressions
    )
    assert all(validate(e, e.source_text).status == "pass" for e in expressions)
    assert (
        planner.plan_adaptive_expression(
            source, status="WEAK", achieved_index=1
        ).generate_type
        == "direct"
    )
    assert source.model_dump_json() == before


def test_adaptive_achieved_expression_without_an_authored_indirect_variant_stays_direct():
    source = structured_source()
    for context in source.problem_spec.supported_contexts:
        context.presentations = [
            p for p in context.presentations if p.generate_type == "direct"
        ]
    expression = ExpressionPlanner().plan_adaptive_expression(
        source, status="ACHIEVED", achieved_index=1
    )
    assert (
        expression.generate_type == "direct"
        and expression.source_text == source.content
    )


@pytest.mark.parametrize(
    "context,kind",
    [("students", "direct"), ("students", "indirect"), ("books", "direct")],
)
def test_verified_compatible_expressions_keep_math_and_independent_answer(
    context, kind
):
    source = structured_source()
    expression = ExpressionPlanner().plan_expression(
        source, context_id=context, generate_type=kind
    )
    assert (
        expression.generate_type == kind
        and expression.problem_spec == source.problem_spec
    )
    assert expression.context_policy == (
        "preserve_source" if context == "students" else "verified_context"
    )
    assert verified_count(expression.problem_spec) == 56
    assert validate(expression, expression.source_text).status == "pass"


@pytest.mark.parametrize(
    "kwargs",
    [{"context_id": "cards"}, {"context_id": "books", "generate_type": "indirect"}],
)
def test_incompatible_context_or_expression_rejected(kwargs):
    with pytest.raises(ValueError, match="compatible"):
        ExpressionPlanner().plan_expression(structured_source(), **kwargs)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda x: x.update(verification_status="unverified"),
        lambda x: x["constraints"].update(order_matters=True),
        lambda x: x["constraints"].update(replacement_allowed=True),
        lambda x: x["parameters"].update(k=9),
        lambda x: x["parameters"].update(n=True),
        lambda x: x["parameters"].update(n=101),
        lambda x: x["supported_contexts"].append(deepcopy(x["supported_contexts"][0])),
        lambda x: x["supported_contexts"][0]["presentations"][0].update(
            template="Use {n.__class__} and {k}"
        ),
        lambda x: x["supported_contexts"][0]["presentations"][0].update(
            template="Use {n} only"
        ),
    ],
)
def test_invalid_structured_metadata_is_not_accepted(mutation):
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mutation(value)
    with pytest.raises((ValidationError, ValueError)):
        ProblemSpec.model_validate(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("question_id", "wrong"),
        ("answer", {"correct_answer": "57", "explanation": "Wrong"}),
        ("solution_steps", ["Changed"]),
        ("content", "Nội dung không khớp nguồn đã kiểm chứng"),
    ],
)
def test_structured_source_metadata_must_agree(field, value):
    source = structured_source().model_dump()
    source[field] = value
    with pytest.raises(ValidationError, match="ProblemSpec"):
        FixtureQuestion.model_validate(source)


@pytest.mark.parametrize(
    "change",
    [
        lambda t: t.replace("8", "9"),
        lambda t: t.replace("không xét thứ tự", "có xét thứ tự"),
        lambda t: t.replace("không hoàn lại", "có hoàn lại"),
        lambda t: t.replace("phân biệt", "giống nhau"),
        lambda t: t.replace(" và không hoàn lại", ""),
        lambda t: t + " Nhóm có ít nhất một học sinh nam.",
        lambda t: t + " Nhóm có số chẵn học sinh nam.",
    ],
)
def test_changed_numbers_removed_conditions_and_added_constraints_fail(change):
    expression = ExpressionPlanner().plan_expression(structured_source())
    result = validate(expression, change(expression.source_text))
    assert result.status == "fail" and result.question is None


def test_indirect_requirements_and_context_are_validated():
    expression = ExpressionPlanner().plan_expression(
        structured_source(), generate_type="indirect"
    )
    assert (
        validate(
            expression,
            expression.source_text.replace(
                "Hãy xác định số nhóm trong danh sách", "Có bao nhiêu nhóm"
            ),
        ).status
        == "fail"
    )
    books = ExpressionPlanner().plan_expression(structured_source(), context_id="books")
    assert (
        validate(books, books.source_text.replace("quyển sách", "học sinh")).status
        == "fail"
    )


def test_paraphrase_unknown_semantics_and_source_answer_errors_never_pass():
    expression = ExpressionPlanner().plan_expression(structured_source())
    # An arbitrary extra prose condition cannot be certified from numeric facts.
    assert (
        validate(
            expression, expression.source_text + " Các thành viên phải thân thiết."
        ).status
        == "needs_review"
    )
    wrong = expression.model_dump()
    wrong["problem_spec"]["verified_answer"] = "57"
    expression = ExpressionSpec.model_validate(wrong)
    assert validate(expression, expression.source_text).status == "fail"


@pytest.mark.parametrize(
    "structure,replacement,n,k,answer",
    [
        ("combination", False, 8, 3, 56),
        ("arrangement", False, 8, 3, 336),
        ("arrangement", True, 8, 3, 512),
        ("permutation", False, 5, None, 120),
        ("combination", False, 1, 0, 1),
        ("arrangement", True, 100, 100, 100**100),
    ],
)
def test_independent_supported_operations(structure, replacement, n, k, answer):
    value = structured_source().problem_spec.model_dump()
    value.update(
        mathematical_structure=structure,
        parameters={"n": n, "k": k},
        verified_answer=str(answer),
        constraints={
            "order_matters": structure != "combination",
            "replacement_allowed": replacement,
        },
    )
    # This test supplies a separately authored minimal statement for each operation.
    value["supported_contexts"] = [
        {
            "context_id": "students",
            "presentations": [
                {
                    "generate_type": "direct",
                    "template": "Bài toán kiểm thử có {n} phần tử"
                    + (" và chọn {k} phần tử." if k is not None else "."),
                    "required_phrases": ["phần tử"],
                }
            ],
        }
    ]
    assert verified_count(ProblemSpec.model_validate(value)) == answer


def test_prompt_uses_presentation_without_disclosing_answers_solutions_or_identity():
    expression = ExpressionPlanner().plan_expression(
        structured_source(), context_id="books"
    )
    prompt = build_prompt(expression)
    data = json.loads(prompt.split("DỮ LIỆU NGUỒN:\n")[1])
    assert data["parameters"] == {"n": 8, "k": 3} and data["context_id"] == "books"
    assert (
        data["generate_type"] == "direct"
        and data["constraints"]["replacement_allowed"] is False
    )
    for secret in [
        "verified_answer",
        "verified_solution",
        "verification_reference",
        "student_id",
        "56",
    ]:
        assert secret not in prompt


def test_structured_retry_rejects_definite_constraint_change_then_accepts():
    expression = ExpressionPlanner().plan_expression(structured_source())

    class Client:
        model = "mock"
        attempts = 2

        def __init__(self):
            self.calls = []

        def generate_one(self, content, **kwargs):
            assert isinstance(content, ExpressionSpec)
            self.calls.append(kwargs)
            text = (
                content.source_text
                if len(self.calls) == 2
                else content.source_text.replace("không hoàn lại", "có hoàn lại")
            )
            return GenerationCandidate(
                raw_response=json.dumps({"question": text}), model=self.model
            )

    client = Client()
    result = QuestionGenerationService(client).generate(
        expression, deadline=time.monotonic() + 10
    )
    assert result.validation.status == "pass" and len(client.calls) == 2
    assert "constraint" in client.calls[1]["feedback"]


def test_legacy_explicit_constraint_flip_fails_but_unknown_equivalence_needs_review():
    text = "Chọn 3 học sinh trong 8 học sinh, không xét thứ tự và không hoàn lại. Có bao nhiêu cách?"
    expression = ExpressionSpec(source_id="legacy", source_text=text)
    assert (
        validate(expression, text.replace("không xét thứ tự", "có xét thứ tự")).status
        == "fail"
    )
    assert (
        validate(expression, text.replace("không hoàn lại", "có hoàn lại")).status
        == "fail"
    )
    assert (
        validate(expression, text.replace(" và không hoàn lại", "")).status
        == "needs_review"
    )


def test_duplicate_detection_distinguishes_changed_parameters():
    text = ExpressionPlanner().plan_expression(structured_source()).source_text
    assert near_duplicate(text, "  " + text.upper())
    assert near_duplicate(text, text.replace("Có bao nhiêu", "Hỏi có bao nhiêu"))
    assert not near_duplicate(text, text.replace("8", "9"))
