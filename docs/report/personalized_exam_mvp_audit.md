# Personalized exam MVP: repository audit and implementation plan

Audit date: 2026-10-27. Working repository: `MVP1/adaptive-learning`, which
matches the supplied module tree; the sibling `adaptive-learning` is an older
skeleton. No AGENTS.md files were found. The existing formatting edit in
`tests/fixtures/nine_skill_relationships.json` belongs to the user and is retained.

Baseline: **258 passed**, one existing Starlette/httpx deprecation warning.
The PATH Python lacks pytest. Tests use the already installed environment:
`../../adaptive-learning/.venv/Scripts/python.exe -m pytest -q`.

| Module / owner | Existing implementation | Missing work | Files to modify | Tests |
| --- | --- | --- | --- | --- |
| Planner / AI | Correct per-skill evidence states, weakest-two focus, half-up rounding, diagnostic/advanced review, mastery bands, teacher locks | No algorithm discrepancy found; retain implementation | No planner changes planned | `test_planner.py`, `test_planner_api.py` |
| Selection / AI | Allocation precedes selection; unique primary-annotated sources, scoped grade/topic, deterministic fallback, capacity errors and related cap | Preserve existing behavior and coverage | No selector changes planned | `test_planner.py`, `test_modular_pipeline.py` |
| Relationships / AI | Typed explicit directed priorities, maximum across focus skills, catalogue mismatch rejection | Document fixture versus production support | Documentation only | Nine-skill modular tests |
| Expression / AI; contracts shared | Direct/preserve-source only; no inferred mathematics | Optional verified ProblemSpec, authored compatible contexts and direct/indirect presentations | New `src/ai/problem_spec.py`; `contracts.py`, `expression_planner.py`; optional source field in `api/data_adapter.py` | New synthetic structured fixture and unit tests |
| Qwen / AI; orchestration Backend | One HTTP call per generate_one, centralized bounded retry, shared deadline and explicit errors | Carry presentation requirements to the prompt without answers or student data | `ai/prompts.py`, `ai/qwen_client.py`, `orchestration/question_generation.py` | Structured prompt, retries, existing HTTP-double tests |
| Validation / AI | Exact JSON shape, length, numeric facts, fail/needs_review | Explicit constraint guards, deterministic combinatorics answer checks, exact authored presentation acceptance; uncertain paraphrases remain needs_review | `validation/math_validator.py`, `question_validator.py` | New structured and legacy constraint cases |
| Assembly / Backend | Count/order, source refs, source answers, scoring, pending status; schema rejects duplicate source IDs | Independently check blueprint/source/quota consistency, accepted content, near duplicates; retain all reference solution steps | `orchestration/exam_assembler.py`, `exam_service.py` | New assembly boundary tests, existing API tests |
| Review and persistence / Backend | Approval, single-question regeneration, revisions, CAS, snapshots, source digest, failure preserves draft | Preserve these and detect regenerated duplicate statements | `orchestration/exam_service.py`; source fingerprint compatibility for optional metadata | Existing `test_exam_review.py`, new failure cases |
| Teacher UI / Backend | Generation, plan, retrieval, answers, status and JSON download | Per-question acceptance/regeneration, refresh, approval, stale-revision recovery | `ui/static/app.js`, small `style.css` additions | Existing teacher UI tests plus executable UI workflow tests |
| Data / Backend | M3 read-only, profiles read-only, separate draft database | Optional authored ProblemSpec input, no migrations or guessed annotations | `api/data_adapter.py`, optional read in `m3_adapter.py` | Adapter compatibility and unchanged source fingerprints |

## Incremental implementation

1. **Planning and selection:** run existing planner/relationship tests unchanged.
   Seven M3 skills remain seven; nine-skill tests use matching synthetic banks.
   No mapping or student mastery is invented.
2. **Structured inputs:** create a Pydantic contract for bounded combinatorics
   parameters, explicit order/replacement constraints, verified answer/solution,
   verification reference, and author-approved statement templates per context
   and presentation. An optional source field preserves legacy behavior. Reject
   unverified/inconsistent metadata and incompatible context requests. Synthetic
   fixtures explicitly identify themselves. No existing M3 data is transformed.
