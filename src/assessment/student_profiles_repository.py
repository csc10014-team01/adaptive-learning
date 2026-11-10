import sqlite3
from pathlib import Path

from grading_repository import get_test, update_status

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR/"data"/"sample"/"memory"/"student_profiles_sample.db"


def get_all_student() -> list[dict[str, object]] | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT student_id, grade_level, name, birthday
            FROM Students
        """)
        rows = cursor.fetchall()

        students = []

        for row in rows:
            student = dict(row)
            student_id = student["student_id"]

            # Lấy lịch sử các bài kiểm tra của học sinh

            student["learning_history"] = get_test(student)
            
            # Lấy mức độ thành thạo kỹ năng
            mastery_rows = cursor.execute("""
                SELECT skill_id, mastery_score, evidence_count
                FROM student_skill_mastery
                WHERE student_id = ?
            """, (student_id,)).fetchall()

            student["skill_mastery"] = [
                dict(item) for item in mastery_rows
            ]

            students.append(student)
            update_status(student)

        return students

    finally:
        conn.close()

def get_student_by_id(student_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        # Lấy thông tin học sinh
        cursor.execute("""
            SELECT student_id, grade_level, name, birthday
            FROM Students
            WHERE student_id = ?
        """, (student_id,))

        row = cursor.fetchone()

        # Không tìm thấy học sinh
        if row is None:
            return None

        student = dict(row)

        # Lấy lịch sử các bài kiểm tra của học sinh

        student["learning_history"] = get_test(student)
        

        # Lấy mức độ thành thạo kỹ năng
        mastery_rows = cursor.execute("""
            SELECT skill_id, mastery_score, evidence_count
            FROM student_skill_mastery
            WHERE student_id = ?
        """, (student_id,)).fetchall()

        student["skill_mastery"] = [
            dict(item) for item in mastery_rows
        ]
        update_status(student)

        return student

    finally:
        conn.close()