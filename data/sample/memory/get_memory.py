import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR/ "memory.db"

import sqlite3

def get_all_student():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT student_id, grade_level, name, birthday
        FROM Students
    """)
    rows = cursor.fetchall()

    students = [dict(row) for row in rows]

    for student in students:
        test_rows = cursor.execute("""
            SELECT test_id
            FROM Tests
            WHERE student_id = ?
        """, (student["student_id"],)).fetchall()

        student["learning_history"] = []

        for test in test_rows:
            test_id = test["test_id"]

            wrong_rows = cursor.execute("""
                SELECT question_id
                FROM test_questions
                WHERE is_correct = 0 AND test_id = ?
                ORDER BY question_order
            """, (test_id,)).fetchall()

            wrongs = [row["question_id"] for row in wrong_rows]

            student["learning_history"].append({
                "test_id": test_id,
                "wrongs": wrongs
            })
            
    conn.close()
    return students

print(get_all_student())
