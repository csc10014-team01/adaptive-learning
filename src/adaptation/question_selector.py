"""Select source questions after allocation; never calls a model or writes data."""

from collections import Counter

from src.adaptation.contracts import AllocationPlan
from src.api.data_adapter import ApiFailure, FixtureQuestion
from src.api.schemas import LEVELS


class QuestionSelector:
    def select(
        self, bank: list[FixtureQuestion], allocation: AllocationPlan,
        locked: bool, seen: set[str], warnings: list[str],
    ) -> tuple[list[FixtureQuestion], dict[str, str]]:
        """D. Hard pool feasibility first; soft cell preferences may safely deviate."""
        skill_counts, skill_levels = allocation.skill_counts, allocation.skill_levels
        weights, levels = allocation.weights, allocation.levels
        n = sum(levels.values())
        available_levels = Counter(q.cognitive_level for q in bank)
        if len(bank) < n or (locked and any(available_levels[level] < count for level, count in levels.items())):
            detail = "; ".join(f"{level}: need {count}, available {available_levels[level]}" for level, count in levels.items())
            exclusions = " ".join(w for w in warnings if w.startswith("Excluded "))
            raise ApiFailure(409, "INSUFFICIENT_QUESTION_BANK",
                             f"Need {n} unique primary-annotated questions, available {len(bank)}. {detail} {exclusions}".strip())
        group_for = {s: g for g, members in allocation.groups.items() for s in members}
        remaining_skills = dict(skill_counts)
        desired = []
        while any(remaining_skills.values()):
            for skill in remaining_skills:
                if remaining_skills[skill]:
                    desired.append(skill)
                    remaining_skills[skill] -= 1
        if locked:
            # Allocate scarce skills first; level capacities remain global.
            desired.sort(key=lambda s: (
                sum(min(count, sum(q.primary_skill_id == s and q.cognitive_level == level for q in bank))
                    for level, count in levels.items()) / max(skill_counts[s], 1),
                list(skill_counts).index(s),
            ))
        preferred = {s: [level for level, count in counts.items() for _ in range(count)]
                     for s, counts in skill_levels.items()}
        remaining_levels = dict(levels)
        used, counts, chosen = set(), Counter(), []
        related_count = 0
        related_limit = allocation.group_counts.get("related_review")

        def preserves_capacity(candidate):
            if related_limit is None:
                return True
            cap = related_limit - related_count - (group_for[candidate.primary_skill_id] == "related_review")
            other = [q for q in bank if q.question_id not in used and q.question_id != candidate.question_id]
            normal = Counter(q.cognitive_level for q in other if group_for[q.primary_skill_id] != "related_review")
            related = Counter(q.cognitive_level for q in other if group_for[q.primary_skill_id] == "related_review")
            if locked:
                needed = {lv: count - (candidate.cognitive_level == lv) for lv, count in remaining_levels.items()}
                return (all(normal[lv] + related[lv] >= count for lv, count in needed.items())
                        and sum(max(0, count - normal[lv]) for lv, count in needed.items()) <= cap)
            return sum(normal.values()) + min(cap, sum(related.values())) >= n - len(chosen) - 1

        for skill in desired:
            if locked:
                level = None
            elif skill_levels:
                level = preferred[skill].pop(0)
            else:
                level = max(LEVELS, key=lambda lv: (remaining_levels[lv], -LEVELS.index(lv)))
            candidates = [q for q in bank if q.question_id not in used
                          and (not locked or remaining_levels[q.cognitive_level] > 0)
                          and (related_limit is None or related_count < related_limit
                               or group_for[q.primary_skill_id] != "related_review")
                          and preserves_capacity(q)]
            if not candidates:
                raise ApiFailure(409, "INSUFFICIENT_QUESTION_BANK",
                                 "Cannot satisfy teacher levels and the related-review cap with unique questions")
            def rank(q):
                primary = q.primary_skill_id
                level_index = LEVELS.index(q.cognitive_level)
                return (
                    primary != skill,
                    group_for[primary] != group_for[skill],
                    max(0, counts[primary] - skill_counts[primary] + 1),
                    -weights[primary][level_index] if locked else abs(level_index - LEVELS.index(level)),
                    q.question_id in seen,
                    q.question_id,
                )
            q = min(candidates, key=rank)
            if q.primary_skill_id != skill or (level is not None and q.cognitive_level != level):
                wanted = f"{skill}/{level or 'teacher levels'}"
                warnings.append(f"Substituted {wanted} with {q.primary_skill_id}/{q.cognitive_level} ({q.question_id}).")
            used.add(q.question_id)
            remaining_levels[q.cognitive_level] -= 1
            counts[q.primary_skill_id] += 1
            related_count += group_for[q.primary_skill_id] == "related_review"
            chosen.append(q)
        return chosen, group_for

