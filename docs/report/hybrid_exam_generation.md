# Hybrid Question Bank + Template Bank — 2026-10-29

Triển khai trong `MVP1/adaptive-learning`, giữ nguyên các thay đổi đã có trong
working tree. Không sửa database nguồn, điểm mastery/evidence, JSON quan hệ
P3/P2/P1, bảng độ khó hay thuật toán phân bổ nguyên phối hợp.

Update 2026-10-30: this report records the earlier 111-Question snapshot.
The latest schema and whole-exam approval implementation supersede its primary
mapping and review prerequisites; see [current report](latest_schema_whole_exam_approval.md).

## 1. Database đã kiểm tra và đường dẫn được xác nhận

Đường dẫn `pre-work/data/sample/questionbank.db` trong yêu cầu không tồn tại.
Người dùng đã xác nhận dùng file đang mở trong IDE:

`D:/HCMUS/TDTT/TH/Main_Project/pre-work/data/sample/dataset/question_bank.db`

Từ thư mục ứng dụng, đây là `../../pre-work/data/sample/dataset/question_bank.db`.
`DEFAULT_BANK` đã trỏ tới nguồn này; `M3_QUESTION_DB` vẫn là cấu hình thay thế.
Không tự tạo file tại tên sai, không copy database cũ đè lên nguồn Data Lead.

| Bảng | Bản ghi |
|---|---:|
| questions | 111 |
| answers | 111 |
| question_skills | 139 |
| question_templates | 18 |
| question_template_skills | 40 |
| skills | 9 |
| question_parts / answer_parts | 10 / 10 |
| answer_options | 0 |
| terminology | 121 |

Database có đủ A001–A009. Cấu trúc template hiện tại **không có cột `name`**:

```sql
CREATE TABLE question_templates (
    template_id TEXT PRIMARY KEY,
    template_content TEXT NOT NULL,
    parameter_rules TEXT NOT NULL,
    answer_rule TEXT NOT NULL,
    solution_rule TEXT NOT NULL,
    difficulty INTEGER NOT NULL CHECK (difficulty >= 1)
);
```

`question_template_skills(template_id, skill_id)` có khóa chính ghép và hai khóa
ngoại tới `question_templates`/`skills`, cùng `ON DELETE CASCADE`. Vì vậy không
cần đoán skill từ tên/nội dung template hay thêm bảng mapping mới.

Mỗi Template có thể hỗ trợ nhiều skill đã được Data Lead liên kết. Selector chọn
đúng **một** target trong tập đó cho mỗi instance; không cộng quota cho các skill
còn lại. Question vẫn tuân theo quy tắc primary riêng hiện có: một liên kết có
thể làm primary; nhiều liên kết cần `primary_skill_id` do tác giả cung cấp.
83 Question có primary xác định theo quy tắc này; 28 Question nhiều skill chưa
có primary bị loại khỏi lựa chọn, kèm cảnh báo.

Template không có grade/topic riêng. Adapter chỉ kế thừa scope khi **tất cả**
skill đã liên kết cùng xác định một grade/topic; không suy từ tên template.
Các liên kết hiện tại đều thuộc lớp 10, Đại số tổ hợp. Skill không hợp lệ,
mapping thiếu hoặc scope mâu thuẫn khiến Template bị loại với lý do rõ ràng.

Question có difficulty 1/2/3/4/5 lần lượt là 41/46/17/6/1 bản ghi. Mapping ứng
dụng hiện có được giữ nguyên: SQL 1→L1, 2→L2, 3→L3, 4–5→L4. Template có
7 L1, 7 L2, 4 L3; MVP1 không dùng Template L3/L4.

Toàn bộ CREATE TABLE, khóa ngoại, counts, catalogue, metadata mẫu và 40 mapping:
[hybrid_sql_audit_2026-10-29.json](hybrid_sql_audit_2026-10-29.json).

## 2. Những rule đang được hỗ trợ

