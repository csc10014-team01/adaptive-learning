"""Assign unique source questions jointly after skill/difficulty allocation."""

from collections import defaultdict

from src.adaptation.contracts import AllocationPlan
from src.adaptation.min_cost_flow import MinCostFlow
from src.adaptation.selection_diagnostics import explain_selection, failure_capacity_summary
from src.api.data_adapter import ApiFailure, FixtureQuestion
from src.api.schemas import LEVELS


class QuestionSelector:
    def select(
        self, bank: list[FixtureQuestion], allocation: AllocationPlan,
        locked: bool, seen: set[str], warnings: list[str], *, audit=None,
    ) -> tuple[list[FixtureQuestion], dict[str, str]]:
        """Minimize deviations globally, reserving scarce sources through matching.

        The lexicographic objective minimizes changed difficulty slots, level
        distance, changed skills, upward changes, groups, then history exposure.
        Hard constraints: unique IDs, primary-only attribution, no forbidden L4,
        related-review cap, and at most one upward level per automatic slot.
        Legacy locked slots retain their exact global level counts.
        """
        n = sum(allocation.levels.values())
        group_for = {s: g for g, members in allocation.groups.items() for s in members}
        safe = []
        for q in sorted(bank, key=lambda q: q.question_id):
            skill = q.primary_skill_id
            if (q.cognitive_level in allocation.forbidden_levels.get(skill, [])
                    or (q.cognitive_level == "advanced_application" and allocation.weights[skill][3] == 0)):
                warnings.append(f"Excluded {q.question_id}: L4 is forbidden by the assessed skill's difficulty policy.")
            else:
                safe.append(q)
        if len(safe) < n:
            exclusions = " ".join(w for w in warnings if w.startswith("Excluded "))
            details = failure_capacity_summary(allocation,
                [("question", q.question_id, [q.primary_skill_id], q.cognitive_level) for q in safe])
            raise ApiFailure(409, "INSUFFICIENT_QUESTION_BANK",
                f"Need {n} unique primary-annotated questions, available {len(safe)}. {details} {exclusions}".strip())

        if not allocation.skill_levels:
            return self._select_legacy(safe, allocation, locked, seen, warnings), group_for

        skill_levels = allocation.skill_levels
        pending = {s: [lv for lv in LEVELS for _ in range(row[lv])] for s, row in skill_levels.items()}
        slots = []
        while any(pending.values()):
            for skill, levels in pending.items():
                if levels:
                    slots.append((skill, levels.pop(0)))

        cells = defaultdict(list)
        for q in safe:
            cells[q.primary_skill_id, q.cognitive_level].append(q)
        cells = {cell: sorted(pool, key=lambda q: (q.question_id in seen, q.question_id))[:n]
                 for cell, pool in sorted(cells.items())}
        def build(caps):
            network = MinCostFlow()
            assignments, sources = {}, {}
            # At most 3N distance units and N of each other objective; one higher
            # digit dominates all lower digits across the entire assignment.
            base = 4 * n + 1
            for index, (skill, level) in enumerate(slots):
                network.add_edge("source", ("slot", index), 1)
                for cell in cells:
                    primary, actual_level = cell
                    delta = LEVELS.index(actual_level) - LEVELS.index(level)
                    if (locked and delta != 0) or (not locked and delta > 1):
                        continue
                    digits = (int(delta != 0), abs(delta), int(primary != skill),
                              int(delta > 0), int(group_for[primary] != group_for[skill]))
                    cost = 0
                    for digit in digits:
                        cost = cost * base + digit
                    assignments[index, cell] = network.add_edge(("slot", index), ("cell", cell), 1, cost * base)
            for cell, pool in cells.items():
                group = group_for[cell[0]]
                for q in pool:
                    sources[q.question_id] = network.add_edge(("cell", cell), ("group", group), 1,
                                                              int(q.question_id in seen))
            for group in allocation.groups:
                network.add_edge(("group", group), "sink", caps[group])
            return network, (assignments, sources)

        assignments, sources = self._best_match(allocation, build, failure_capacity_summary(allocation,
            [("question", q.question_id, [q.primary_skill_id], q.cognitive_level) for q in safe]))

        available = {cell: [q for q in pool if sources[q.question_id].flow] for cell, pool in cells.items()}
        selected = []
        for index, (skill, level) in enumerate(slots):
            cell = next(cell for cell in cells if (index, cell) in assignments and assignments[index, cell].flow)
            q = available[cell].pop(0)
            selected.append(q)
        explain_selection(audit, allocation, slots,
            [("question", q.question_id, [q.primary_skill_id], q.cognitive_level) for q in safe],
            [("question", q.question_id, q.primary_skill_id, q.cognitive_level) for q in selected], warnings)
        return selected, group_for

    @staticmethod
    def _select_legacy(bank, allocation, locked, seen, warnings):
        """Legacy global quotas have no planned skill/level cells to match.

        Keep locked columns exact, minimizing group then skill quota deviations. This
        preserves scarce skill coverage without inventing arbitrary locked cells.
        Public teacher creation rejects these legacy modes before the planner.
        """
        n = sum(allocation.levels.values())
        def build(caps):
            network, sources = MinCostFlow(), {}
            group_for = {s: g for g, members in allocation.groups.items() for s in members}
            base = n * n + 1
            for level, count in allocation.levels.items():
                if locked:
                    network.add_edge("source", ("level", level), count)
                else:
                    for k in range(1, n + 1):
                        network.add_edge("source", ("level", level), 1,
                                         (2 * k - 1 - 2 * count) * base ** 3)
            for q in sorted(bank, key=lambda q: (q.question_id in seen, q.question_id)):
                sources[q.question_id] = network.add_edge(("level", q.cognitive_level),
                    ("skill", q.primary_skill_id), 1, int(q.question_id in seen))
            for skill, count in allocation.skill_counts.items():
                for k in range(1, n + 1):
                    network.add_edge(("skill", skill), ("group", group_for[skill]), 1,
                                     (2 * k - 1 - 2 * count) * base)
            for group, count in allocation.group_counts.items():
                cap = caps[group]
                for k in range(1, cap + 1):
                    network.add_edge(("group", group), "sink", 1,
                                     (2 * k - 1 - 2 * count) * base * base)
            return network, sources

        sources = QuestionSelector._best_match(allocation, build, failure_capacity_summary(allocation,
            [("question", q.question_id, [q.primary_skill_id], q.cognitive_level) for q in bank]))
        chosen = [q for q in bank if sources[q.question_id].flow]
        # Per-cell substitution messages require planned cells; legacy deviations
        # are reported by the planner's group/skill/level quota summaries instead.
        if any(sum(q.primary_skill_id == s for q in chosen) != count
               for s, count in allocation.skill_counts.items()):
            warnings.append("Substituted legacy skill slots to meet exact global difficulty totals.")
        return sorted(chosen, key=lambda q: q.question_id)

    @staticmethod
    def _best_match(allocation, build, failure_details=""):
        """Enumerate the tiny related cap to enforce its share after fallback.

        For each k, Related <= k and Focus <= N-2k imply Related <= Balanced.
        Conversely, any valid selection appears in the case k=actual Related.
        Comparing global flow costs therefore preserves optimality, including
        when fallback changes the achieved Review question count.
        """
        n = sum(allocation.levels.values())
        caps = {g: n for g in allocation.groups}
        choices = [caps]
        if "related_review" in caps:
            limit = allocation.group_counts["related_review"]
            if "focus" in caps:
                choices = [{**caps, "related_review": k, "focus": n - 2 * k} for k in range(limit + 1)]
            else:
                choices = [{**caps, "related_review": limit}]
        best_cost, best = None, None
        for limits in choices:
            network, payload = build(limits)
            if network.send("source", "sink", n) and (best_cost is None or network.total_cost < best_cost):
                best_cost, best = network.total_cost, payload
        if best is None:
            raise ApiFailure(409, "INSUFFICIENT_QUESTION_BANK",
                "Cannot satisfy difficulty safety and the related-review cap with unique source questions. " + failure_details)
        return best
