# Automatic profile-driven difficulty: audit and implementation

Date: 2026-10-27. Scope: exam allocation, selection, Demo assembly and teacher
creation/preview controls only. The official A001–A009 policy is unchanged. Data
Lead SQL migration remains separate. All nine-skill examples below are synthetic.

Policy amendment 2026-10-28: classification now uses WEAK <2.0/4 and the six-band
difficulty table in [the finalized mastery policy](mastery_2of4_policy.md).
The original audit/test results below describe the automatic-planning update.

## Baseline and causes

Before edits, `git status` showed the earlier MVP and relationship-policy work;
those edits were retained. Baseline: **354 passed, 1 optional Node bridge skipped**,
one pre-existing Starlette/httpx warning. Tests use the installed environment:

```powershell
& '../../adaptive-learning/.venv/Scripts/python.exe' -m pytest -q
```

The UI let teachers force `standard` and manual percentages. Both public endpoints
accepted these overrides. The planner's standard mode intentionally ignored
mastery. Separately, FakeExamGenerator called `question_slots()` and selected
source questions by global default percentages, bypassing the preview planner.
Thus Demo could display a different skill/difficulty/source plan from preview.

Automatic planning already used mastery bands for reliable skills, but rounded
default percentages independently for every insufficiently assessed skill. Nine
one-question skills could all round to L2. Selection ranked primary skill ahead
of difficulty and had no hard L4 guard for the very-weak band; an unavailable
easy cell could be replaced by a much harder question.

## Allocation policy

Classification remains evidence-based: 0 → NO_DATA, 1–2 → PARTIAL; with at least
3 evidence, mastery <2.0/4 → WEAK and mastery ≥2.0/4 → ACHIEVED. A reliable mastery of
zero is WEAK. There is no percentage-of-missing-skills threshold.

The existing Focus/Review algorithm is preserved: one weak skill gets 40% Focus;
the weakest two get 60%; no weak skill yields diagnostic, mixed
diagnostic/maintenance, or advanced review according to existing policy.
Relationship priority still uses max P3/P2/P1, stable IDs and the Related Review
cap. Relationships never set difficulty. Neither profiles nor evidence is updated.

After allocating skill counts, reliable skills use their own configured mastery
band; NO_DATA/PARTIAL skills use `PlannerPolicyConfig.default_levels`. These
per-skill integer allocations are combined for a personalized/mixed exam.
One reliable skill is sufficient to prevent a whole-exam default override.

Only when every scoped skill is NO_DATA/PARTIAL does the planner first round the
exam-wide default, then distribute those integer levels across allocated skill
slots deterministically. Largest remainder retains L1→L4 ties: 10 questions with
25/35/30/10 yield **3/3/3/1**, rather than rounding many single-slot skills to L2.
Each skill's row total and the exam total remain exact.

## Public API boundary and stored compatibility

Both `/api/v1/exams/plan` and `/api/v1/exams/generate` use the same
`automatic_exam_request` dependency. Mode omission defaults to adaptive.
`standard` and `default_blueprint`, and every non-null manual
`difficulty_distribution`, return **422 REQUEST_VALIDATION_ERROR** with the
corresponding body field. Overrides are rejected, never silently ignored.
OpenAPI advertises adaptive and null-only deprecated difficulty input.

For compatibility, the underlying `GenerateExamRequest` can still parse old
internal mode/quota values. Existing generic direct planner tests of hard
quotas remain meaningful, but these values cannot reach a teacher creation route.
`question_slots` is retained only for those legacy internal constraints; neither
Demo, Qwen exam generation nor automatic API output validation recomputes an
automatic exam from it. Old stored standard drafts remain readable, approvable
and individually regeneratable; new standard drafts cannot be created over HTTP.
No second request schema or second planning algorithm was introduced.

## Controlled selection fallback

Automatic selection first excludes source L4 questions whose primary skill's
configured mastery band assigns zero to L4. Both finalized WEAK bands have zero
L4 preference, so a reliably WEAK skill's
L4 source cannot re-enter through another skill's fallback slot.

Within remaining candidates, prefer the target primary skill and exact difficulty,
then nearer levels; at equal distance prefer the easier level. Automatic slots
permit at most one level upward. Easier levels remain possible when the bank is
scarce. This bounded upward fallback is explicit policy for this MVP, not a claim
that all soft difficulty quotas are hard constraints. Large upward jumps are
rejected even when a different skill has an advanced source.

Capacity lookahead reserves suitable remaining levels and respects the existing
Related Review cap so an early choice cannot consume the only suitable easy
question needed by a later slot. No source cognitive label is changed. Missing
cells can still change soft skill/group/level totals; every substitution and final
deviation is reported. Infeasible safe capacity produces
`409 INSUFFICIENT_QUESTION_BANK`, never a fabricated problem or partial draft.
There is no exam-wide mandatory advanced-question minimum.

