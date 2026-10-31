# Final mastery policy: WEAK below 2.0 on the 0–4 scale

Date: 2026-10-28. Repository: `MVP1/adaptive-learning`, on the existing feature
branch. The independently cloned `pre-work` directory was not edited. Existing
uncommitted MVP, relationship and automatic-difficulty changes were preserved.

## Audit and minimal production change

Baseline before edits: **407 passed, 1 optional Node bridge skipped**, one
pre-existing Starlette/httpx warning. The current source already had automatic-only
teacher UI/API restrictions, shared Demo/Qwen planning, coherent whole-exam
diagnostic rounding, per-skill mastery weights and an automatic-selector L4 guard.
Those implementations were inspected and retained.

The remaining discrepancy was in `src/adaptation/policy.py`: mastery_target was
3.0 and the 1.5–2.0 weak band was not distinguished from the 2.0–2.5 band. This
file contains the policy configuration change:

- `version = "mvp-personalization-v3-mastery-2of4"`.
- `mastery_target = 2.0`, preserving `min_evidence = 3`.
- Insert exclusive upper bound 2.0 with weights 30/45/25/0, keeping the remaining
  approved bands and validation intact.

Final source review also found that an internal legacy locked quota could skip
the existing zero-L4 guard. `src/adaptation/question_selector.py` now applies
that guard unconditionally before feasibility checks; a quota cannot override
the safety policy. No planner/selector rewrite, API/UI change, Qwen change or
allocation contract, skill mapping or relationship matrix change was needed.

## Classification and difficulty

| Condition | Classification |
| --- | --- |
| Evidence = 0 | NO_DATA |
| Evidence = 1–2 | PARTIAL |
| Evidence ≥3 and mastery <2.0 | WEAK |
| Evidence ≥3 and mastery ≥2.0 | ACHIEVED |

Mastery remains in **[0,4]**. Zero with reliable evidence is a weak score, not
missing data. At 1.99 a reliable skill is WEAK; at exactly 2.00 it is ACHIEVED.

| Mastery /4 | Recognition | Understanding | Application | Advanced Application |
| --- | ---: | ---: | ---: | ---: |
| [0.0,1.5) | 50 | 35 | 15 | 0 |
| [1.5,2.0) | 30 | 45 | 25 | 0 |
| [2.0,2.5) | 25 | 45 | 25 | 5 |
| [2.5,3.0) | 10 | 30 | 45 | 15 |
| [3.0,3.5) | 5 | 20 | 50 | 25 |
| [3.5,4.0] | 0 | 10 | 50 | 40 |

The exclusive-upper-bound lookup still includes 4.0 in the final band. Existing
configuration validation still requires four nonnegative percentages totaling
100%. Tests also reject NaN, infinity, wrong sums and wrong-length distributions.
These weights are percentages, separate from the 0–4 mastery scale.

For NO_DATA/PARTIAL skills the default preferences remain 25/35/30/10 within
their assigned quotas. The complete default diagnostic blueprint is used only
when no relevant skill has sufficient evidence; missing rows are NO_DATA. With
any reliable skill, the planner retains Focus/Review, Diagnostic/Maintenance or
Advanced Review and uses each selected skill's own band. A single reliable
2.0 skill produces maintenance allocation, not a whole-exam default override.

Focus shares remain 40% for one weak skill and 60% for the two weakest. The
directional A001–A009 P3/P2/P1 matrix, maximum priority against two Focus skills,
deterministic ties and Related Review cap are unchanged.

## Weak-skill source safety and generation

Both sufficiently assessed WEAK bands now assign zero L4. The existing automatic
selector excludes L4 sources by the source's **primary skill's allocation weights**
before capacity checks and fallback ranking. It does not infer weakness from
question IDs, and an unsafe source cannot re-enter by filling another slot.
The same exclusion applies to legacy internal locked quotas; infeasible manual
constraints cannot force a zero-L4 primary into an advanced source.
Suitable other skills or nearby levels may be substituted with warnings;
inadequate safe capacity returns INSUFFICIENT_QUESTION_BANK. Cognitive labels are
never rewritten. Strong skills can still supply L4 questions: there is no global
advanced ban and no mandatory global advanced quota.

Teacher creation/preview accepts only adaptive, with omitted/null manual
difficulty input. Non-null manual percentages and obsolete standard modes still
return 422. Old stored drafts remain readable and reviewable. Internal legacy
mode/quota parsing remains the previously documented compatibility boundary;
it is not exposed as a teacher override.

Both Demo and Qwen continue to generate from the actual ExamPlan. Tests compare
their source IDs, primary targets, cognitive levels, quota summaries and policy
versions at the new classification boundary. Qwen is mocked for automated tests.

## Actual SQL and catalogue inspection

