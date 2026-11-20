# W08 AI grading integration handoff — 2026-11-20

Implemented only in `D:/HCMUS/TDTT/TH/Main_Project/MIRA/adaptive-learning`.
Owner: Phạm Yến Trân — AI & Algorithm Lead. No commit or push was performed.

## Delivered behavior

The existing FastAPI application now supports protected, durable asynchronous
grading jobs using the extracted frozen Qwen v11 engine. A separate `/grading`
page accepts/imports explicit experimental context, edits raw answers, submits
jobs, polls persisted progress, distinguishes certainty from processing completion,
reopens jobs and downloads compact business JSON. Existing generation and approval
remain available. One bounded local worker and an application-owned SQLite store
preserve raw submissions, context, results and provenance. There are no grading
points, result overrides, teacher work queues or mastery/profile writes.

Source revision: `R2026-11-17-scoped-skill-guidance-v11`; integration revision:
`W08-2026-11-20-v1`. Source hash and extracted-definition hashes are recorded in
`docs/notes/grading_source_manifest.json`. The standalone source was only read.

## Exact changed paths and reasons

All paths below are relative to this repository. “Added” files are untracked until
the owner reviews and stages them; no runtime artifacts belong in a commit.

| Path | Change | Reason |
|---|---|---|
| `.env.example` | Modified | Separate validated GRADING settings, queue/storage/debug documentation |
| `README.md` | Modified | Git Bash launch, API/job lifecycle, input modes, storage and limitations |
| `src/api/main.py` | Modified | Service injection, protected route mounting, shutdown cleanup and storage separation |
| `src/ui/__main__.py` | Modified | `--grading` entry while preserving launcher options |
| `src/ui/routes.py` | Modified | Mount the separate grading page alongside generation |
| `tests/integration/test_fake_api.py` | Modified | OpenAPI now has 11 paths; new submission route returns 202; all routes retain auth assertions |
| `src/grading/__init__.py` | Added | Dedicated grading package |
| `src/grading/engine.py` | Added | Frozen reusable prompts/schema/math/source/extraction/repair/stopping/formatter |
| `src/grading/qwen_client.py` | Added | Independent Ollama grading transport with injected offline transport |
| `src/grading/config.py` | Added | Validated grading-only model, limits and runtime paths |
| `src/grading/adapter.py` | Added | Experimental normalization, exact approved revision reads, future repository interfaces |
| `src/grading/schemas.py` | Added | Separate request, context, metadata and compact result contracts |
| `src/grading/service.py` | Added | Bounded worker, blank policy, per-question progress, whole-exam feedback |
| `src/grading/store.py` | Added | Transactional persistence/idempotency/admission/restart and local process lease |
| `src/grading/routes.py` | Added | Three protected job endpoints |
| `src/grading/cleanup.py` | Added | Retention of optional traces without deleting business records |
| `src/ui/grading_routes.py` | Added | Separate page and matching security headers |
| `src/ui/static/grading.html` | Added | Experimental and approved input forms; job/result display |
| `src/ui/static/grading.js` | Added | Safe rendering, import/edit/submit/poll/reopen/download and retry keys |
| `src/ui/static/grading.css` | Added | Responsive grading page styles |
| `src/ui/static/grading-example.json` | Added | Two clearly synthetic input questions, no gold/verdict labels |
| `tests/fixtures/grading_v11/README.md` | Added | Recorded response fixture provenance and inference isolation |
| `tests/fixtures/grading_v11/recorded_replays.json` | Added | Twenty recorded responses, request hashes and frozen compact expected outputs |
| `tests/grading/__init__.py` | Added | Integration test package |
| `tests/grading/test_engine.py` | Added | AST/payload/output equivalence, repair and provider safeguards |
| `tests/grading/test_integration.py` | Added | API/context/storage/lifecycle/DB-boundary and failure verification |
| `tests/grading/test_javascript.py` | Added | Runs the shipped JS workflow checks through pytest when Node is available |
| `tests/ui/grading.test.cjs` | Added | Twelve grading UI workflow and safe rendering checks |
| `tools/run_grading_smoke.py` | Added | Explicit live synthetic inference through API/worker and runtime evidence |
| `docs/design/W08_AI_Grading_Design_Final.md` | Added | Vietnamese first-person implementation report and authoritative grading workflow |
| `docs/notes/W08_Grading_Current_State.md` | Added | Integration changelog/current state, separate from engine revision |
| `docs/notes/grading_source_manifest.json` | Added | Verified frozen source/AST provenance |
| `docs/report/w08_grading_database_audit.json` | Added | Read-only schema/count audit without personal data |
| `docs/report/W08_AI_Grading_Handoff.md` | Added | This handoff, examples, evidence and suggested commit/PR text |

