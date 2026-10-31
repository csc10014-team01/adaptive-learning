# MIRA missing student mastery — 2026-10-31

The current rule is **no evidence → API null mastery, 0 evidence → UI `--/4` →
Planner NO_DATA**. The earlier proposed neutral display `2.0/4` does not apply.
Positive evidence must retain its authoritative SQLite score, including 0.0.
Positive evidence with a null/missing score is an integrity error, never NO_DATA.

## Actual cause of fabricated-looking data

There are two different student databases with the same basename:

| Source | Stored mastery rows | Role |
| --- | ---: | --- |
| `pre-work/data/sample/memory/student_profiles_sample.db` | 11 | Data Lead source, now the application default |
| `MVP1/adaptive-learning/data/sample/memory/student_profiles_sample.db` | 140 | Historical offline seeded testing copy, formerly the application default |

The 140 rows match `data/sample/memory/profile_scenarios.json` **exactly**, across
all student IDs, skills, scores and evidence counts. That manifest explicitly says
`fixture_kind=synthetic_planner_testing` and states that the snapshots are not
derived from retained assessment history. `seed_sample_profiles.py` is an explicit
offline writer, and the existing USAGE document already describes the data as
synthetic. It is not called by the runtime profile reader.

Therefore the previous diverse/personalized-looking values came from reading an
already-seeded SQL copy, not from randomization during API requests. The default
source was wrong for the requirement to use Data Lead assessment data. No runtime
`2.0` missing-score filler was found. The old schema required a numeric score,
forwarded zero-evidence placeholders, and returned only stored skill rows, leaving
A008/A009 absent instead of exposing explicit nullable response states.

Concrete source differences:

| Student/skill | Former seeded default | Data Lead value now preserved |
| --- | --- | --- |
| ST001 / A001 | 1.1, 8 evidence | 2.3, 1 evidence |
| ST004 / A005 | 3.4, 5 evidence | **0.0, 1 evidence** |
| ST011 / A004 | 0.0, 0 evidence | **3.0, 1 evidence** |
| ST012 | Seeded assessed scenario | No stored skill assessments; nine null/0 response entries |

ST011 must not be treated as entirely unassessed merely because the old seeded
fixture says so: its actual A004 evidence remains PARTIAL. ST012–ST020 currently
have no assessment rows and correctly have nine NO_DATA classifications.

## Implementation

- `SkillMastery.mastery_score` is nullable. Zero evidence normalizes an existing
  numeric placeholder to null in the response model only. Positive evidence with
  null/missing mastery fails validation without changing the count.
- `M3DataAdapter` validates the raw rows before completing the response catalogue.
  Missing skill rows become null/0 entries in the **response only**. Unknown,
  duplicate or malformed source rows are not silently dropped. SQLite is opened
  with `mode=ro`, `query_only=ON` and a read transaction; there are no INSERT/UPDATE
  operations in this path.
- The default student source now points to the Data Lead file in `pre-work`.
  `M3_STUDENT_DB` is still an explicit override; relative paths resolve from the
  application root, consistently with Question Bank paths. Missing/unreadable/
  corrupt SQL returns `INVALID_PROFILE_DATA`; no Fake/Demo or seeded-copy fallback
  is used. A nonexistent student returns `STUDENT_NOT_FOUND`.
- Planner classification remains evidence-first. Missing/zero evidence is NO_DATA;
  1–2 evidence is PARTIAL; sufficient evidence uses the unchanged WEAK/ACHIEVED
  threshold and difficulty bands. A defensive null-score guard rejects invalid
  positive-evidence profiles even when model validation was bypassed.
- The UI's shared formatter returns exactly `--/4` for absent/zero-evidence skills.
  Measured zero displays `0.00 / 4`; finite measured values retain the existing
  two-decimal display. Positive-evidence/null-score responses are rejected before
  setting an active UI profile. The formatter never uses a falsey check that would
  discard a legitimate measured zero.

The nine-skill definitions, mastery scale 0–4, Focus/Review ratios and difficulty
allocation policies are unchanged. No Question/Template generation implementation,
source selection, Qwen prompt or postponed six-layer Validator was modified.

## Current authoritative-source audit

Reproduce without writing any source database:

```powershell
python -m eval.missing_mastery_audit --output eval/results/missing_mastery_2026-10-31.json
```

The recorded audit shows:

