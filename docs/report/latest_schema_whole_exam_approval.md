# Latest SQL schema and whole-exam approval — 2026-10-30

Implementation is complete for the supplied snapshot. The canonical Question
Bank and student database were not modified. No commit, reset, push or merge was
performed. The existing personalized allocation and source matching policy were
preserved.

## Confirmed source and configuration

The exact requested path `pre-work/data/sample/questionbank.db` does **not** exist.
The user explicitly reconfirmed `pre-work/data/sample/dataset/question_bank.db`
for this update. That file is the backend default and matches the new uploaded
schema/counts. Its extracted sibling `dataset/dataa/question_bank.db` is byte
identical; it was inspected, but was not substituted into application configuration.
The app-local legacy sample database is not the new canonical source.

Question Bank SHA256 before/after:
`12871bbe1b7823d89bfdcc8873c77f73d279f51593d31cdbdcccb6b1b9ac9276`.

`M3_QUESTION_DB` still overrides the default explicitly. Relative values now
resolve from the application root, independently of the shell working directory.
Missing configured files cause an error, never an automatic switch or creation.
`M3_STUDENT_DB`, `PROFILE_SOURCE`, and `EXAM_BACKEND` retain their existing roles.
Preview and generation use the same configured adapter. Its file-version guard
rejects mixing cached Questions with a changed Template Bank (`409 SOURCE_CHANGED`).
After a Data Lead update, call `M3DataAdapter.reload_bank()` or restart the backend.
Reload clears catalogue/question/source caches and diagnostics; it writes nothing.

SQLite retrieval uses `mode=ro`, `PRAGMA query_only=ON`, and read transactions.
Template connections now also close explicitly.

## Current schema and invalid rows

The inspected schema has the columns specified in the implementation request,
including the exact misspelling `answers.explaination`. Current counts:

| Table | Rows |
|---|---:|
| questions | 121 |
| QuestionMainSkill | 114 |
| question_skills | 152 |
| answers | 120 |
| skills | 9 |
| question_templates | 18 |
| question_template_skills | 40 |

All 121 source statuses are `draft`. The pre-existing eligibility policy permits
essay Questions in grade 10 with source status `draft` or `active`, subject to
content, skill, difficulty, answer and solution checks. That policy is unchanged.
SQL source status is not generated-exam approval and is never updated by approval.

`QuestionMainSkill` is authoritative whenever the table exists. Exactly one main
mapping is required; its skill must be in the approved catalogue and among the
Question's complete `question_skills` links. An obsolete `questions.primary_skill_id`
column cannot override that relationship. A missing main mapping never triggers
sole-skill inference in the new schema. Secondary skills stay attached as metadata;
each selected Question credits exactly its one main skill.

For explicit legacy compatibility only, a database without `QuestionMainSkill`
retains its prior explicit-column/sole-skill migration, with a legacy-schema warning.
This branch does not override or weaken new-schema validation.

The new reader loads **113 valid Questions**, including **30 multi-skill Questions**.
The previous blanket exclusion caused by absent `questions.primary_skill_id` is
resolved. Rows are validated independently, so invalid data does not disable
unrelated valid sources. Diagnostics contain IDs and specific reason codes and
are included in Planner warnings:

| Current row(s) | Reasons for exclusion |
|---|---|
| QA0114 | Main skill is inconsistent with question_skills |
| QA0115 | Missing main-skill mapping and answer record |
| QA0116–QA0121 | Missing main-skill mappings and question_skills links |

There are no permanent ID exclusions. Missing/ambiguous main mappings, unknown
skills, missing/invalid answers or explanations, invalid difficulty, blank content,
and incomplete optional question parts are rejected by conditions. Verified part
content and its answer/solution are preserved. Malformed optional ProblemSpec
metadata also excludes that row rather than forcing it through validation.

Tests repair QA0114–QA0121 **only in an isolated synthetic copy**, using explicitly
synthetic statements, verified arithmetic, answers and mappings. All eight become
eligible after reload, proving that future Data Lead repairs need no code change.
The real outstanding records still require Data Lead correction; no skills or
answers were guessed for them.

## Template compatibility

Templates continue to use `question_template_skills`. One instance may credit one
of its verified linked skills while retaining every link as metadata. No main
skill or redundant SQL skill column is invented. Only exact compatible L1/L2
Template edges are allowed; L3/L4 use Questions. All sources are jointly reserved,
with existing uniqueness, safety, fallback warnings and quota diagnostics intact.

