"""Deterministic, read-only exam planning in five small policy stages."""

from math import floor

from pydantic import ValidationError

from src.adaptation.contracts import AllocationPlan
from src.adaptation.question_selector import QuestionSelector
from src.adaptation.skill_relationships import SkillRelationships
from src.adaptation.policy import PlannerPolicyConfig
from src.api.data_adapter import ApiFailure, FixtureQuestion, StaticDataAdapter
from src.api.schemas import (
    LEVELS, CognitiveLevel, ContractModel, GenerateExamRequest, Identifier, Mode,
    PlannerSummary, QuotaSummary, StudentProfileResponse, Text,
)
from src.api.services import level_counts, question_slots


class PlannedQuestion(ContractModel):
    source_id: Identifier
    target_skill_id: Identifier
    skill_ids: list[Identifier]
    cognitive_level: CognitiveLevel
    group: str
    targeted: bool
    reasons: list[Text]


class ExamPlan(PlannerSummary):
    student_id: Identifier
    requested_mode: Mode
    personalized: bool
    priority_skills: list[Identifier]
    target_count: int
    achieved_target_count: int
    questions: list[PlannedQuestion]


# Compatibility import for existing callers.
Allocation = AllocationPlan


def fair_counts(total: int, skills: list[str]) -> dict[str, int]:
    """Round-robin counts; caller supplies the stable order for extra slots."""
    if not skills:
        return {}
    base, extra = divmod(total, len(skills))
    return {skill: base + (i < extra) for i, skill in enumerate(skills)}


