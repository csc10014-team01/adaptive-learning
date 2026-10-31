# Official A001–A009 skill relationship policy

The official MVP catalogue is **A001–A009**. The Data Lead owns the separate
SQL migration. This update changes relationship configuration and its tests;
it does not migrate databases, annotate questions, or change student mastery.

`skill_relationships_a001_a009.json` is the authoritative relationship policy,
version `a001-a009-relationships-v1`. It replaces the former SK-series nine-skill
matrix. `tests/fixtures/nine_skill_relationships.json` is a test snapshot of this
file; a unit test requires exact JSON equality to prevent configuration drift.
It contains the same official policy, not a second independently maintained one.

## Final catalogue and directional relationships

| Focus | Official Vietnamese name | P3 (3) | P2 (2) | P1 (1) |
| --- | --- | --- | --- | --- |
| A001 | Quy tắc cộng | A005, A008 | A002 | A007, A009 |
| A002 | Quy tắc nhân | A005, A008 | A001 | A003, A004, A006, A007, A009 |
| A003 | Hoán vị | A002, A008 | A004, A006 | A007, A009 |
| A004 | Tổ hợp | A002, A008 | A003, A006 | A007, A009 |
| A005 | Sơ đồ cây | A001, A002 | A009 | A007 |
| A006 | Chỉnh hợp | A002, A008 | A003, A004 | A007, A009 |
| A007 | Kết hợp | A003, A004, A006 | A001, A002, A005 | A008, A009 |
| A008 | Kỹ năng tính toán | — | — | A001, A002, A003, A004, A006 |
| A009 | Đếm có điều kiện ràng buộc | A001, A002, A005 | A003, A004, A006 | A007 |

A007 combines counting techniques (permutation, arrangement and combination).
A008 includes calculation and expression simplification. A009 covers counting
with conditions and constraints. The former SK-series meanings are not mapped
onto these IDs. These are configurable educational priorities, not statistical
correlations or mandatory prerequisite edges.

P3 means direct foundational support; P2 means conceptual comparison or
methodological support; P1 means related application/extension. Omitted edges are
P0. Each skill has exactly one row; all targets are known skills, priorities are
strict integers 1–3 and self-edges are forbidden. Edges are directional; for
example A004→A008 is P3 while A008→A004 is P1.

The unchanged `SkillRelationships.rank_review_skills()` uses the maximum
priority against either Focus, then ascending skill ID. It never sums priorities.
This relationship update preserves Focus quotas, evidence thresholds, mastery
bands, primary-skill selection and the Related Review cap. The subsequent
[automatic difficulty update](../docs/report/automatic_difficulty_fix.md) removes
teacher difficulty locks from public endpoints and controls difficulty fallback.
No production Python module required modification for the relationship update itself.

## Load through the existing mechanism

For the confirmed nine-skill Data Lead database, run from this repository:

```powershell
$env:SKILL_RELATIONSHIPS_FILE = (Resolve-Path '.\config\skill_relationships_a001_a009.json').Path
# Configure these to the Data Lead's approved database files if not at defaults:
# $env:M3_QUESTION_DB = 'path/to/approved/question_bank.db'
# $env:M3_STUDENT_DB = 'path/to/approved/student_profiles.db'
python -m src.ui
```

Use your installed virtual-environment Python in place of `python` as needed.
The application reads process environment variables; it does not automatically
load `.env`. Restart an existing server after changing configuration.

The existing `create_app()` loads this file once using `SkillRelationships.load`.
Both `/api/v1/exams/plan` and the Qwen `/api/v1/exams/generate` pipeline receive
the policy through the existing `RuleBasedPlanner` integration. A valid plan
reports the `+a001-a009-relationships-v1` suffix in `policy_version`. Allocation
still precedes question selection. No new loading system, public API field or
fallback catalogue has been added.

The existing catalogue-ID equality guard remains in force. If the policy and
active question-bank catalogue differ, planning/generation returns
`500 DATA_SOURCE_ERROR` with `Relationship policy does not match the data
catalogue`, before Qwen inference or draft storage. Invalid JSON, missing rows,
unknown references and invalid priorities fail at the existing Pydantic loader.