3. **Generation and validation:** pass the expression contract through the same
   single-attempt transport; keep JSON `{question}` and retry ownership intact.
   Check numeric facts against the chosen authored presentation, known condition
   changes, and independently computed supported answers. Only an exact approved
   presentation with consistent mathematics can pass; open paraphrases retain
   needs_review. Neither answer nor solution enters the model prompt.
4. **Assembly and review:** check final blueprint integrity without repeating
   mathematical validation. Reject duplicate source identities and flag duplicate wording,
   preserve source answers/solutions and source digest behavior. Connect existing
   API mutations to the existing UI, with explicit acceptance of every question,
   expected_revision, full response refresh, and conflict reload controls.
5. **Integration and documentation:** run the complete suite; add mocked complete
   structured generation/review tests. Check local Ollama availability and run a
   separately reported smoke test only if the configured model exists. Document
   supported operations, trust boundary and remaining data limitations.

All source owners above are identified before edits. Changes crossing AI/Backend
boundaries are limited to the optional contract and its pipeline integration.
Public routes, request fields, cognitive values and old stored drafts remain
compatible. Source databases are never written. Out-of-scope grading, submissions,
mastery updates, dashboards and student delivery remain excluded.

## Phase results

| Phase | Changed files / result | Verification | Regressions / remaining work |
| --- | --- | --- | --- |
| 1: audit | This report; reviewed required ADRs, design, source modules, API schemas, UI, fixtures and sample sources | Baseline 258 passed | No baseline failures; PATH Python lacks pytest |
| 2: planning/selection | No algorithm changes; retained catalogue compatibility rules and user fixture edit | 99 planner, modular and plan-API tests passed | No regressions; approved nine-skill operational data remains external |
| 3: structured problems | `ai/problem_spec.py`, `ai/contracts.py`, `expression_planner.py`, optional source adapter fields; new synthetic fixture and unit tests | Structured + modular tests: 57 passed (includes phase 4 checks) | No M3 mutation; existing prose sources remain direct |
| 4: generation/validation | `prompts.py`, `qwen_client.py`, `question_generation.py`, both validators | Full intermediate suite: 293 passed; constraint/JSON/answer failures and retry checks pass | No baseline regressions; arbitrary semantic equivalence cannot be proven |
| 5: assembly/review | `exam_assembler.py`, `exam_service.py`, `source_snapshot.py`, additive context ID in `schemas.py`, UI JS/CSS; new boundary/API/JS tests | 84 focused tests passed before final refinements; eight actual-app.js workflow scenarios passed | One newly written test initially expected the later teacher-lock error while its setup triggered an earlier integrity error; corrected its setup to test the intended quota condition. No existing test changed |
| 6: integration/docs | New ADR-005, README updates, optional live smoke CLI and captured output | Live local Qwen: all three smoke paths succeeded in 7.04s; final pytest result recorded below | Python's Node bridge skips when node is absent from PATH; JS suite was separately executed in the available Node runtime |

Final behavior and limits are documented in
[ADR-005](../decisions/ADR-005-verified-problems-and-teacher-ui.md). No dependency,
architecture, grading or profile-write changes were introduced. Textual duplicate
detection is a human-review warning; source-ID uniqueness is enforced. Production
structured data and an approved nine-skill data catalogue are not supplied by this
implementation. Existing M3 source annotations and scoring rubrics still require
teacher review. Browser layout/screenshot QA was not performed.

## Final verification

- Complete pytest suite: **320 passed, 1 skipped, 1 existing warning in 49.73s**.
  All 258 baseline tests remain passing and their files are unchanged. The skip
  is the optional Node subprocess bridge because Node is absent from PATH.
- Actual `app.js` executed in the available Node runtime: **8 workflow scenarios
  passed**, covering complete acceptance, approval payload/auth, single-question
  regeneration, preserved unrelated content, failed regeneration, stale revision
  and refresh, busy controls, demo/approved states, and safe answer rendering.
- Live local `qwen3:1.7b`: **3 successful smoke paths**; full M3 draft generation
  and synthetic context/direct and indirect generation. Captured JSON is in
  `eval/results/personalized_exam_smoke_2026-10-27.json`. An initial Windows
  console encoding issue in the smoke CLI was corrected to UTF-8 before the
  successful captured run.
- `git diff --check`: clean. Canonical M3 database timestamps remain unchanged;
  adapter tests additionally verify the canonical bank hash is unchanged.
- Work is on `feature/personalized-exam-mvp`. No source files outside this
  repository or unrelated user edits were changed.