## Demo and Qwen consistency

FakeExamGenerator now calls RuleBasedPlanner and assembles exactly the source IDs
from the finalized plan. It includes target skills and `planner_summary`. Its
title/review notes identify Demo/Fixture output, provenance stays fake/model=null,
and validation stays not_evaluated. It presents existing content without inference.
The application injects the same configured relationship policy into Demo and
Qwen planners.

Qwen ExamService already generates from the finalized plan and was left unchanged.
Qwen transport, expression planning, mathematical validation, teacher review and
persistence implementations are unchanged by this task. API output checks compare
achieved planner levels with actual selected metadata instead of default weights.

## Files and verification responsibilities

| File(s) | Change / verification |
| --- | --- |
| `src/adaptation/planner.py` | Coherent all-insufficient-evidence diagnostic rounding; existing personalized bands and Focus algorithm retained |
| `src/adaptation/question_selector.py` | Per-primary L4 safety, bounded upward fallback, nearer/easier ranking and remaining-capacity checks |
| `src/api/schemas.py` | Adaptive request default and accurate deprecated/null-only HTTP schema; old internal/stored values remain parseable |
| `src/api/main.py` | Shared public request restriction, Demo relationship injection and achieved-level output checks |
| `src/api/services.py` | Demo reuses the actual planner; source assembly/provenance preserved |
| `src/ui/static/index.html`, `app.js` | Removed mode, lock and percentage inputs; adaptive-only requests; read-only plan preview and existing review actions retained |
| `eval/smoke_exam_generation.py` | Optional manual smoke entry now requests adaptive, matching the public workflow; no new live-model CI dependency |
| `tests/unit/test_automatic_difficulty.py` | Scenarios A–G, integer rounding at N=1/2/3/5/9/10, mastery zero, independent bands, safe shortages, nearest fallback, capacity reservation and immutable inputs |
| `tests/integration/test_automatic_difficulty_api.py` | Scenarios A–F through preview and both backends, rejection of manual overrides on both routes, null/omitted input, and old stored-draft review/regeneration |
| Existing planner/fake/real/review/policy/UI integration tests | Migrated HTTP fixtures to automatic mode; assertions that relied on teacher percentages now check rejection or actual achieved plan, preserving access, failures, provenance, review, source integrity and persistence checks |
| `tests/ui/teacher_review.test.cjs`, its pytest bridge | Actual app.js request tests added; ten executable creation/review scenarios with mocked HTTP; Node bridge remains optional |
| README, demo-fixture README, ADR-003 note, policy README | Removed stale instructions for manual/default/Demo behavior and linked this report |

The old safe-fallback unit case now supplies L3 instead of L4 to test a valid
one-level substitution from L2. Separate tests assert that the former large
upward substitution fails. A mutating generator's invalid profile is now caught
earlier by the shared planner with INVALID_PROFILE_DATA rather than only at the
output gate. Test intents remain preserved; changed business rules were not
worked around by changing canonical questions or profiles.

Intermediate verification: the new scenario/API tests and relevant API boundary
checks passed (**72 tests**). The first full run had one OpenAPI assertion issue:
FastAPI drops a JSON-schema `const: null` during schema serialization. The public
schema now uses `enum: [null]` instead, and both its assertion and old-draft
workflow test pass. Runtime rejection was already working.

## Final verification

- Full suite: **407 passed, 1 skipped, 1 existing warning in 36.72s**. There are
  53 new scenario/API cases in addition to the 354 baseline cases. Existing tests
  were updated only where their teacher overrides or independent Demo behavior
  conflict with the revised requirements.
- Actual `app.js` in the available Node runtime: **10 scenarios passed**, including
  no manual controls, automatic preview/generation request bodies, approval,
  individual regeneration, conflict refresh, failed-generation preservation,
  busy controls and safe answer rendering. The pytest Node subprocess bridge
  skips because Node is absent from PATH; it was independently exercised here.
- SHA-256 comparison confirms both canonical M3 databases remain unchanged.
  Of the source tree, only the seven runtime files listed above changed during
  this task. Qwen, expression planning, mathematical validators, orchestration,
  review and persistence source files match the pre-update versions.
- `git diff --check` reports no whitespace errors. The repository has no
  configured Ruff checks or Ruff configuration; none was introduced.
- No commit, push, merge, SQL migration, question annotation or operational
  profile/mastery/evidence update was performed. No new legacy-catalogue branch
  was introduced; the existing catalogue guard still applies while Data Lead
  supplies the approved nine-skill SQL data.

Browser screenshot/layout QA and new live inference were not performed for this
policy update. Automated Qwen tests use transport doubles. A previously running
server must be restarted and the page reloaded to load the new backend and UI.