## SQL integration status

Update 2026-10-29: the user confirmed
`../../pre-work/data/sample/dataset/question_bank.db` relative to this application
as the authoritative source. It contains A001–A009, 111 questions, 18 templates
and 40 explicit `question_template_skills` links. The application now defaults
to that database, with `M3_QUESTION_DB` retained as an override. The approved
relationship JSON above is unchanged and can be enabled against this catalogue.
Existing student profiles still contain only A001–A007; absent A008/A009 evidence
remains NO_DATA. No database or mastery values were migrated by the application.
See the [hybrid generation report](../docs/report/hybrid_exam_generation.md).

The inspection below records the historical seven-skill source from 2026-10-27;
that legacy database remains unchanged and is no longer the default bank.

Read-only inspection on 2026-10-27 found the checked-out default databases still
contain the previous seven-skill data:

- `data/sample/dataset/question_bank.db`: skills table contains A001–A007;
  there are no A008/A009 catalogue rows. A005 is still named `Sơ đồ hình cây`,
  whereas the finalized name is `Sơ đồ cây`. Adapter-eligible question links
  currently use A001–A006, with 53 primary-annotated questions available.
- `data/sample/memory/student_profiles_sample.db`: existing mastery rows use
  A001–A007. No A008/A009 scores or evidence are supplied by this change.
- `M3_QUESTION_DB`, `M3_STUDENT_DB` and `SKILL_RELATIONSHIPS_FILE` were unset in
  the inspected process environment; therefore default source paths apply.

This is an outstanding Data Lead dependency, not a change to the official target
catalogue. The current UI was not reconfigured against incompatible data. No
seven-skill compatibility branch, seven-to-nine mapping or synthetic production
mastery was added. The generic adapter continues to return source IDs and names
unchanged. The updated catalogue must also come with approved question metadata
and appropriate profile inputs; this policy does not fabricate bank coverage.

## Tests and scope

`tests/unit/test_skill_relationship_policy.py` checks the full approved matrix,
all omitted P0 edges, strict schema failures, directional priorities, rankings,
one/two Focus quotas, deterministic selection and input immutability.
`tests/unit/test_modular_pipeline.py` now uses A-series policy cases, preserving
its original quota, teacher-level, retry and complete-pipeline assertions. Its
maximum-versus-sum example now distinguishes the two algorithms: with Focus
A001/A003, candidates A002/A005/A008 all have max P3 but different sums; the
result must follow ascending IDs.

`tests/integration/test_skill_relationship_policy_api.py` uses an explicitly
synthetic nine-skill SQLite catalogue with exact approved names and in-memory
question/profile fixtures. It checks environment-based policy loading, both
existing endpoints, hard teacher quotas, primary-source references, persistence
and unchanged inputs without live Ollama. Separate checks use the actual
seven-skill databases only to verify the existing mismatch error and unchanged
baseline behavior. These are tests of the existing generic guard, not new legacy
compatibility logic. Canonical database hashes must remain unchanged.

Focused verification: **71 passed**, with the existing Starlette/httpx warning.
The baseline before this policy update was **320 passed, 1 skipped**. The skipped
test is the optional Node executable bridge, unrelated to relationships. The
repository has no configured Ruff checks or Ruff configuration; none was added.

Final verification: **354 passed, 1 skipped, 1 existing warning in 16.62s**.
All 320 pre-update passing tests remain passing; 34 focused policy/API cases
were added. The optional Node bridge remains the sole skip. `git diff --check`
found no whitespace errors. SHA-256 comparison of all 41 source files and both
canonical database files found **no changes** during this policy update.

Files changed for this update are limited to this directory, the existing
nine-skill fixture and modular tests, the two new policy test modules, and the
relevant README / ADR-004 / `.env.example` configuration documentation. Earlier
MVP edits elsewhere in the working tree are preserved. No commit, push, merge,
SQL mutation, Qwen implementation change or teacher-review change is performed.
