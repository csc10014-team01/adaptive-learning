"""Configurable MVP policy; no evidence or mastery is written by the planner."""

from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True)
class PlannerPolicyConfig:
    version: str = "mvp-personalization-v4-coordinated-difficulty"
    min_evidence: int = 3
    mastery_target: float = 2.0
    max_focus_skills: int = 2
    one_focus_share: float = 0.4
    two_focus_share: float = 0.6
    diagnostic_share: float = 0.6
    default_levels: tuple[float, ...] = (25, 35, 30, 10)
    # Exclusive upper bounds; the final bound includes the maximum mastery (4).
    mastery_levels: tuple[tuple[float, tuple[float, ...]], ...] = (
        (1.5, (50, 40, 10, 0)),
        (2.0, (35, 45, 20, 0)),
        (2.5, (25, 40, 30, 5)),
        (3.0, (20, 35, 35, 10)),
        (3.5, (15, 30, 40, 15)),
        (float("inf"), (10, 25, 45, 20)),
    )

    def __post_init__(self):
        if self.min_evidence < 1 or self.max_focus_skills not in (1, 2):
            raise ValueError("Policy requires positive evidence and one or two focus skills")
        if not 0 <= self.mastery_target <= 4:
            raise ValueError("Mastery target must be on the 0–4 scale")
        if any(not 0 <= share <= 1 for share in (
            self.one_focus_share, self.two_focus_share, self.diagnostic_share,
        )):
            raise ValueError("Group shares must be between zero and one")
        for weights in (self.default_levels, *(weights for _, weights in self.mastery_levels)):
            if len(weights) != 4 or any(not 0 <= w <= 100 for w in weights) or not isclose(sum(weights), 100):
                raise ValueError("Level weights must contain four nonnegative percentages totaling 100")
        bounds = [bound for bound, _ in self.mastery_levels]
        if not bounds or bounds != sorted(set(bounds)) or bounds[-1] <= 4:
            raise ValueError("Mastery bands must increase and cover the 0–4 scale")
