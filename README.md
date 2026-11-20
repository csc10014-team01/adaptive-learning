# adaptive-learning

## Fake FastAPI backend — MVP1

Chạy từ repository root, Python 3.11 trở lên. Các endpoint sinh đề fake không gọi
Ollama/Qwen và không ghi vào Data databases. Phần AI grading riêng được mô tả bên
dưới. Contract sinh đề fake và giới hạn: [N04](docs/notes/N04_architecture_api.md).

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

Qwen uses local Ollama (`qwen3:4b-q4_K_M` by default). The launcher enables experimental
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

## AI grading integration (W08, 2026-11-20)

The separate `/grading` page uses the extracted frozen engine
`R2026-11-17-scoped-skill-guidance-v11`, with real local Ollama inference.
It accepts explicitly supplied experimental multi-question context and raw answers.
The synthetic example is reusable from the page or
[`grading-example.json`](src/ui/static/grading-example.json). It has no gold/verdict labels.
Generation remains at `/`; `--fake` affects generation only.

Git Bash, from this repository:

```bash
python -m venv .venv
source .venv/Scripts/activate           # Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
ollama serve                          # separate terminal, only if not already running
ollama list                           # must contain the exact GRADING_MODEL tag
# If missing, explicitly install it yourself: ollama pull qwen3:4b-q4_K_M
export GRADING_MODEL='qwen3:4b-q4_K_M'
python -m src.ui --grading
```

The browser opens with a temporary workspace credential. Click **Nạp ví dụ tổng hợp**,
edit the raw answers if desired, then **Bắt đầu chấm bằng AI**. Reopen using the stored
job ID and download compact result JSON. Press **Ctrl+C** in the server terminal to
stop. For headless/API use, export a secret `API_TEACHER_TOKEN`, then:

```bash
python -m src.ui --grading --no-browser
# Or plain API (single application worker):
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Protected endpoints: `POST /api/v1/grading/jobs` (202),
`GET /api/v1/grading/jobs/{job_id}`, and
`GET /api/v1/grading/jobs/{job_id}/result` (409 until completed).
Each response separates `metadata` from compact `result`. Supply an `idempotency_key`;
identical retries return the same job, changed content with the same key returns 409.
Capacity defaults to four active jobs including the running job. One bounded local
worker processes them; no Redis/Celery. Use **one application process**; a store lease
rejects competing workers on the same machine. Do not share this SQLite worker across hosts.

`COMPLETED` means all questions were processed and persisted; some may be `UNCERTAIN`.
An AI/provider failure never becomes a student error. Explicit blank answers are
`INCORRECT` with `Bài làm tự luận chưa đầy đủ.` and no wrong skill IDs; missing answer
records are rejected. There are no numeric grading scores, overrides or profile updates.

Jobs, original text, exact context and compact results persist in
`data/runtime/grading.db`. At the first grading access after restart, previously
queued/running jobs become `INTERRUPTED`; they are never resumed automatically.
Completed results remain readable. Graceful shutdown also interrupts unfinished work.
Optional `GRADING_DEBUG=true` writes sensitive traces under `data/runtime/grading_debug/`
after the corresponding result transaction. Clean only old diagnostic files with:

```bash
python -m src.grading.cleanup --older-than-days 7
python tools/run_grading_smoke.py --live     # explicit real inference via API + worker
python -m pytest -q --basetemp .pytest_tmp_mira/grading_check
node tests/ui/grading.test.cjs
```

All runtime files are already covered by `.gitignore`. Cleanup never deletes stored
submissions/results. `.env.example` documents separate `GRADING_*` settings; export
them explicitly because the application does not auto-load `.env`.

Approved mode accepts `mode=approved_snapshot`, exact `exam_id`, `exam_revision`,
`student_id` and `answers`; reference data loads server-side from that revision.
**Current generated snapshots are not grading-ready:** their `criteria/sub_score`
rubrics lack authoritative rubric IDs and per-step skill mappings. They return
`GRADING_CONTEXT_NOT_READY` before inference once approval/membership checks pass.
The canonical `student_answer_attempt` table exists but is empty; historical
`test_questions` has no original free-text submission. Future database access is
an explicit repository interface, not a completed integration.

The older `src/ai/answer_grading.py` and `scripts/grading/run_demo.py` remain isolated;
their post-extraction semantics differ from this API. Legacy `requires_teacher` and
`teacher_comment` fields remain only for frozen output compatibility, with no teacher
grading workflow. See the [Vietnamese final design](docs/design/W08_AI_Grading_Design_Final.md)
and [precise handoff](docs/report/W08_AI_Grading_Handoff.md) for contracts, database audit,
verification evidence and remaining model limitations.
