"""Typed planning boundary: quotas precede source-question selection."""

from typing import Annotated

from pydantic import Field, model_validator

from src.api.schemas import CognitiveLevel, ContractModel, Identifier, LEVELS

Quota = Annotated[int, Field(strict=True, ge=0)]


class AllocationPlan(ContractModel):
    strategy: str
    focus: list[Identifier]
    groups: dict[str, list[Identifier]]
    group_counts: dict[str, Quota]
    skill_counts: dict[Identifier, Quota]
    weights: dict[Identifier, tuple[float, ...]]
    skill_levels: dict[Identifier, dict[CognitiveLevel, Quota]]
    levels: dict[CognitiveLevel, Quota]
    forbidden_levels: dict[Identifier, list[CognitiveLevel]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_totals(self):
        total = sum(self.levels.values())
        if set(self.levels) != set(LEVELS):
            raise ValueError("Allocation requires all four cognitive levels")
        if total < 1 or sum(self.skill_counts.values()) != total or sum(self.group_counts.values()) != total:
            raise ValueError("Group, skill and level allocations must total N")
        if set(self.groups) != set(self.group_counts):
            raise ValueError("Every group requires a quota")
        for skill, counts in self.skill_levels.items():
            if set(counts) != set(LEVELS):
                raise ValueError("Per-skill allocation requires all four levels")
            if sum(counts.values()) != self.skill_counts.get(skill):
                raise ValueError("Per-skill level allocation must match its skill quota")
            if any(counts[level] for level in self.forbidden_levels.get(skill, [])):
                raise ValueError("Per-skill allocation contains a forbidden level")
        if self.skill_levels:
            if set(self.skill_levels) != set(self.skill_counts):
                raise ValueError("Every skill requires a difficulty allocation")
            if any(sum(row[lv] for row in self.skill_levels.values()) != self.levels[lv] for lv in LEVELS):
                raise ValueError("Per-skill difficulty columns must match exam totals")
        return self
