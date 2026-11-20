# W07 — bộ ánh xạ sau khi AI tách bước (bản nội bộ 0.1)

File bàn giao chính: `src/ai/answer_grading.py`. Không cần FastAPI, Ollama hoặc pip để chạy bản này. Module chỉ xử lý **sau khi AI đã tách bài làm thành step/description**, không gọi Qwen, không sửa DB, không tính điểm câu/mastery.

## Chạy trong Git Bash

Giải nén, đứng tại thư mục có `run_demo.py`:

```bash
python -m unittest discover -s tests -v
python run_demo.py
```

Nếu dùng launcher Windows: thay `python` bằng `py -3`. Python 3.11+.

Demo xuất `demo_results.json`. Thời gian in ra là thời gian ánh xạ bằng code, không gồm thời gian Qwen tách bước, lấy dữ liệu, API hoặc giáo viên.

## Kết quả đã kiểm tra

14 unit tests đạt. Chạy demo trên 4 bài làm mẫu cho kết quả tổng thể:

| Câu | Kết quả tổng thể | Ghi chú |
|---|---|---|
| QA0007 | CORRECT | Các bước đã nằm trong bộ phát biểu tham chiếu của fixture |
| QA0038 | CORRECT | Có lời văn và nhiều phép toán trong một bước |
| QA0064 | INCORRECT | Lỗi điều kiện gốc; bước sau là lỗi kéo theo |
| QA0102 | UNCERTAIN / NEEDS_REVIEW | Đáp án DB 156 và lời giải không khớp đề; reference được đánh conflicting |

Chỉ đối chiếu nhãn tổng thể, không tuyên bố toàn bộ output khớp từng câu feedback của expected_result do nhóm gửi. Không có benchmark Qwen hoặc độ chính xác trên cách viết mới ở đây.

## Giao diện tạm

```python
from src.ai.answer_grading import grade_answer

result = grade_answer(
    student_steps=[{"step": 1, "description": "..."}],
    question_snapshot=snapshot,
    reference_answer=reference,
    rubric=rubric,
    skill_catalog=["A001", "A002", "A003", "A004", "A005", "A006", "A007", "A008", "A009"],
    expected_exam_version="APPROVED_V1",
)
```

Đầu vào của học sinh chính là mảng `answer` trong mẫu sau tách, truyền vào student_steps. Không truyền expected_result. Module không biết test_id/student_id vì ánh xạ một câu không cần chúng; API sẽ bọc các ID này bên ngoài.

Snapshot phải có question_id, exam_version, content, approved=true. Reference và rubric phải cùng question_id/exam_version. Reference chứa hash chính xác của nội dung câu (dùng hàm content_hash) để ngăn tái sử dụng reference khi nội dung đã đổi.

`observed_level` lấy từ rubric.levels_by_result do bên gọi cung cấp, không tự suy ra thang 0–4 hay điểm số. Fixture dùng mức chuỗi CORRECT/INCORRECT để thử luồng. Đây chưa phải thang rubric chính thức của nhóm.

Output có grading_status, requires_teacher, overall_result, final_answer_correct, observed_level, step_results, errors, missing_steps, mapping, reason_codes, review_reason, teacher_comment=null và thông tin phiên bản. AI_GRADED là tên trạng thái tương thích mẫu; trường grader chỉ rõ module thực hiện là post-extraction mapper, không ngụ ý lần chạy này có gọi model.

## Cách ánh xạ thực sự của bản đầu

Reference chứa nhiều method; mỗi method có checkpoints và variants. Mỗi variant là **toàn bộ phát biểu đã được tác giả xác nhận**, có kết quả đúng/sai/phụ thuộc, feedback và kỹ năng lỗi nếu có. So sánh chuẩn hóa Unicode, khoảng trắng, hoa/thường và ký hiệu nhân/trừ. Module không gắn cứng theo số thứ tự step của học sinh và không phân nhánh theo question_id.

Nội dung và phép toán của một phát biểu chỉ được chấp nhận khi khớp một variant đã xác nhận. Không suy ra toàn bộ lập luận đúng chỉ vì cùng đáp số. Variant sai ghi rõ nguyên nhân; dependent variant dẫn đến cause_steps và không tạo kỹ năng sai mới. Mapping thiếu, trùng hoặc mơ hồ đều chuyển giáo viên; vẫn giữ bằng chứng đã nhận diện.

**Giới hạn quan trọng:** chưa có ánh xạ ngữ nghĩa tổng quát hay nhiều-nhiều. Cách diễn đạt mới, gộp/tách khác checkpoint và cách giải khác không có variant sẽ chuyển GV. Bản đầu không tự sinh variants từ lời giải text trong DB. Không phải chỉ đưa JSON mẫu của học sinh vào là chấm được: còn cần bộ reference/rubric phù hợp.

Các variants trong fixture được soạn để kiểm tra chính 4 mẫu đã biết; đây là kiểm tra nhánh code trên dữ liệu đã hỗ trợ, không phải đánh giá khả năng hiểu bài mới. Việc dữ liệu này được gắn verified là xác nhận **giả lập**, chỉ dùng khi allow_demo=True. Core mặc định từ chối fixture demo. Trước khi triển khai thật cần người phụ trách xác nhận reference, kỹ năng và rubric; phía API chịu trách nhiệm cung cấp snapshot được duyệt hợp lệ.

## Dữ liệu mẫu

`fixtures/demo_inputs.json` có 4 payload với:
- Bài học sinh đã tách từ mẫu cung cấp.
- Nội dung đề/đáp án nguồn từ snapshot DB cũ.
- Phiên bản đề và rubric **giả lập** (DEMO_APPROVED_V1).
- Reference method/checkpoints/variants bổ sung để thử ánh xạ; chưa phải dữ liệu có sẵn trong DB nhóm.

QA0064 dùng A009 cho lỗi điều kiện như **đề xuất fixture**, chưa phải nhãn Data Lead chốt; DB cũ chỉ gắn A001/A002. Toàn bộ catalog 9 kỹ năng được truyền vào demo để thử lỗi này. Không âm thầm sửa liên kết DB thật.

`fixtures/gold.json` giữ nhãn kỳ vọng riêng; chỉ run_demo.py đọc sau khi chấm. Không nằm trong input của grade_answer.

## Nối contract sau

Adapter bên API thực hiện: lấy snapshot + đáp án/rubric đúng phiên bản, truyền bài làm đã tách vào grade_answer, rồi chuyển tên trường/trạng thái theo contract chính thức. Nếu contract định nghĩa mức khác, cập nhật quy tắc rubric và adapter; không tự dùng thiết kế PCM/profile cũ.

Các mã review chính: UNAPPROVED_SNAPSHOT, VERSION_MISMATCH, REFERENCE_CONTENT_MISMATCH, REFERENCE_UNVERIFIED, MISSING_RUBRIC, INVALID_STUDENT_STEP, DUPLICATE_STEP_ID, UNMAPPED_STUDENT_STEP, INCOMPLETE_MAPPING, AMBIGUOUS_MAPPING, FINAL_ANSWER_UNVERIFIED, INVALID_REFERENCE_SPEC.

Đây là phần đầu của deliverable answer_grading.py. Chưa nối API #58, chưa có rubric chính thức, chưa mở rộng ánh xạ ngữ nghĩa, và chưa làm báo cáo Indirect EA0004 trong gói này. Không xem module này là hoàn thành toàn bộ issue W07.
