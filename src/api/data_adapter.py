"""Read-only boundary for static Data JSON and the canonical skill catalogue."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from src.ai.problem_spec import ProblemSpec, render_template
from src.api.schemas import (
    Answer,
    CognitiveLevel,
    ContractModel,
    ExamResponse,
    GradeLevel,
    Identifier,
    SkillLabel,
    StudentProfileResponse,
    StudentSummary,
    Text,
    Topic,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / "data" / "sample" / "api_demo"
# User-confirmed Data Lead database in this workspace. M3_QUESTION_DB remains
# the deployment override; algorithm modules never hardcode database paths.
DEFAULT_BANK = (
    ROOT.parents[1] / "pre-work" / "data" / "sample" / "dataset" / "question_bank.db"
)


class ApiFailure(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class ProfileFile(ContractModel):
    fixture_kind: Literal["synthetic_api_demo", "data_module"]
    topic_id: Literal["combinatorics"]
    students: list[StudentProfileResponse]


class FixtureQuestion(ContractModel):
    question_id: Identifier
    grade_level: GradeLevel
    skill_ids: list[Identifier] = Field(min_length=1)
    topic_id: Literal["combinatorics"] = "combinatorics"
    # Legacy multi-skill sources remain readable, but cannot be planned until
    # their author supplies a primary. Never infer it from skill list order.
    primary_skill_id: Identifier | None = None
    cognitive_level: CognitiveLevel
    generate_type: Literal["direct"]
    content: Text
    answer: Answer
    solution_steps: list[Text] = Field(min_length=1)
    rubric_criteria: list[Text] = Field(min_length=1)
    problem_spec: ProblemSpec | None = None

    @model_validator(mode="after")
    def valid_skill_links(self):
        if len(set(self.skill_ids)) != len(self.skill_ids):
            raise ValueError("Question skill_ids must be unique")
        if self.primary_skill_id is None and len(self.skill_ids) == 1:
            # Documented legacy sole-skill migration at the read boundary only.
            self.primary_skill_id = self.skill_ids[0]
        if (
            self.primary_skill_id is not None
            and self.primary_skill_id not in self.skill_ids
        ):
            raise ValueError("primary_skill_id must belong to skill_ids")
        if self.problem_spec is not None and (
            self.problem_spec.source_id != self.question_id
            or self.problem_spec.verified_answer != self.answer.correct_answer
            or self.problem_spec.verified_solution != self.solution_steps
        ):
            raise ValueError(
                "ProblemSpec must match the source identity, answer and solution steps"
            )
        if self.problem_spec is not None:
            spec = self.problem_spec
            context = next(
                c
                for c in spec.supported_contexts
                if c.context_id == spec.source_context_id
            )
            direct = next(
                p for p in context.presentations if p.generate_type == "direct"
            )
            if self.content != render_template(direct.template, spec.parameters):
                raise ValueError(
                    "ProblemSpec direct source presentation must match source content"
                )
        return self


class QuestionFile(ContractModel):
    fixture_kind: Literal["synthetic_api_demo", "data_module"]
    topic_id: Literal["combinatorics"]
    questions: list[FixtureQuestion]


class StaticDataAdapter:
    """Read MVP profiles without deriving evidence or applying planner policies."""

    def __init__(
        self, fixture_dir: Path = DEFAULT_FIXTURES, bank_path: Path = DEFAULT_BANK
    ):
        self._fixture_dir = fixture_dir
        self._bank_path = bank_path
        self._lock = RLock()
        self._topic: Topic | None = None
        self._profiles: dict[str, StudentProfileResponse] | None = None
        self._questions: list[FixtureQuestion] | None = None
        self._sources: tuple[dict[str, set[str]], set[str]] | None = None
        self._templates = []
        self.template_warnings = []
        self.question_warnings = []
        self.question_diagnostics = []
        self._presentation_registry = None

    @property
    def presentation_registry(self):
        from src.ai.template_presentations import (
            DEFAULT_PRESENTATIONS,
            TemplatePresentations,
        )

        path = Path(
            os.getenv("TEMPLATE_PRESENTATIONS_FILE", str(DEFAULT_PRESENTATIONS))
        )
        if not path.is_absolute():
            path = ROOT / path
        try:
            registry = self._presentation_registry or TemplatePresentations.load(path)
            enabled = os.getenv("KORO_EXPERIMENTAL_INDIRECT")
            if enabled is not None:
                if enabled.lower() not in ("0", "1", "true", "false"):
                    raise ValueError(
                        "KORO_EXPERIMENTAL_INDIRECT must be 0/1/true/false"
                    )
                registry = registry.model_copy(
                    update={"experimental_indirect": enabled.lower() in ("1", "true")}
                )
            return registry
        except (OSError, ValueError) as exc:
            raise ApiFailure(
                500,
                "PRESENTATION_CONFIG_ERROR",
                "Cannot read valid Template presentation configuration",
            ) from exc

    @property
    def templates(self):
        """JSON/demo catalogues opt into explicitly supplied templates only."""
        return self._templates

    @property
    def topic(self) -> Topic:
        with self._lock:
            if self._topic is None:
                self._topic = self._load_topic(self._bank_path)
            return self._topic

    @property
    def profiles(self) -> dict[str, StudentProfileResponse]:
        with self._lock:
            if self._profiles is None:
                self._profiles = self._load_profiles()
            return self._profiles

    @property
    def questions(self) -> list[FixtureQuestion]:
        with self._lock:
            if self._questions is None:
                self._questions = self._load_questions()
            return self._questions

    def _load_profiles(self) -> dict[str, StudentProfileResponse]:
        try:
            profiles = ProfileFile.model_validate(
                self._read(self._fixture_dir / "student_profiles.json")
            )
        except (OSError, ValueError, ValidationError) as exc:
            raise ApiFailure(
                500, "INVALID_PROFILE_DATA", "Không đọc được static profiles hợp lệ."
            ) from exc

        result: dict[str, StudentProfileResponse] = {}
        known_skills = {skill.skill_id for skill in self.topic.skills}
        for profile in profiles.students:
            try:
                if profile.student_id in result or any(
                    skill.skill_id not in known_skills
                    for skill in profile.skill_mastery
                ):
                    raise ValueError("Duplicate student or unknown skill")
            except (ValueError, ValidationError) as exc:
                raise ApiFailure(
                    500, "INVALID_PROFILE_DATA", "Static profile vi phạm contract."
                ) from exc
            result[profile.student_id] = profile
        return result

    def _load_questions(self) -> list[FixtureQuestion]:
        try:
            questions = QuestionFile.model_validate(
                self._read(self._fixture_dir / "questions.json")
            )
        except (OSError, ValueError, ValidationError) as exc:
            raise ApiFailure(
                500, "DATA_SOURCE_ERROR", f"Invalid question fixtures: {exc}"
            ) from exc
        known_skills = {skill.skill_id for skill in self.topic.skills}
        if len({q.question_id for q in questions.questions}) != len(
            questions.questions
        ) or any(
            skill not in known_skills
            for q in questions.questions
            for skill in q.skill_ids
        ):
            raise ApiFailure(
                500,
                "DATA_SOURCE_ERROR",
                "Question fixtures có ID trùng hoặc skill không tồn tại.",
            )
        return questions.questions

    def _source_catalogue(self) -> tuple[dict[str, set[str]], set[str]]:
        """Existing SQL identities/links only; no invented template skill mapping."""
        with self._lock:
            if self._sources is None:
                try:
                    connection = sqlite3.connect(
                        self._bank_path.resolve().as_uri() + "?mode=ro", uri=True
                    )
                    try:
                        connection.execute("PRAGMA query_only=ON")
                        rows = connection.execute(
                            "SELECT q.question_id, qs.skill_id FROM questions AS q "
                            "LEFT JOIN question_skills AS qs ON qs.question_id = q.question_id "
                            "WHERE q.grade_level = ?",
                            (10,),
                        ).fetchall()
                        templates = {
                            row[0]
                            for row in connection.execute(
                                "SELECT template_id FROM question_templates"
                            )
                        }
                    finally:
                        connection.close()
                except (sqlite3.Error, OSError) as exc:
                    raise ApiFailure(
                        500, "DATA_SOURCE_ERROR", "Không đọc được source catalogue."
                    ) from exc
                questions: dict[str, set[str]] = {}
                for question_id, skill_id in rows:
                    skills = questions.setdefault(question_id, set())
                    if skill_id is not None:
                        skills.add(skill_id)
                self._sources = questions, templates
            return self._sources

    def validate_exam_references(self, exam: ExamResponse) -> None:
        """Check immutable Questions or recompute Template proofs before storage.

        Template scope comes from explicit SQL skill links. The type-specific
        branches preserve content/answers for Questions and revalidate parameters,
        answer, solution, scope and fingerprints for generated Template instances.
        """
        from src.ai.template_instantiator import TemplateInstantiator, template_digest
        from src.ai.template_presentations import validate_template_wording
        from src.orchestration.source_snapshot import source_digest

        known = {s.skill_id for s in self.topic.skills}
        questions = {q.question_id: q for q in self.questions}
        templates = {t.template_id: t for t in self.templates}
        for question in exam.questions:
            if not set(question.skill_ids).issubset(known):
                raise ValueError("Unknown source skill IDs")
            ref = question.source_ref
            if ref.kind == "question":
                source = questions.get(ref.id)
                if source is None:
                    raise ValueError("Question source is not in the eligible bank")
                if (
                    question.content_latex != source.content
                    or question.answer != source.answer
                    or question.generate_type != source.generate_type
                    or [s.explanation for s in question.step_solutions]
                    != source.solution_steps
                    or question.skill_ids != source.skill_ids
                    or question.cognitive_level != source.cognitive_level
                    or exam.grade_level != source.grade_level
                    or question.topic_tag != source.topic_id
                    or (
                        question.target_skill_id is not None
                        and question.target_skill_id != source.primary_skill_id
                    )
                    or (
                        question.source_digest is not None
                        and question.source_digest != source_digest(source)
                    )
                ):
                    raise ValueError(
                        "Immutable Question metadata, answer, solution or content changed"
                    )
            else:
                template = templates.get(ref.id)
                if template is None or question.template_instance is None:
                    raise ValueError(
                        "Template source or instance provenance is missing"
                    )
                instance = TemplateInstantiator().materialize(
                    template, question.template_instance.parameters
                )
                if (
                    template.difficulty not in (1, 2)
                    or question.template_instance != instance.record
                    or question.source_digest != template_digest(template)
                    or question.answer != instance.answer
                    or [s.explanation for s in question.step_solutions]
                    != instance.solution_steps
                    or question.skill_ids != template.skill_ids
                    or question.target_skill_id not in template.skill_ids
                    or question.cognitive_level != template.cognitive_level
                    or question.topic_tag != template.topic_id
                    or exam.grade_level != template.grade_level
                ):
                    raise ValueError(
                        "Template instance does not reproduce its verified source rules"
                    )
                validate_template_wording(
                    instance,
                    question.content_latex,
                    question.generate_type,
                    question.template_presentation,
                    self.presentation_registry,
                )

    @staticmethod
    def _read(path: Path) -> object:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _load_topic(bank_path: Path) -> Topic:
        try:
            connection = sqlite3.connect(
                bank_path.resolve().as_uri() + "?mode=ro", uri=True
            )
            try:
                connection.execute("PRAGMA query_only=ON")
                rows = connection.execute(
                    "SELECT skill_id, name FROM skills WHERE grade_level = ? AND topic = ? ORDER BY skill_id",
                    (10, "Đại số tổ hợp"),
                ).fetchall()
            finally:
                connection.close()
            if not rows:
                raise ValueError("Empty skill catalogue")
            return Topic(
                topic_id="combinatorics",
                topic_name="Đại số tổ hợp",
                grade_level=10,
                skills=[SkillLabel(skill_id=row[0], name=row[1]) for row in rows],
            )
        except (sqlite3.Error, ValueError, OSError) as exc:
            raise ApiFailure(
                500, "DATA_SOURCE_ERROR", "Không đọc được canonical skill catalogue."
            ) from exc

    def get_profile(self, student_id: str) -> StudentProfileResponse:
        profiles = self.profiles
        if student_id not in profiles:
            raise ApiFailure(404, "STUDENT_NOT_FOUND", "Không tìm thấy học sinh.")
        return profiles[student_id].model_copy(deep=True)

    def list_students(self) -> list[StudentSummary]:
        return [
            StudentSummary.model_validate(
                {
                    field: getattr(profile, field)
                    for field in StudentSummary.model_fields
                }
            )
            for profile in self.profiles.values()
        ]