class RuleBasedPlanner:
    def __init__(self, data: StaticDataAdapter, policy: PlannerPolicyConfig | None = None,
                 relationships: SkillRelationships | None = None):
        self.data = data
        self.policy = policy or PlannerPolicyConfig()
        self.selector = QuestionSelector()
        self.relationships = relationships

    def _check_relationship_catalogue(self, skills):
        if self.relationships is not None and set(self.relationships.catalogue_ids) != set(skills):
            raise ApiFailure(500, "DATA_SOURCE_ERROR", "Relationship policy does not match the data catalogue")

    def build_allocation_plan(
        self, request: GenerateExamRequest, profile: StudentProfileResponse,
    ) -> AllocationPlan:
        """Allocate skill/level quotas without reading or selecting questions."""
        try:
            profile = StudentProfileResponse.model_validate(profile)
        except ValidationError as exc:
            raise ApiFailure(500, "INVALID_PROFILE_DATA", "Invalid planner profile") from exc
        skills = sorted(s.skill_id for s in self.data.topic.skills)
        self._check_relationship_catalogue(skills)
        if request.student_id != profile.student_id or any(s.skill_id not in skills for s in profile.skill_mastery):
            raise ApiFailure(500, "INVALID_PROFILE_DATA", "Profile identity or skill catalogue mismatch")
        if profile.grade_level != self.data.topic.grade_level:
            raise ApiFailure(409, "INSUFFICIENT_QUESTION_BANK", "No catalogue for the requested grade")
        return self._allocate(request, profile, self.classify(profile, skills))

    def _validate(
        self, request: GenerateExamRequest, profile: StudentProfileResponse,
    ) -> tuple[StudentProfileResponse, list[FixtureQuestion], list[str], list[str]]:
        """A. Validate the whole input bank before filtering its scoped pool."""
        try:
            profile = StudentProfileResponse.model_validate(profile)
        except ValidationError as exc:
            raise ApiFailure(500, "INVALID_PROFILE_DATA", f"Invalid planner profile: {exc}") from exc
        known = {s.skill_id for s in self.data.topic.skills}
        self._check_relationship_catalogue(known)
        if request.student_id != profile.student_id or any(s.skill_id not in known for s in profile.skill_mastery):
            raise ApiFailure(500, "INVALID_PROFILE_DATA", "Profile identity or skill catalogue mismatch")
        bank, ids, warnings = [], set(), []
        for raw in self.data.questions:
            try:
                q = FixtureQuestion.model_validate(raw)
                if q.question_id in ids:
                    raise ValueError(f"Duplicate question_id: {q.question_id}")
                if not set(q.skill_ids).issubset(known):
                    raise ValueError(f"Unknown skill in question {q.question_id}")
                ids.add(q.question_id)
            except (ValueError, ValidationError) as exc:
                raise ApiFailure(500, "DATA_SOURCE_ERROR", f"Invalid question bank: {exc}") from exc
            if q.grade_level != profile.grade_level or q.topic_id not in request.selected_topic_ids:
                continue
            if q.primary_skill_id is None:
                warnings.append(f"Excluded {q.question_id}: multi-skill source requires explicit primary_skill_id.")
                continue
            bank.append(q)
        # Catalogue, rather than profile rows or bank coverage, defines the scope.
        skills = sorted(known) if profile.grade_level == self.data.topic.grade_level else []
        if not skills:
            raise ApiFailure(409, "INSUFFICIENT_QUESTION_BANK", "No question catalogue for the requested topic and grade")
        return profile, sorted(bank, key=lambda q: q.question_id), skills, warnings

    def classify(self, profile: StudentProfileResponse, skills: list[str]) -> dict[str, str]:
        """B. Missing profile rows are NO_DATA, independently for each skill."""
        rows = {s.skill_id: s for s in profile.skill_mastery}
        result = {}
        for skill in skills:
            row = rows.get(skill)
            if row is None or row.evidence_count == 0:
                result[skill] = "NO_DATA"
            elif row.evidence_count < self.policy.min_evidence:
                result[skill] = "PARTIAL"
            elif row.mastery_score < self.policy.mastery_target:
                result[skill] = "WEAK"
            else:
                result[skill] = "ACHIEVED"
        return result

    def _allocate(
        self, request: GenerateExamRequest, profile: StudentProfileResponse, statuses: dict[str, str],
    ) -> Allocation:
        """C. Group half-up rounding, fair skill coverage, then level preferences."""
        rows = {s.skill_id: s for s in profile.skill_mastery}
        weak = sorted((s for s in statuses if statuses[s] == "WEAK"),
                      key=lambda s: (rows[s].mastery_score, s))
        focus = weak[:self.policy.max_focus_skills] if request.generation_mode == "adaptive" else []
        skills = list(statuses)
        n = request.total_questions
        if request.generation_mode != "adaptive":
            strategy, groups = "standard", {"standard": skills}
            group_counts = {"standard": n}
        elif focus:
            strategy = "focused_practice"
            groups = {"focus": focus, "review": [s for s in skills if s not in focus]}
            share = self.policy.two_focus_share if len(focus) == 2 else self.policy.one_focus_share
            count = floor(n * share + 0.5)
            group_counts = {"focus": count, "review": n - count}
        else:
            diagnostic = [s for s in skills if statuses[s] in ("NO_DATA", "PARTIAL")]
            achieved = [s for s in skills if statuses[s] == "ACHIEVED"]
            if not diagnostic:
                strategy, groups = "advanced_review", {"advanced_review": achieved}
                group_counts = {"advanced_review": n}
            else:
                strategy, groups = "diagnostic_review", {"diagnostic": diagnostic, "maintenance": achieved}
                count = floor(n * self.policy.diagnostic_share + 0.5) if achieved else n
                group_counts = {"diagnostic": count, "maintenance": n - count}
        if focus and self.relationships is not None:
            review = groups.pop("review")
            review_count = group_counts.pop("review")
            ranked = self.relationships.rank_review_skills(focus, review)
            # Exact cap, including odd/small N: at most floor(review_count / 2).
            related_count = review_count // 2 if ranked and len(review) > 1 else 0
            related = ranked[:min(related_count, max(0, len(review) - 1))]
            balanced = [s for s in review if s not in related]
            groups.update(related_review=related, balanced_review=balanced)
            group_counts.update(related_review=related_count, balanced_review=review_count - related_count)
        skill_counts = {}
        for group, members in groups.items():
            skill_counts.update(fair_counts(group_counts[group], members))
        # Preserve requested group targets even when a very narrow topic cannot
        # supply a review skill; expose the unavoidable deviation in the result.
        unassigned = n - sum(skill_counts.values())
        for skill, count in fair_counts(unassigned, focus or skills).items():
            skill_counts[skill] = skill_counts.get(skill, 0) + count
        weights = {}
        for skill, status in statuses.items():
            weights[skill] = self.policy.default_levels
            if request.generation_mode == "adaptive" and status in ("WEAK", "ACHIEVED"):
                weights[skill] = next(w for bound, w in self.policy.mastery_levels if rows[skill].mastery_score < bound)
        # Explicit teacher totals are allocated globally, never rounded per skill.
        locked = request.difficulty_distribution is not None
        standard = request.generation_mode != "adaptive"
        skill_levels = {} if locked or standard else {s: level_counts(count, weights[s]) for s, count in skill_counts.items()}
        if locked:
            levels = question_slots(request)
        elif standard:
            levels = level_counts(n, self.policy.default_levels)
        else:
            levels = {level: sum(counts[level] for counts in skill_levels.values()) for level in LEVELS}
        return AllocationPlan(strategy=strategy, focus=focus, groups=groups,
            group_counts=group_counts, skill_counts=skill_counts, weights=weights,
            skill_levels=skill_levels, levels=levels)

    def _select(self, bank, allocation, locked, seen, warnings):
        """Compatibility entry point; selection belongs to QuestionSelector."""
        return self.selector.select(bank, allocation, locked, seen, warnings)

    def plan(self, request: GenerateExamRequest, profile: StudentProfileResponse) -> ExamPlan:
        """E. Integrate selection, achieved quotas, explanations, and warnings."""
        allocation = self.build_allocation_plan(request, profile)
        profile, bank, skills, warnings = self._validate(request, profile)
        statuses = self.classify(profile, skills)
        seen = {qid for test in profile.learning_history for qid in test.wrong_questions}
        unknown = seen - {q.question_id for q in self.data.questions}
        if unknown:
            warnings.append("History IDs unavailable in the bank (no skill/evidence inferred): " + ", ".join(sorted(unknown)))
        locked = request.difficulty_distribution is not None
        selected, group_for = self._select(bank, allocation, locked, seen, warnings)
        questions = []
        for q in selected:
            skill = q.primary_skill_id
            reasons = [f"{group_for[skill]}: {skill} is {statuses[skill]}; strategy={allocation.strategy}.",
                       "Previously recorded in history; alternatives exhausted for preferred cell." if q.question_id in seen
                       else "No prior exposure recorded in available history."]
            questions.append(PlannedQuestion(
                source_id=q.question_id, target_skill_id=skill, skill_ids=list(q.skill_ids),
                cognitive_level=q.cognitive_level, group=group_for[skill], targeted=skill in allocation.focus, reasons=reasons,
            ))
        achieved_skills = {s: sum(q.target_skill_id == s for q in questions) for s in allocation.skill_counts}
        achieved_groups = {g: sum(q.group == g for q in questions) for g in allocation.groups}
        achieved_levels = {level: sum(q.cognitive_level == level for q in questions) for level in LEVELS}
        achieved_skill_levels = {s: {level: sum(q.target_skill_id == s and q.cognitive_level == level for q in questions)
                                     for level in LEVELS} for s in allocation.skill_counts}
        for name, requested, achieved in (
            ("group", allocation.group_counts, achieved_groups),
            ("skill", allocation.skill_counts, achieved_skills),
            ("level", allocation.levels, achieved_levels),
        ):
            if requested != achieved:
                warnings.append(f"Soft {name} quotas deviated: requested={requested}, achieved={achieved}.")
        target = allocation.group_counts.get("focus", 0)
        targeted = achieved_groups.get("focus", 0)
        if targeted != target:
            warnings.append(f"Focus quota achieved {targeted}/{target}; substituted valid in-scope questions.")
        return ExamPlan(
            policy_version=self.policy.version + ("+" + self.relationships.version if self.relationships else ""),
            student_id=profile.student_id, requested_mode=request.generation_mode,
            strategy=allocation.strategy, personalized=bool(allocation.focus) and targeted > 0, priority_skills=allocation.focus,
            target_count=target, achieved_target_count=targeted, warnings=warnings, questions=questions,
            difficulty_locked=locked, skill_classifications=statuses,
            quota_summary=QuotaSummary(
                requested_groups=allocation.group_counts, achieved_groups=achieved_groups,
                requested_skills=allocation.skill_counts, achieved_skills=achieved_skills,
                requested_levels=allocation.levels, achieved_levels=achieved_levels,
                requested_skill_levels=allocation.skill_levels, achieved_skill_levels=achieved_skill_levels,
            ),
        )
