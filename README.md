# adaptive-learning

## Backend cá nhân hóa MVP — M3 + rule-based + Qwen

### Mở giao diện thử tạo đề

Từ thư mục `adaptive-learning`, chạy:

```powershell
.\.venv\Scripts\python.exe -m src.ui
```

Lệnh này chạy FastAPI tại `http://127.0.0.1:8000/`, tạo teacher token tạm nếu chưa
cấu hình và tự mở giao diện trong trình duyệt. UI đọc danh sách hồ sơ M3, cho
chọn số câu/chế độ/độ khó, xem kế hoạch, tạo đề, mở lại đề theo ID và tải JSON.
Đáp án, lời giải và rubric nằm trong phần mở rộng ở mỗi câu. Nội dung toán học
hiện hiển thị nguyên văn; chưa có bộ render LaTeX riêng.

Hồ sơ sample hiện có đủ 7 kỹ năng mỗi học sinh, với mastery/evidence giả lập đa
dạng để test. Thử ST001 (một skill yếu), ST003 (hai skill yếu), ST008 (đã thành
thạo), ST009 (thiếu dữ liệu một phần) và ST011 (chưa có evidence). Chọn Adaptive
và bấm **Xem kế hoạch**. Danh sách đầy đủ, nguồn fixture và cách seed có backup:
[hướng dẫn hồ sơ mẫu](data/sample/memory/USAGE.md).

Tạo đề thật cần Ollama chạy cùng model `qwen3:1.7b` (hoặc `QWEN_MODEL` đã cấu hình).
Để thử giao diện ngay mà không gọi model:

```powershell
.\.venv\Scripts\python.exe -m src.ui --fake
```

Demo vẫn đọc 20 hồ sơ M3 nhưng chỉ ghép câu nguồn, không thực hiện cá nhân hóa
trong bước tạo đề; UI ghi rõ chế độ demo. Xem kế hoạch vẫn gọi rule-based planner.
Draft demo nằm trong RAM và mất khi restart. Tắt server bằng Ctrl+C.

Nếu port 8000 đang được sử dụng, thêm `--port 8001`. Nếu chạy bằng lệnh uvicorn
ở phần dưới, mở `/` và nhập teacher token của server. `--no-browser` yêu cầu đặt
`API_TEACHER_TOKEN` trước. Token launcher được truyền bằng URL fragment, xóa ngay
khi trang đọc xong, không gửi trong URL HTTP hay lưu vào localStorage. Tải lại
trang cần nhập token đã cấu hình hoặc mở lại từ launcher. UI chỉ dành cho giáo
viên test local; chưa có màn hình học sinh, duyệt đề hay chấm bài trên UI.

API mặc định chạy backend thật (`EXAM_BACKEND=qwen`), đọc hồ sơ trực tiếp từ
`data/sample/memory/student_profiles_sample.db` và câu hỏi từ
`data/sample/dataset/question_bank.db`. Hai database M3 chỉ được đọc.

Planner phân loại độc lập theo từng skill: evidence 0 là NO_DATA, 1–2 là PARTIAL;
từ **3 evidence**, mastery dưới **3.0/4** là WEAK. Hai skill yếu nhất nhận 60%
Focus; một skill yếu nhận 40% Focus. Quota độ khó giáo viên đặt là ràng buộc cứng.
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
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Swagger: `http://127.0.0.1:8000/docs`; Authorize bằng teacher token của process.
Ứng dụng không tự load `.env`; `.env.example` là danh sách biến để cấu hình.

Lấy học sinh thật qua `GET /api/v1/students`. Ví dụ `ST001`, mode `adaptive`:

```json
{
  "student_id": "ST001",
  "generation_mode": "adaptive",
  "selected_topic_ids": ["combinatorics"],
  "total_questions": 4,
  "duration_minutes": 45,
  "difficulty_distribution": {
    "recognition": 20, "understanding": 40,
    "application": 30, "advanced_application": 10
  }
}
```

Gửi body này tới `POST /api/v1/exams/plan` để xem skill ưu tiên, ID câu nguồn,
lý do chọn và cảnh báo thiếu quota. Endpoint này không gọi Qwen, không lưu đề.
Gửi tới `POST /api/v1/exams/generate` để lập kế hoạch, gọi Qwen và nhận đề hoàn chỉnh.
`GET /api/v1/exams/{exam_id}` đọc lại đề kể cả sau khi khởi động lại API.

Qwen chỉ viết lại câu chữ; đáp án lấy nguyên từ M3. Nguồn hiện đều là draft,
cognitive labels dùng mapping ứng dụng ghi trong ADR-002, rubric là tiêu chí tổng
quát cần duyệt. Mọi đề mới giữ `pending_teacher_review`, `auto_status=needs_review`.
Kiểm tra JSON/số liệu chưa chứng minh tương đương ngữ nghĩa hay đáp án nguồn đúng.
Không đổi số liệu bài toán, không sinh template mới hoặc chấm bài/cập nhật mastery.

