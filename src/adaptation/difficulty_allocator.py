"""Joint rounding of skill, group and exam difficulty preferences.

Exam columns use largest remainder (stable L1-to-L4 ties). An integral flow
preserves every skill row and those columns, first minimizing squared group
rounding error, then squared skill error. Convex marginal costs generalize
largest remainder to a constrained matrix. Zero preferences forbid allocation.
"""

from fractions import Fraction
from math import floor, lcm

from src.adaptation.min_cost_flow import MinCostFlow
from src.api.schemas import LEVELS


def largest_remainder(ideals: list[Fraction], total: int) -> dict[str, int]:
    counts = [floor(value) for value in ideals]
    order = sorted(range(4), key=lambda i: (-(ideals[i] - counts[i]), i))
    for index in order[:total - sum(counts)]:
        counts[index] += 1
    return dict(zip(LEVELS, counts))


def coordinated_levels(
    skill_counts: dict[str, int], weights: dict[str, tuple[float, ...]],
    groups: dict[str, list[str]], *,
    forbidden_levels: dict[str, list[str]] | None = None,
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    """Allocate before looking at bank capacity.

    Normal policy has three common foundational levels and optional L4. For custom
    policies with incompatible supports, the nearest feasible exam columns replace
    infeasible largest-remainder columns.
    """
    total = sum(skill_counts.values())
    forbidden_levels = forbidden_levels or {}
    ideals = {s: [Fraction(str(w)) * count / 100 for w in weights[s]]
              for s, count in skill_counts.items()}
    group_for = {s: g for g, members in groups.items() for s in members}
    group_ideals = {g: [sum((ideals[s][i] for s in members), Fraction()) for i in range(4)]
                    for g, members in groups.items()}
    exam_ideals = [sum((row[i] for row in ideals.values()), Fraction()) for i in range(4)]
    columns = largest_remainder(exam_ideals, total)
    denominator = lcm(*(v.denominator for row in ideals.values() for v in row))
    # One unit of group objective dominates the entire possible skill objective.
    group_factor = 2 * total * total * denominator + 1
    exam_factor = group_factor * group_factor

    def solve(relax_columns=False):
        network, cells = MinCostFlow(), {}
        for skill, count in skill_counts.items():
            network.add_edge("source", ("skill", skill), count)
            for i, level in enumerate(LEVELS):
                cells[skill, level] = []
                if weights[skill][i] == 0 or level in forbidden_levels.get(skill, []):
                    continue
                for k in range(1, count + 1):
                    cost = int((2 * k - 1 - 2 * ideals[skill][i]) * denominator)
                    cells[skill, level].append(network.add_edge(
                        ("skill", skill), ("group_level", group_for[skill], level), 1, cost))
        for group, members in groups.items():
            count = sum(skill_counts[s] for s in members)
            for i, level in enumerate(LEVELS):
                for k in range(1, count + 1):
                    cost = int((2 * k - 1 - 2 * group_ideals[group][i]) * denominator)
                    network.add_edge(("group_level", group, level), ("level", level), 1, cost * group_factor)
        for level in LEVELS:
            if relax_columns:
                for k in range(1, total + 1):
                    network.add_edge(("level", level), "sink", 1,
                                     (2 * k - 1 - 2 * columns[level]) * exam_factor)
            else:
                network.add_edge(("level", level), "sink", columns[level])
        if not network.send("source", "sink", total):
            return None
        result = {s: {lv: sum(e.flow for e in cells[s, lv]) for lv in LEVELS} for s in skill_counts}
        return result, {lv: sum(row[lv] for row in result.values()) for lv in LEVELS}

    result = solve()
    if result is None:
        result = solve(relax_columns=True)
    if result is None:
        raise ValueError("No feasible skill/difficulty allocation")
    return result
