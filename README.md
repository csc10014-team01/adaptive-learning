# adaptive-learning

## Backend cá nhân hóa MVP — M3 + rule-based + Qwen

### Mở giao diện thử tạo đề

Từ thư mục `adaptive-learning`, chạy:

```powershell
.\.venv\Scripts\python.exe -m src.ui
```

Lệnh này chạy FastAPI tại `http://127.0.0.1:8000/`, tạo teacher token tạm nếu chưa
cấu hình và tự mở giao diện trong trình duyệt. UI đọc danh sách hồ sơ M3, cho
chọn học sinh/chủ đề/số câu/thời gian, xem kế hoạch, tạo đề, mở lại đề theo ID và tải JSON.
Độ khó và chiến lược được planner tự xác định từ hồ sơ; giáo viên chỉ xem kết quả.
Đáp án, lời giải và rubric nằm trong phần mở rộng ở mỗi câu. Nội dung toán học
hiện hiển thị nguyên văn; chưa có bộ render LaTeX riêng.

Hồ sơ mặc định đọc SQLite Data Lead trong `pre-work/data/sample/memory`, không
đọc bản app-local đã seed để test. File hiện có 20 học sinh và 11 dòng assessment.
Thử ST001 (A001: 2.3/4, 1 evidence), ST004 (A005: 0.0/4, 1 evidence),
ST011 (A004: 3.0/4, 1 evidence), hoặc ST012 (chưa có assessment).
API trả đủ 9 kỹ năng: không có evidence thì `mastery_score=null`, `evidence_count=0`;
UI hiện `--/4`, Planner phân loại NO_DATA. Có evidence thì giữ đúng điểm SQL,
kể cả điểm 0.0. Có evidence nhưng mastery null là lỗi dữ liệu, không được đổi
thành NO_DATA. Bản fixture 140 dòng và manifest seed cũ chỉ phục vụ kiểm thử
offline; không dùng làm fallback cho dữ liệu thật.

Tạo đề thật cần Ollama chạy cùng model `qwen3:1.7b` (hoặc `QWEN_MODEL` đã cấu hình).
Để thử giao diện ngay mà không gọi model:

```powershell
.\.venv\Scripts\python.exe -m src.ui --fake
```

Demo dùng cùng rule-based planner và chính sách chọn nguồn như backend Qwen.
Question giữ nguyên văn; Template hiển thị đề đã gán tham số và đáp án tính bằng
rule engine, không gọi model. UI ghi rõ Demo/Fixture. Xem kế hoạch chưa chốt lời
văn; tham số mẫu có thể khác ở lần tạo đề mới.
Draft demo nằm trong RAM và mất khi restart. Tắt server bằng Ctrl+C.

Nếu port 8000 đang được sử dụng, thêm `--port 8001`. Nếu chạy bằng lệnh uvicorn
ở phần dưới, mở `/` và nhập teacher token của server. `--no-browser` yêu cầu đặt
`API_TEACHER_TOKEN` trước. Token launcher được truyền bằng URL fragment, xóa ngay
khi trang đọc xong, không gửi trong URL HTTP hay lưu vào localStorage. Tải lại
trang cần nhập token đã cấu hình hoặc mở lại từ launcher. UI chỉ dành cho giáo
viên test local; chưa có màn hình học sinh hay chấm bài trên UI.
Sau khi tạo hoặc mở đề, giáo viên có thể xem đáp án, đánh dấu đã kiểm tra từng
câu, tạo lại câu từ Template (backend Qwen), tải lại phiên bản mới nhất và duyệt đề.
Tạo lại câu đưa đề về trạng thái chờ duyệt; xung đột phiên bản yêu cầu tải lại.
Giáo viên có thể duyệt toàn bộ bản nháp hợp lệ ngay sau khi xem đề, không cần
đánh dấu từng câu. Các checkbox kiểm tra riêng là tùy chọn; duyệt toàn đề không
tự đánh dấu những câu chưa được kiểm tra riêng.