All 18 actual rule sets were inspected. The existing bounded AST instantiator
already supports the safely executable subset; extending it was unnecessary for
this snapshot. It computes answers/solutions independently of Qwen, samples within
resource bounds, checks constraints, and never evaluates arbitrary SQL code.

| Template | Level | Mathematical/parameter requirements | Current eligibility |
|---|---:|---|---|
| EA0001 | 1 | Sum of integer array; disjoint-group declaration | Executable |
| EA0002 | 1 | Sum of integer array whose length equals integer n | Executable |
| EA0003 | 1 | Integer product; groups declares array but supplies a string | Unsupported inconsistent parameter rule |
| EA0004 | 2 | Integer arithmetic; equivalent chained formulas n²−n and n(n−1); fixed condition | Executable |
| EA0005 | 3 | Digit-condition string arrays and constrained enumeration | Excluded by MVP level policy |
| EA0006 | 3 | Partial permutation/factorials, n≥k and no repetition | Excluded by MVP level policy |
| EA0007 | 2 | Nested symbol arrays, product of lengths, repetition/independence branches | Unsupported descriptive conditional rule |
| EA0008 | 2 | Distinct digit arrays, parity enum, leading-zero and length constraints | Unsupported descriptive enumeration |
| EA0009 | 2 | Divisibility, digit repetition boolean, leading-zero constraint | Unsupported descriptive enumeration |
| EA0010 | 2 | Bounded occupancy vectors and multinomial sum; empty-group boolean | Unsupported descriptive conditional sum |
| EA0011 | 2 | Piecewise factorials for alternating groups, including empty cases | Unsupported descriptive piecewise rule |
| EA0012 | 1 | C(n,2), exact division, fixed unordered-pair condition | Executable |
| EA0013 | 1 | C(team_count,2) × matches_per_pair; chained formula equality | Executable |
| EA0014 | 3 | Distinct digits, required adjacent digits, no leading zero | Excluded by MVP level policy |
| EA0015 | 1 | Ordered distinct vertex pairs n(n−1), fixed booleans/string | Executable |
| EA0016 | 3 | Distinct digit enumeration and forbidden-prefix subtraction | Excluded by MVP level policy |
| EA0017 | 1 | Factorial, distinct complete arrangement | Executable |
| EA0018 | 2 | Factorial subtraction n!−2(n−1)!; fixed restrictions | Executable |

The eight executable IDs are EA0001, EA0002, EA0004, EA0012, EA0013, EA0015,
EA0017 and EA0018. Unsupported Templates remain unavailable with reasons and
stored-Question fallback. No Template data was changed. Qwen remains wording-only;
stored Questions are immutable and cannot be regenerated.

## Whole-exam approval

The existing endpoint remains `POST /api/v1/exams/{exam_id}/approve`. Only
`expected_revision` is required. `notes` and `accepted_question_ids` are optional.
The latter now records actual optional individual acknowledgements; it may be a
subset or omitted. Unknown or duplicate IDs are rejected. Existing clients that
explicitly acknowledge every Question remain compatible.

Approval checks current revision, pending state, complete typed question/scoring
structure, mandatory automated validation and absence of `blocking_errors`.
The API also revalidates immutable stored content/answers/solutions and recomputes
Template parameters, answer, solution and source proof against the configured
bank before atomic compare-and-swap persistence. Production output marked
`not_evaluated` cannot be approved. The existing Demo backend remains labelled
`not_evaluated` and never claims Qwen semantic validation.

`needs_review` continues to carry editorial/source-label/rubric warnings; it is
not a replacement for Template mathematical validation. Generated mathematics
still passes the engine and source-proof checks. Failed generation never produces
a partial draft. A new optional `validation.blocking_errors` field distinguishes
blocking failures from advisory review notes, including on the UI.

Whole-exam approval writes its UTC teacher review record and increments revision.
It does **not** set every question's `teacher_approved` flag. Only IDs explicitly
acknowledged individually are marked; omitted IDs retain their actual state.
Approved exams may therefore have zero individually approved Questions. Older
approved snapshots with individual flags remain readable. A pending draft may
carry genuine optional individual acknowledgement, but no whole-exam review record.
Generation explicitly rejects attempts to self-approve or invent individual
acknowledgements, as well as incomplete/blocked automated output.

