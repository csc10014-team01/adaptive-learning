import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "student_profiles_sample.db"


def update_status(student: dict) -> None:
    test_num = len(student["learning_history"])
    if test_num >= 2:
        student["status"] = "sufficent"
    elif test_num >= 1:
        student["status"] = "partial"
    else:
        student["status"] = "no_data"


def add_test(test: dict, student: dict, test_questions) -> None:
    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO Tests (test_id, student_id, test_name, date, score)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                test["test_id"],
                student["student_id"],
                test["test_name"],
                test["date"],
                test["score"],
            ),
        )

        cursor.execute(
            """
            INSERT OR IGNORE INTO test_question (test_id, question_id, question_order, is_correct)
            VALUES (?, ?, ?, ?)
        """,
            (
                test["test_id"],
                test_questions["question_id"],
                test_questions["question_order"],
                test_questions["is_correct"],
            ),
        )

        conn.commit()

        student["learning_history"].append(test)
        update_status(student)

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Cannot add test: {e}")

    finally:
        conn.close()


def get_test(student: dict) -> list[dict[str, str | list[str]]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        # Lấy lịch sử các bài kiểm tra của học sinh
        test_rows = cursor.execute(
            """
            SELECT test_id
            FROM Tests
            WHERE student_id = ?
        """,
            (student["student_id"],),
        ).fetchall()

        learning_history = []

        for test in test_rows:
            test_id = test["test_id"]

            # Lấy các câu trả lời sai trong từng bài kiểm tra
            wrong_rows = cursor.execute(
                """
                SELECT question_id
                FROM test_questions
                WHERE test_id = ?
                  AND is_correct = 0
                ORDER BY question_order
            """,
                (test_id,),
            ).fetchall()

            learning_history.append(
                {
                    "test_id": test_id,
                    "wrongs": [item["question_id"] for item in wrong_rows],
                }
            )

        return learning_history

    except sqlite3.Error as e:
        print(f"Cannot get test history: {e}")
        return []

    finally:
        conn.close()


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
            mastery_rows = cursor.execute(
                """
                SELECT skill_id, mastery_score, evidence_count
                FROM student_skill_mastery
                WHERE student_id = ?
            """,
                (student_id,),
            ).fetchall()

            student["skill_mastery"] = [dict(item) for item in mastery_rows]

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
        cursor.execute(
            """
            SELECT student_id, grade_level, name, birthday
            FROM Students
            WHERE student_id = ?
        """,
            (student_id,),
        )

        row = cursor.fetchone()

        # Không tìm thấy học sinh
        if row is None:
            return None

        student = dict(row)

        # Lấy lịch sử các bài kiểm tra của học sinh

        student["learning_history"] = get_test(student)

        # Lấy mức độ thành thạo kỹ năng
        mastery_rows = cursor.execute(
            """
            SELECT skill_id, mastery_score, evidence_count
            FROM student_skill_mastery
            WHERE student_id = ?
        """,
            (student_id,),
        ).fetchall()

        student["skill_mastery"] = [dict(item) for item in mastery_rows]
        update_status(student)

        return student

    finally:
        conn.close()
