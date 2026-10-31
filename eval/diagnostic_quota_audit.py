"""Read-only, reproducible replay of the 5/2/3/0 diagnostic discrepancy.

Run from the application root: python -m eval.diagnostic_quota_audit
The old objective is replayed explicitly, without changing production policy.
Only the JSON report is written; no SQLite database is opened for writing.
"""

from collections import Counter
import hashlib
import json

from src.adaptation.planner import RuleBasedPlanner
from src.adaptation.source_selector import SourceSelector, Unit
from src.ai.template_instantiator import TemplateInstantiator
from src.api.data_adapter import DEFAULT_BANK, ROOT, StaticDataAdapter
from src.api.m3_adapter import M3DataAdapter, readonly
from src.api.schemas import LEVELS, GenerateExamRequest


def replay_old_priority(bank, templates, allocation, seed):
    """Former hybrid exact-DP cost: changed cell, skill, distance, ... ."""
    n = sum(allocation.levels.values())
    group_for = {s: g for g, members in allocation.groups.items() for s in members}
    slots = [(s, lv) for s, row in allocation.skill_levels.items() for lv in LEVELS for _ in range(row[lv])]
    units, template_audit = [], []
    for definition in sorted(templates, key=lambda t: t.template_id):
        detail = dict(id=definition.template_id, skills=definition.skill_ids, level=definition.cognitive_level)
        try:
            if definition.difficulty not in (1, 2):
                raise ValueError("MVP permits templates only at L1/L2")
            instances = TemplateInstantiator().instances(definition, n, seed=seed)
            detail.update(prepared_instances=len(instances), eligible=True,
                has_requested_cell=any((s, definition.cognitive_level) in slots for s in definition.skill_ids))
            units.extend(Unit("template", definition.template_id, definition.skill_ids,
                definition.cognitive_level, i, instance) for i, instance in enumerate(instances))
        except (ValueError, SyntaxError, TypeError, KeyError, OverflowError) as exc:
            detail.update(eligible=False, reason=str(exc))
        template_audit.append(detail)
    units.extend(Unit("question", q.question_id, [q.primary_skill_id], q.cognitive_level) for q in bank
        if q.cognitive_level not in allocation.forbidden_levels.get(q.primary_skill_id, [])
        and not (q.cognitive_level == LEVELS[3] and allocation.weights[q.primary_skill_id][3] == 0))
    edges, base = {}, 20 * n + 1
    for ui, unit in enumerate(units):
        for si, (skill, level) in enumerate(slots):
            actual = skill if unit.kind == "template" else unit.skills[0]
            delta = LEVELS.index(unit.level) - LEVELS.index(level)
            if actual not in group_for:
                continue
            if unit.kind == "template" and (skill not in unit.skills or delta):
                continue
            if unit.kind == "question" and delta > 1:
                continue
            cost = 0
            for digit in (int(actual != skill or delta != 0), int(actual != skill), abs(delta),
                          int(delta > 0), int(group_for[actual] != group_for[skill]),
                          int(unit.kind == "question" and level in LEVELS[:2]), unit.ordinal, 0):
                cost = cost * base + digit
            edges[ui, si] = cost, actual, group_for[actual]
    chosen = SourceSelector()._fallback(units, slots, edges, allocation)
    rows = []
    for si, (skill, level) in enumerate(slots):
        unit, actual = units[chosen[si]], edges[chosen[si], si][1]
        reason = "exact cell matched"
        if (skill, level) != (actual, unit.level):
            reason = ("requested cell unavailable; old cost prefers same skill over difficulty"
                      if skill == actual else "requested cell unavailable; same-level skill fallback")
        rows.append(dict(slot=si + 1, requested_skill=skill, requested_level=level,
            actual_skill=actual, actual_level=unit.level, source_kind=unit.kind,
            source_id=unit.identifier, reason=reason))
    return rows, template_audit


def main():
    before = hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest()
    data = M3DataAdapter(bank_path=DEFAULT_BANK)
    planner = RuleBasedPlanner(data)
    request = GenerateExamRequest(student_id="ST011", selected_topic_ids=["combinatorics"],
                                  total_questions=10, duration_minutes=45)
    student = data.get_profile(request.student_id)
    allocation = planner.build_allocation_plan(request, student)
    _, bank, skills, _ = planner._validate(request, student)
    old, templates = replay_old_priority(bank, data.templates, allocation, seed=0)
    old_counts = Counter(row["actual_level"] for row in old)
    assert [old_counts[lv] for lv in LEVELS] == [5, 2, 3, 0]
    plan = planner.plan(request, student, seed=0)
    assert plan.quota_summary.achieved_levels == allocation.levels
    with readonly(DEFAULT_BANK) as connection:
        raw_counts = dict(connection.execute("SELECT difficulty, COUNT(*) FROM questions GROUP BY difficulty"))
        sql_counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                      for table in ("questions", "question_templates", "skills")}
    substitutes = {x.slot: x.model_dump() for x in plan.selection_diagnostics.substitutions}
    new = []
    for old_row, source in zip(old, plan.questions):
        slot = old_row["slot"]
        new.append(dict(slot=slot, requested_skill=old_row["requested_skill"],
            requested_level=old_row["requested_level"], actual_skill=source.target_skill_id,
            actual_level=source.cognitive_level, source_kind=source.source_kind, source_id=source.source_id,
            reason=substitutes[slot]["reason"] if slot in substitutes else "exact cell matched"))
    scarcity = {}
    for missing in (LEVELS[1], LEVELS[3]):
        isolated = StaticDataAdapter(bank_path=DEFAULT_BANK)
        isolated._topic = data.topic
        isolated._questions = [q for q in data.questions if q.cognitive_level != missing]
        isolated._templates = [t for t in data.templates if t.cognitive_level != missing]
        case = RuleBasedPlanner(isolated).plan(request, student)
        scarcity[missing] = dict(quotas=case.quota_summary.model_dump(),
            diagnostics=case.selection_diagnostics.model_dump(), warnings=case.warnings)
    after = hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest()
    assert before == after
    output = dict(database=str(DEFAULT_BANK), requested_path_exists=(ROOT.parents[1] /
        "pre-work/data/sample/questionbank.db").exists(), sha256_before=before, sha256_after=after,
        sql_counts=sql_counts, raw_question_difficulties=raw_counts,
        eligible_question_counts={s: {lv: sum(q.primary_skill_id == s and q.cognitive_level == lv for q in bank)
                                     for lv in LEVELS} for s in skills},
        excluded_multi_skill_question_ids=[q.question_id for q in data.questions if q.primary_skill_id is None],
        eligible_l4_question_ids=[q.question_id for q in bank if q.cognitive_level == LEVELS[3]],
        templates=templates, allocation=allocation.model_dump(), seed=0,
        legacy_achieved_levels={lv: old_counts[lv] for lv in LEVELS}, legacy_slots=old,
        corrected_plan=plan.model_dump(mode="json"), corrected_slots=new, artificial_shortage_cases=scarcity)
    destination = ROOT / "eval/results/diagnostic_quota_audit_2026-10-29.json"
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(report=str(destination.relative_to(ROOT)),
        requested=allocation.levels, before=output["legacy_achieved_levels"],
        after=plan.quota_summary.achieved_levels, l4_sources=output["eligible_l4_question_ids"],
        sql_unchanged=before == after), indent=2))


if __name__ == "__main__":
    main()
