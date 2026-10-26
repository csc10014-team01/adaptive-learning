"""Read-only boundary for static Data JSON and the canonical skill catalogue."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from src.api.schemas import (
    Answer, CognitiveLevel, ContractModel, ExamResponse, GradeLevel, Identifier, SkillLabel,
    StudentProfileResponse, StudentSummary, Text, Topic,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / "data" / "sample" / "api_demo"
DEFAULT_BANK = ROOT / "data" / "sample" / "dataset" / "question_bank.db"


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

    @model_validator(mode="after")
    def valid_skill_links(self):
        if len(set(self.skill_ids)) != len(self.skill_ids):
            raise ValueError("Question skill_ids must be unique")
        if self.primary_skill_id is None and len(self.skill_ids) == 1:
            # Documented legacy sole-skill migration at the read boundary only.
            self.primary_skill_id = self.skill_ids[0]
        if self.primary_skill_id is not None and self.primary_skill_id not in self.skill_ids:
            raise ValueError("primary_skill_id must belong to skill_ids")
        return self


class QuestionFile(ContractModel):
    fixture_kind: Literal["synthetic_api_demo", "data_module"]
    topic_id: Literal["combinatorics"]
    questions: list[FixtureQuestion]


class StaticDataAdapter:
    """Read MVP profiles without deriving evidence or applying planner policies."""

    def __init__(self, fixture_dir: Path = DEFAULT_FIXTURES, bank_path: Path = DEFAULT_BANK):
        self._fixture_dir = fixture_dir
        self._bank_path = bank_path
        self._lock = RLock()
        self._topic: Topic | None = None
        self._profiles: dict[str, StudentProfileResponse] | None = None
        self._questions: list[FixtureQuestion] | None = None
        self._sources: tuple[dict[str, set[str]], set[str]] | None = None

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
            profiles = ProfileFile.model_validate(self._read(self._fixture_dir / "student_profiles.json"))
        except (OSError, ValueError, ValidationError) as exc:
            raise ApiFailure(500, "INVALID_PROFILE_DATA", "Không đọc được static profiles hợp lệ.") from exc

        result: dict[str, StudentProfileResponse] = {}
        known_skills = {skill.skill_id for skill in self.topic.skills}
        for profile in profiles.students:
            try:
                if profile.student_id in result or any(
                    skill.skill_id not in known_skills for skill in profile.skill_mastery
                ):
                    raise ValueError("Duplicate student or unknown skill")
            except (ValueError, ValidationError) as exc:
                raise ApiFailure(500, "INVALID_PROFILE_DATA", "Static profile vi phạm contract.") from exc
            result[profile.student_id] = profile
        return result

    def _load_questions(self) -> list[FixtureQuestion]:
        try:
            questions = QuestionFile.model_validate(self._read(self._fixture_dir / "questions.json"))
        except (OSError, ValueError, ValidationError) as exc:
            raise ApiFailure(500, "DATA_SOURCE_ERROR", f"Invalid question fixtures: {exc}") from exc
        known_skills = {skill.skill_id for skill in self.topic.skills}
        if len({q.question_id for q in questions.questions}) != len(questions.questions) or any(
            skill not in known_skills for q in questions.questions for skill in q.skill_ids
        ):
            raise ApiFailure(500, "DATA_SOURCE_ERROR", "Question fixtures có ID trùng hoặc skill không tồn tại.")
        return questions.questions

    def _source_catalogue(self) -> tuple[dict[str, set[str]], set[str]]:
        """Existing SQL identities/links only; no invented template skill mapping."""
        with self._lock:
            if self._sources is None:
                try:
                    connection = sqlite3.connect(self._bank_path.resolve().as_uri() + "?mode=ro", uri=True)
                    try:
                        connection.execute("PRAGMA query_only=ON")
                        rows = connection.execute(
                            "SELECT q.question_id, qs.skill_id FROM questions AS q "
                            "LEFT JOIN question_skills AS qs ON qs.question_id = q.question_id "
                            "WHERE q.grade_level = ?", (10,),
                        ).fetchall()
                        templates = {row[0] for row in connection.execute(
                            "SELECT template_id FROM question_templates"
                        )}
                    finally:
                        connection.close()
                except (sqlite3.Error, OSError) as exc:
                    raise ApiFailure(500, "DATA_SOURCE_ERROR", "Không đọc được source catalogue.") from exc
                questions: dict[str, set[str]] = {}
                for question_id, skill_id in rows:
                    skills = questions.setdefault(question_id, set())
                    if skill_id is not None:
                        skills.add(skill_id)
                self._sources = questions, templates
            return self._sources

    def validate_exam_references(self, exam: ExamResponse) -> None:
        """Check membership and question-skill links before a draft is stored.

        This establishes referential integrity, not source approval/math correctness.
        Canonical template rows do not have skill links, so only their identities and
        global skill membership can be verified without finalizing a new Data schema.
        """
        known_skills = {skill.skill_id for skill in self.topic.skills}
        canonical_questions, templates = self._source_catalogue()
        fixture_questions = None
        for question in exam.questions:
            skills = set(question.skill_ids)
            if len(skills) != len(question.skill_ids) or not skills.issubset(known_skills):
                raise ValueError("Unknown or duplicate returned skill IDs")
            source = question.source_ref
            if question.target_skill_id is not None:
                bank = {q.question_id: q for q in self.questions}
                original = bank.get(source.id)
                if original is None or original.primary_skill_id != question.target_skill_id:
                    raise ValueError("Returned target does not match the source primary skill")
                if (question.skill_ids != original.skill_ids or question.cognitive_level != original.cognitive_level
                        or exam.grade_level != original.grade_level or question.topic_tag != original.topic_id):
                    raise ValueError("Returned question metadata does not match its source")
            if source.kind == "template":
                if source.id not in templates:
                    raise ValueError("Unknown template source reference")
                continue
            if source.id in canonical_questions:
                source_skills = canonical_questions[source.id]
            else:
                if fixture_questions is None:
                    fixture_questions = {q.question_id: set(q.skill_ids) for q in self.questions}
                if source.id not in fixture_questions:
                    raise ValueError("Unknown question source reference")
                source_skills = fixture_questions[source.id]
            if not skills.issubset(source_skills):
                raise ValueError("Returned skills do not match the source question")

    @staticmethod
    def _read(path: Path) -> object:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _load_topic(bank_path: Path) -> Topic:
        try:
            connection = sqlite3.connect(bank_path.resolve().as_uri() + "?mode=ro", uri=True)
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
                topic_id="combinatorics", topic_name="Đại số tổ hợp", grade_level=10,
                skills=[SkillLabel(skill_id=row[0], name=row[1]) for row in rows],
            )
        except (sqlite3.Error, ValueError, OSError) as exc:
            raise ApiFailure(500, "DATA_SOURCE_ERROR", "Không đọc được canonical skill catalogue.") from exc

    def get_profile(self, student_id: str) -> StudentProfileResponse:
        profiles = self.profiles
        if student_id not in profiles:
            raise ApiFailure(404, "STUDENT_NOT_FOUND", "Không tìm thấy học sinh.")
        return profiles[student_id].model_copy(deep=True)

    def list_students(self) -> list[StudentSummary]:
        return [StudentSummary.model_validate({
            field: getattr(profile, field) for field in StudentSummary.model_fields
        }) for profile in self.profiles.values()]