`requirements.txt`, `.github/workflows/ci.yml`, `.gitignore`, generation UI assets,
the old grading engine/tests/demo, canonical databases and other authors' design
documents are unchanged. Existing `/data/runtime/` and `/.pytest_tmp_mira/` ignores
already cover generated stores, locks, smoke evidence and debug traces.

An unrelated deletion of `docs/notes/W08_upgrade_qwen.md` appeared during work and
was left untouched. It is not a grading integration change and is not included in
the file inventory above. Do not include it accidentally when staging this work.

## Confirmed current data limitations

- Canonical bank: 121 draft questions and 121 answers, 9 skills, 18 templates.
  Question rubrics contain `{step, description}` without stable rubric IDs or
  per-step skills. Fifteen template rubrics use that shape; three are invalid JSON.
- Canonical memory: 20 students, 11 historical tests, 40 test_questions. The
  `student_answer_attempt` table exists with `test_id, question_id, answer,
  student_id` but has **zero rows**. Historical `test_questions` has no original
  essay text; its `AI` values are integer flags. Its newer PCM columns exist but
  are not used or updated by this integration.
- Existing runtime exams: 2 drafts, 3 revisions, none approved at audit time;
  generated rubric contract is `{criteria, sub_score}`. Even after approval, that
  rubric is insufficient for grading until authoritative IDs and step skills exist.
- Approved mode checks server-owned exact revision, approval, student association
  and membership, then returns actionable `GRADING_CONTEXT_NOT_READY` for missing
  context. A sufficiently structured snapshot adapter is tested with synthetic
  server data. A concrete canonical submission adapter is **not implemented**.
- Database audit records full table column names/counts and unchanged source hashes.
  No canonical table/schema was written and no historical correctness flag was
  repurposed as raw text.

Future Data/API work must provide immutable approved revision binding, exact
question membership, preserved raw text per question (including explicit blank),
stable submission/student IDs, reference answers/reasoning, rubric IDs/version and
authoritative per-step skill mappings. No migration is prescribed here.

## API examples

Use the existing workspace bearer token. An actual full experimental request is
`src/ui/static/grading-example.json`; it contains both authoritative experimental
context and separate raw answer records. Its IDs are synthetic. Example:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/grading/jobs \
  -H "Authorization: Bearer $API_TEACHER_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @src/ui/static/grading-example.json
```

POST durably records the request, returns HTTP 202 promptly, and responds with
an outer envelope. This excerpt illustrates the shape; runtime IDs/timestamps vary:

```json
{
  "metadata": {
    "job_id":"G_<uuid>",
    "state":"QUEUED",
    "experimental":true,
    "completed_questions":0,
    "total_questions":2,
    "definite_questions":0,
    "uncertain_questions":0
  },
  "result": {
    "test_id":"SYN_MANUAL_EXAM",
    "student_id":"SYN_MANUAL_STUDENT",
    "submissions":[],
    "feedback":null
  }
}
```

The full metadata also includes engine/integration revision, configuration, exact
exam revision, timestamps, processing times, per-question issues and model/repair
call counts. These fields do not enter compact business JSON. Identical retries
with the same idempotency key return the same stored job. Changed payload with
that key gives 409; change the key deliberately for a new run.

```bash
export JOB_ID='G_<actual returned job ID>'
curl -sS "http://127.0.0.1:8000/api/v1/grading/jobs/$JOB_ID" \
  -H "Authorization: Bearer $API_TEACHER_TOKEN"
curl -sS "http://127.0.0.1:8000/api/v1/grading/jobs/$JOB_ID/result" \
  -H "Authorization: Bearer $API_TEACHER_TOKEN"
```

GET result returns 409 until COMPLETED; GET job always exposes the persisted partial
results. COMPLETED may include UNCERTAIN. The UI downloads only the `result`
object. Incorrect questions keep `final_answer_correct: null` when the final answer
was not verified; CORRECT retains true. Legacy `requires_teacher` and
`teacher_comment` are compatibility fields without a teacher-handling feature.

An approved request supplies **no client reference data**:

```json
{
  "mode":"approved_snapshot",
  "idempotency_key":"approved-submission-001",
  "exam_id":"EX_example",
  "exam_revision":3,
  "student_id":"SYN_STUDENT",
  "answers":[{"question_id":"Q1","student_answer":""}]
}
```

Empty/whitespace strings with valid context mean explicit blank work:
INCORRECT, `Bài làm tự luận chưa đầy đủ.`, no wrong skill IDs and no model call.
Missing records, null text, duplicate/unknown questions and invalid context are
input errors. Typical context error after approval/membership validation:

```json
{
  "error": {
    "code":"GRADING_CONTEXT_NOT_READY",
    "message":"Snapshot chưa có grading context được hỗ trợ. Cần rubric [{id, description, skill_ids}], mapping kỹ năng từng tiêu chí và đáp án tham chiếu thuộc tập biểu thức được hỗ trợ; criteria/sub_score hoặc step/description không đủ. Dùng chế độ thử nghiệm với context tường minh.",
    "details":[]
  }
}
```

## Git Bash installation, launch, real example and stop

```bash
# From MIRA/adaptive-learning; Python 3.11+
python -m venv .venv
source .venv/Scripts/activate             # Linux/macOS: .venv/bin/activate
python -m pip install -r requirements.txt

