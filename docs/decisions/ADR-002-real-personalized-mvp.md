# ADR-002: Cá nhân hóa ngay trong MVP bằng dữ liệu M3 và Qwen

- Ngày: 23/10/2026.
- Trạng thái: triển khai theo yêu cầu người dùng trong phiên làm việc; người dùng
  đã chọn cá nhân hóa ngay từ 1 evidence theo skill. Không suy diễn đây là phê
  duyệt của toàn nhóm cho các tham số còn lại.
- Thay thế phần ngưỡng/fallback cũ của ADR-001 và mã giả N03 §4 đối với backend thật.
  Fake vẫn giữ hành vi fixture phục vụ kiểm thử contract.

## Quy tắc MVP v1

1. `generation_mode=default_blueprint`: chọn cân bằng kỹ năng, không dùng mastery
   để ưu tiên. `adaptive`: đọc mastery, evidence từng skill và lịch sử sai.
2. Chỉ xét skill có `evidence_count >= 1`. Không cộng count giữa các skill, không
   tính lại mastery, không suy count từ lịch sử. Không evidence: dùng phân bổ cân
   bằng và giải thích trong plan; không tuyên bố đã cá nhân hóa.
3. Skill ưu tiên khi `mastery_score < 2.5` trên thang 0–4, hoặc có câu sai đã tra
   được liên kết skill từ ngân hàng. Điểm 2.5 là tham số chính sách MVP mới, không
   phải thuộc tính sẵn có của M3. Câu sai không xác định được ID: cảnh báo, không
   tự đoán skill. Không có evidence cho skill thì history cũng không kích hoạt nó.
4. Trọng số skill: `(4 - mastery) * confidence + wrong_bonus`, với confidence=1
   khi có 1 evidence, =2 khi có >=2 evidence; wrong_bonus=1 nếu từng sai cùng skill.
5. Mục tiêu `ceil(0.6 * total_questions)` câu thuộc skill ưu tiên. Giữ exact counts
   theo phân bổ nhận thức request; làm tròn largest remainder như API trước đây.
   Chọn quota ưu tiên trên toàn bộ mức trước khi lấp các slot còn lại để tránh
   thứ tự duyệt mức làm hụt quota khả thi.
6. Trong nhóm ứng viên ưu tiên, sắp theo: tránh ID từng sai, giảm lặp kỹ năng đã
   chọn, trọng số ưu tiên cao hơn, cuối cùng ID tăng dần để tái lập. Các slot còn
   lại ưu tiên skill ngoài nhóm ưu tiên trước. History chỉ chứa câu sai nên không
   thể bảo đảm câu được chọn chưa từng xuất hiện trong bất kỳ bài nào.
7. Thiếu quota ưu tiên: lấp bằng câu khác đúng mức và cảnh báo target/achieved.
   Thiếu tổng số câu ở một mức: 409; không lặp source, không trả đề thiếu câu.
   Profile/request sai: từ chối; không che lỗi bằng fake/default.

## Nguồn dữ liệu và annotations

- `M3DataAdapter`: read-only SQLite, normalize `answers.explaination` và lấy history
  từ `Tests/test_questions` sang `wrong_questions`; không gọi legacy writers/status.
  Hồ sơ SQL đọc mới mỗi request để nhận cập nhật M3; bank/catalogue cache theo process.
- `PROFILE_SOURCE=json`: cùng schema hồ sơ đã chốt, câu vẫn đọc từ M3 SQLite.
- Bỏ câu thiếu skill link, nhiều/thiếu đáp án chính, thiếu đáp án ý nhỏ hoặc có
  difficulty không hỗ trợ. Giữ đủ nội dung và đáp án từng ý của câu nhiều phần.
- M3 hiện chỉ có numeric difficulty. **Mapping do ứng dụng quy định v1**, không
  giả nhận đã có cognitive annotations được Data duyệt:
  1→recognition; 2→understanding; 3→application; 4/5→advanced_application.
- Chỉ xét essay lớp 10, status draft/active, skill thuộc chủ đề canonical. Toàn bộ
  nguồn sample hiện là draft; cho phép soạn đề chờ review, không dùng làm đề đã duyệt.
- Đáp án và giải thích nguồn được giữ nguyên; một bước giải tổng hợp và một rubric
  tổng quát nhận toàn bộ điểm câu, không tuyên bố là barem chi tiết đã duyệt.

## Vai trò Qwen và kiểm định

`QwenExamGenerator` dùng `RuleBasedPlanner` trước; `QwenClient` gọi Ollama
`/api/generate` thật với model cấu hình (`qwen3:1.7b` mặc định). Qwen chỉ viết lại
câu chữ theo `direct`, không đổi bài toán hay tự chọn skill/đáp án/điểm.
Prompt chỉ có nội dung câu nguồn, không chứa student ID/name/mastery/history.

Kiểm tra envelope model/done, JSON một khóa `question`, kích thước/độ dài và tập
số liệu (kể cả số lần xuất hiện). Retry tối đa 2 lần mặc định khi output sai;
timeout mỗi lượt 45s, ngân sách đề 180s; 1 request Qwen/process, bận trả 503.
Provider lỗi trả 502/503/504, không fallback âm thầm sang fake. API xác minh schema,
source-skill links, exact count/distribution và tổng điểm 10 theo bước 0.25.

**Chưa có bộ chứng minh tương đương ngữ nghĩa**: Qwen vẫn có thể đổi điều kiện
không chứa số; đáp án M3 draft cũng có thể sai. Luôn `auto_status=needs_review`,
`teacher_approved=false`, `pending_teacher_review`; giáo viên cần đối chiếu nguồn
qua source_ref trước khi sử dụng. Không coi việc Qwen giải lại là bằng chứng đúng.

## API và lưu trữ

- Mặc định `src.api.main:app` chạy qwen/m3. Fake chọn rõ `EXAM_BACKEND=fake`.
- `POST /api/v1/exams/plan`: cùng request generate, trả plan version, ưu tiên,
  target/achieved, nguồn, lý do và cảnh báo; không gọi model/không lưu.
- `POST /api/v1/exams/generate`: generate đồng bộ, chỉ lưu đề hoàn chỉnh hợp lệ.
- `SQLiteExamStore` lưu đề riêng trong `data/runtime/exams.db`; đọc lại sau restart.
  Không thay đổi hoặc tự insert vào canonical M3 bank; chưa có workflow duyệt/ghi
  ngược câu sinh mới vào M3. MVP chỉ viết lại nguồn, không tạo source template mới.
- Giữ teacher bearer access; chưa mở student endpoint, login/roles/ownership,
  chấm bài hay cập nhật mastery. Không tuyên bố là backend production hoàn chỉnh.

Kiểm thử `tests/integration/test_real_api.py`: M3 read-only, cá nhân hóa thực sự
thay đổi nguồn chọn, evidence/history, quota/distribution, HTTP Ollama giả lập,
provider failures, no-partial-save, SQLite restart và không đưa PII vào prompt.
Chưa xác nhận suy luận model thật trên máy nếu Ollama không chạy.
