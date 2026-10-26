"""Read canonical M3 databases without running legacy writers or changing their schema."""

from pathlib import Path
import sqlite3

from pydantic import ValidationError

from src.api.data_adapter import ApiFailure, FixtureQuestion, ROOT, StaticDataAdapter
from src.api.schemas import StudentProfileResponse

DEFAULT_STUDENTS = ROOT / "data/sample/memory/student_profiles_sample.db"
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
            known = {s.skill_id for s in self.topic.skills}
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
                result[profile.student_id] = profile
            return result
        except (sqlite3.Error, OSError, ValueError, ValidationError) as exc:
            raise ApiFailure(500, "INVALID_PROFILE_DATA", "Không đọc được hồ sơ M3 hợp lệ.") from exc
        finally:
            if connection is not None:
                connection.close()

    def _load_questions(self) -> list[FixtureQuestion]:
        connection = None
        try:
            connection = readonly(self._bank_path)
            connection.execute("BEGIN")
            known = {s.skill_id for s in self.topic.skills}
            result = []
            for row in connection.execute(
                "SELECT * FROM questions WHERE question_type = 'essay' "
                "AND grade_level = 10 AND status IN ('draft', 'active') ORDER BY question_id"
            ):
                skills = [s[0] for s in connection.execute(
                    "SELECT skill_id FROM question_skills WHERE question_id = ? ORDER BY skill_id",
                    (row["question_id"],),
                )]
                # Do not infer missing links or guess unrecognised difficulty labels.
                if not skills or not set(skills).issubset(known) or row["difficulty"] not in DIFFICULTY_LEVELS:
                    continue
                answers = connection.execute(
                    "SELECT correct_answer, explaination FROM answers WHERE question_id = ? ORDER BY answer_id",
                    (row["question_id"],),
                ).fetchall()
                if len(answers) != 1:
                    continue
                parts = connection.execute(
                    "SELECT p.label, p.content, a.correct_answer, a.explanation "
                    "FROM question_parts p LEFT JOIN answer_parts a USING(part_id) "
                    "WHERE p.question_id = ? ORDER BY p.label", (row["question_id"],),
                ).fetchall()
                if any(not p["correct_answer"] or not p["explanation"] for p in parts):
                    continue
                content = row["content"] + "".join(f"\n{p['label']}) {p['content']}" for p in parts)
                answer, explanation = answers[0]
                if parts:
                    answer += "\n" + "\n".join(f"{p['label']}) {p['correct_answer']}" for p in parts)
                    explanation += "\n" + "\n".join(f"{p['label']}) {p['explanation']}" for p in parts)
                result.append(FixtureQuestion(
                    question_id=row["question_id"], grade_level=row["grade_level"], skill_ids=skills,
                    primary_skill_id=row["primary_skill_id"] if "primary_skill_id" in row.keys() else None,
                    cognitive_level=DIFFICULTY_LEVELS[row["difficulty"]], generate_type="direct",
                    content=content, answer={"correct_answer": answer, "explanation": explanation},
                    solution_steps=[explanation],
                    rubric_criteria=["Lập luận đúng phương pháp và kết luận phù hợp đáp án nguồn M3."],
                ))
            return result
        except (sqlite3.Error, OSError, ValueError, ValidationError) as exc:
            raise ApiFailure(500, "DATA_SOURCE_ERROR", "Không đọc được ngân hàng câu hỏi M3.") from exc
        finally:
            if connection is not None:
                connection.close()