# Separate terminal, only if Ollama is not already running:
ollama serve
ollama list
# If absent, explicitly install the required tag yourself:
# ollama pull qwen3:4b-q4_K_M

export GRADING_MODEL='qwen3:4b-q4_K_M'
export GRADING_TIMEOUT_SECONDS=120
export GRADING_NUM_PREDICT=1200
export GRADING_NUM_CTX=8192
export GRADING_MAX_REPAIRS=1
python -m src.ui --grading
```

The launcher opens `/grading` and passes a temporary token through the URL fragment.
Click **Nạp ví dụ tổng hợp**, edit raw answer text, then **Bắt đầu chấm bằng AI**.
Observe progress and the distinction between all questions processed and definite
verdicts. Download the compact result or reopen the job ID. Generation remains at
`/`. `--fake` controls generation only; nonblank grading still calls Qwen.

For a terminal-only real example, stop the UI server first if it owns the same
grading store, then run:

```bash
python tools/run_grading_smoke.py --live
```

For headless API use, export a secret token and share it only with the intended
workspace client, then run **one process**:

```bash
export API_TEACHER_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m src.ui --grading --no-browser
# Alternative:
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Stop the app using **Ctrl+C** in its terminal. Graceful shutdown marks unfinished
jobs INTERRUPTED and keeps committed results. After restart, first grading access
also interrupts unfinished old jobs; inference is never automatically resumed.
Completed results stay readable. Unfinished jobs require a deliberately new
idempotency key to run again. The same key continues to retrieve the interrupted job.
Environment variables must be exported; `.env` is not loaded automatically.

## Runtime storage and diagnostics

`data/runtime/grading.db` stores job state, original raw text, exact context,
operational metadata and compact results. `GRADING_DB` may select a separate
runtime path; canonical and exam-store collisions are rejected. Default capacity
is four queued/running jobs total, with one inference worker. A local process lease
at `grading.db.worker.lock` rejects competing processes using that same DB.

Optional `GRADING_DEBUG=true` writes full sensitive traces after compact results
are durable, under `data/runtime/grading_debug/G_<uuid>/<position>.json`.
`python -m src.grading.cleanup --older-than-days 7` deletes only old optional trace
files; original inputs/results are never cleanup targets. Debug storage failure
does not rewrite a student verdict. Routine logs and public errors omit raw text
and detailed exceptions. No runtime database/debug/smoke artifact should be staged.

## Verification actually performed

- Frozen engine: 20 recorded selected-v11 P/N replays match request payload hashes
  and exact compact outputs/feedback, covering correct, method/arithmetic errors,
  incomplete, valid alternate methods, invalid evidence and uncertainty. AST hashes
  match apart from explicitly normalized client/request injection. Extraction-only
  repair stays at 160 tokens and no test allows a third inference call.
- API/storage: auth, IDs/membership, provenance, exact server revision binding,
  insufficient context before inference, blank/missing, prompt return/progress,
  partial/full feedback, idempotency across restart, queue bounds/process lease,
  interrupted work/partial persistence, provider/internal failures, optional trace
  cleanup and canonical DB immutability are covered.
- UI: the shipped JS passed 12 Node DOM/fetch event-flow checks. The unchanged
  generation UI's 20 checks also ran through pytest. These are executed UI code
  checks, not a claim of browser layout certification.
- Full repository: **670 passed**, no skipped/failed tests, one existing Starlette
  deprecation warning, 107.90 seconds. The first regression attempt exposed the old
  OpenAPI eight-path count; it now checks eleven authenticated paths and the 202
  job response. Replay validation caught and corrected CRLF prompt whitespace
  before the successful run. No model-mismatch failure was hidden by changing a
  mock's intended failure mode.
- Actual CI inspected: `.github/workflows/ci.yml` installs existing requirements
  and runs `pytest -q` on Python 3.11/Ubuntu. No new dependencies or weakened CI.
  Local final commands used Python 3.13.13, a fresh dedicated Windows basetemp and Node on PATH. CI itself was inspected, not executed remotely.
