# adaptive-learning

## Fake FastAPI backend — MVP1

Chạy từ repository root, Python 3.11 trở lên. API không gọi Ollama/Qwen và không ghi
vào Data databases. Contract và giới hạn: [N04](docs/notes/N04_architecture_api.md).

### Cài và chạy (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:FAKE_API_TEACHER_TOKEN = [guid]::NewGuid().ToString('N')
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
`DEMO_SUFFICIENT_001` và mode `adaptive` để thử eligibility >=3.

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


## Finalized Exam Generator integration

The existing fake/JSON API and non-adaptive `default_blueprint` requests remain
available. The integrated teacher workflow uses the tracked, project-local Data
Lead databases, with no demo fallback if SQL is unavailable:

```powershell
python -m src.ui
# SQL-backed demonstration without model inference:
python -m src.ui --fake
```

The local launcher binds to loopback, creates an in-memory teacher credential,
and opens the UI. For headless use, configure `API_TEACHER_TOKEN` and use
`--no-browser`. For a plain API deployment, explicitly set `EXAM_BACKEND=qwen`
and `PROFILE_SOURCE=m3`, then run `python -m uvicorn src.api.main:app`.
Environment variables must be exported in the process; `.env` is documentation,
not an automatically loaded credential file.

Adaptive requests omit `difficulty_distribution` (or send null). The Planner
handles all nine skills, including NO_DATA/PARTIAL students. Existing
non-adaptive requests retain their manual distribution. New endpoints are
`POST /api/v1/exams/plan`, `POST /api/v1/exams/{id}/approve`, and
`POST /api/v1/exams/{id}/questions/{question_id}/regenerate`; all require the
existing teacher bearer authentication. Approval and regeneration require
`expected_revision`. Whole-exam approval does not require individual checkboxes.

Qwen uses local Ollama (`qwen3:1.7b` by default). The launcher enables experimental
Indirect wording; set `KORO_EXPERIMENTAL_INDIRECT=0` for verified-only behavior.
Experimental semantic equivalence remains unproven and visible to the teacher.
Backend answers/solutions stay authoritative. Fake mode demonstrates assembly
without establishing real-model wording quality.

`M3_QUESTION_DB` and `M3_STUDENT_DB` default to the tracked files under
`data/sample/dataset/` and `data/sample/memory/`. They are read-only. Only generated
drafts/revisions are stored in `data/runtime/exams.db` (or `EXAM_DB`), separately
from the canonical databases. Relative database paths resolve from the project
root. Optional skill relationships use `SKILL_RELATIONSHIPS_FILE`; their activation
policy is unchanged from the finalized implementation. No sibling `pre-work`
checkout is required in CI.

See [the integration report](docs/report/finalized_generator_integration.md) for
source provenance, changed files, compatibility decisions and verification.