- 20 students, 9 catalogue skills, 180 response skill entries.
- 11 stored assessed skill rows, all with 1 evidence; all 11 scores and counts
  preserved exactly from Data Lead SQLite.
- 169 missing pairs projected as null mastery / 0 evidence / NO_DATA.
- 11 PARTIAL and 169 NO_DATA skill classifications; no invented WEAK/ACHIEVED.
- All 20 current profiles select `diagnostic_review` because none has sufficient
  assessment evidence for personalized mastery bands. This follows the existing
  policy and does not change the policy to force a strategy.
- ST012–ST020 are fully unassessed. N=10 diagnostic planning keeps the existing
  requested difficulty distribution 3/3/3/1.

Before/after hashes match for all three files:

| File | SHA256 |
| --- | --- |
| Data Lead student SQL | `894861fe34ab1ec2ba097a1572c6957dd6b1f200be598f76192645a983f978f4` |
| Data Lead Question Bank | `12871bbe1b7823d89bfdcc8873c77f73d279f51593d31cdbdcccb6b1b9ac9276` |
| Historical app-local seeded copy | `beadded2b39db5c7e3962f272bd1139003361a4d2376abfe2babdce7eac9dede` |

No source records were inserted, normalized in place, randomized or overwritten.
Synthetic measurements used by tests exist only in isolated temporary databases
or explicitly selected historical fixture paths.

## Regression coverage and results

`tests/integration/test_missing_mastery.py` covers missing rows, zero-evidence
scores (null/0/2/4), genuine measured zero, mixed profiles, strict positive-null
integrity errors, live SQL updates, inaccessible/corrupt/missing-table SQL without
fallback, nonexistent students, nullable OpenAPI schema, exact Data Lead values,
source selection and relative-path configuration. The Planner tests cover default
diagnostic allocation and unchanged focus/difficulty behavior for real evidence.

`tests/fixtures/missing_mastery_profile.json` is a shared API/UI contract fixture:
the Python test compares an actual SQLite-backed API response against it, then
the JavaScript harness renders that same response through the shipped app.js.
It verifies `--/4`, 0 evidence, valid `0.00 / 4`, preserved measured precision, and
rejection of a positive-evidence/null response. Existing teacher review workflows
remain covered in the same harness.

- Full suite: **706 passed, 0 failed, 1 skipped**, 31.29 seconds.
- **18 JavaScript UI scenarios passed separately** through the available Node
  runtime, including the four new profile scenarios. The full-suite skip is the
  shell-Node wrapper because Node is not on the shell PATH; the UI tests themselves
  were executed successfully.
- Ruff and `git diff --check`: passed; existing Windows line-ending notices and a
  pre-existing Starlette/httpx deprecation warning remain.

Historical seeded-scenario tests now explicitly select their seeded SQL fixture.
Historical diagnostic quota tests likewise select the frozen scenario explicitly.
An existing regeneration test now selects a Template by source kind instead of
assuming the first question is a Template after the student source changes.
Those compatibility updates do not change Question/Template generation behavior.

## Files changed in this correction

- Production: `src/api/schemas.py`, `src/api/m3_adapter.py`, `src/api/main.py`,
  `src/adaptation/planner.py` (null guard only), `src/ui/static/app.js`.
- New tests/fixture: `tests/integration/test_missing_mastery.py`,
  `tests/fixtures/missing_mastery_profile.json`.
- Compatibility/UI tests: `tests/integration/test_real_api.py`,
  `tests/integration/test_sample_profiles.py`, `tests/integration/test_fake_api.py`,
  `tests/integration/test_experimental_indirect_api.py` (explicit synthetic partial
  score for its in-memory fixture), `tests/integration/test_exam_review.py`,
  `tests/unit/test_diagnostic_quotas.py`, `tests/ui/teacher_review.test.cjs`,
  `tests/integration/test_teacher_review_javascript.py`.
- Audit: `eval/missing_mastery_audit.py`,
  `eval/results/missing_mastery_2026-10-31.json`.
- Documentation/config: `.env.example`, `README.md`,
  `data/sample/memory/USAGE.md`, this report.

Unrelated pre-existing modifications were preserved. No commit was made. Restart
the backend to switch an already-running process away from its old configured
student source; `M3_STUDENT_DB` must not point to the seeded testing copy when the
intended source is Data Lead assessment data.
