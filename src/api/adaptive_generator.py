"""Compatibility boundary between team contracts and the finalized Generator.

The namespaced core retains its committed algorithms. Only DTOs and repository
paths cross this boundary; legacy non-adaptive fixture assembly stays separate.
"""

from collections import Counter
from pathlib import Path

from src.api.data_adapter import (
    DEFAULT_BANK,
    DEFAULT_FIXTURES,
    FixtureQuestion,
    StaticDataAdapter,
)
from src.api.schemas import ExamResponse, StudentProfileResponse, Topic
from src.exam_generator.adaptation.planner import RuleBasedPlanner
from src.exam_generator.api import schemas as core
from src.exam_generator.api.data_adapter import FixtureQuestion as CoreQuestion
from src.exam_generator.api.data_adapter import StaticDataAdapter as CoreData
from src.exam_generator.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter
from src.exam_generator.orchestration.exam_service import ExamService


def core_profile(profile: StudentProfileResponse) -> core.StudentProfileResponse:
    return core.StudentProfileResponse(
        student_id=profile.student_id,
        name=profile.student_name,
        grade_level=profile.grade_level,
        skill_mastery=[s.model_dump() for s in profile.skill_mastery],
        learning_history=[item.model_dump() for item in profile.learning_history],
    )


def public_profile(profile: core.StudentProfileResponse) -> StudentProfileResponse:
    value = profile.model_dump()
    value["student_name"] = value.pop("name")
    # SQL has no profile-level evidence aggregate. Do not fabricate one.
    return StudentProfileResponse(**value, recommended_blueprint_mode="adaptive")


def core_exam(exam: ExamResponse) -> core.ExamResponse:
    return core.ExamResponse.model_validate(
        exam.model_dump(exclude={"evidence_count", "data_status"})
    )


def public_exam(exam: core.ExamResponse, metadata) -> ExamResponse:
    return ExamResponse(
        **exam.model_dump(),
        evidence_count=metadata.evidence_count,
        data_status=metadata.data_status,
    )


class SQLDataAdapter(StaticDataAdapter):
    """Project-local Data Lead databases, read-only, without demo fallback."""

    def __init__(
        self,
        *,
        bank_path: Path = DEFAULT_BANK,
        student_path: Path = DEFAULT_STUDENTS,
        fixture_dir: Path = DEFAULT_FIXTURES,
    ):
        super().__init__(fixture_dir, bank_path)
        self.core = M3DataAdapter(bank_path=bank_path, student_path=student_path)

    @property
    def topic(self):
        return Topic.model_validate(self.core.topic.model_dump())

    @property
    def profiles(self):
        return {key: public_profile(value) for key, value in self.core.profiles.items()}

    @property
    def questions(self):
        fields = FixtureQuestion.model_fields
        return [
            FixtureQuestion.model_validate(q.model_dump(include=set(fields)))
            for q in self.core.questions
        ]

    def get_profile(self, student_id):
        return public_profile(self.core.get_profile(student_id))


def core_data(data: StaticDataAdapter) -> CoreData:
    if isinstance(data, SQLDataAdapter):
        return data.core
    # JSON remains an explicit test/offline source, never a missing-SQL fallback.
    result = CoreData(data._fixture_dir, data._bank_path)
    result._topic = core.Topic.model_validate(data.topic.model_dump())
    result._questions = [
        CoreQuestion.model_validate(q.model_dump()) for q in data.questions
    ]
    return result


def core_request(request):
    return core.GenerateExamRequest.model_validate(request.model_dump())


class AdaptiveExamGenerator:
    def __init__(
        self, data, client=None, *, fake=False, relationships=None, instance_seed=None
    ):
        self.data = core_data(data)
        self.planner = RuleBasedPlanner(self.data, relationships=relationships)
        self.service = ExamService(
            self.data,
            client,
            planner=self.planner,
            fake=fake,
            instance_seed=instance_seed,
        )

    def plan(self, request, profile):
        return self.planner.plan(core_request(request), core_profile(profile))

    def generate(self, request, profile):
        return public_exam(
            self.service.generate(core_request(request), core_profile(profile)),
            profile,
        )

    def validate_output(self, request, profile, exam):
        """Compare requested quotas with an independent allocation, not provider claims."""
        allocation = self.planner.build_allocation_plan(
            core_request(request), core_profile(profile)
        )
        summary = exam.planner_summary
        if summary is None:
            raise ValueError("Adaptive output requires the Planner blueprint")
        quota = summary.quota_summary
        if (
            quota.requested_levels != allocation.levels
            or quota.requested_skills != allocation.skill_counts
            or quota.requested_skill_levels != allocation.skill_levels
            or quota.requested_groups != allocation.group_counts
            or summary.strategy != allocation.strategy
            or summary.skill_classifications
            != self.planner.classify(
                core_profile(profile), list(allocation.skill_counts)
            )
            or summary.difficulty_locked
        ):
            raise ValueError("Adaptive output changed the Planner allocation")
        levels = Counter(q.cognitive_level for q in exam.questions)
        skills = Counter(q.target_skill_id for q in exam.questions)
        if (
            quota.achieved_levels != {lv: levels[lv] for lv in core.LEVELS}
            or quota.achieved_skills
            != {skill: skills[skill] for skill in allocation.skill_counts}
            or quota.achieved_skill_levels
            != {
                skill: {
                    level: sum(
                        q.target_skill_id == skill and q.cognitive_level == level
                        for q in exam.questions
                    )
                    for level in core.LEVELS
                }
                for skill in allocation.skill_counts
            }
            or quota.achieved_groups
            != {
                group: sum(q.target_skill_id in members for q in exam.questions)
                for group, members in allocation.groups.items()
            }
            or any(
                q.target_skill_id not in allocation.skill_counts for q in exam.questions
            )
        ):
            raise ValueError("Reported achieved quotas do not describe the exam")
        if quota.achieved_levels != allocation.levels:
            diagnostics = summary.selection_diagnostics
            if (
                diagnostics is None
                or diagnostics.exact_exam_levels_feasible
                or not diagnostics.level_shortages
                or not diagnostics.substitutions
            ):
                raise ValueError(
                    "Difficulty substitution requires explicit shortage diagnostics"
                )
        self.data.validate_exam_references(core_exam(exam))

    def regenerate_question(self, exam, question_id):
        return public_exam(
            self.service.regenerate_question(core_exam(exam), question_id), exam
        )
