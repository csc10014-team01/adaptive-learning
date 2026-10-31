"""Final integrity checks protect the blueprint boundary without redoing math."""

from copy import deepcopy

import pytest

from src.adaptation.planner import RuleBasedPlanner
from src.ai.contracts import ValidatedQuestion, ValidationResult
from src.ai.expression_planner import ExpressionPlanner
from src.api.data_adapter import ApiFailure
from src.orchestration.exam_assembler import ExamAssembler
from tests.unit.test_planner import make_data, profile, request
from tests.unit.test_structured_problems import structured_source


def inputs():
    data = make_data()
    student, req = profile(), request(4)
    plan = RuleBasedPlanner(data).plan(req, student)
    sources = {s.question_id: s for s in data.questions}
    candidates = []
    for index, slot in enumerate(plan.questions):
        source = sources[slot.source_id]
        source.content = (
            f"Nội dung câu kiểm thử thứ {index + 1}, dùng để kiểm tra lắp đề."
        )
        expression = ExpressionPlanner().plan_expression(source)
        candidates.append(
            ValidatedQuestion(
                expression=expression,
                content=expression.source_text,
                validation=ValidationResult(
                    status="needs_review",
                    question=expression.source_text,
                    reasons=["Review"],
                ),
            )
        )
    return req, student, plan, sources, candidates


def assemble(values):
    return ExamAssembler().assemble(*values, model="mock")


def test_complete_assembly_preserves_order_sources_answers_and_scores():
    values = inputs()
    exam = assemble(values)
    assert exam.status == "pending_teacher_review" and exam.teacher_review is None
    assert [q.order_index for q in exam.questions] == [1, 2, 3, 4]
    assert [q.source_ref.id for q in exam.questions] == [
        q.source_id for q in values[2].questions
    ]
    assert all(
        q.answer == values[3][q.source_ref.id].answer and q.source_digest
        for q in exam.questions
    )
    assert sum(q.max_score for q in exam.questions) == 10


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v[4].pop(),
        lambda v: v[2].questions.pop(),
        lambda v: v[2].questions.__setitem__(1, deepcopy(v[2].questions[0])),
        lambda v: v[2].questions[0].__setattr__("target_skill_id", "A004"),
        lambda v: v[2].questions[0].__setattr__("skill_ids", ["A004"]),
        lambda v: (
            v[2].questions[0].__setattr__("cognitive_level", "advanced_application")
        ),
        lambda v: v[3].pop(v[2].questions[0].source_id),
        lambda v: v[2].quota_summary.achieved_groups.update(diagnostic=99),
        lambda v: v[2].quota_summary.achieved_skills.update(A001=99),
        lambda v: v[2].quota_summary.achieved_levels.update(recognition=99),
        lambda v: (
            v[2].quota_summary.achieved_skill_levels["A001"].update(recognition=99)
        ),
        lambda v: v[4][0].__setattr__("content", "Unchecked replacement content"),
        lambda v: v[4][0].validation.__setattr__("status", "fail"),
        lambda v: v[4][0].expression.__setattr__("source_id", "wrong"),
    ],
)
def test_corrupted_or_incomplete_blueprint_is_never_assembled(change):
    values = inputs()
    change(values)
    with pytest.raises(ApiFailure) as error:
        assemble(values)
    assert error.value.code == "EXAM_INTEGRITY_FAILED"


def test_teacher_level_lock_is_checked_against_selected_blueprint():
    values = list(inputs())
    values[0] = request(
        4,
        difficulty_distribution={
            "recognition": 0,
            "understanding": 0,
            "application": 0,
            "advanced_application": 100,
        },
    )
    values[2].difficulty_locked = True
    with pytest.raises(ApiFailure, match="teacher-locked"):
        assemble(values)


def test_duplicate_wording_is_flagged_while_source_uniqueness_is_enforced():
    values = inputs()
    first, second = values[4][:2]
    second.content = first.content
    second.validation.question = first.content
    # Duplicate wording can exist in two immutable bank records. Align the
    # stored source too; generated text alone may no longer rewrite a Question.
    second.expression.source_text = first.content
    values[3][values[2].questions[1].source_id].content = first.content
    exam = assemble(values)
    assert any(
        "duplicate" in note for note in exam.questions[1].validation.review_notes
    )
    assert exam.questions[1].validation.auto_status == "needs_review"


def test_structured_reference_solution_steps_are_all_preserved():
    source = structured_source()
    data = make_data(bank=[source])
    req, student = request(1), profile()
    plan = RuleBasedPlanner(data).plan(req, student)
    expression = ExpressionPlanner().plan_expression(source)
    candidate = ValidatedQuestion(
        expression=expression,
        content=expression.source_text,
        validation=ValidationResult(
            status="pass", question=expression.source_text, reasons=["Fixture verified"]
        ),
    )
    exam = assemble((req, student, plan, {source.question_id: source}, [candidate]))
    assert [
        s.explanation for s in exam.questions[0].step_solutions
    ] == source.problem_spec.verified_solution
    assert sum(s.score for s in exam.questions[0].step_solutions) == 10
    # Rubric and source metadata still require teacher acceptance.
    assert exam.questions[0].validation.auto_status == "needs_review"
