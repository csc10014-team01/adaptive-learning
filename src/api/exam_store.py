"""Application-owned storage. Never writes generated drafts into canonical M3 tables."""

from pathlib import Path
import sqlite3

from src.api.data_adapter import ApiFailure
from src.api.schemas import ExamResponse


class SQLiteExamStore:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS exam_drafts (exam_id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS exam_revisions ("
                               "exam_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, "
                               "PRIMARY KEY (exam_id, revision))")
        except Exception:
            connection.close()
            raise
        return connection

    def save(self, exam: ExamResponse) -> None:
        connection = self._connect()
        try:
            with connection:
                connection.execute("INSERT INTO exam_drafts VALUES (?, ?)", (exam.exam_id, exam.model_dump_json()))
                connection.execute("INSERT INTO exam_revisions VALUES (?, ?, ?)",
                                   (exam.exam_id, exam.revision, exam.model_dump_json()))
        finally:
            connection.close()

    def get(self, exam_id: str) -> ExamResponse:
        connection = self._connect()
        try:
            row = connection.execute("SELECT body FROM exam_drafts WHERE exam_id = ?", (exam_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ApiFailure(404, "EXAM_NOT_FOUND", "Không tìm thấy exam draft.")
        return ExamResponse.model_validate_json(row[0])

    def replace(self, exam: ExamResponse, *, expected_revision: int) -> None:
        """Compare-and-swap prevents a slow regeneration overwriting teacher review."""
        exam = ExamResponse.model_validate(exam)
        if exam.revision != expected_revision + 1:
            raise ValueError("Replacement must advance the revision once")
        connection = self._connect()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT body FROM exam_drafts WHERE exam_id = ?", (exam.exam_id,)).fetchone()
                if row is None:
                    raise ApiFailure(404, "EXAM_NOT_FOUND", "Exam not found")
                current = ExamResponse.model_validate_json(row[0])
                if current.revision != expected_revision:
                    raise ApiFailure(409, "EXAM_REVISION_CONFLICT", "Reload the latest draft before changing it")
                # Also preserve the original snapshot for pre-upgrade draft files.
                connection.execute("INSERT OR IGNORE INTO exam_revisions VALUES (?, ?, ?)",
                                   (current.exam_id, current.revision, current.model_dump_json()))
                connection.execute("UPDATE exam_drafts SET body = ? WHERE exam_id = ?",
                                   (exam.model_dump_json(), exam.exam_id))
                connection.execute("INSERT INTO exam_revisions VALUES (?, ?, ?)",
                                   (exam.exam_id, exam.revision, exam.model_dump_json()))
        finally:
            connection.close()
