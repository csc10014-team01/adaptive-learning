"""Explain finite source capacity and every relaxed skill/difficulty cell.

Capacity entries are (kind, identifier, linked_skills, level); a shared template
instance counts once globally, and once in each linked cell. Cell capacities
therefore must not be summed to claim joint matrix feasibility.
"""

from collections import Counter

from src.api.schemas import LEVELS


FALLBACK_POLICY = (
    "Preserve difficulty before skill; exact linked-skill L1/L2 Templates first. "
    "Only if exact difficulty is infeasible: minimize changed difficulty slots, "
    "then distance; Question upward <=1, downward allowed; forbidden L4 and "
    "actual related-review cap remain hard constraints."
)


def explain_selection(audit, allocation, slots, capacity, selected, warnings):
    """selected entries align to slots: (kind, identifier, actual_skill, level)."""
    # Prepared Templates cannot move to a different skill or difficulty. Count
    # their capacity only if at least one requested cell accepts that instance.
    capacity = [(kind, identifier, skills, lv) for kind, identifier, skills, lv in capacity
                if kind == "question" or any((s, lv) in slots for s in skills)]
    questions = Counter(lv for kind, _, _, lv in capacity if kind == "question")
    templates = Counter(lv for kind, _, _, lv in capacity if kind == "template")
    cells = Counter((s, lv) for _, _, skills, lv in capacity for s in skills)
    achieved = Counter(lv for _, _, _, lv in selected)
    shortages = []
    for skill, row in allocation.skill_levels.items():
        for lv in LEVELS:
            requested = row[lv]
            available = cells[skill, lv]
            if requested > available:
                shortages.append(dict(skill_id=skill, level=lv, requested=requested,
                                      available=available, shortage=requested - available))
    level_shortages = []
    for lv in LEVELS:
        requested = allocation.levels[lv]
        if achieved[lv] >= requested:
            continue
        available = questions[lv] + templates[lv]
        reason = ("eligible source capacity exhausted" if available < requested else
                  "joint slot eligibility and safety constraints prevent the exact blueprint")
        item = dict(level=lv, requested=requested, available=available, achieved=achieved[lv],
                    shortage=requested - achieved[lv], reason=reason)
        level_shortages.append(item)
        warnings.append(f"Difficulty shortage {lv}: requested={requested}, eligible={available}, "
                        f"achieved={achieved[lv]}, shortage={item['shortage']}; {reason}.")
    substitutions = []
    for i, ((skill, lv), (kind, identifier, actual, actual_lv)) in enumerate(zip(slots, selected)):
        if (skill, lv) == (actual, actual_lv):
            continue
        available = cells[skill, lv]
        reason = (f"requested cell has {available}/{allocation.skill_levels[skill][lv]} eligible sources"
                  if available < allocation.skill_levels[skill][lv] else
                  "joint assignment reserves shared capacity and satisfies hard safety constraints")
        if lv == actual_lv:
            reason += "; same difficulty preserved via skill fallback"
        else:
            reason += "; exact exam difficulty infeasible; applied declared Question difficulty fallback"
        substitutions.append(dict(slot=i + 1, requested_skill=skill, requested_level=lv,
            actual_skill=actual, actual_level=actual_lv, source_kind=kind, source_id=identifier, reason=reason))
        warnings.append(f"Substituted {skill}/{lv} with {actual}/{actual_lv} ({identifier}): {reason}.")
    if audit is not None:
        audit.update(exact_skill_level_matrix_feasible=not substitutions,
            exact_exam_levels_feasible=all(achieved[lv] == allocation.levels[lv] for lv in LEVELS),
            eligible_question_levels={lv: questions[lv] for lv in LEVELS},
            eligible_template_instance_levels={lv: templates[lv] for lv in LEVELS},
            cell_shortages=shortages, level_shortages=level_shortages,
            substitutions=substitutions, fallback_policy=FALLBACK_POLICY)


def failure_capacity_summary(allocation, capacity):
    """Report raw safe capacity bounds even when no full assignment exists."""
    counts = Counter(lv for _, _, _, lv in capacity)
    return "Source capacity by level: " + "; ".join(
        f"{lv} requested={allocation.levels[lv]}, eligible={counts[lv]}, "
        f"capacity_shortage={max(0, allocation.levels[lv] - counts[lv])}"
        for lv in LEVELS) + ". Joint slot eligibility and safety constraints also apply."