The inspected process settings `PROFILE_SOURCE`, `M3_STUDENT_DB`,
`M3_QUESTION_DB` and `SKILL_RELATIONSHIPS_FILE` were unset. The default Qwen backend
uses M3, with read-only access to:

- `data/sample/memory/student_profiles_sample.db`.
- `data/sample/dataset/question_bank.db`.

The actual student_skill_mastery DDL has
`CHECK (mastery_score >= 0.0 AND mastery_score <= 4.0)` and
`CHECK (evidence_count >= 0)`. There are **140 rows**, stored mastery min/max
**0.0/4.0**, and evidence min/max **0/18**. `SkillMastery` already enforces finite
0–4 values in Pydantic; the M3 adapter reads stored values directly. No score was
multiplied by 2.5, rescaled, seeded, or migrated.

Both checked-out databases still use **A001–A007**; A008/A009 are absent. The
question-bank catalogue still names A005 `Sơ đồ hình cây`; the finalized target
name is `Sơ đồ cây`. This is a separate Data Lead dependency. The official target
remains A001–A009, demonstrated by synthetic nine-skill tests and the unchanged
approved relationship configuration. No additional legacy compatibility logic
or automatic catalogue mapping was introduced.

The source sample manifest retains its historical <3 scenario descriptions and
expected_strategy strings. Neither it nor the database was modified to satisfy
tests. Under the new policy ST005 and ST012 are Advanced Review; ST003 has one
weak skill. SQL integration assertions and the sample usage guide reflect these
new outcomes using the original scores/evidence.

## Changed files and verification

| File | Reason |
| --- | --- |
| `src/adaptation/policy.py` | Threshold 2.0, new weak band and policy version |
| `src/adaptation/question_selector.py` | Existing zero-L4 exclusion also applies to internal locked quotas |
| `tests/unit/test_planner.py` | Exact classification and difficulty boundary cases; synthetic third weak skill kept below 2.0 |
| `tests/unit/test_mastery_2of4_policy.py` (new) | Policy identity, invalid percentages/scores, insufficient-evidence high scores, reliable 2.0 maintenance, different reliable profiles, weak L4 exclusion with strong-skill L4 fallback and legacy-lock safety |
| `tests/unit/test_automatic_difficulty.py` | Distinct weak bands below 2.0 and scarce-bank checks at 1.50/1.99 |
| `tests/unit/test_modular_pipeline.py`, `test_skill_relationship_policy.py` | Existing two-Focus synthetic cases now use two scores below the new boundary; original caps/tie/level assertions retained |
| `tests/integration/test_skill_relationship_policy_api.py` | Same adjustment for the synthetic policy-loading API case |
| `tests/integration/test_automatic_difficulty_api.py` | New end-to-end boundary assertions through preview and both generation modes |
| `tests/integration/test_sample_profiles.py` | New expected strategies for ST005/ST012 without altering source snapshots |
| README, sample USAGE guide, prior automatic-difficulty report | Correct current threshold, example students and policy references |

The existing scarcity/Related Review-cap test retains its exact selected-source
assertion. Its artificial unassessed skill weights now use the actual diagnostic
default rather than zero L4, so the test still isolates capacity/cap behavior.
Separate new tests cover the formerly bypassable locked zero-L4 constraint.

Initial updated full suite: **419 passed, 1 skipped**. Focused mastery, planner,
automatic/API and real sample-profile checks after the additional coverage:
**189 passed**. Relevant frontend check: **10 actual-app.js scenarios passed**
in the available Node runtime, with mocked HTTP. This is a logic/API check,
not screenshot QA. The ordinary pytest Node bridge skips when Node is absent
from PATH. No Ruff configuration or configured Ruff commands exist in this repo.

## Final verification

- **461 passed, 1 skipped, 1 existing warning in 38.74s**. There are 54 additional
  classification, band, input-domain, safety and API cases relative to the 407-case
  passing baseline; existing scenarios were retained and updated for the new rules.
- The final legacy-quota safety change separately passed **129 focused tests**.
- **10 frontend scenarios passed** against actual app.js in the Node runtime.
  The optional pytest Node executable bridge is the sole skip because Node is
  absent from PATH. No live Ollama dependency was added.
- SHA-256 comparison across **48 source/data/configuration files** found only
  `src/adaptation/policy.py` and `src/adaptation/question_selector.py` changed.
  Both M3 databases, all sampled JSON question/profile data, the authoritative
  relationship matrix and its fixture snapshot are byte-for-byte unchanged.
- `git diff --check` has no whitespace errors. The repository has no configured
  Ruff checks or Ruff configuration. The unrelated `pre-work` clone remains
  clean at commit `2761f74`.
- No commit, push, merge or SQL migration was performed. A previously running
  server needs a restart before it uses the new policy version.
