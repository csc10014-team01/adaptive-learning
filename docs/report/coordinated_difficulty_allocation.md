# Coordinated adaptive difficulty allocation

Implemented on 2026-10-29 in `MVP1/adaptive-learning`. Existing uncommitted work
was retained. No canonical databases, mastery/evidence data, skill catalogue,
P3/P2/P1 relationship configuration, or teacher configuration controls were changed.

## Policy and architecture

Policy version: `mvp-personalization-v4-coordinated-difficulty`.
Mastery remains on 0–4, with reliable weakness below 2.0 and at least three
observations. Missing/zero evidence is NO_DATA; one or two observations is PARTIAL.

| Mastery | L1 | L2 | L3 | L4 |
|---|---:|---:|---:|---:|
| [0, 1.5) | 50 | 40 | 10 | 0 |
| [1.5, 2.0) | 35 | 45 | 20 | 0 |
| [2.0, 2.5) | 25 | 40 | 30 | 5 |
| [2.5, 3.0) | 20 | 35 | 35 | 10 |
| [3.0, 3.5) | 15 | 30 | 40 | 15 |
| [3.5, 4.0] | 10 | 25 | 45 | 20 |
| NO_DATA/PARTIAL | 25 | 35 | 30 | 10 |

Exclusive upper bounds and four-percentage validation are preserved. Focus,
Diagnostic/Maintenance, Advanced Review, fair skill coverage, maximum relationship
priority across two Focus skills, and the 50% Related Review cap are unchanged.

The pipeline remains Allocation → Selection → Expression → Qwen → Validation →
Assembly. Both Fake and Qwen call the same RuleBasedPlanner and QuestionSelector.
Neither generator rounds its own global default blueprint.

## Allocation algorithm

1. Classify skills, choose groups and allocate integer group/skill counts using
   the existing policy, before accessing questions.
2. Compute each fractional cell `ideal[s,l] = n[s] * weight[s,l] / 100` using
   exact rational arithmetic. Sum these to group and exam fractional targets.
3. Round exam targets by largest remainder, with stable L1 → L4 ties.
4. Solve a small integral min-cost flow: source → skill → group/level → exam/level
   → sink. Source capacities preserve every skill's integer count; sink capacities
   preserve the exam columns. Each skill belongs to exactly one policy group.
5. Convex marginal costs `2*k - 1 - 2*ideal` minimize squared group rounding error
   first, then squared individual-skill error. Integer scaling makes this objective
   hierarchy exact. This is coordinated constrained largest-remainder rounding:
   groups share exam columns rather than independently rounding their columns.
6. Zero-preference cells and explicitly forbidden levels have no allocation edges.
   WEAK skills explicitly forbid L4, independently of an eventual bank fallback.

The helper includes a nearest-feasible-column fallback for custom policies with
disconnected level supports. The approved policy's ordinary exam columns remain
exact. No minimum L4 count is introduced. All-insufficient-evidence profiles use
the same algorithm, whose aggregate target is the default diagnostic blueprint.

The shared flow helper uses deterministic Bellman-Ford shortest augmenting paths
and reverse residual edges. All capacities and flows are integers. It sends at
most ten units, adds no dependency, and can reconsider an earlier assignment.

## Actual before/after example

Synthetic student: A004 mastery 1.8/evidence 5; all eight other approved A-series
skills mastery 3.2/evidence 5; N=10. The approved relationship policy is enabled.

| Allocation | L1 | L2 | L3 | L4 | Total |
|---|---:|---:|---:|---:|---:|
| Before: Focus, previous policy + independent rounding | 1 | 2 | 1 | 0 | 4 |
| Before: Review, six single-question skills | 0 | 0 | 6 | 0 | 6 |
| Before: exam | 1 | 2 | 7 | 0 | 10 |
| After: Focus A004 | 1 | 2 | 1 | 0 | 4 |
| After: Related Review | 1 | 1 | 1 | 0 | 3 |
| After: Balanced Review | 0 | 1 | 1 | 1 | 3 |
| After: Review combined | 1 | 2 | 2 | 1 | 6 |
| After: exam | 2 | 4 | 3 | 1 | 10 |

Actual requested and achieved group quotas are both:
`{"focus": 4, "related_review": 3, "balanced_review": 3}`.
Requested and achieved skill quotas are both:
`{"A004": 4, "A002": 1, "A008": 1, "A003": 1, "A001": 1, "A005": 1, "A006": 1, "A007": 0, "A009": 0}`.
Requested/achieved per-skill difficulty cells also match exactly in the full synthetic bank.
The result contains no substitutions. It explicitly warns that ten available A004
L4 questions were excluded by the weak-skill safety policy.

The complete actual quota summary, selected source IDs, classifications,
per-question reasons, warnings, and reconstructed prior rounding are saved in
[`eval/results/coordinated_difficulty_example_2026-10-29.json`](../../eval/results/coordinated_difficulty_example_2026-10-29.json).
The before counts reconstruct the previous policy on the same skill quotas;
the after counts come directly from the current planner and selector.

## Selection and fallback

Automatic planned skill/level cells become slots in another integral assignment
network. Actual bank cells have capacity equal to their unique source questions.
Question sources are partitioned by their explicit primary skill and real
cognitive level. Secondary skills remain metadata; they never create extra quota
credit. The planner validates all source IDs, topic, grade and primary annotations
before handing the scoped bank to the selector.

