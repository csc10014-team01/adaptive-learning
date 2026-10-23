# Static JSON cho Fake API MVP1

Các file trong thư mục này là **synthetic API demo fixtures**, không phải Profile JSON
đã được M3 bàn giao, không phải bản sao của các student records `ST*`, và không phải
question bank đã được teacher review. Chúng được thêm vì repository hiện chỉ có
SQLite sample + readers, chưa có canonical static Profile JSON với root evidence.

Không sửa hoặc tự export/aggregate các SQLite records để lấp field còn thiếu.
Canonical M3/AI source code và hai database hiện có được giữ nguyên.

## Files và mapping

- `student_profiles.json`: raw field `name` map sang public `student_name`;
  `grade_level` giữ nguyên; root `evidence_count` là synthetic input được khai báo
  sẵn, thuộc student/topic `combinatorics`, không tính từ history hoặc nested counts.
  `data_status` và recommended mode derive từ root count 0 / 1–2 / >=3.
- `skill_mastery[].mastery_score`: giữ scale 0–4 theo CHECK của
  `data/sample/memory/student_profiles_sample.db::student_skill_mastery`.
  Nested evidence thuộc skill, không cộng thành root count.
- `learning_history`: cùng shape `test_id/wrongs` của `get_test()` trong
  `data/sample/memory/get_student_profiles.py`; chỉ giữ ở raw fixture, không dùng
  recalculation hoặc public response. Đây là danh sách câu sai, không phải toàn bộ
  graded records của mỗi test, nên không suy count từ độ dài `wrongs`.
- `questions.json`: 8 câu demo độc lập có ID `DEMO_Q*`; cognitive labels và scoring
  text là annotation dành cho contract testing, chưa phải approved metadata.
  `content` map sang `content_latex`; API không tự chuyển prose thành LaTeX.
  `solution_steps` / `rubric_criteria` là metadata mới của demo fixture, không phải
  SQL columns. Fake assembler chia điểm theo đơn vị 0.25, cùng tổng cho hai views.
- `fixture_kind`: provenance cho input, nhận `synthetic_api_demo` hoặc `data_module`;
  không phải field có sẵn của canonical Data schema. Dù input do Data cung cấp,
  fake generator vẫn trả `provenance.generator="fake"`, `auto_status="not_evaluated"`.
- Canonical skill labels A001…A007 được đọc **read-only** từ `question_bank.db::skills`;
  không tạo thêm bản sao catalogue JSON. Topic text `Đại số tổ hợp` map explicit sang
  `topic_id="combinatorics"`.

Chạy API với `FAKE_API_FIXTURE_DIR` để trỏ tới thư mục JSON khác, theo envelope đã
validate trong `src/api/data_adapter.py`. Khi M3 bàn giao schema khác, sửa adapter
có chủ đích; không tắt validation hoặc tự bịa root evidence.

## Giới hạn có chủ đích

Fake chỉ kiểm tra evidence eligibility và ráp fixture đúng requested distribution.
Fake **không triển khai** real skill-priority algorithm, expression personalization,
math-rule instantiation, semantic validation hoặc Qwen. Adaptive response chỉ xác
nhận eligibility/API contract; không chứng minh đề đã cá nhân hóa theo thuật toán.

Mỗi cognitive level có 2 câu. Request không đủ candidate sẽ trả
`409 INSUFFICIENT_QUESTION_BANK`, không lặp câu hoặc trả partial success.
Default 4 câu (20/40/30/10) và 8 câu (25/25/25/25) đều đủ source.

## Fixture handoff

Data cần cung cấp profile-level evidence theo định nghĩa được nhóm duyệt. Proposal
trong cuộc review là số question IDs khác nhau đã được đánh giá trong student/topic;
đúng/sai đều tính, một câu nhiều skills không được cộng lặp ở root count.
Backend chỉ đọc giá trị chuẩn bị sẵn; không áp dụng proposal này lên legacy DB.

Sources: `docs/notes/N03_algorithm_ai.md` §4, §7;
`docs/design/wireframes.md` §1.3, §2.2, §3.2;
`data/notes/Format_dictionary.md`; hai SQLite sample databases.