API mặc định chạy backend thật (`EXAM_BACKEND=qwen`), đọc hồ sơ trực tiếp từ
`../../pre-work/data/sample/memory/student_profiles_sample.db` và câu hỏi từ
`../../pre-work/data/sample/dataset/question_bank.db` tính từ thư mục ứng dụng.
Đây là đường dẫn Data Lead đã được người dùng xác nhận thay cho tên
`pre-work/data/sample/questionbank.db` không tồn tại. Biến `M3_QUESTION_DB` cho
phép cấu hình vị trí khác. `M3_STUDENT_DB` ghi đè rõ ràng nguồn hồ sơ; đường dẫn
tương đối được tính từ thư mục ứng dụng. Hai database Data Lead chỉ được đọc;
nguồn thiếu/lỗi không chuyển sang Fake/Demo hoặc bản SQL đã seed.
Chi tiết nguyên nhân số liệu trông như giả lập và quy tắc nullable mastery:
[Missing student mastery](docs/report/missing_student_mastery.md).
Schema mới đọc main skill từ `QuestionMainSkill`, toàn bộ liên kết từ
`question_skills`, và lời giải từ `answers.explaination` (đúng chính tả SQL).
Dòng lỗi bị loại kèm chẩn đoán. Sau khi Data Lead sửa nguồn, gọi
`M3DataAdapter.reload_bank()` hoặc khởi động lại backend; phiên đang giữ cache
sẽ từ chối dùng lẫn phiên bản nguồn cũ/mới. Đường dẫn tương đối của
`M3_QUESTION_DB` được tính từ thư mục ứng dụng; file thiếu không được thay tự động.
Chi tiết schema và ví dụ duyệt không có xác nhận riêng từng câu:
[latest schema / whole-exam approval](docs/report/latest_schema_whole_exam_approval.md).

Khi chạy `python -m src.ui`, MVP local mặc định bật **Indirect thử nghiệm** từ
Template L1/L2, không cần mẫu Indirect được duyệt trước. Đặt
`$env:KORO_EXPERIMENTAL_INDIRECT='0'` trước khi chạy để dùng chế độ chỉ cho phép
presentation đã duyệt. Khi chạy API trực tiếp bằng uvicorn, bật bằng
`$env:KORO_EXPERIMENTAL_INDIRECT='1'`; không tự đọc `.env`.
ExpressionPlanner luân phiên Direct/Indirect giữa các slot Template phù hợp,
không phụ thuộc mastery hay gắn Indirect riêng với L2. Qwen dùng temperature 0.7
cho nhánh thử nghiệm, nhận tình huống gợi ý và lời văn trước để tránh lặp.
Các câu thử nghiệm mang `verification_status=experimental`, luôn cần teacher
review và hiển thị rõ **chưa kiểm chứng đầy đủ về ngữ nghĩa toán học**.
Backend vẫn tính tham số, đáp án và lời giải. Các kiểm tra số liệu/nguồn/điều kiện
cơ bản không chứng minh tương đương ngữ nghĩa hay mức nhận thức của lời văn.

Cơ chế mẫu đã duyệt trong `config/template_presentations.json` vẫn được giữ;
8 đề xuất ở đó vẫn chưa được duyệt, không bị tự đổi thành `verified`.
Exact-pattern validation chỉ được nới ở nhánh `experimental_indirect`.
Tạo lại ưu tiên instance mới và presentation khác; nếu Indirect không qua kiểm
tra thì thử Direct trên cùng tham số, có ghi lý do. Duyệt toàn đề vẫn không yêu
cầu checkbox từng câu. Xem [báo cáo thử nghiệm](docs/report/experimental_indirect.md)
và [thiết kế verified-only trước đó](docs/report/template_presentations.md).

