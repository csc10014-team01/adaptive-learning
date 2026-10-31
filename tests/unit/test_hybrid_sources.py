"""SQL-authored mappings, safe formula interpretation and hybrid capacity tests."""

from copy import deepcopy
import hashlib
import json
from math import factorial

import pytest

from src.adaptation.contracts import AllocationPlan
from src.adaptation.planner import RuleBasedPlanner
from src.adaptation.source_selector import SourceSelector
from src.ai.contracts import GenerationCandidate
from src.ai.prompts import build_prompt
from src.ai.template_instantiator import TemplateDefinition, TemplateInstantiator
from src.api.data_adapter import ApiFailure, DEFAULT_BANK
from src.api.m3_adapter import M3DataAdapter
from src.api.template_repository import load_templates
from src.api.schemas import LEVELS
from src.orchestration.exam_service import ExamService
from src.validation.question_validator import QuestionValidator
from tests.unit.test_planner import make_data, profile, question, request


def template(tid="TEST_FORMULA", skills=("A001",), level=1, **changes):
    values = dict(template_id=tid, template_content="Có {n} phần tử phân biệt. Hỏi có bao nhiêu cách sắp xếp tất cả các phần tử thành một hàng?",
        parameter_rules={"n": {"type": "integer", "min": 2, "max": 12}},
        answer_rule="P(n) = n!", solution_rule="Áp dụng quy tắc nhân, số cách sắp xếp là n!.",
        difficulty=level, skill_ids=list(skills), grade_level=10, topic_id="combinatorics")
    values.update(changes)
    return TemplateDefinition(**values)


def allocation(cells):
    skills = sorted(cells)
    rows = {s: dict(zip(LEVELS, values)) for s, values in cells.items()}
    return AllocationPlan(strategy="advanced_review", focus=[], groups={"advanced_review": skills},
        group_counts={"advanced_review": sum(map(sum, cells.values()))},
        skill_counts={s: sum(values) for s, values in cells.items()}, weights={s: (25, 35, 30, 10) for s in skills},
        skill_levels=rows, levels={lv: sum(row[lv] for row in rows.values()) for lv in LEVELS})


def select(cells, templates=(), bank=()):
    warnings = []
    selected, _ = SourceSelector().select(list(bank), list(templates), allocation(cells), False, set(), warnings)
    return selected, warnings


def test_actual_sql_schema_and_verified_links_are_loaded_without_writes():
    before = hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest()
    templates, warnings = load_templates(DEFAULT_BANK)
    assert len(templates) == 18 and not warnings
    assert len(M3DataAdapter().topic.skills) == 9
    first = next(t for t in templates if t.template_id == "EA0001")
    assert first.skill_ids == ["A001"]
    assert next(t for t in templates if t.template_id == "EA0004").skill_ids == ["A002", "A009"]
    assert first.parameter_rules["counts"]["type"] == "array"
    assert sum(t.difficulty == 1 for t in templates) == 7
    assert sum(t.difficulty == 2 for t in templates) == 7
    assert sum(t.difficulty == 3 for t in templates) == 4
    assert hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("mutation", ["missing_links", "invalid_skill", "bad_json", "wrong_scope"])
def test_incomplete_sql_metadata_is_excluded_with_a_reason(tmp_path, mutation):
    import shutil
    import sqlite3
    path = tmp_path / "isolated.db"
    shutil.copyfile(DEFAULT_BANK, path)
    with sqlite3.connect(path) as c:
        if mutation == "missing_links":
            c.execute("DROP TABLE question_template_skills")
        elif mutation == "invalid_skill":
            c.execute("UPDATE question_template_skills SET skill_id='BAD' WHERE template_id='EA0001'")
        elif mutation == "bad_json":
            c.execute("UPDATE question_templates SET parameter_rules='[]' WHERE template_id='EA0001'")
        else:
            c.execute("UPDATE skills SET grade_level=11 WHERE skill_id='A001'")
    templates, warnings = load_templates(path)
    assert not any(t.template_id == "EA0001" for t in templates)
    assert warnings


