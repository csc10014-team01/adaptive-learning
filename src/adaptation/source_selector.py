"""Template-first exact L1/L2 matching, followed by safe global fallback.

Prepared mathematical instances reserve finite capacity; preview does not claim
that wording has been generated. Templates can credit exactly one skill from
their SQL-authored links. Immutable questions retain their explicit primary.
"""

from dataclasses import dataclass

from src.adaptation.min_cost_flow import MinCostFlow
from src.adaptation.question_selector import QuestionSelector
from src.adaptation.selection_diagnostics import explain_selection, failure_capacity_summary
from src.ai.template_instantiator import TemplateInstantiator
from src.api.data_adapter import ApiFailure
from src.api.schemas import LEVELS


@dataclass
class SelectedSource:
    source_kind: str
    source_id: str
    primary_skill_id: str
    skill_ids: list[str]
    cognitive_level: str
    instance: object = None


@dataclass
class Unit:
    kind: str
    identifier: str
    skills: list[str]
    level: str
    ordinal: int = 0
    instance: object = None


class SourceSelector:
    def __init__(self):
        self.engine = TemplateInstantiator()

    def select(self, bank, templates, allocation, locked, seen, warnings, *, seed=0, excluded_templates=(), audit=None):
        group_for = {s: g for g, members in allocation.groups.items() for s in members}
        n = sum(allocation.levels.values())
        units = []
        for template in sorted(templates, key=lambda t: t.template_id):
            if template.template_id in excluded_templates or template.difficulty not in (1, 2):
                continue
            if not any(allocation.skill_counts.get(s, 0) for s in template.skill_ids):
                continue
            try:
                instances = self.engine.instances(template, n, seed=seed)
                if not instances:
                    raise ValueError("no valid parameter instances in the bounded search")
                units.extend(Unit("template", template.template_id, template.skill_ids,
                    template.cognitive_level, i, instance) for i, instance in enumerate(instances))
            except (ValueError, SyntaxError, TypeError, KeyError, OverflowError) as exc:
                warnings.append(f"Template {template.template_id} unsupported: {exc}; Question Bank fallback allowed.")
        if not units or not allocation.skill_levels:
            selected, group_for = QuestionSelector().select(bank, allocation, locked, seen, warnings, audit=audit)
            if templates:
                warnings.append("No executable eligible Template filled the planned L1/L2 cells; used Question Bank fallback.")
            return [SelectedSource("question", q.question_id, q.primary_skill_id, q.skill_ids, q.cognitive_level) for q in selected], group_for
        for q in bank:
            if (q.cognitive_level in allocation.forbidden_levels.get(q.primary_skill_id, [])
                    or (q.cognitive_level == LEVELS[3] and allocation.weights[q.primary_skill_id][3] == 0)):
                warnings.append(f"Excluded {q.question_id}: L4 is forbidden by the assessed skill's difficulty policy.")
                continue
            units.append(Unit("question", q.question_id, [q.primary_skill_id], q.cognitive_level))
        slots = [(s, lv) for s, row in allocation.skill_levels.items() for lv in LEVELS for _ in range(row[lv])]
        # Tuple objectives are encoded exactly; one digit dominates the sum of
        # every lower-priority digit across N questions.
        base = 20 * n + 1
        edges = {}
        for ui, unit in enumerate(units):
            for si, (skill, level) in enumerate(slots):
                actual = skill if unit.kind == "template" else unit.skills[0]
                if actual not in group_for:
                    continue
                delta = LEVELS.index(unit.level) - LEVELS.index(level)
                if unit.kind == "template" and (skill not in unit.skills or delta):
                    continue
                if unit.kind == "question" and ((locked and delta != 0) or delta > 1):
                    continue
                # A missing skill/level cell may relax skill coverage, but must
                # never discard an available exact-difficulty assignment merely
                # to preserve that skill. All sources are matched jointly.
                digits = (int(delta != 0), abs(delta), int(actual != skill), int(delta > 0),
                          int(group_for[actual] != group_for[skill]),
                          int(unit.kind == "question" and level in LEVELS[:2]), unit.ordinal,
                          int(unit.kind == "question" and unit.identifier in seen))
                cost = 0
                for value in digits:
                    cost = cost * base + value
                edges[ui, si] = cost, actual, group_for[actual]

        # Most exams have an exact feasible matrix. A min-cost matching reserves
        # shared templates/questions jointly, with template preference/diversity.
        network, assignment_edges = MinCostFlow(), {}
        for ui in range(len(units)):
            network.add_edge("source", ("unit", ui), 1)
        for si in range(n):
            network.add_edge(("slot", si), "sink", 1)
        for (ui, si), (cost, actual, group) in edges.items():
            if (actual, units[ui].level) == slots[si]:
                assignment_edges[ui, si] = network.add_edge(("unit", ui), ("slot", si), 1, cost)
        if network.send("source", "sink", n):
            chosen = {si: ui for (ui, si), edge in assignment_edges.items() if edge.flow}
        else:
            chosen = self._fallback(units, slots, edges, allocation)
        result = []
        question_map = {q.question_id: q for q in bank}
        for si, (skill, level) in enumerate(slots):
            unit = units[chosen[si]]
            actual = edges[chosen[si], si][1]
            if unit.kind == "question" and level in LEVELS[:2]:
                warnings.append(f"Question fallback for {skill}/{level}: selected {unit.identifier}; no feasible preferred Template assignment.")
            skills = unit.skills if unit.kind == "template" else question_map[unit.identifier].skill_ids
            result.append(SelectedSource(unit.kind, unit.identifier, actual, list(skills), unit.level, unit.instance))
        explain_selection(audit, allocation, slots,
            [(u.kind, u.identifier, u.skills, u.level) for u in units],
            [(q.source_kind, q.source_id, q.primary_skill_id, q.cognitive_level) for q in result], warnings)
        return result, group_for

    def _fallback(self, units, slots, edges, allocation):
        """Exact finite assignment DP for N<=10 when some quotas must deviate.

        State is filled slots and achieved Related/Balanced counts. Each source
        is processed once, so neither a question nor a mathematical instance can
        be reused. Equal cells use canonical slot order to reduce symmetric states.
        """
        n = len(slots)
        empty = (-1,) * n
        states = {(0, 0, 0): (0, empty)}
        related_limit = allocation.group_counts.get("related_review", n)
        previous = {i: max((j for j in range(i) if slots[j] == slot), default=-1) for i, slot in enumerate(slots)}
        for ui, _ in enumerate(units):
            options = [(si, *value) for (index, si), value in edges.items() if index == ui]
            for (mask, related, balanced), (cost, chosen) in list(states.items()):
                for si, extra, actual, group in options:
                    if mask & (1 << si) or (previous[si] >= 0 and not mask & (1 << previous[si])):
                        continue
                    r = related + (group == "related_review")
                    b = balanced + (group == "balanced_review")
                    if r > related_limit:
                        continue
                    key = mask | (1 << si), r, b
                    value = cost + extra
                    if key not in states or value < states[key][0]:
                        updated = list(chosen)
                        updated[si] = ui
                        states[key] = value, tuple(updated)
        finals = [value for (mask, r, b), value in states.items()
                  if mask == (1 << n) - 1 and ("related_review" not in allocation.groups or r <= b)]
        if not finals:
            details = failure_capacity_summary(allocation,
                [(u.kind, u.identifier, u.skills, u.level) for u in units])
            raise ApiFailure(409, "INSUFFICIENT_QUESTION_BANK",
                "No complete safe hybrid source assignment satisfies the plan and Review cap. " + details)
        return dict(enumerate(min(finals, key=lambda value: value[0])[1]))
