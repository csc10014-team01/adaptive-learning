import sqlite3
from pathlib import Path
from helper_functions import check_required_fields, check_duplicate, serialize_json
import json
import re
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data"/"sample"/"dataset"/ "question_bank.db"

# =========================
# QUESTIONS
# =========================


def parse_json(text):
    if not text:
        return None

    text = re.sub(r',\s*([}\]])', r'\1', text)

    return json.loads(text)


def validate_question(DB_PATH, question: dict) -> bool:
    """
    Kiểm tra:
    - Đủ trường bắt buộc.
    - Dữ liệu hợp lệ.
    - question_id chưa tồn tại.
    """

    required_fields = [
        "question_id",
        "question_type",
        "difficulty",
        "content",
        "grade_level",
        "status",
        "rubric",
        "step_difficulties"
    ]

    if not check_required_fields(question, required_fields):
        return False

    if not isinstance(question["question_id"], str) or not question["question_id"].strip():
        return False

    if not isinstance(question["content"], str) or not question["content"].strip():
        return False

    if not isinstance(question["difficulty"], (int, float)):
        return False

    if not isinstance(question["grade_level"], (int, str)):
        return False

    if check_duplicate(
        DB_PATH, "questions", "question_id", question["question_id"]
    ):
        return False

    return True


def add_question(DB_PATH, question: dict) -> bool:
    """Thêm câu hỏi vào bảng questions."""

    if not validate_question(DB_PATH, question):
        return False

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO questions (
                    question_id,
                    question_type,
                    difficulty,
                    content,
                    grade_level,
                    status,
                    rubric,
                    step_difficulties
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                question["question_id"],
                question["question_type"],
                question["difficulty"],
                question["content"],
                question["grade_level"],
                question["status"],
                question["rubric"],
                question["step_difficulties"]
            ))

        return True

    except sqlite3.Error as e:
        raise RuntimeError(f"Cannot add question: {e}")


# =========================
# ANSWERS
# =========================

def validate_answer(DB_PATH, answer: dict) -> bool:
    """
    Kiểm tra:
    - Đủ trường bắt buộc.
    - question_id tồn tại.
    - answer_id chưa tồn tại.
    """

    required_fields = [
        "answer_id",
        "question_id",
        "correct_answer",
        "explanation"
    ]

    if not check_required_fields(answer, required_fields):
        return False

    if not isinstance(answer["answer_id"], str) or not answer["answer_id"].strip():
        return False

    if check_duplicate(
        DB_PATH, "answers", "answer_id", answer["answer_id"]
    ):
        return False

    # Kiểm tra question_id có tồn tại không
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 1 FROM questions
                WHERE question_id = ?
                LIMIT 1
            """, (answer["question_id"],))

            if cursor.fetchone() is None:
                return False

    except sqlite3.Error as e:
        raise RuntimeError(f"Database error: {e}")

    return True


def add_answer(DB_PATH, answer: dict) -> bool:
    """Thêm đáp án vào bảng answers."""

    if not validate_answer(DB_PATH, answer):
        return False

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO answers (
                    answer_id,
                    question_id,
                    correct_answer,
                    explanation
                )
                VALUES (?, ?, ?, ?)
            """, (
                answer["answer_id"],
                answer["question_id"],
                answer["correct_answer"],
                answer["explanation"]
            ))

        return True

    except sqlite3.Error as e:
        raise RuntimeError(f"Cannot add answer: {e}")


# =========================
# QUESTION TEMPLATES
# =========================

def validate_template(DB_PATH, template: dict) -> bool:
    """
    Kiểm tra:
    - Đủ trường bắt buộc.
    - Các trường dữ liệu có kiểu hợp lệ.
    - template_id chưa tồn tại.
    """

    required_fields = [
        "template_id",
        "template_content",
        "parameter_rule",
        "answer_rule",
        "difficulty",
        "rubric",
        "step_difficulties"
    ]

    if not check_required_fields(template, required_fields):
        return False

    if not isinstance(template["template_id"], str) or not template["template_id"].strip():
        return False

    if not isinstance(template["template_content"], str):
        return False

    if not isinstance(template["difficulty"], (int, float)):
        return False

    if not isinstance(template["rubric"], list):
        return False

    if not isinstance(template["step_difficulties"], list):
        return False

    if not isinstance(template["parameter_rule"], (dict, list)):
        return False

    if not isinstance(template["answer_rule"], (dict, list)):
        return False

    if check_duplicate(
        DB_PATH, "question_templates", "template_id",
        template["template_id"]
    ):
        return False

    return True