@pytest.mark.parametrize("tid,parameters,answer", [
    ("EA0001", {"counts": [3, 5, 7]}, 15),
    ("EA0002", {"n": 3, "counts": [3, 5, 7]}, 15),
    ("EA0004", {"n": 5, "condition": "Hai người được chọn không thuộc cùng cặp đôi"}, 20),
    ("EA0012", {"n": 5, "pair_order_matters": False}, 10),
    ("EA0013", {"team_count": 5, "matches_per_pair": 2}, 20),
    ("EA0015", {"vertex_count": 5, "ordered_pair": True, "same_vertex_allowed": False,
        "counting_unit": "Cặp đỉnh có thứ tự, không gộp các vectơ hình học bằng nhau"}, 20),
    ("EA0017", {"n": 5, "arrange_all": True, "distinct": True}, 120),
    ("EA0018", {"n": 5, "restricted_pair_count": 2, "adjacent_forbidden": True, "people_distinct": True}, 72),
])
def test_actual_explicit_formulas_compute_independent_answers_and_solutions(tid, parameters, answer):
    definition = next(t for t in load_templates(DEFAULT_BANK)[0] if t.template_id == tid)
    instance = TemplateInstantiator().materialize(definition, parameters)
    assert instance.answer.correct_answer == str(answer)
    assert instance.solution_steps[0] == definition.solution_rule
    assert str(answer) in instance.solution_steps[-1]
    assert "{" not in instance.content and "}" not in instance.content


@pytest.mark.parametrize("tid", ["EA0003", "EA0007", "EA0008", "EA0009", "EA0010", "EA0011"])
def test_inconsistent_or_descriptive_rules_remain_unsupported(tid):
    definition = next(t for t in load_templates(DEFAULT_BANK)[0] if t.template_id == tid)
    with pytest.raises(ValueError):
        TemplateInstantiator().instances(definition, 1)


@pytest.mark.parametrize("rule", [
    "N = __import__('os').system('anything')", "N = open('anything')", "N = n.__class__",
    "N = [x for x in counts]", "N = 1 / 0", "N = -1", "N = 1 = 2", "N = n ** 9999999",
])
def test_untrusted_rule_strings_are_never_executed(rule):
    with pytest.raises((ValueError, SyntaxError)):
        TemplateInstantiator().instances(template(answer_rule=rule), 1)


@pytest.mark.parametrize("parameters", [{"n": True}, {"n": -1}, {"n": 13}, {"n": 2.0}, {"n": 3, "injected": 1}, {}])
def test_parameter_validation_rejects_wrong_types_bounds_and_extra_values(parameters):
    with pytest.raises(ValueError):
        TemplateInstantiator().materialize(template(), parameters)


def test_instances_are_bounded_deterministic_and_mathematically_unique():
    engine = TemplateInstantiator()
    first = engine.instances(template(), 10)
    assert len(first) == 10
    assert [x.record for x in engine.instances(template(), 10)] == [x.record for x in first]
    assert len({x.record.signature for x in first}) == 10
    assert all(int(x.answer.correct_answer) == factorial(x.record.parameters["n"]) for x in first)
    assert engine.instances(template(), 1, excluded={x.record.signature for x in first})


def test_commutative_group_reordering_does_not_create_a_new_mathematical_instance():
    definition = next(t for t in load_templates(DEFAULT_BANK)[0] if t.template_id == "EA0001")
    engine = TemplateInstantiator()
    assert engine.materialize(definition, {"counts": [3, 5, 7]}).record.signature == engine.materialize(
        definition, {"counts": [7, 3, 5]}).record.signature


def test_declared_unique_arrays_generate_distinct_in_range_values():
    definition = template(template_content="Có các nhóm phân biệt với số lượng {counts}. Chọn một đối tượng. Có bao nhiêu cách?",
        parameter_rules={"counts": {"type": "array", "length": 4, "unique_items": True,
                                   "items": {"type": "integer", "min": 0, "max": 6}}},
        answer_rule="N = sum(counts)")
    instances = TemplateInstantiator().instances(definition, 3)
    assert len(instances) == 3
    for item in instances:
        assert len(set(item.record.parameters["counts"])) == 4
        assert item.answer.correct_answer == str(sum(item.record.parameters["counts"]))


