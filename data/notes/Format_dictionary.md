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
    "skills": [A001]
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
## MVP 1

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

# 6. question_template:
{
    'template_id': 'EA0001', 
    'template_content': 'Có các nhóm phân biệt, không giao nhau, với số lượng đối tượng lần lượt là {counts}. Chọn đúng một đối tượng từ một trong các nhóm. Hỏi có bao nhiêu cách chọn?', 
    'parameter_rules': '{
        "counts": {
            "type": "array", 
            "items": {"type": "integer", "min": 0}, 
            "min_length": 2
            }, 
        "groups": {
            "type": "disjoint_groups", 
            "description": "Các nhóm phân biệt và không giao nhau"
            }
        }', 
    'answer_rule': 'N = sum(counts)', 
    'solution_rule': 'Vì chỉ chọn một đối tượng từ đúng một trong các nhóm phân biệt, áp dụng quy tắc cộng: cộng số đối tượng của tất cả các nhóm.', 
    'difficulty': 1, 
    'skills': ['A001']
}

**Kiểu trả về của AI sau khi sinh đề**
- `test` (`dict`): thông tin bài kiểm tra cần thêm.
    test = {
        "test_id": "T001",
        "test_name": "Kiểm tra Đại số tổ hợp",
        "date": "2026-10-21",
        "score": 8.5
    }
- `test_question`: các câu hỏi trong test đó
    test_questions = [
        {
            "question_id": "QA0001",
            "question_order": 1,
            "is_correct": 1
        },
        {
            "question_id": "QA0002",
            "question_order": 2,
            "is_correct": 0
        },
        {
            "question_id": "QA0003",
            "question_order": 3,
            "is_correct": 1
        }
    ]
Nếu là AI tự sinh câu hỏi mới thì phải add question đó vào question_bank.