Updated 2026-10-29: [diagnostic quota investigation](diagnostic_quota_investigation.md)
reproduced avoidable difficulty drift caused by the former changed-cell/skill-first
objective. The selector now globally minimizes changed difficulty slots, level
distance, changed target skills, upward changes, group changes, then recorded
history exposure. Hybrid selection additionally prefers exact linked L1/L2
Templates before Question fallback. Stable source order resolves remaining ties.
An available exact exam difficulty assignment always wins over preserving a skill
at a different difficulty. All sources are assigned jointly. Each question is
selected at most once. The existing cap on upward fallback (one level) is retained;
downward fallback is permitted. This deliberately can reject an L4-only bank even
for achieved skills when foundational slots cannot safely be filled.

Weak-primary L4 sources are excluded before matching, including legacy internal
standard/locked requests. Related Review capacity is hard. The matcher enumerates
the small possible Related counts and caps Focus at `N - 2*k` for each Related
cap `k`. This guarantees Related ≤ Balanced after substitutions, even if the
achieved Review total shrinks, while choosing the globally cheapest valid flow.
No full feasible flow
means `409 INSUFFICIENT_QUESTION_BANK`, without a partial exam or model invocation.
Every substituted slot reports its requested cell, actual cell and source ID.
The planner additionally reports group, skill and exam-level quota deviations and
retains both requested and achieved matrices.

Legacy internal global-lock requests use a separate flow formulation preserving
their exact columns while minimizing group and skill quota deviations. This keeps
old stored integrations usable without exposing manual difficulty to teachers.
HTTP endpoints continue rejecting nonadaptive modes and manual percentages; the
UI already shows planned/achieved difficulty totals as read-only information.

`personalized` now reflects reliable profile information in the selected questions,
including achieved-skill maintenance and Advanced Review. It does not require
Focus questions. A completely diagnostic result remains unpersonalized.

## Safe expressions

Difficulty allocation does not depend on presentation type. The default expression
planner prioritizes direct wording for WEAK and insufficient-evidence skills.
Across ACHIEVED questions, it alternates direct/indirect opportunities only if the
selected source has a verified ProblemSpec with an authored compatible indirect
presentation in the original context. It never changes source cognitive level,
parameters, constraints, operation semantics, answers or solutions. Explicit
internal presentation/context configurations retain their behavior.

Unstructured sources remain direct/preserve-source even for an achieved skill.
Structured sources with no compatible indirect presentation also remain direct.
Regeneration preserves the stored presentation, context and source level. Existing
ExpressionSpec, prompt and mathematical validators enforce the safety boundary.
No unstructured prose is promoted to verified equivalent mathematics.

## Validation and remaining limits

- Baseline: **461 passed, 1 skipped**, using the existing sibling `.venv`.
- Final: **494 passed, 1 skipped**; no live model inference. The skip is the pytest
  wrapper for JavaScript UI tests because `node` is absent from shell PATH.
- The available Node REPL separately ran the actual shipped CommonJS UI harness:
  **10 passed**, including automatic planning, approval and regeneration flows.
- Added aggregate single-slot rounding, exact one-WEAK example, profile sweeps
  across N=1…10, small-instance exhaustive optimization oracles, safe scarce-bank
  matching and achieved Related Review share checks, allocation contract checks,
  small Advanced Review exams without L4,
  legacy/verified expression boundaries, API/Fake/Qwen consistency, and verified
  simple indirect generation/regeneration tests. Old policy assertions were updated.
- Ruff passes on all implementation/test files changed by this task. Full
  `ruff check src tests` still reports **14 pre-existing findings** in
  `src/ai/qwen_client.py`, `tests/integration/test_exam_review.py`,
  `tests/integration/test_skill_relationship_policy_api.py`, and
  `tests/integration/test_structured_exam_api.py` (unused imports, pytest fixture
  redefinition warnings and existing semicolon-separated statements).
- `git diff --check` passes. Existing tests verify canonical SQL hashes are
  unchanged. No commits, merges, pushes or database migrations were performed.
- The repository's canonical legacy SQL catalogue still has seven skills; its
  optional nine-skill relationship policy correctly rejects that mismatch rather
  than inventing A008/A009 data. Nine-skill coverage uses the approved existing
  configuration and synthetic fixtures. An approved nine-skill bank is needed
  for production use of that configuration.
- Production indirect expressions require author-verified mathematical metadata
  and compatible presentations. Existing synthetic examples demonstrate the
  capability; the implementation does not infer missing metadata from legacy text.

## Exact files modified or added by this task

Implementation:

- `src/adaptation/policy.py`
- `src/adaptation/planner.py`
- `src/adaptation/contracts.py`
- `src/adaptation/question_selector.py`
- `src/adaptation/difficulty_allocator.py` (new)
- `src/adaptation/min_cost_flow.py` (new)
- `src/ai/expression_planner.py`
- `src/orchestration/exam_service.py`

Tests:

- `tests/unit/test_planner.py`
- `tests/unit/test_automatic_difficulty.py`
- `tests/unit/test_mastery_2of4_policy.py`
- `tests/unit/test_coordinated_difficulty.py` (new)
- `tests/unit/test_structured_problems.py`
- `tests/integration/test_automatic_difficulty_api.py`
- `tests/integration/test_planner_api.py`
- `tests/integration/test_real_api.py`
- `tests/integration/test_sample_profiles.py`

Review artifacts:

- `docs/report/coordinated_difficulty_allocation.md` (this report, new)
- `eval/results/coordinated_difficulty_example_2026-10-29.json` (new)

Other pre-existing working-tree changes were left intact. API request/response,
prompt/AI contracts, Fake generation, teacher UI and SQL adapters were inspected
and exercised by tests; their existing behavior already met the relevant task
requirements and did not require additional edits here.