`parameter_rules` là JSON lưu trong TEXT. `answer_rule` trộn công thức với mô tả
bằng lời; `solution_rule` là giải thích thuật toán bằng văn bản. Engine không
coi chúng là Python để chạy.

| Template | Mức | Công thức được kiểm tra độc lập |
|---|---|---|
| EA0001 | L1 | sum(counts) |
| EA0002 | L1 | sum(counts), length(counts)=n |
| EA0004 | L2 | n*n-n = n*(n-1) |
| EA0012 | L1 | C(n,2) = n*(n-1)/2 |
| EA0013 | L1 | C(team_count,2)*matches_per_pair |
| EA0015 | L1 | vertex_count*(vertex_count-1) |
| EA0017 | L1 | P(n) = n! |
| EA0018 | L2 | n! - 2*(n-1)! |

Hiện có **8/18 Template thực thi được**, gồm 6 L1 và 2 L2.

- EA0003 khai báo `groups.type=array` nhưng `groups.value` là chuỗi. Engine không
  bỏ qua sự mâu thuẫn này để giả vờ rule hợp lệ. Data Lead có thể sửa riêng mô
  tả hai nhóm thành một object/description phù hợp rồi kiểm chứng lại. Ứng dụng
  chưa thực hiện thay đổi đó trong SQL.
- EA0007–EA0011 có thuật toán điều kiện mô tả bằng lời, chưa có trình thực thi
  đầy đủ được duyệt. Engine không chỉ lấy một nhánh thuận tiện để tính đáp án.
- EA0005, EA0006, EA0014, EA0016 thuộc L3 nên không được chọn dù có thể bổ sung
  bộ giải sau này.

