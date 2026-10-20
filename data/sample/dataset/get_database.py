import sqlite3
import csv
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "question_bank.db"


#Hàm trả về tập tất cả question
def get_all_questions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    # Lấy dữ liệu từ bảng Questions
    cursor.execute("""
        SELECT question_id, question_type, difficulty,
            content, grade_level, status
        FROM questions
    """)

    rows = cursor.fetchall()
    # Chuyển mỗi dòng SQL thành Dictionary
    questions = [dict(row) for row in rows]

    for question in questions:
        cursor.execute("""
            SELECT part_id, label, content
            FROM question_parts
            WHERE question_id = ?
        """, (question["question_id"],))

        parts = cursor.fetchall()
        question["part"] = [dict(row) for row in parts]
    conn.close()
    return questions

#Hàm trả về 1 question
def get_question(question_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT * FROM questions WHERE question_id = ?",
            (question_id,)
        ).fetchone()

        if not row:
            return None
        
        question = dict(row)

        parts = conn.execute(
            "SELECT * FROM question_parts WHERE question_id = ?",
            (question_id,)
        ).fetchall()

        question["part"] = [dict(row) for row in parts]

        return question
    
def get_all_answers():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT * FROM answers"
        ).fetchall()

        answers = [dict(row) for row in rows]

        for answer in answers:
            question_id = answer["question_id"]

            part_ids = conn.execute(
                """
                SELECT part_id
                FROM question_parts
                WHERE question_id = ?
                """,
                (question_id,)
            ).fetchall()

            parts = []

            for row in part_ids:
                part_id = row["part_id"]

                part_rows = conn.execute(
                    "SELECT * FROM answer_parts WHERE part_id = ?",
                    (part_id,)
                ).fetchall()

                parts.extend(dict(row) for row in part_rows)

            answer["part"] = parts

        return answers

def get_answer(answer_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT * FROM answers WHERE answer_id = ?",
            (answer_id,)
        ).fetchone()
        if not row:
            return None

        answer = dict(row)
        question_id = answer["question_id"]
        cursor = conn.execute(
            "SELECT part_id FROM question_parts WHERE question_id = ?",
            (question_id,)
        )
        part_ids = cursor.fetchall()

        parts = []

        for row in part_ids:
            part_id = row[0]

            rows = conn.execute(
                "SELECT * FROM answer_parts WHERE part_id = ?",
                (part_id,)
            ).fetchall()

            parts.extend(dict(row) for row in rows)

        answer["part"] = parts

        return answer

def get_all_terminology():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    # Lấy dữ liệu từ bảng Terminology
    cursor.execute("""
        SELECT term, text
        FROM terminology
    """)

    rows = cursor.fetchall()
    # Chuyển mỗi dòng SQL thành Dictionary
    terminology = [dict(row) for row in rows]

    conn.close()

    return terminology

def get_terminology(term):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT * FROM terminology WHERE term = ?",
            (term,)
        ).fetchone()

        return dict(row) if row else None

def get_all_skills():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    # Lấy dữ liệu từ bảng Skills
    cursor.execute("""
        SELECT skill_id, topic, name, grade_level, description
        FROM skills
    """)

    rows = cursor.fetchall()
    # Chuyển mỗi dòng SQL thành Dictionary
    skills = [dict(row) for row in rows]
    conn.close()
    return skills

def get_skill(skill_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT * FROM skills WHERE skill_id = ?",
            (skill_id,)
        ).fetchone()

        return dict(row) if row else None


def get_question_template():
    conn = None

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM question_templates
        """)

        rows = cursor.fetchall()

        templates = [dict(row) for row in rows]
        return templates

    except sqlite3.Error as e:
        print(f"Lỗi khi đọc question_templates: {e}")
        return []

    finally:
        if conn is not None:
            conn.close()

def get_question_template_by_id(template_id):
    conn = None

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM question_templates
            WHERE template_id = ?
        """, (template_id,))

        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    except sqlite3.Error as e:
        print(f"Lỗi khi đọc question_templates: {e}")
        return None

    finally:
        if conn is not None:
            conn.close()
print(get_question_template_by_id("EA0001")['solution_rule'])