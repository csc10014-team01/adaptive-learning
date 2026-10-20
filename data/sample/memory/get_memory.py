import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR/ "memory.db"

import sqlite3

import sqlite3


def get_all_student():
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
            test_rows = cursor.execute("""
                SELECT test_id
                FROM Tests
                WHERE student_id = ?
            """, (student_id,)).fetchall()

            learning_history = []

            for test in test_rows:
                test_id = test["test_id"]

                wrong_rows = cursor.execute("""
                    SELECT question_id
                    FROM test_questions
                    WHERE test_id = ?
                      AND is_correct = 0
                    ORDER BY question_order
                """, (test_id,)).fetchall()

                learning_history.append({
                    "test_id": test_id,
                    "wrongs": [
                        item["question_id"]
                        for item in wrong_rows
                    ]
                })

            student["learning_history"] = learning_history

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

        return students

    finally:
        conn.close()

def get_student_by_id(student_id):
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
        test_rows = cursor.execute("""
            SELECT test_id
            FROM Tests
            WHERE student_id = ?
        """, (student_id,)).fetchall()

        learning_history = []

        for test in test_rows:
            test_id = test["test_id"]

            wrong_rows = cursor.execute("""
                SELECT question_id
                FROM test_questions
                WHERE test_id = ?
                  AND is_correct = 0
                ORDER BY question_order
            """, (test_id,)).fetchall()

            learning_history.append({
                "test_id": test_id,
                "wrongs": [
                    item["question_id"]
                    for item in wrong_rows
                ]
            })

        student["learning_history"] = learning_history

        # Lấy mức độ thành thạo kỹ năng
        mastery_rows = cursor.execute("""
            SELECT skill_id, mastery_score, evidence_count
            FROM student_skill_mastery
            WHERE student_id = ?
        """, (student_id,)).fetchall()

        student["skill_mastery"] = [
            dict(item) for item in mastery_rows
        ]

        return student

    finally:
        conn.close()