def test_nonintegral_counts_are_rejected_and_parameter_sampling_retries_with_a_bound():
    definition = template(template_content="Chia {n} vật thành hai nhóm bằng nhau. Mỗi nhóm có bao nhiêu vật?",
                          answer_rule="N = n / 2", solution_rule="Chia số vật cho 2.")
    instances = TemplateInstantiator().instances(definition, 3)
    assert len(instances) == 3
    assert all(i.record.parameters["n"] % 2 == 0 for i in instances)
    assert all(int(i.answer.correct_answer) * 2 == i.record.parameters["n"] for i in instances)


@pytest.mark.parametrize("level", [0, 1])
def test_l1_l2_prefer_an_exact_template_over_an_exact_question(level):
    cells = {"A001": tuple(int(i == level) for i in range(4))}
    selected, _ = select(cells, [template(level=level + 1)], [question(level=LEVELS[level])])
    assert selected[0].source_kind == "template"
    assert selected[0].primary_skill_id == "A001" and selected[0].cognitive_level == LEVELS[level]


@pytest.mark.parametrize("level", [2, 3])
def test_l3_l4_never_use_templates(level):
    cells = {"A001": tuple(int(i == level) for i in range(4))}
    selected, _ = select(cells, [template(level=level + 1)], [question(level=LEVELS[level])])
    assert selected[0].source_kind == "question"
    with pytest.raises(ApiFailure) as error:
        select(cells, [template(level=level + 1)])
    assert error.value.code == "INSUFFICIENT_QUESTION_BANK"


def test_wrong_skill_or_unsupported_template_uses_question_fallback():
    for definition in [template(skills=("A002",)), template(answer_rule="descriptive count")]:
        selected, warnings = select({"A001": (1, 0, 0, 0)}, [definition], [question()])
        assert selected[0].source_kind == "question" and warnings


@pytest.mark.parametrize("change", [{"grade_level": 11}, {"topic_id": "other"}])
def test_template_scope_is_checked_before_selection(change):
    data = make_data(bank=[question(level="understanding")])
    data._templates = [template(level=2).model_copy(update=change)]
    planned = RuleBasedPlanner(data).plan(request(1), profile())
    assert planned.questions[0].source_kind == "question"


def test_shared_template_capacity_reserves_the_only_question_for_the_other_skill():
    fixed = template(skills=("A001", "A002"), parameter_rules={"n": {"type": "integer", "value": 2, "min": 2, "max": 2}})
    selected, _ = select({"A001": (1, 0, 0, 0), "A002": (1, 0, 0, 0)}, [fixed], [question()])
    assert [(s.source_kind, s.primary_skill_id) for s in selected] == [("question", "A001"), ("template", "A002")]


def test_reuse_of_a_template_requires_different_parameters_and_prefers_id_diversity():
    selected, _ = select({"A001": (3, 0, 0, 0)}, [template("T1"), template("T2")])
    assert {s.source_id for s in selected} == {"T1", "T2"}
    assert len({s.instance.record.signature for s in selected}) == 3
    assert len({s.instance.record.instance_id for s in selected}) == 3


def test_template_prompt_excludes_answers_and_validation_rejects_math_changes():
    source = TemplateInstantiator().instances(template(), 1)[0]
    service = ExamService(make_data(), None, fake=True)
    expression = service._expression(source)
    prompt = build_prompt(expression)
    for secret in ["answer_rule", "solution_rule", "correct_answer", "student_id", "verified_answer"]:
        assert secret not in prompt
    candidate = GenerationCandidate(model="mock", raw_response=json.dumps({"question": source.content}))
    assert QuestionValidator().validate(expression, candidate).status == "pass"
    for text in [source.content + " Thêm 999 đối tượng.", source.content.replace("phân biệt", "giống nhau"),
                 source.content.replace("tất cả các phần tử", "một số phần tử")]:
        changed = candidate.model_copy(update={"raw_response": json.dumps({"question": text})})
        assert QuestionValidator().validate(expression, changed).status == "fail"
    assert source.record.parameters == deepcopy(source.record.parameters)
