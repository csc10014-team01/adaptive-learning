import sqlite3
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data"/"sample"/"memory"/ "student_profiles_sample.db"


def update_status(student: dict) -> None:
    test_num = len(student["learning_history"])
    if test_num >= 2:
        student["status"] = "sufficent"
    elif test_num >= 1:
        student["status"] = "partial"
    else:
        student["status"] = "no_data"
 
   
def add_test(DB_PATH, test: dict, student: dict, test_questions) -> None:
    """ Chỉ thêm test vào sql, chưa cập nhật mastery_score """
    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO Tests (test_id, student_id, test_name, date, score)
            VALUES (?, ?, ?, ?, ?)
        """, (
            test["test_id"],
            student["student_id"],
            test["test_name"],
            test["date"],
            test["score"]
        ))

        cursor.execute("""
        INSERT OR IGNORE INTO test_question (
            test_id,
            question_id,
            question_order,
            is_correct,
            observed_level,
            theta_eap,
            question_mastery_score,
            pcm_parameter_version,
            reference_parameter_version,
            prior_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        test["test_id"],
        test_questions["question_id"],
        test_questions["question_order"],
        test_questions["is_correct"],
        test_questions.get("observed_level"),
        test_questions.get("theta_eap"),
        test_questions.get("question_mastery_score"),
        test_questions.get("pcm_parameter_version"),
        test_questions.get("reference_parameter_version"),
        test_questions.get("prior_version")
    ))

        conn.commit()

        student["learning_history"].append(test)
        update_status(student)
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Cannot add test: {e}")

    finally:
        conn.close()

def get_test(DB_PATH, student_id: str) -> list[dict]:
    """
    {
    'test_id': 'TA0001', 
    'wrongs': ['QA0064'], 
    'question_mastery': 
        [
            {
                'question_id': 'QA0007', 
                'question_mastery_score': None
            }, 

            {
                'question_id': 'QA0038', 
                'question_mastery_score': None
            }, 

            {
                'question_id': 'QA0064',
                'question_mastery_score': None
            }, 
            
            {
                'question_id': 'QA0102', 
                'question_mastery_score': None
            }
        ]
    } 
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        # Lấy lịch sử các bài kiểm tra của học sinh
        test_rows = cursor.execute("""
            SELECT test_id
            FROM Tests
            WHERE student_id = ?
        """, (student_id,)).fetchall()

        learning_history = []
        i = 0
        for test in test_rows:
           
            test_id = test["test_id"]

            # Lấy các câu trả lời sai trong từng bài kiểm tra
            wrong_rows = cursor.execute("""
                SELECT question_id
                FROM test_questions
                WHERE test_id = ?
                  AND is_correct = 0
                ORDER BY question_order
            """, (test_id,)).fetchall()

            # Lấy mastery score của từng câu hỏi trong bài kiểm tra
            mastery_score = cursor.execute("""
                SELECT question_id, question_mastery_score
                FROM test_questions
                WHERE test_id = ?
                ORDER BY question_order
            """, (test_id,)).fetchall()

            learning_history.append({
                "test_id": test_id,
                "wrongs": [
                    item["question_id"]
                    for item in wrong_rows
                ],
                "question_mastery": [
                    dict(row) for row in mastery_score
                ]
            })
            s = cursor.execute("""
                SELECT question_id
                FROM test_questions
                WHERE test_id = ?
                ORDER BY question_order
            """, (test_id,)).fetchall()

            questions =[row["question_id"] for row in s]
            j = 0
            for q in questions:
               
                learning_history[i]["question_mastery"][j]["answer"] = get_student_answer_attempt(DB_PATH, q)
                j += 1

            i += 1

        return learning_history

    except sqlite3.Error as e:
        print(f"Cannot get test history: {e}")
        return []

    finally:
        conn.close()

def get_student_answer_attempt(DB_PATH, question_id: str)-> dict | None:
    """ Lấy câu trả lời của học sinh """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        
        # Lấy lịch sử các bài kiểm tra của học sinh
        answer = None
        answer = cursor.execute("""
            SELECT answer
            FROM student_answer_attempt
            WHERE question_id = ?
        """, (question_id,)).fetchall()

        if answer:
            answer = dict(json.loads(answer))

        return answer

    finally:
        conn.close()