- Supplemental Ruff checks pass for new integration/adapter/service/tests; frozen
  engine formatting is intentionally retained. `git diff --check` passes.

Reproduction commands:

```bash
python -m pytest -q --basetemp .pytest_tmp_mira/grading_final
node tests/ui/grading.test.cjs
node tests/ui/teacher_review.test.cjs
```

**Live Qwen was performed**, through the protected API and bounded worker, using
the exact installed `qwen3:4b-q4_K_M`. Synthetic job
`G_705b5e794cab49a2a83962644c7c5aa2` processed 2/2 questions, CORRECT / INCORRECT,
zero uncertain/provider failures. Per-question times were 32.513 s and 19.611 s;
command wall time was 52.666 s. Artifact:
`data/runtime/grading_smoke/G_705b5e794cab49a2a83962644c7c5aa2.json`.
This two-question smoke demonstrates connectivity/integration only; mock/replay
tests and the smoke are not new accuracy benchmarks.

Both canonical DB SHA-256 values match the initial read-only audit. The frozen
standalone source SHA-256 also remains unchanged. No original standalone file was
modified, and the old post-extraction grading demo remains isolated.

## Remaining limitations

Approved current generator snapshots lack authoritative rubric IDs and step skill
mapping. Canonical raw submissions are absent, and no concrete future submission
adapter or migration is implemented. The worker supports one local process/store,
not multi-host/distributed operation or automatic resume. Authentication remains
the existing shared teacher workspace gate, not individual identity or student auth.

Frozen semantics remain Qwen-dependent for natural-language mathematical reasoning,
earliest faulty action, alternatives, explanation fidelity and skill attribution.
The v11 notes preserve known wrong-action N07, invalid-evidence P07 and broad-span/
English-reason limitations. Python validates supported structure/source/arithmetic;
it does not independently prove arbitrary reasoning. Expression/unit support is
bounded, and source membership alone cannot prove a selected quote is the intended
final conclusion. Detailed model traces are persisted only when explicitly enabled.

## Suggested English commit message

```text
Integrate frozen Qwen grading with durable jobs and a separate grading UI
```

## Suggested PR description

### What

Integrate the frozen v11 Qwen grading engine into the existing FastAPI backend.
Explicit experimental multi-question context and raw student answers now produce
durable asynchronous jobs and compact results through a separate `/grading` page.

### Why

The current canonical datasets contain no original submitted answers and current
generated rubrics lack stable criterion IDs/per-step skills. Experimental inputs
allow real grading now while the exact approved-snapshot adapter rejects incomplete
authoritative context before inference. Existing generation/approval remains intact.

### Contribution area

- [x] Design
- [x] Implementation
- [x] Evaluation
- [x] Communication

### How tested / verified

20 recorded frozen-engine replays match request hashes and compact outputs; AST
equivalence protects extracted definitions. Full repository pytest: 670 passed,
no skips/failures, one pre-existing deprecation warning. UI workflow checks: 12
grading cases and 20 existing generation cases. Coverage includes auth, context/
revision binding, blank/missing answers, progress/feedback timing, idempotency,
persistence/restart, queue/process bounds, provider failures, diagnostics cleanup
and unchanged canonical database hashes. A real two-question Qwen smoke completed
through API + worker with CORRECT / INCORRECT results and no provider failures.

### AI use

- **Tool:** OpenAI Codex; local Qwen via Ollama at runtime.
- **What it produced:** Codex extracted/refactored the user-supplied frozen engine,
  implemented job/API/storage/UI integration and drafted tests/documentation. Qwen
  proposes source-grounded actions/judgments during grading.
- **What changed:** Separate transport/configuration, validated context boundaries,
  explicit blank policy, bounded durable worker, compact result envelope and UI.
  Frozen prompts, decisions, arithmetic/source checks and one-repair policy remain.
- **How verified:** Recorded-response and AST equivalence, full regression suite,
  actual JS event handlers, read-only DB audit and real integrated Qwen smoke.
  Neither Codex nor Python verification certifies arbitrary mathematical semantics.

### Limits for review

One local process/worker; current approved snapshots deliberately report context
not ready until Data/API provides authoritative rubric mappings. Future canonical
submissions remain an interface. Known frozen-model diagnosis limitations remain.
Legacy teacher-named result fields do not add teacher grading functionality.

### Definition of done

- [x] Implementation and relevant tests/documentation delivered
- [x] No canonical database changes, runtime artifacts or credentials included
- [x] Prompt/API/storage/UI contracts aligned with this integration
- [ ] Repository owner review and PR approval (not performed by this assistant)
