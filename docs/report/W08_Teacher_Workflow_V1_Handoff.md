# W08 — Bàn giao luồng giáo viên V1

Ngày bàn giao: 21/11/2026. Phạm vi được chốt: **sinh → duyệt → chấm → lưu và mở lại kết quả**.
V1 là bản bàn giao đầu tiên của luồng UI giáo viên đầy đủ trong phạm vi này.
Integration: `W08-2026-11-21-teacher-workflow-v2`; engine kế thừa:
`R2026-11-17-scoped-skill-guidance-v11`. Hai mã này không phải phiên bản model.

## Chức năng đã nối

| Bước | Hành vi V1 |
|---|---|
| Hồ sơ và cấu hình | UI mới đọc hồ sơ mẫu M3, hiển thị kế hoạch và phân phối câu hỏi. |
| Sinh và xem đề | Sinh đề, xem câu hỏi/đáp án/lời giải, thay câu template, mở lại đề. |
| Duyệt | Giáo viên kiểm tra reference, mô tả rubric và kỹ năng từng tiêu chí; backend lưu cùng revision đã duyệt. |
| Nhập bài | Chuyển từ đề sang trang chấm với đúng học sinh/revision; nhập văn bản từng câu hoặc nhập JSON hàng loạt. |
| Chấm | Tạo job bất đồng bộ, theo dõi từng câu, hiển thị verdict và nhận xét, tải JSON kết quả. |
| Lưu và xem lại | SQLite giữ revision, bài nộp, context và kết quả; có lịch sử và mở lại sau restart. |

API kiểm tra trạng thái duyệt, revision, học sinh và tập ID câu. Retry cùng
`idempotency_key` và nội dung trả job đã lưu; đổi nội dung nhưng giữ key trả 409.
Một revision đã duyệt vẫn dùng được khi đề có bản nháp mới. Khi thay câu, context
chấm của câu đó bị xóa và đề phải được duyệt lại trước khi dùng revision mới.

## Những ghi chú quan trọng

1. **Qwen 4B là cấu hình cho cả hai tác vụ.** Đặt riêng `QWEN_MODEL` và
   `GRADING_MODEL` thành `qwen3:4b-q4_K_M`; kiểm tra đúng tag bằng `ollama list`.
   Ollama phải chạy. Ứng dụng không tự tải model, không tự load `.env`.
   `--fake` chỉ thay bộ sinh đề; bài làm không rỗng vẫn cần model thật để chấm.
2. **Thông luồng và chất lượng model cần được nghiệm thu riêng.** Kiểm thử V1
   dùng transport Qwen giả lập; chưa chạy inference Qwen 4B thật trong lần bàn giao
   này vì kết nối Ollama bị từ chối. Bộ 30 đề ngày 14/11 dùng Qwen 1.7B; không dùng
   kết quả đó để kết luận chất lượng 4B. Cần chạy và chấm đánh giá lại với đúng tag.
3. **Rubric chấm bài cần giáo viên xác nhận trước khi duyệt.** Gợi ý từ lời giải
   chưa phải barem được chứng nhận. Không tự chuyển rubric chất lượng đề W06 hay
   `criteria/sub_score` thành rubric chấm. Context lưu mô tả và kỹ năng theo tiêu chí.
   Snapshot cũ thiếu context hợp lệ phải tạo bản nháp mới rồi duyệt lại.
4. **Engine có giới hạn biểu thức số học.** Adapter chỉ chuẩn hóa định dạng xác
   định như `53 cách chọn` hoặc đẳng thức đã kiểm chứng; văn xuôi tùy ý cần giáo
   viên nhập reference biểu thức phù hợp. Đáp án nguồn được giữ nguyên.
5. **Kết quả hiện tại là verdict, chưa phải điểm số.** Mỗi câu có `CORRECT`,
   `INCORRECT` hoặc `UNCERTAIN`. `COMPLETED` nghĩa đã xử lý và lưu đủ câu, có thể
   còn `UNCERTAIN`. Lỗi AI/provider không tự trở thành lỗi hoặc điểm 0 của học sinh.
6. **PCM/EAP để giai đoạn sau theo phạm vi đã chốt.** Chưa tính điểm tổng/điểm
   từng tiêu chí, `observed_level`, mastery hay cập nhật hồ sơ. Chưa có sửa kết quả
   AI, chốt toàn bài theo nghiệp vụ hoặc giao đề cho giao diện học sinh.
7. **Đây là ứng dụng giáo viên chạy local.** Token được giữ trong bộ nhớ trình
   duyệt; tải lại trang cần kết nối lại. Runtime mặc định là `data/runtime/exams.db`
   và kho grading theo cấu hình; không ghi hai database mẫu. Chạy một process API
   cho kho grading; job bị dừng giữa chừng thành `INTERRUPTED`, chưa tự resume.

## Bằng chứng kiểm chứng

- Toàn repo: **879 test đạt, 14 subtest đạt**, một cảnh báo deprecation Starlette
  hiện có. Lệnh: `.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest_tmp_mira/teacher_workflow_final --tb=short`.
- Chrome headless chạy UI thật: chọn hồ sơ → cấu hình → sinh đề → thay câu →
  duyệt rubric → nhập bài → chấm → restart backend → xem lịch sử/kết quả → quay
  lại đề. Không ghi nhận JavaScript exception.
- Lượt browser dùng bộ sinh fake, SQL readers thật, transport Qwen giả lập;
  engine/API/SQLite thật. Kiểm thử tích hợp xác nhận revision, retry, xung đột key,
  dữ liệu review sai và đọc lại sau restart.
- Hai database mẫu và engine/transport Qwen v11 giữ nguyên. Không dùng số test
  hoặc lượt browser này làm số đo độ chính xác của model.

## Chạy thử và nghiệm thu tiếp theo

```powershell
ollama list
# Chỉ cần tải nếu chưa có đúng model:
# ollama pull qwen3:4b-q4_K_M
# Nếu Ollama chưa chạy: mở terminal riêng và chạy ollama serve.
$env:QWEN_MODEL = 'qwen3:4b-q4_K_M'
$env:GRADING_MODEL = 'qwen3:4b-q4_K_M'
.\.venv\Scripts\python.exe -m src.ui
```

Chạy một đề nhỏ qua UI, duyệt rubric, nhập bài đúng/sai/để trống và mở lại kết quả
sau restart. Tiếp đó lập bộ bài làm có nhãn chuẩn độc lập để đo chất lượng chấm
và đánh giá chất lượng đề trên đúng Qwen 4B. Đây là công việc nghiệm thu model
còn lại; V1 hiện chưa có số liệu độ chính xác mới.

API, payload, trạng thái và lỗi: [W08 Exam and Grading Contract](../api/W08_Exam_and_Grading_Contract.md).