Planner phân loại độc lập theo từng skill: evidence 0 là NO_DATA, 1–2 là PARTIAL;
từ **3 evidence**, mastery dưới **2.0/4** là WEAK; từ **2.0/4** là ACHIEVED.
Điểm mastery giữ nguyên thang **0–4**, không đổi sang thang 10. Hai skill yếu nhất nhận 60%
Focus; một skill yếu nhận 40% Focus. Độ khó theo mastery riêng của từng kỹ năng đủ
evidence; kỹ năng NO_DATA/PARTIAL dùng ưu tiên mặc định. Chỉ khi không có kỹ năng
nào đủ evidence mới dùng blueprint chẩn đoán mặc định cho toàn đề. Mastery 0 với
evidence ≥3 vẫn là WEAK. Giáo viên không đặt tỷ lệ hoặc ép chế độ chuẩn.
Chi tiết thay đổi và giới hạn fallback: [automatic difficulty](docs/report/automatic_difficulty_fix.md).
Ngưỡng 2.0/4 và bảng sáu dải độ khó mới nhất:
[coordinated difficulty](docs/report/coordinated_difficulty_allocation.md).
Chính sách: [ADR-003](docs/decisions/ADR-003-rule-based-planner-mvp.md).
Pipeline module và duyệt đề: [ADR-004](docs/decisions/ADR-004-modular-generation-and-review.md).

### Chạy backend thật (PowerShell, từ thư mục adaptive-learning)

```powershell
# Cần Python 3.11+ và Ollama đã cài trên máy.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull qwen3:1.7b
# Nếu Ollama chưa chạy, mở terminal riêng và chạy: ollama serve
$env:API_TEACHER_TOKEN = [guid]::NewGuid().ToString('N')
$env:EXAM_BACKEND = 'qwen'
$env:PROFILE_SOURCE = 'm3'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:QWEN_MODEL = 'qwen3:1.7b'
$env:SKILL_RELATIONSHIPS_FILE = 'config/skill_relationships_a001_a009.json'
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Swagger: `http://127.0.0.1:8000/docs`; Authorize bằng teacher token của process.
Ứng dụng không tự load `.env`; `.env.example` là danh sách biến để cấu hình.

Lấy hồ sơ qua `GET /api/v1/students`. Ví dụ `ST001`, mode `adaptive`:

```json
{
  "student_id": "ST001",
  "generation_mode": "adaptive",
  "selected_topic_ids": ["combinatorics"],
  "total_questions": 4,
  "duration_minutes": 45
}
```

Gửi body này tới `POST /api/v1/exams/plan` để xem skill ưu tiên, ID câu nguồn,
lý do chọn và cảnh báo thiếu quota. Endpoint này không gọi Qwen, không lưu đề.
Hai endpoint tạo/xem kế hoạch chỉ chấp nhận `generation_mode=adaptive` (mặc định
khi bỏ trống). `difficulty_distribution` chỉ được bỏ trống hoặc null; tỷ lệ thủ
công và mode `standard`/`default_blueprint` trả 422 với chi tiết field.
Gửi tới `POST /api/v1/exams/generate` để lập kế hoạch, gọi Qwen và nhận đề hoàn chỉnh.
`GET /api/v1/exams/{exam_id}` đọc lại đề kể cả sau khi khởi động lại API.

L1/L2 ưu tiên Template đúng kỹ năng, topic, grade và độ khó với rule thực thi được;
nếu không có thì dùng Question. L3/L4 chỉ dùng Question. Question được giữ nguyên
đề, đáp án và lời giải, không gọi Qwen và không cho tạo lại. Template được gán
tham số hợp lệ, tính đáp án/lời giải độc lập rồi mới gọi Qwen viết lời văn. Chưa
có metadata cho biến đổi bối cảnh/indirect an toàn nên chỉ dùng direct, giữ toàn
bộ đề đã gán số. Mọi đề mới vẫn cần giáo viên duyệt.

`source_ref.kind` phân biệt `question`/`template`; câu Template có thêm
`template_instance` gồm instance ID, tham số, chữ ký toán học và fingerprint
template. Đề không gọi model có provenance `question_bank`/`model=null`; đề có
câu Template gọi model mang provenance `qwen`. Contract cũ vẫn đọc được, nhưng
câu Question cũ cũng bị chặn tạo lại theo chính sách bất biến mới.

Lỗi Template/Qwen được retry có giới hạn rồi chọn Template khác hoặc fallback
Question, kèm cảnh báo. Khi cả hai nguồn không thể hoàn thành đề, trả
`409 INSUFFICIENT_QUESTION_BANK`; không lưu đề dở hoặc âm thầm trả fake. Tạo lại
Template thất bại trả lỗi model tương ứng và giữ nguyên draft. Mỗi process có
một slot gọi Qwen; đề chỉ gồm Question không cần slot model. MVP chạy một worker.
Đề lưu riêng tại `data/runtime/exams.db`, không ghi ngược vào nguồn M3.

