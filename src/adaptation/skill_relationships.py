"""Explicit catalogue-specific review relationships; never remaps student data."""

from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator

from src.api.schemas import ContractModel, Identifier


class SkillRelationships(ContractModel):
    version: Identifier
    catalogue_ids: list[Identifier]
    priorities: dict[Identifier, dict[Identifier, Annotated[int, Field(strict=True, ge=1, le=3)]]]

    @model_validator(mode="after")
    def known_skills(self):
        known = set(self.catalogue_ids)
        if len(known) != len(self.catalogue_ids) or set(self.priorities) != known:
            raise ValueError("Every unique catalogue skill requires a relationship row")
        for source, targets in self.priorities.items():
            if source in targets or not set(targets).issubset(known):
                raise ValueError("Relationships require distinct known skills")
        return self

    @classmethod
    def load(cls, path: Path):
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def rank_review_skills(self, focus: list[str], review: list[str]) -> list[str]:
        def priority(skill):
            return max((self.priorities[f].get(skill, 0) for f in focus), default=0)
        return sorted((s for s in review if priority(s) > 0), key=lambda s: (-priority(s), s))
