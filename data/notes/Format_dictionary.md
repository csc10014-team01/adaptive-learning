**Định dạng**

# 1. Question
question = {
    "question_id": "QA0001",
    "question_type": "essay",
    "difficulty": 1,
    "content": "Một công việc có thể được hoàn thành bằng một trong hai hành động...",
    "grade_level": 10,
    "status": "active",
    "part": [
        {
            "part_id": "QPA0001",
            "label": "a",
            "content": "Tính số cách thực hiện hành động thứ nhất."
        }
    ]
}
get_all_questions() trả về list các question
# 2. Answer
answer = {
    "answer_id": "AA0001",
    "question_id": "QA0001",
    "correct_answer": "15",
    "explanation": "Áp dụng quy tắc cộng...",
    "solution_method": "Cộng số cách của hai hành động.",
    "part": [
        {
            "part_id": "QPA0001",
            "correct_answer": "7",
            "explanation": "Có 7 cách thực hiện hành động thứ nhất."
        }
    ]
}
get_all_answers() trả về list các answer

# 3. Terminology
terminology = {
    "term": "Quy tắc cộng",
    "text": "Nếu một công việc có thể hoàn thành bằng một trong hai hành động riêng biệt..."
}
get_all_terminology() trả về list các term
# 4. Skill
skill = {
    "skill_id": "A001",
    "topic": "Đại số tổ hợp",
    "name": "Quy tắc cộng",
    "grade_level": 10,
    "description": "Vận dụng quy tắc cộng để tính số cách thực hiện một công việc."
}
get_all_skills() trả về list các skill
# 5. Student
# MVP 1

student = {
"student_id": "HS001",
“name”: “Nguyễn Văn A”
    "grade_level": 11,
    "skill_mastery":[
        "skill_id": "A001",
        "mastery_score": 3.4,
        "evidence_count": 4
    ]
    "learning_history": [
        {
            "test_id": "T001",
            "wrong_questions": ["A002", "A003"]
        },
        {
            "test_id": "T002",
            "wrong_questions": ["A003", "A004"]
        }
    ]
}