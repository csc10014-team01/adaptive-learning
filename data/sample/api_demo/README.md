# Static JSON cho Fake API MVP1

Các file trong thư mục này là **synthetic API demo fixtures**, không phải Profile JSON
đã được M3 bàn giao, không phải bản sao của các student records `ST*`, và không phải
question bank đã được teacher review. Chúng được thêm vì repository hiện chỉ có
SQLite sample + readers. Student shape tuân theo format Ánh Dương đã chốt trong
`data/notes/Format_dictionary.md`; các giá trị và ID demo vẫn là synthetic.

Không sửa hoặc tự export/aggregate các SQLite records để lấp field còn thiếu.
Canonical M3/AI source code và hai database hiện có được giữ nguyên.

## Files và mapping

- `student_profiles.json`: mỗi student gồm `student_id`, `name`, `grade_level`,
  `skill_mastery`, `learning_history`. Profile response giữ nguyên cấu trúc này;
  students list chỉ trả `student_id`, `name`, `grade_level`.
  Không có evidence chung, `data_status` hoặc recommended mode.
- `skill_mastery[].mastery_score`: giữ scale 0–4 theo CHECK của
  `data/sample/memory/student_profiles_sample.db::student_skill_mastery`.
  `skill_mastery[].evidence_count` là số nguyên không âm, độc lập cho mỗi skill;
  API giữ nguyên giá trị, không cộng thành count chung.
- `learning_history`: mỗi phần tử gồm `test_id`, `wrong_questions` theo format đã
  chốt. API trả nguyên lịch sử trong profile và chuyển cho generator. Không suy
  evidence từ số bài hoặc số câu sai. Legacy `get_test()` vẫn dùng `wrongs`; khi nối
  trực tiếp getter cần chuẩn hóa tên trường trong adapter.
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
validate trong `src/api/data_adapter.py`. Mỗi student được validate bằng cùng schema
với profile response. Field ngoài format hoặc thiếu evidence từng skill bị báo lỗi.

## Giới hạn có chủ đích

Fake ráp fixture cùng khối lớp, đúng requested distribution và số câu.
Fake **không triển khai** real skill-priority algorithm, expression personalization,
math-rule instantiation, semantic validation hoặc Qwen. Cả hai generation modes
được chuyển cho service mà không đặt ngưỡng evidence trong API. Adaptive response
chỉ xác nhận API contract; không chứng minh đề đã cá nhân hóa theo thuật toán.

Mỗi cognitive level có 2 câu. Request không đủ candidate sẽ trả
`409 INSUFFICIENT_QUESTION_BANK`, không lặp câu hoặc trả partial success.
Default 4 câu (20/40/30/10) và 8 câu (25/25/25/25) đều đủ source.
Profile nhận khối lớp là số nguyên dương, gồm lớp 11 trong ví dụ Data. Catalogue và
question fixtures hiện chỉ có lớp 10; sinh đề cho lớp khác nhận 409 vì thiếu câu.

## Fixture handoff

### Planner primary skills

The rule-based planner requires an explicit primary for multi-skill questions.
The six sole-skill demo questions now contain `primary_skill_id`. The adapter
also supports the documented legacy sole-skill migration in memory. No canonical
SQLite data is modified. `DEMO_Q07` and `DEMO_Q08` still need author-supplied
primaries and are excluded from planning with warnings; the planner therefore
has no eligible L4 demo questions yet. The fake assembler keeps its existing
fixture behavior. See `docs/decisions/ADR-003-rule-based-planner-mvp.md` for the
contracts, teacher locks, and remaining data dependencies.

Data cung cấp JSON theo student format đã chốt, với evidence cho từng skill.
Algorithm Lead phối hợp Data Lead chốt cách ghi nhận một evidence, cập nhật mastery
sau chấm bài và dùng evidence để lập đề. Backend hiện chỉ đọc và chuyển nguyên
hồ sơ cho service; không tự thêm chính sách bằng tổng/max/count của các skill.

Sources: `docs/notes/N03_algorithm_ai.md` §4, §7;
`docs/design/wireframes.md` §1.3, §2.2, §3.2;
`data/notes/Format_dictionary.md`; hai SQLite sample databases.
