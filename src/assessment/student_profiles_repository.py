import sqlite3
from pathlib import Path
from helper_functions import check_required_fields, check_duplicate
from grading_repository import get_test, update_status
from question_repository import get_question, get_answer
import json
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR/"data"/"sample"/"memory"/"student_profiles_sample.db"


def validate_student(DB_PATH, student: dict) -> bool:
    """
    Kiểm tra:
    - Đủ trường bắt buộc: student_id, grade_level, name, birthday.
    - Kiểu dữ liệu hợp lệ.
    - student_id chưa tồn tại trong database.
    """

    required_fields = [
        "student_id",
        "grade_level",
        "name",
        "birthday"
    ]

    if not check_required_fields(student, required_fields):
        return False

    if not isinstance(student["student_id"], str) or not student["student_id"].strip():
        return False

    if not isinstance(student["name"], str) or not student["name"].strip():
        return False

    if not isinstance(student["grade_level"], int):
        return False

    if not isinstance(student["birthday"], str) or not student["birthday"].strip():
        return False

    # Kiểm tra định dạng birthday: YYYY-MM-DD
    from datetime import datetime

    try:
        datetime.strptime(student["birthday"], "%Y-%m-%d")
    except ValueError:
        return False

    # Kiểm tra student_id trùng
    if check_duplicate(
        DB_PATH,
        "students",
        "student_id",
        student["student_id"]
    ):
        return False

    return True


def add_student(DB_PATH, student: dict) -> bool:
    """Thêm sinh viên vào bảng students."""

    if not validate_student(DB_PATH, student):
        return False

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO students (
                    student_id,
                    grade_level,
                    name,
                    birthday
                )
                VALUES (?, ?, ?, ?)
            """, (
                student["student_id"],
                student["grade_level"],
                student["name"],
                student["birthday"]
            ))

        return True

    except sqlite3.Error as e:
        raise RuntimeError(f"Cannot add student: {e}")


def get_all_student(DB_PATH) -> list[dict[str, object]] | None:

    """
    
{
    'student_id': 'ST001', 
    'grade_level': 10, 
    'name': 'Nguyen Ngoc Gia Han', 
    'birthday': '2010-08-11', 
    'learning_history': [
        {
            'test_id': 'TA0001', 
            'wrongs': ['QA0064'], 
            'question_mastery_score': [
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
        }, 
            {
            'test_id': 'TA0002',
            'wrongs': ['QA0049'], 
            'question_mastery_score': [
                {
                    'question_id': 'QA0015', 
                    'question_mastery_score': None
                }, 
                
                {
                    'question_id': 'QA0049', 
                    'question_mastery_score': None
                }, 
                
                {
                    'question_id': 'QA0083', 
                    'question_mastery_score': None
                }, 
                
                {
                    'question_id': 'QA0108', 
                    'question_mastery_score': None
                }
            ]
        }
    ], 
    'skill_mastery': [
        {
            'skill_id': 'A001', 
            'mastery_score': 2.3, 
            'evidence_count': 1
        }, 
        
        {
            'skill_id': 'A002', 
            'mastery_score': 2.0, 
            'evidence_count': 1
        }, 
        ...   
    ]
}
    """

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

            student["learning_history"] = get_test(DB_PATH, student["student_id"])
            
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

def get_student_by_id(DB_PATH, student_id: str) -> dict | None:
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

        student["learning_history"] = get_test(DB_PATH, student["student_id"])
        

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

        
DB_PATH1 = BASE_DIR / "data"/"sample"/"dataset"/ "question_bank.db"

def test(student_id: str):
    conn = sqlite3.connect(DB_PATH1)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        student = get_student_by_id(DB_PATH , student_id)
        question = []
        answer = []
        for order in range(0, 4):
            q = get_question(DB_PATH1 , student["learning_history"][0]["question_mastery_score"][order]["question_id"])
            question.append(q)
            answer.append(q["rubric"])
        learning_history = student["learning_history"][0]
        print(json.dumps(learning_history, indent=4, ensure_ascii=False))
        
        for q in question:
            print("question_id: ", q["question_id"])
            print("content: ", q["content"])
            print("correct_answer: ")
            i = 0
            print(json.dumps(answer[i], indent=4, ensure_ascii=False))
            print()

            i = i+1
    finally:
        conn.close()

#test("ST001")