Để dùng JSON hồ sơ Data theo format đã chốt, đặt `PROFILE_SOURCE=json` và
`API_PROFILE_DIR` tới thư mục chứa `student_profiles.json` có envelope
`fixture_kind/topic_id/students`. Backend Qwen vẫn lấy câu từ SQLite M3.
Mặc định JSON trong repo là demo synthetic, không phải học sinh thật M3.

### Duyệt đề và tạo lại câu hỏi

Các thao tác dưới đây dùng cùng teacher bearer token và trả đề đầy đủ đồng bộ:

- `POST /api/v1/exams/{exam_id}/approve` nhận `expected_revision`;
  `accepted_question_ids` và `notes` đều tùy chọn.
  Danh sách ID chỉ ghi nhận những câu thực sự được xác nhận riêng, có thể bỏ trống.
  Chỉ thao tác này mới chuyển đề sang `approved`; AI không tự duyệt đề.
- `POST /api/v1/exams/{exam_id}/questions/{question_id}/regenerate` nhận
  `expected_revision`. Chỉ áp dụng cho Template: tạo tham số khác, tính lại đáp
  án/lời giải, sinh và kiểm tra lời văn; giữ template nguồn, kỹ năng, mức độ và
  điểm. Thành công đưa toàn đề về `pending_teacher_review` và bỏ duyệt cũ.
  Question trả `409 QUESTION_REGENERATION_FORBIDDEN`; UI không có nút Tạo lại.
  Demo cũng tạo tham số Template mới nhưng chỉ hiển thị đề đã gán số, không gọi
  Qwen và giữ `auto_status=not_evaluated`.

Mỗi lần sửa tăng `revision` một đơn vị. Revision cũ trả 409
`EXAM_REVISION_CONFLICT`; client cần tải lại đề. Lỗi model không thay đổi draft.
SQLite giữ các snapshot trong `exam_revisions`, gồm bản đã duyệt trước khi tạo
lại câu. Teacher token dùng chung chưa xác định danh tính từng giáo viên.
Approve hiện chưa giao đề cho học sinh; chưa có student authentication/delivery.

Ví dụ duyệt đề (thay ID bằng các giá trị trong response mới nhất):

```json
{
  "expected_revision": 1,
  "notes": "Đã kiểm tra câu hỏi, đáp án và rubric."
}
```

Pipeline nội bộ: `AllocationPlan → SourceSelector → Question nguyên bản hoặc
TemplateInstantiator → Qwen (chỉ Template) → QuestionValidator → ExamAssembler`.
Retry lời văn dùng cùng tham số và deadline. Model không nhận đáp án/lời giải.
Preview đánh dấu Template `pending_wording`; mỗi lần generate có seed tham số
mới. Chính sách phân bổ/chọn nguồn tương thích giữa preview và generate, nhưng
không có cam kết khóa instance/lời văn khi chưa có persisted plan ID.
[Chi tiết triển khai, giới hạn và ví dụ đề hỗn hợp](docs/report/hybrid_exam_generation.md).

Policy P3/P2/P1 hỗ trợ cấu hình `SKILL_RELATIONSHIPS_FILE` theo đúng danh mục dữ
liệu. Catalogue chính thức của MVP là **A001–A009**; policy chuẩn nằm tại
`config/skill_relationships_a001_a009.json`, bản fixture kiểm thử được đối chiếu
tự động với file này. Ma trận SK cũ không còn là policy 9 kỹ năng đang dùng.
Database `pre-work` đã có 9 kỹ năng và 40 liên kết `question_template_skills`.
SQL cũ trong `data/sample/dataset` vẫn có 7 kỹ năng và không được tự sửa/remap.
Hồ sơ sample cũ thiếu evidence A008/A009 được phân loại NO_DATA; không tạo điểm
mastery giả. [Ma trận chính thức và cấu hình](config/README.md).

### Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test tích hợp backend thật dùng HTTP server giả lập Ollama để kiểm tra giao thức,
personalization, failure, provenance và persistence; không thay thế kiểm thử chất
lượng với model thật. CLI thử model độc lập: `python src/ai/qwen_spike.py`.

## Fake FastAPI backend — chế độ tương thích để test/demo

Chạy từ repository root, Python 3.11 trở lên. API không gọi Ollama/Qwen và không ghi
vào Data databases. Contract và giới hạn: [N04](docs/notes/N04_architecture_api.md).

### Cài và chạy (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:FAKE_API_TEACHER_TOKEN = [guid]::NewGuid().ToString('N')
$env:EXAM_BACKEND = 'fake'
$env:PROFILE_SOURCE = 'json'
# Chỉ khi UI khác origin; thay bằng origin thực tế của UI:
$env:FAKE_API_CORS_ORIGINS = 'http://localhost:5173'
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Swagger: `http://127.0.0.1:8000/docs`. Dùng nút **Authorize** với bearer token vừa cấu
hình. Tất cả `/api/v1` endpoints đều dành cho teacher; không cấu hình token trả 503,
thiếu token trả 401, token sai trả 403. Đây là access gate cho local fake demo,
không phải hệ thống login/roles cho production. Không nhúng teacher secret vào
student-facing UI hoặc build artifact công khai.

### Gọi API

Trong terminal PowerShell khác, dùng cùng teacher token của process server:

```powershell
$teacherToken = Read-Host 'Teacher token'
$headers = @{ Authorization = "Bearer $teacherToken" }
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/students' -Headers $headers
$body = @{
    student_id = 'DEMO_NEW_001'
    generation_mode = 'adaptive'
    selected_topic_ids = @('combinatorics')
    total_questions = 4
    duration_minutes = 45
} | ConvertTo-Json -Depth 5
$exam = Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/exams/generate' `
    -Method Post -Headers $headers -ContentType 'application/json' -Body $body
$exam
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/exams/$($exam.exam_id)" -Headers $headers
```

POST trả complete teacher exam JSON trong cùng request. Dùng
`DEMO_SUFFICIENT_001` và mode `adaptive` để thử cùng HTTP contract.
Profile giữ format Data: `student_id`, `name`, `grade_level`, `skill_mastery`,
`learning_history` với `wrong_questions`. Evidence chỉ có trong từng skill.
API chuẩn hóa trạng thái chưa đánh giá thành null trước khi chuyển hồ sơ cho service; cả Demo và Qwen dùng chính sách evidence,
phân bổ kỹ năng và chọn câu của cùng RuleBasedPlanner.

### Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Trên Linux/macOS dùng `.venv/bin/python` thay cho `.venv\Scripts\python.exe` và
`export FAKE_API_TEACHER_TOKEN=...` để cấu hình process environment.
Ứng dụng không tự load `.env`.

### Giới hạn / handoff

- N04 ban đầu là file rỗng; contract implementation được ghi lại từ bản draft đã
  review trong cuộc trò chuyện, cùng các compatibility/security decisions rõ ràng.
- Chưa có canonical M3 JSON. [Demo fixtures](data/sample/api_demo/README.md) dùng
  synthetic IDs, không thay thế hoặc aggregate legacy student database.
- Fake dùng planner thật rồi ráp câu nguồn, không thực hiện semantic validation.
  Không có timeout/retry/model-busy machinery cho inference vì fake không gọi inference.
- Có 8 câu demo nhưng chỉ 6 câu đủ primary metadata; thiếu source phù hợp trả 409.
  Points/scoring trong fixture vẫn cần teacher review.
- Exam drafts chỉ lưu trong memory của **một worker**, mất khi restart; không có TTL.
- Chưa mở student endpoint hoặc student authentication. `StudentExamResponse` và
  `ExamResponse.student_view()` là allowlist loại answer/solution/rubric/validation
  cho student integration sau này; teacher routes vẫn yêu cầu teacher token.
- Real service thay qua `create_app(generator=...)` hoặc dependency override
  `get_exam_generator`, giữ `ExamGenerator.generate(request, profile) -> ExamResponse`.
