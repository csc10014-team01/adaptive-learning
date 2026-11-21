# Rule-based exam planner MVP

The planner implements the supplied `Exam_Planner_Implementation_Prompt_MVP.md`.
It reads profiles and selects existing source questions without grading, writing
mastery/evidence, generating mathematics, or calling a model.

## Five stages

1. `RuleBasedPlanner._validate` checks profile identity, skill membership, question
   identities, metadata, grade, topic, and primary links. Malformed source records
   produce `500 DATA_SOURCE_ERROR`; malformed profiles produce
   `500 INVALID_PROFILE_DATA` through the existing error envelope.
2. `classify` uses each skill's evidence independently. Missing scoped profile
   rows are `NO_DATA`; evidence 1–2 is `PARTIAL`; evidence ≥3 allows comparison
   with mastery 3.0. Wrong-answer history does not override this classification.
3. `_allocate` chooses Focused Practice, Diagnostic Review, Advanced Review, or
   Standard. Group shares use half-up rounding, skills use stable round-robin,
   and cognitive weights use largest remainder with L1→L4 ties. All thresholds,
   group shares, and mastery weights live in `PlannerPolicyConfig`.
4. `_select` first checks overall distinct capacity and, when locked, capacity
   at every teacher level. Every selected question consumes one primary-skill
   slot. It prefers the desired primary, group coverage, level, available-history
   novelty, and stable source ID. Missing cells permit safe substitutions and
   explicit warnings. No question can be selected twice.
5. `plan` returns `ExamPlan` with classifications, selection reasons, requested
   and achieved group/skill/level quotas, per-skill level counts, and warnings.
   `/api/v1/exams/plan` previews without generation or draft storage. The existing
   Qwen generator carries targets and a typed `planner_summary` into the teacher
   draft. API output checks enforce explicit teacher levels before storage.

## Compatible contracts

- Existing `adaptive` and `default_blueprint` modes remain accepted. `standard`
  is an additive alias for `default_blueprint`.
- Existing difficulty percentages remain percentages, converted to integer
  global quotas by largest remainder. A non-null `difficulty_distribution` is
  an explicit hard constraint, even when equal to the configured default.
  Omission or null means no teacher lock and survives serialization unchanged.
  Standard then uses the global configured 25/35/30/10 default. Adaptive uses
  per-skill mastery preferences (the same default for insufficient evidence).
- `priority_skills`, `target_count`, `achieved_target_count`, `targeted`, and
  `personalized` retain their focus-related meaning. Diagnostic and Advanced
  strategies are identified by `strategy`, including when `personalized=false`.
- `ExamQuestion.target_skill_id` and `ExamResponse.planner_summary` are optional
  additions so old stored drafts and replacement generators remain readable.
  Planned questions always have a primary target and complete `skill_ids`.
  When supplied in a generated draft, target, complete skill list, cognitive
  level, grade, and topic are checked against the source record.
- The fake assembler retains its existing contract-testing behavior. It does
  not run the adaptive planner. Use `/exams/plan` to inspect planning with either
  backend, or the real generator to assemble a planned draft.

## Primary-skill data dependency

`questions.json` and the canonical SQLite `questions` table originally had no
`primary_skill_id`. The six sole-skill demo rows now explicitly name that sole
skill. Legacy sole-skill input is normalized to its sole skill in memory at the
adapter boundary. This is a documented compatibility migration; it never writes
the canonical database.

No primary is inferred for a multi-skill row. Such legacy rows remain readable
for compatibility but are excluded from the planning pool, with the source ID
and missing field in warnings. If exclusions make a full exam infeasible, the
API returns `409 INSUFFICIENT_QUESTION_BANK` with capacity and exclusion details,
never a partial exam. Invalid supplied primaries, duplicate IDs/skills, and
invalid cognitive levels are validation errors rather than fallback candidates.

At implementation time, the M3 reader exposes 84 source questions: 53 sole-skill
questions can be planned, while 31 multi-skill rows need author annotations.
The eligible level counts are L1=29, L2=15, L3=7, L4=2. `DEMO_Q07` and `DEMO_Q08`
also need author annotations; consequently the demo planner has no eligible L4
sources. Its legacy fake assembler can still assemble the original demo rows.

Data authors can supply `primary_skill_id` in JSON records or in an optional
SQLite `questions.primary_skill_id` column. `M3DataAdapter` reads that column when
present. The value must be one of that question's linked skill IDs. The planner
does not choose annotations or alter either canonical database.

## Limits and verification

- Scope remains the existing grade-10 combinatorics catalogue (seven canonical
  skills), the existing maximum of ten questions, and four API cognitive labels:
  `recognition`, `understanding`, `application`, `advanced_application`.
- M3 numeric difficulty still uses the pre-existing application annotation
  mapping (1→L1, 2→L2, 3→L3, 4/5→L4); it is not teacher-approved cognition data.
- History contains only `wrong_questions`, so novelty means no recorded exposure
  in that available subset. There is no complete attempt history or reliable
  source-variety metadata. Missing history never creates evidence.
- Selection is deterministic without randomness or a seed API. Soft quotas use
  a greedy coverage heuristic, with scarce skills considered first under teacher
  locks. Soft quotas can deviate; hard constraints are checked before selection.
  This is not a global optimizer for every soft preference.
- Scores and solutions in generation use the existing assembler; no grading,
  learning updates, or semantic/model correctness claims were added.

Run from `adaptive-learning`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

`tests/unit/test_planner.py` covers classification, policy boundaries, allocations,
primary semantics, validation, feasibility, fallbacks, and determinism.
`tests/integration/test_planner_api.py` covers API strategy previews, teacher
constraints, errors, additive schema fields, and metadata propagation with a
local generator double. `tests/integration/test_real_api.py` exercises the M3
reader, local HTTP provider double, draft persistence, and provider failures.
No tests require an actual Qwen model.

Verified on 2026-10-25: **205 passed, 0 failed in 21.41 seconds**. The sole
warning is the existing Starlette/httpx TestClient deprecation. The baseline
before this upgrade was 126 passing tests. Earlier failures from the obsolete
one-/two-evidence targeting policy were updated to the specified ≥3 threshold.

| Test file | Final result |
| --- | --- |
| `tests/unit/test_planner.py` | 62 passed |
| `tests/unit/test_smoke.py` | 1 passed |
| `tests/integration/test_planner_api.py` | 15 passed |
| `tests/integration/test_real_api.py` | 25 passed |
| `tests/integration/test_fake_api.py` | 102 passed (unchanged by this upgrade) |

Files touched for this upgrade (other pre-existing working-tree edits retained):

- `src/adaptation/planner.py`, `src/adaptation/policy.py`
- `src/api/data_adapter.py`, `src/api/m3_adapter.py`, `src/api/schemas.py`
- `src/api/services.py`, `src/api/main.py`, `src/api/real_generator.py`
- `data/sample/api_demo/questions.json`, `data/sample/api_demo/README.md`
- `tests/unit/test_planner.py`, `tests/integration/test_planner_api.py`,
  `tests/integration/test_real_api.py`
- `docs/decisions/ADR-003-rule-based-planner-mvp.md`, `docs/examples/exam_plans.json`

Complete example JSON for weak-skill, mixed missing-data, and all-achieved
students is in [`../examples/exam_plans.json`](../examples/exam_plans.json).
These are actual deterministic planner outputs from the synthetic bank helpers
in `tests/unit/test_planner.py`; IDs refer to that test bank, not M3 records.