Engine dùng AST với whitelist hẹp: số nguyên, tên tham số đã khai báo, +/−/*/,
sum, C/P và factorial. Không dùng eval, exec, pickle, import động hoặc shell để
thực thi rule. Phép chia dùng Fraction; các biểu thức trong một chuỗi đẳng thức
phải cùng cho một số nguyên không âm. Từ chối biểu thức quá dài/phức tạp, giá trị
sai kiểu, thiếu/thừa tham số, điều kiện cố định bị đổi hoặc count không hợp lệ.

Sampling được giới hạn 96 lần mỗi Template, dùng một miền hữu hạn trong các
khoảng tác giả cho phép: số nguyên tối đa 12, mảng tối đa 12 phần tử, độ dài
mảng chưa chỉ định được lấy trong miền nhỏ. Đây là giới hạn tài nguyên để tạo
instance, không phải điều kiện toán học mới được chèn vào đề. Engine kiểm tra
lại range, length, length_equals, unique_items và các giá trị cố định. Mẫu số
liệu không tạo được count nguyên hợp lệ được thử lại trong budget.

Lời giải gồm `solution_rule` nguyên bản cùng bước thay tham số và kết quả tính
từ công thức. Qwen không tính hoặc cung cấp đáp án/lời giải chuẩn.

## 3. Phân bổ và chọn nguồn

Luồng giữ nguyên thứ tự:

`AllocationPlan → SourceSelector → Question nguyên bản hoặc Template instance
→ Qwen chỉ cho Template → Validation → ExamAssembler → draft store`.

Planner vẫn quyết định classification 0–4, Focus/Review, quan hệ, quota skill và
ma trận difficulty phối hợp **trước khi** đọc/chọn nguồn cụ thể. L1/L2 ưu tiên
Template khớp đúng skill, difficulty, topic và grade; không đổi target để dùng
Template. L3/L4 chỉ có Question. WEAK vẫn cấm L4 kể cả fallback.

Selector chuẩn bị các instance toán học hợp lệ trong bộ nhớ để biết dung lượng
và chống trùng; preview chưa có lời văn Qwen hoặc đề được lưu. Min-cost matching
chọn đồng thời các nguồn để tránh chiếm mất nguồn duy nhất của slot khác. Nếu
ma trận chính xác không khả thi, DP hữu hạn cho N≤10 tìm assignment toàn cục,
giữ các hard constraint và tối thiểu hóa lần lượt: cell lệch, skill lệch, khoảng
cách level, tăng level, đổi group; sau đó ưu tiên Template L1/L2, đa dạng ID mẫu
và tie-break history đã biết. Template không được tham gia các slot lệch level.
Question fallback giữ giới hạn tăng tối đa một level như selector hiện có.

Related Review không vượt quota đã cấp và không vượt 50% Review **thực đạt**.
Mọi thay nguồn/skill/level đều có cảnh báo; requested/achieved quota vẫn được
trả đầy đủ. Không tồn tại assignment an toàn thì trả
`409 INSUFFICIENT_QUESTION_BANK`, không gọi model bịa đề hoặc lưu đề dở.

## 4. Generation, provenance và tính bất biến

Question dùng chính xác content, answer, solution, skill metadata và cognitive
level nguồn. Không gọi Qwen, kể cả khi backend cấu hình `qwen` hoặc model bận.
Validator trước lưu kiểm tra lại toàn bộ các phần này. Đề chỉ gồm Question có
provenance `question_bank` và `model=null`, tránh tuyên bố đã gọi model.

Template đi qua gán/kiểm tra tham số → tính đáp án/lời giải → Qwen → kiểm tra.
Prompt chỉ chứa đề mẫu, tham số, điều kiện, cognitive level và kiểu direct;
không chứa đáp án, lời giải hoặc danh tính học sinh. JSON output chỉ được có
`question`. Numeric facts, điều kiện và proof được kiểm tra lại độc lập.

Database hiện không có bộ guard cho diễn đạt/context thay thế đã được tác giả
duyệt. Vì vậy MVP giữ toàn bộ câu đề đã gán số; không tự chứng nhận một cách
paraphrase/indirect mới là tương đương. Exact statement có kiểm tra toán; ngữ
nghĩa chưa chắc chắn vẫn cần giáo viên duyệt. Rule này có thể làm wording bị
từ chối và fallback, thay vì chấp nhận một bài toán khác dưới nhãn L1/L2 cũ.

Mỗi câu Template lưu `source_ref.kind=template`, ID gốc, `template_instance`
(instance ID, parameters, signature, template digest), nội dung, đáp án, lời
giải, metadata và trạng thái kiểm tra. Fingerprint bao gồm rule/metadata nguồn.
Signature không chứa lời văn; đổi chữ không tạo instance toán học mới. Thứ tự
nhóm trong bài sum(counts) được chuẩn hóa để không tạo mới chỉ bằng đảo mảng.
Một Template có thể xuất hiện nhiều lần nếu chữ ký toán học khác nhau; matcher
ưu tiên đa dạng Template ID và không dùng trùng một instance trong đề.

Mỗi generate dùng seed tham số mới; `instance_seed` nội bộ hỗ trợ smoke test có
thể lặp lại. Preview dùng seed kiểm soát và `source_status=pending_wording`.
Cam kết giữa preview và generate là cùng policy/phân bổ; tham số, lời văn và
nguồn fallback có thể khác. Chưa triển khai persisted plan ID để khóa instance.

Word retry dùng cùng tham số và deadline. Sau budget, Template thất bại bị loại
và selector thử lại các Template khác/Question; lý do giữ trong warnings. Đề
chỉ được lưu sau khi mọi câu hoàn tất. Không có fallback hợp lệ thì trả lỗi
structured, gồm cả lý do Template/Qwen thất bại.

Demo dùng cùng policy nhưng hiển thị đề Template đã gán số mà không gọi model;
provenance vẫn `fake`, validation là `not_evaluated`.

## 5. Duyệt và tạo lại

- Question: UI không có nút Tạo lại. API và service cùng chặn bằng
  `409 QUESTION_REGENERATION_FORBIDDEN`, trước khi gọi model. Không thay bằng
  Question khác dưới danh nghĩa regeneration.
- Template: UI có nút Tạo lại. Backend kiểm tra definition digest, instance,
  đáp án/lời giải và scope cũ; tạo tham số khác với mọi instance đang có trong
  đề; tính lại kết quả; gọi/kiểm tra Qwen rồi mới thay câu. Giữ nguyên template
  gốc, target skill, cognitive level, vị trí và max score.
- Thành công tăng revision, đưa đề về pending review và bỏ chấp thuận cũ. Các
  câu khác giữ nguyên ngoài cờ teacher_approved cần vô hiệu hóa. expected_revision
  và compare-and-swap của SQLite store được giữ nguyên.
- Lỗi model/parameter/source hoặc revision conflict không đổi draft cũ. Rule
  nguồn thay đổi bị phát hiện trước inference. Instance cũ thiếu proof vẫn đọc
  được nhưng không thể tạo lại an toàn.
- Demo cũng cho tạo tham số Template mới, không gọi model và vẫn gắn nhãn Demo.

## 6. Ví dụ end-to-end trên SQL thực tế

Chạy script với sample ST001, N=10, policy quan hệ chuẩn, seed=42 và transport
Ollama giả lập cục bộ. Đây không phải kết quả live Qwen.

| Câu | Nguồn | ID gốc | Target | Level | Tham số Template |
|---:|---|---|---|---|---|
| 1 | template | EA0001 | A001 | L1 | counts=[5,8,6] → 19 |
| 2 | template | EA0002 | A001 | L1 | n=3, counts=[1,12,4] → 17 |
| 3 | question | QA0001 | A001 | L1 | nguyên bản |
| 4 | question | QA0002 | A001 | L1 | nguyên bản |
| 5 | question | QA0077 | A009 | L3 | nguyên bản |
| 6 | question | QA0073 | A008 | L1 | nguyên bản |
| 7 | template | EA0004 | A002 | L2 | n=1, điều kiện không cùng cặp → 0 |
| 8 | template | EA0018 | A003 | L2 | n=11, A/B không cạnh nhau → 32659200 |
| 9 | question | QA0078 | A009 | L3 | nguyên bản |
| 10 | question | QA0061 | A002 | L4 | nguyên bản |

4 Template + 6 Question; 4 lần gọi model cho generation. Quota group requested
và achieved đều là Focus=4, Related=3, Balanced=3. Ma trận difficulty requested
là **3/3/3/1**, achieved là **5/2/2/1**: ngân hàng không đủ các cell chính xác
theo primary-skill rules; fallback được báo trong JSON, không giả vờ quota khớp.
Hai Question A001 L1 được dùng cho các slot thiếu level phù hợp, không ép
Template L1 vào một slot L2 chỉ để tăng số câu sinh từ mẫu.

Sau duyệt revision 2, tạo lại EA0001 đổi counts [5,8,6] thành [9,10,5], tính
lại đáp án từ 19 thành 24, gọi model một lần và lưu/retrieve revision 3 pending
review. Metadata và scoring các câu khác được giữ nguyên.

Toàn bộ preview, quota, đề, đáp án/lời giải, warnings, provenance và regeneration:
[hybrid_exam_smoke_2026-10-29.json](../../eval/results/hybrid_exam_smoke_2026-10-29.json).
Chạy lại bằng `python -m eval.smoke_hybrid_exam_generation`. Script chỉ ghi
artifact và draft DB riêng `data/runtime/hybrid_smoke_drafts.db`.

## 7. Kiểm thử và giới hạn còn lại

- Baseline: **494 passed, 1 skipped**.
- Final: **555 passed, 1 skipped**, không cần Ollama đang chạy. 61 test mới gồm
  SQL/mapping, công thức, input độc hại, parameter retry, source capacity,
  duplicate instances, hybrid persistence, question immutability, Template-only
  regeneration, failure atomicity, proof tampering và Demo regeneration.
- **12 JavaScript UI workflows passed** qua Node runtime. Pytest wrapper skip
  vì `node` không có trong shell PATH, không phải vì các workflow chưa được chạy.
- `ruff check src tests eval/smoke_hybrid_exam_generation.py`: pass.
- `ruff check .`: còn **7 lỗi có sẵn** trong hai script dữ liệu cũ không sửa ở
  task này: `data/sample/dataset/get_database.py` và
  `data/sample/memory/get_student_profiles.py` (unused/duplicate imports, E402).
- `git diff --check`: pass. SQL nguồn và profile giữ nguyên SHA-256 trước/sau.
  Hash question bank là `81d3727d88183c226451fd1e2d70196214a2486c70642c5d39c53cec6ad8e643`.

Các test cũ yêu cầu Qwen viết lại/regen Question đã được cập nhật theo chính
sách bất biến mới; các kiểm tra quota, scoring, review, persistence và revision
vẫn được giữ. Test nguồn bảy skill cũ dùng đường dẫn legacy rõ ràng để tiếp tục
kiểm tra guard mismatch, không ép database mới về bảy skill.

Không tuyên bố tất cả 18 Template đã hoạt động. EA0003 cần sửa metadata bởi
Data Lead; năm L2 mô tả cần bộ rule/solver được duyệt và kiểm chứng. 28 Question
nhiều skill cần primary do tác giả cung cấp nếu muốn đưa vào selection. Hồ sơ
sample cũ thiếu evidence A008/A009 vẫn là NO_DATA; không tạo score giả. Live
Qwen chất lượng lời văn chưa được đánh giá trong test tự động này. Indirect/
context cần metadata tương đương ngữ nghĩa được duyệt trước khi mở rộng.

Completed-question history là bước tương lai: bổ sung nguồn history hoàn chỉnh
rồi thay source-preference tại SourceSelector để ưu tiên Question chưa làm,
Template L1/L2 khi nguồn đó cạn. MVP1 hiện luôn Template-first; không dùng
wrong_questions như một lịch sử hoàn thành đầy đủ và không tạo history giả.

## 8. File tạo/sửa trong task này

Implementation (file mới được ghi rõ):

- `src/adaptation/planner.py`
- `src/adaptation/source_selector.py` — mới
- `src/ai/template_instantiator.py` — mới
- `src/ai/contracts.py`
- `src/ai/prompts.py`
- `src/ai/qwen_client.py` — giữ compatibility export và sửa lint
- `src/api/data_adapter.py`
- `src/api/m3_adapter.py`
- `src/api/template_repository.py` — mới
- `src/api/main.py`
- `src/api/schemas.py`
- `src/api/services.py`
- `src/orchestration/exam_assembler.py`
- `src/orchestration/exam_service.py`
- `src/orchestration/question_generation.py`
- `src/orchestration/review_service.py`
- `src/ui/static/app.js`
- `src/ui/static/index.html`
- `src/validation/question_validator.py`

Tests:

- `tests/unit/test_hybrid_sources.py` — mới
- `tests/integration/test_hybrid_exam_api.py` — mới
- `tests/unit/test_exam_assembly.py`
- `tests/unit/test_modular_pipeline.py`
- `tests/integration/test_automatic_difficulty_api.py`
- `tests/integration/test_exam_review.py`
- `tests/integration/test_fake_api.py`
- `tests/integration/test_planner_api.py`
- `tests/integration/test_real_api.py`
- `tests/integration/test_sample_profiles.py`
- `tests/integration/test_skill_relationship_policy_api.py`
- `tests/integration/test_structured_exam_api.py`
- `tests/integration/test_teacher_review_javascript.py`
- `tests/ui/teacher_review.test.cjs`

Config/docs/artifacts:

- `.env.example`
- `README.md`
- `config/README.md`
- `docs/report/hybrid_exam_generation.md` — mới, báo cáo này
- `docs/report/hybrid_sql_audit_2026-10-29.json` — mới
- `eval/smoke_hybrid_exam_generation.py` — mới
- `eval/results/hybrid_exam_smoke_2026-10-29.json` — mới

Runtime audit/log và draft smoke DB nằm riêng trong `data/runtime`. Không commit,
push, merge, reset hay ghi vào canonical question/template/student database.