def add_template(DB_PATH, template: dict) -> bool:
    """Thêm template vào bảng question_templates."""

    if not validate_template(DB_PATH, template):
        return False

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO question_templates (
                    template_id,
                    template_content,
                    parameter_rule,
                    answer_rule,
                    difficulty,
                    rubric,
                    step_difficulties
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                template["template_id"],
                template["template_content"],
                serialize_json(template["parameter_rule"]),
                serialize_json(template["answer_rule"]),
                template["difficulty"],
                serialize_json(template["rubric"]),
                serialize_json(template["step_difficulties"])
            ))

        return True

    except sqlite3.Error as e:
        raise RuntimeError(f"Cannot add template: {e}")


#Hàm trả về tập tất cả question
def get_all_questions(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    # Lấy dữ liệu từ bảng Questions
    cursor.execute("""
        SELECT *
        FROM questions
    """)

    rows = cursor.fetchall()
    # Chuyển mỗi dòng SQL thành Dictionary
    questions = [dict(row) for row in rows]
    for item in questions:
        item["rubric"] = json.loads(item["rubric"])

    for question in questions:
        cursor.execute("""
            SELECT part_id, label, content
            FROM question_parts
            WHERE question_id = ?
        """, (question["question_id"],))

        parts = cursor.fetchall()
        question["part"] = [dict(row) for row in parts]

        cursor.execute("""
            SELECT skill_id
            FROM question_skills
            WHERE question_id = ?
        """, (question["question_id"],))
        question_skills = cursor.fetchall()

        question["skills"] = [row["skill_id"] for row in question_skills]

        cursor.execute("""
            SELECT skill_id
            FROM QuestionMainSkill
            WHERE question_id = ?
        """, (question["question_id"],))
        main_skill = cursor.fetchall()
        question["main_skill"] =  [row["skill_id"] for row in main_skill][0]

    conn.close()
    return questions

#Hàm trả về 1 question
def get_question(DB_PATH, question_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # Lấy thông tin question
        row = conn.execute("""
            SELECT *
            FROM questions
            WHERE question_id = ?
        """, (question_id,)).fetchone()

        if not row:
            return None

        question = dict(row)
        question["rubric"] = json.loads(question["rubric"])

        # Lấy danh sách question parts
        parts = conn.execute("""
            SELECT part_id, label, content
            FROM question_parts
            WHERE question_id = ?
        """, (question_id,)).fetchall()

        question["part"] = [dict(row) for row in parts]

        # Lấy danh sách skills
        question_skills = conn.execute("""
            SELECT skill_id
            FROM question_skills
            WHERE question_id = ?
        """, (question_id,)).fetchall()

        question["skills"] = [
            row["skill_id"] for row in question_skills
        ]

        # Lấy main skill
        main_skill = conn.execute("""
            SELECT skill_id
            FROM QuestionMainSkill
            WHERE question_id = ?
        """, (question_id,)).fetchall()

        question["main_skill"] = (
            main_skill[0]["skill_id"] if main_skill else None
        )

        return question
    
def get_all_answers(DB_PATH):
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

def get_answer(DB_PATH, answer_id):
    """Lấy đáp án đúng"""
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

def get_all_terminology(DB_PATH):
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

def get_terminology(DB_PATH, term):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT * FROM terminology WHERE term = ?",
            (term,)
        ).fetchone()

        return dict(row) if row else None

def get_all_skills(DB_PATH):
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

def get_skill(DB_PATH, skill_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT * FROM skills WHERE skill_id = ?",
            (skill_id,)
        ).fetchone()

        return dict(row) if row else None


def get_all_question_templates(DB_PATH):
    """
    """

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
        for template in templates:
            cursor.execute("""
            SELECT skill_id FROM question_template_skills WHERE template_id = ?
        """, (template["template_id"],))
            template_id = cursor.fetchall()

            template["skills"] = [dict(row) for row in template_id]

            template["rubric"] = parse_json(template["rubric"])
            template["parameter_rules"] = parse_json(template["parameter_rules"])

        return templates

    except sqlite3.Error as e:
        print(f"Lỗi khi đọc question_templates: {e}")
        return []

    finally:
        if conn is not None:
            conn.close()

def get_question_template_by_id(DB_PATH, template_id) -> dict | None:
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

        template = dict(row)
        template["rubric"] = parse_json(template["rubric"])
        template["parameter_rules"] = parse_json(template["parameter_rules"])

        return template

    except sqlite3.Error as e:
        print(f"Lỗi khi đọc question_templates: {e}")
        return None

    finally:
        if conn is not None:
            conn.close()