The UI enables **Duyệt toàn bộ đề** for a complete valid draft, with no checkbox
prerequisite. Optional individual checkboxes, answer/solution inspection, stale
revision protection and busy/error states remain. Question sources have no
regeneration button; the backend rejects them. Template regeneration retains its
validated new-instance workflow. A successful regeneration invalidates approval,
increments revision and returns a pending draft that can immediately be approved
again without individual clicks. Failure preserves the previous data and approval.

## Reproducible example and diagnostic coverage

Run from the application root with project dependencies installed:

```powershell
..\..\adaptive-learning\.venv\Scripts\python.exe -m eval.latest_schema_approval_audit
..\..\adaptive-learning\.venv\Scripts\python.exe -m pytest -q
ruff check src tests eval/latest_schema_approval_audit.py
```

The audit uses actual read-only SQL and a local mocked Qwen wording client.
Its application-owned draft DB is temporary. The report includes SQL schema,
all 18 Template rules and eligibility reasons, current invalid rows, source
availability, source provenance, full preview/draft/approval and unchanged hashes:
[audit JSON](../../eval/results/latest_schema_approval_2026-10-30.json).

ST011, N=10 produces **7 Questions + 3 Templates**, requested and achieved levels
**3/3/3/1**, pending revision **1**, and **0** individually reviewed Questions.
This request succeeds without per-question actions:

```json
{"expected_revision": 1}
```

The persisted result is **approved**, revision **2**, with a whole-exam review
timestamp and **0** individual flags changed. Retrieval after application restart
returns the identical approved object. Integration tests additionally cover failed
regeneration preserving revision 2; successful regeneration returning pending
revision 3; and reapproval without individual actions producing approved revision 4.

The nine-skill catalogue, 0–4 mastery thresholds, Focus/Review shares, relationship
priorities, Review cap, balanced weights, coordinated integer rounding and current
difficulty-first source matching are unchanged. Historical 5/2/3/0 regression
capacity is frozen as a synthetic fixture so new Data Lead coverage does not erase
that regression test. The 2026-10-29 SQL audit remains a historical snapshot.

Current eligible Question capacity totals L1/L2/L3/L4 = **39/45/17/12**.
The requested diagnostic matrix still lacks A004/L3, A005/L2, A007/L3 and A008/L4,
each by one. New main-skill mappings resolve the former A001/L2 and A001/L3 holes.
Skill substitutions remain explicit, and exam difficulty totals are exact.
A005 and A007 have no eligible main-skill Questions; A007 has an executable L2
Template link, which cannot fill its requested L3 slot. Full nine-skill diagnostic
coverage is therefore not claimed. No Planner redesign or fabricated source was
used to conceal these data/slot shortages.

## Changed files and validation

Application changes:

- `src/api/question_repository.py`: independent row validation and diagnostics.
- `src/api/m3_adapter.py`: new schema reader, explicit reload and source-version guard.
- `src/api/data_adapter.py`: diagnostic containers.
- `src/api/template_repository.py`: explicit closing and read transaction.
- `src/adaptation/planner.py`: carries SQL exclusion warnings.
- `src/api/schemas.py`: independent whole-exam approval, optional acknowledgements and blocking errors.
- `src/orchestration/review_service.py`: readiness guard and truthful individual flags.
- `src/api/main.py`: explicit path resolution, generation/approval validation gates.
- `src/ui/static/app.js`: immediate whole-exam approval and optional individual checks.

Tests and evidence:

- New `tests/unit/test_latest_sql_schema.py` and `tests/integration/test_whole_exam_approval.py`.
- Updated existing real API, structured API, exam review and historical diagnostic tests.
- Updated `tests/ui/teacher_review.test.cjs` and its Python runner.
- Added `eval/latest_schema_approval_audit.py` and generated JSON evidence.
- Updated README, ADR-004, ADR-005 and the older hybrid report's supersession note.
- This report records the current implementation; existing unrelated changes were preserved.

Validation: **590 pytest cases passed, 1 skipped, 0 failed**, in 34.49 seconds.
The skipped test is the shell Node wrapper; the same harness ran separately
through the available Node runtime and passed **14 UI scenarios**. Ruff and
`git diff --check` passed. The suite has a pre-existing Starlette/httpx deprecation
warning. All automated inference uses mocks; no live Qwen process is required.

Remaining Data Lead work is the eight currently invalid Question records and,
where desired, additional verified source coverage/Template semantics. The exact
`questionbank.db` spelling remains absent, but the application path is resolved by
the user's explicit confirmation of `dataset/question_bank.db`.
