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
            if sum(counts.values()) != self.skill_counts.get(skill):
                raise ValueError("Per-skill level allocation must match its skill quota")
        return self