Lỗi Ollama/model không sẵn sàng trả 503, timeout 504, JSON/số liệu sai sau retry
trả 502. Không lưu đề dở, không âm thầm trả fake. Mỗi process chỉ phục vụ một
request sinh đề Qwen tại một thời điểm; MVP chạy một worker.
Đề lưu riêng tại `data/runtime/exams.db`, không ghi ngược vào nguồn M3.

Để dùng JSON hồ sơ Data theo format đã chốt, đặt `PROFILE_SOURCE=json` và
`API_PROFILE_DIR` tới thư mục chứa `student_profiles.json` có envelope
`fixture_kind/topic_id/students`. Backend Qwen vẫn lấy câu từ SQLite M3.
Mặc định JSON trong repo là demo synthetic, không phải học sinh thật M3.

### Duyệt đề và tạo lại câu hỏi

Các thao tác dưới đây dùng cùng teacher bearer token và trả đề đầy đủ đồng bộ:

- `POST /api/v1/exams/{exam_id}/approve` nhận `expected_revision`,
  `accepted_question_ids` (đủ tất cả ID câu hiện tại) và `notes` tùy chọn.
  Chỉ thao tác này mới chuyển đề sang `approved`; AI không tự duyệt đề.
- `POST /api/v1/exams/{exam_id}/questions/{question_id}/regenerate` nhận
  `expected_revision`. Pipeline Qwen viết lại cùng câu nguồn, giữ đáp án/điểm và
  tạo ID câu mới. Thành công đưa toàn đề về `pending_teacher_review` và bỏ duyệt
  cũ. Fake generator không hỗ trợ thao tác này và trả 409.

Mỗi lần sửa tăng `revision` một đơn vị. Revision cũ trả 409
`EXAM_REVISION_CONFLICT`; client cần tải lại đề. Lỗi model không thay đổi draft.
SQLite giữ các snapshot trong `exam_revisions`, gồm bản đã duyệt trước khi tạo
lại câu. Teacher token dùng chung chưa xác định danh tính từng giáo viên.
Approve hiện chưa giao đề cho học sinh; chưa có student authentication/delivery.

Ví dụ duyệt đề (thay ID bằng các giá trị trong response mới nhất):

```json
{
  "expected_revision": 1,
  "accepted_question_ids": ["QW_example_1", "QW_example_2"],
  "notes": "Đã kiểm tra câu hỏi, đáp án và rubric."
}
```

Pipeline nội bộ: `AllocationPlan → QuestionSelector → ExpressionPlanner →
Qwen generate_one → QuestionValidator → ExamAssembler`. Retry được quản lý
một lần tại `QuestionGenerationService`, dùng chung deadline toàn đề.
Expression hiện giữ nguyên bối cảnh và dạng direct; chưa suy đặc tả toán học từ
văn bản hoặc tự đổi sang indirect.

Policy P3/P2/P1 hỗ trợ cấu hình `SKILL_RELATIONSHIPS_FILE` theo đúng danh mục dữ
liệu. Bộ thử 9 kỹ năng tại `tests/fixtures/nine_skill_relationships.json` không
phải mapping cho 7 kỹ năng M3: không dùng file đó với database M3 hiện tại.
Xem [kế hoạch hai người](docs/design/implementation_plan_two_people.md).

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
    generation_mode = 'default_blueprint'
    selected_topic_ids = @('combinatorics')
    total_questions = 4
    duration_minutes = 45
    difficulty_distribution = @{
        recognition = 20; understanding = 40
        application = 30; advanced_application = 10
    }
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
API chuyển nguyên hồ sơ cho service; chính sách evidence để lập đề thuộc Planner,
fake chưa áp dụng ngưỡng adaptive hoặc cá nhân hóa theo evidence.

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
- Fake ráp câu tĩnh đúng count/distribution; không thực hiện real personalized
  planning hoặc semantic validation. Không có timeout/retry/model-busy machinery
  cho inference vì fake không gọi inference.
- Có 8 câu demo; thiếu source trả 409. Points/scoring trong fixture chưa teacher-review.
- Exam drafts chỉ lưu trong memory của **một worker**, mất khi restart; không có TTL.
- Chưa mở student endpoint hoặc student authentication. `StudentExamResponse` và
  `ExamResponse.student_view()` là allowlist loại answer/solution/rubric/validation
  cho student integration sau này; teacher routes vẫn yêu cầu teacher token.
- Real service thay qua `create_app(generator=...)` hoặc dependency override
  `get_exam_generator`, giữ `ExamGenerator.generate(request, profile) -> ExamResponse`.
