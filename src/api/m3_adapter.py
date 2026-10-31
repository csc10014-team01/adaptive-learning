"""Read canonical M3 databases without running legacy writers or changing their schema."""

from pathlib import Path
from contextlib import contextmanager
import sqlite3

from pydantic import ValidationError

from src.api.data_adapter import ApiFailure, FixtureQuestion, ROOT, StaticDataAdapter
from src.api.schemas import SkillMastery, StudentProfileResponse

# Data Lead source, not the app-local SQL copy populated by offline scenarios.
# Explicit M3_STUDENT_DB overrides are applied at API configuration time.
DEFAULT_STUDENTS = ROOT.parents[1] / "pre-work/data/sample/memory/student_profiles_sample.db"
# Explicit application annotation policy v1; this is not metadata supplied by M3.
DIFFICULTY_LEVELS = {
    1: "recognition", 2: "understanding", 3: "application",
    4: "advanced_application", 5: "advanced_application",
}


def readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


class M3DataAdapter(StaticDataAdapter):
    """Profiles stay live; bank questions/skills are cached for the process lifetime."""

    def __init__(self, *, student_path: Path = DEFAULT_STUDENTS, profile_json: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.student_path = student_path
        self.profile_json = profile_json
        self._bank_stamp = None

    def _assert_bank_version(self):
        try:
            info = self._bank_path.stat()
        except OSError as exc:
            raise ApiFailure(500, "DATA_SOURCE_ERROR", f"Configured Question Bank is unavailable: {self._bank_path}") from exc
        stamp = (info.st_mtime_ns, info.st_size)
        if self._bank_stamp is not None and stamp != self._bank_stamp:
            raise ApiFailure(409, "SOURCE_CHANGED",
                "Configured Question Bank changed; reload_bank() or restart before preview/generation")
        self._bank_stamp = stamp

    @contextmanager
    def _bank_read(self):
        # Questions are cached, Templates are re-read for integrity. Do not mix
        # those caches with a newly replaced Data Lead file without a reload.
        with self._lock:
            self._assert_bank_version()
            yield
            self._assert_bank_version()

    @property
    def topic(self):
        with self._bank_read():
            return super().topic

    @property
    def questions(self):
        with self._bank_read():
            return super().questions

    @property
    def templates(self):
        # Reload definitions for source-integrity checks on regeneration. This
        # reads only 18 definitions and never writes the Data Lead's database.
        from src.api.template_repository import load_templates
        with self._bank_read():
            try:
                templates, self.template_warnings = load_templates(self._bank_path)
                return templates
            except (sqlite3.Error, OSError, ValueError) as exc:
                self.template_warnings = [f"Template Bank unavailable: {exc}; using Question Bank."]
                return []

    @property
    def profiles(self) -> dict[str, StudentProfileResponse]:
        if self.profile_json:
            return super().profiles
        return self._load_profiles()

    def _load_profiles(self) -> dict[str, StudentProfileResponse]:
        if self.profile_json:
            return super()._load_profiles()
        connection = None
        try:
            connection = readonly(self.student_path)
            connection.execute("BEGIN")
            result = {}
            catalogue = sorted(s.skill_id for s in self.topic.skills)
            known = set(catalogue)
            for student in connection.execute(
                "SELECT student_id, name, grade_level FROM Students ORDER BY student_id"
            ):
                record = dict(student)
                record["skill_mastery"] = [dict(row) for row in connection.execute(
                    "SELECT skill_id, mastery_score, evidence_count FROM student_skill_mastery "
                    "WHERE student_id = ? ORDER BY skill_id", (student["student_id"],),
                )]
                record["learning_history"] = [
                    {"test_id": test[0], "wrong_questions": [row[0] for row in connection.execute(
                        "SELECT question_id FROM test_questions WHERE test_id = ? "
                        "AND is_correct = 0 ORDER BY question_order", (test[0],),
                    )]}
                    for test in connection.execute(
                        "SELECT test_id FROM Tests WHERE student_id = ? ORDER BY date, test_id",
                        (student["student_id"],),
                    )
                ]
                profile = StudentProfileResponse.model_validate(record)
                if any(s.skill_id not in known for s in profile.skill_mastery):
                    raise ValueError("Unknown M3 skill")
                measured = {s.skill_id: s for s in profile.skill_mastery}
                # Complete the response catalogue only. Never INSERT a student
                # skill or invent a neutral/estimated numeric mastery in SQLite.
                profile.skill_mastery = [measured[skill] if skill in measured else
                    SkillMastery(skill_id=skill, mastery_score=None, evidence_count=0)
                    for skill in catalogue]
                result[profile.student_id] = profile
            return result
        except (sqlite3.Error, OSError, ValueError, ValidationError) as exc:
            detail = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
            raise ApiFailure(500, "INVALID_PROFILE_DATA",
                f"Không đọc được hồ sơ SQLite hợp lệ ({self.student_path}): {detail}") from exc
        finally:
            if connection is not None:
                connection.close()

    def reload_bank(self):
        """Reload corrected Data Lead records; never update the source database."""
        with self._lock:
            self._topic = self._questions = self._sources = None
            self._bank_stamp = None
            self.question_diagnostics = []
            self.question_warnings = []
            self.template_warnings = []

    def _load_questions(self) -> list[FixtureQuestion]:
        from src.api.question_repository import read_questions
        connection = None
        try:
            connection = readonly(self._bank_path)
            connection.execute("BEGIN")
            known = {s.skill_id for s in self.topic.skills}
            result, self.question_diagnostics, self.question_warnings = read_questions(
                connection, known, DIFFICULTY_LEVELS)
            return result
        except (sqlite3.Error, OSError, ValueError, ValidationError) as exc:
            raise ApiFailure(500, "DATA_SOURCE_ERROR",
                f"Cannot read configured Question Bank {self._bank_path}: {exc}") from exc
        finally:
            if connection is not None:
                connection.close()
