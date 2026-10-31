# Safe Template Direct/Indirect presentation — 2026-10-30

> Historical verified-only implementation report. The newer product decision
> enables an explicitly experimental local-Qwen pathway without author-approved
> patterns. See [experimental_indirect.md](experimental_indirect.md) for current
> local activation, relaxed checks and semantic limitations. The verified-only
> mechanism and its strict pattern matching remain available.

## Outcome and approval boundary

The Template pipeline now supports verified Direct/Indirect presentations through
ExpressionPlanner, presentation-aware local Qwen prompts, deterministic wording
checks, durable presentation provenance, and regeneration that prefers another
verified presentation. Question Bank items remain immutable. RuleBasedPlanner,
mastery 0–4, nine-skill catalogue, allocation and source priorities are unchanged.
L1/L2 remain Template-first; L3/L4 remain Question-only.

**Production Indirect coverage is ZERO.** The current SQL has 18 Templates and no
author-approved presentation metadata. The repository's existing Indirect
ProblemSpec is explicitly a synthetic C(8,3) test example, not approval of any SQL
Template or its parameter domain. Its contexts cannot be transferred to SQL
merely because a formula looks similar. No synthetic approval is loaded by the
application. No mathematical or educational verification has been fabricated.

Eight inactive Indirect proposals in `config/template_presentations.json` are
provided for human review of the currently executable Template families:

| Templates | Runtime status | Work still required |
| --- | --- | --- |
| EA0001, EA0002 | SQL Direct only | Review proposed disjoint-choice/list contexts, array and zero-count cases, cognitive level |
| EA0004 | SQL Direct only | Review proposal's excluded partner condition, full parameter domain, cognitive level |
| EA0012, EA0013 | SQL Direct only | Review unordered pairs / multiplicity, contextual interpretation and cognitive level |
| EA0015 | SQL Direct only | Review ordered vertex pairs, no self-pair, no collapsing equal geometric vectors, cognitive level |
| EA0017, EA0018 | SQL Direct only | Review all objects/distinctness/row ordering, small and zero parameters where allowed, forbidden adjacency, cognitive level |
| EA0003 | Existing instantiation exclusion | Repair/approve inconsistent array declaration upstream; then verify a presentation |
| EA0007–EA0011 | Existing instantiation exclusion | Descriptive/nested parameter or counting semantics remain unsupported; then verify a presentation |
| EA0005, EA0006, EA0014, EA0016 | Question fallback at these L3 slots | Templates remain prohibited at L3 in MVP1; no source-policy expansion |

Thus **none of EA0001–EA0018 has a usable verified Indirect variant**. Supported
families retain the existing SQL Direct path, not an unverified contextual rewrite.
Unsupported families retain their existing eligible Question fallback.

## Why Indirect was blocked

The former Template ExpressionSpec contract required `direct`, ExamService never
selected a presentation, prompts hardcoded Direct, and both wording validation
and source validation required retaining the original Direct statement.
Regeneration changed parameters and invoked Qwen but prohibited generate_type
changes. Temperature 0 was not the cause of these structural restrictions.

## Configuration contract

The versioned file contains a `presentations` array. Each entry records:

- Template ID and presentation ID; `generate_type` (`direct` or `indirect`).
- Complete Vietnamese `pattern`, plain `required_placeholders`, permitted context,
  mathematical invariants and required result.
- `source_digest`: fingerprint of the complete original Template definition,
  including parameter/answer/solution rules, difficulty and skill/scope metadata.
- Reviewed `cognitive_level`, independent of presentation type.
- `verification_status`: `proposed` or `verified`; mathematical review reference,
  `cognitive_level_preserved`, and cognitive review reference.

`verified` requires both references and an explicit true cognitive-preservation
declaration. Runtime eligibility additionally requires exact Template identity,
source fingerprint, matching reviewed cognitive level and complete source
placeholders. Invalid/duplicate configurations fail closed; proposed or stale
variants are ineligible. A configured missing/malformed file reports
`PRESENTATION_CONFIG_ERROR`, not a hidden replacement registry.

The built-in `sql_direct` / `sql-direct-v1` presentation preserves the original SQL
statement and existing computation. Its fingerprint binds to that SQL definition;
it does not claim a new author-approved contextual rewrite. Every Template has
this safe default. Persisted legacy Direct drafts without the new metadata remain
readable and are rechecked against the SQL statement. Indirect without provenance
is rejected.

The application re-reads the configuration for source-integrity checks. A removed,
revoked, changed or re-versioned selected presentation fails approval/regeneration;
the stored exam and revision are not overwritten. Changes to unrelated proposals
do not invalidate an unchanged selected presentation at the same version.

## Selection, prompting and minimal validation

`ExpressionPlanner.plan_template_expression()` explicitly selects presentation
after parameter generation and answer/solution computation. Initial generation
alternates Direct/Indirect across slots whose Templates have verified Indirect
options, starting Direct. Templates with no Indirect do not consume the alternation
index. Additional same-type variants rotate deterministically per Template/type.
There is no cognitive-level or mastery gate: L1 can use Indirect, L2 can use Direct,
and NO_DATA/PARTIAL can receive Indirect. This MVP uses a balanced policy for all
statuses; no optional ACHIEVED weighting was added.

Prompts carry the actual generate_type and resolved approved pattern. Indirect
prompts specify only the permitted context and mathematical requirements, without
requiring the old Direct sentence. Both types forbid new parameters, restrictions,
counting rules, answers and solutions. The prompt receives no authoritative answer,
answer_rule, solution_rule, student identity or approval references. Local Qwen
model settings, including temperature 0, are unchanged.

Minimal checks reuse the existing validator:

1. Resolve the selected presentation against trusted configuration and SQL source.
2. Recompute the mathematical instance with the unchanged parameter engine.
3. Require complete plain placeholders and preserve source numerical facts.
4. Preserve known constraint markers and numeric occurrences against the selected
   presentation, not against a different Direct sentence.
5. Accept only the selected approved pattern after case/whitespace normalization.
   Added/missing conditions, unknown additions and plausible free paraphrases fail
   with an explicit uncertain-equivalence reason.
6. At assembly/storage/approval, independently compare source ID, digest, parameters,
   authoritative answer/solution, target skill, scope and cognitive level.

Exact pattern matching is intentionally narrow. JSON validity, matching keywords,
and matching answers alone never establish equivalence. Human approval certifies
the pattern's mathematical and educational meaning; runtime verifies adherence to
that approved artifact. Qwen currently realizes that finite approved wording;
unrestricted contextual paraphrasing is unsupported. Teacher approval remains a
separate requirement.

**The postponed six-layer Validator was NOT implemented.** No semantic AI judge,
LLM correctness scoring, grading system, new external API or automatic approval
was introduced. `ProblemSpec`, mathematical engine, Question fingerprints and
Qwen sampling settings were inspected and retain their prior behavior.

## Regeneration and fallback

The existing Template-only API/button remains. UI sends only expected_revision
and displays the accepted actual Direct/Indirect label. No new presentation button
or teacher difficulty control was added.

Regeneration validates the previous mathematical/presentation provenance, samples
a different valid mathematical instance when available, recomputes the answer and
solution, and prefers an alternative presentation (opposite type first). Only the
target question's instance, wording, presentation metadata, derived answer/solution,
rubric and question revision ID can change. Target skill, source, cognitive level,
question position, points and unrelated question content remain fixed. Existing
review workflow clears whole-exam approval and all individual review flags.
Revision advances once only after success and atomic persistence.

If finite instance capacity is exhausted but another verified presentation exists,
the same mathematical instance may be used with a different approved presentation.
A metadata-only upgrade of a legacy Direct record is not a new presentation.

Missing compatible Indirect uses SQL Direct and records why in review notes. An
invalid Indirect output retries within the existing per-presentation attempt bound
on exactly the same instance. On `INVALID_QWEN_OUTPUT` exhaustion, SQL Direct gets
one fresh bounded wording budget on that same instance and under the SAME overall
deadline. The final generate_type/provenance records Direct, with explicit fallback
notes. Transport, busy or timeout errors are not hidden by wording fallback.
Initial generation retains its existing failed-Template exclusion and eligible
Question fallback. Failed regeneration never replaces the target source or writes
a partial revision. Whole-exam approval still requires no individual checkboxes.

## Reproducible end-to-end examples (mock local Qwen)

Normal tests require no Ollama. The verified examples below use ONLY synthetic
approvals bound to `TEST_FORMULA` / `SYNTHETIC_*`, never real SQL Template approval.

| Example | End-to-end behavior | Regression |
| --- | --- | --- |
| Direct Template | Finalize n!, select `sql_direct`, prompt Direct, validate output, assemble mixed exam and persist metadata | `test_approved_direct_regenerates_to_verified_indirect_then_back_preserving_other_questions` |
| Verified Indirect | An eligible slot selects synthetic `synthetic_shelf`, uses the approved book-display wording without the original Direct sentence, keeps n!, persists and approves whole exam with zero individual flags | `test_mixed_initial_generation_has_balanced_presentation_for_no_data_partial_and_achieved` |
| Direct → Indirect regeneration | Approve Direct at revision 2; regenerate with a new valid n, recomputed n!, and synthetic Indirect; save pending revision 3; approve whole exam at revision 4 | `test_approved_direct_regenerates_to_verified_indirect_then_back_preserving_other_questions` |
| No verified Indirect | Proposed-only metadata stays inactive; generation and regeneration use `sql_direct` and record the missing-verification reason | `test_direct_fallback_without_verified_indirect_metadata_is_truthfully_recorded` |
| Invalid Indirect output | Bounded retries reject an added adjacency condition; unchanged-parameter SQL Direct fallback is persisted with truthful Direct metadata | `test_invalid_indirect_output_falls_back_to_direct_with_persisted_truthful_metadata` |

For the same synthetic n=5 instance, Direct is:

> Có 5 phần tử phân biệt. Hỏi có bao nhiêu cách sắp xếp tất cả các phần tử thành một hàng?

The test-only approved Indirect pattern renders:

> Một thư viện có 5 quyển sách phân biệt. Người phụ trách đặt tất cả sách thành một hàng và lập danh sách mọi cách bố trí. Danh sách có bao nhiêu cách bố trí?

Both retain the same instance record, answer 120 and authoritative solution. A
regeneration with a different n recomputes n! before Qwen; it does not retain 120
when the parameter changes. The original Direct sentence need not appear inside
the Indirect output. These examples demonstrate infrastructure, not production
Indirect rollout or human approval of the proposed SQL contexts.

A separate in-memory end-to-end run with `instance_seed=0`, synthetic hybrid data
and EchoTemplateClient produced this concrete transition:

| Field | Generated revision 1 | Regenerated revision 2 |
| --- | --- | --- |
| Template | TEST_FORMULA | TEST_FORMULA |
| Parameters | n=2 | n=7 |
| Authoritative answer | 2 | 5040 |
| generate_type | direct | indirect |
| presentation_id | sql_direct | synthetic_shelf |
| Configuration | sql-direct-v1 | synthetic-tests-v1 |
| Status | pending_teacher_review | pending_teacher_review |

This run used only synthetic test approvals and a mocked local model; it did not
call Ollama, edit canonical data or claim author approval of any SQL proposal.

Run from application root using the workspace Python environment:

```powershell
& '..\..\adaptive-learning\.venv\Scripts\python.exe' -m pytest -q tests/unit/test_template_presentations.py tests/integration/test_template_presentations_api.py
& '..\..\adaptive-learning\.venv\Scripts\python.exe' -m pytest -q
ruff check src tests
node tests/ui/teacher_review.test.cjs
```

## Files changed in this task

| Area | Files |
| --- | --- |
| Presentation metadata | NEW `config/template_presentations.json`, NEW `src/ai/template_presentations.py` |
| Expression/prompt | `src/ai/contracts.py`, `src/ai/expression_planner.py`, `src/ai/prompts.py` |
| Validation/API | `src/validation/question_validator.py`, `src/api/data_adapter.py`, `src/api/schemas.py`, `src/api/main.py` |
| Orchestration | `src/orchestration/exam_service.py`, `src/orchestration/question_generation.py`, `src/orchestration/exam_assembler.py`, `src/orchestration/review_service.py` |
| UI | `src/ui/static/app.js` |
| Tests | NEW `tests/unit/test_template_presentations.py`, NEW `tests/integration/test_template_presentations_api.py`, `tests/ui/teacher_review.test.cjs` |
| Documentation/config | `.env.example`, `README.md`, NEW this report |

Pre-existing unrelated modifications were preserved. No commit, push, merge,
reset, stash or discard was performed. Canonical SQL and student profiles were
not edited. Final validation results are recorded below after execution.

## Executed validation

- Baseline before edits: **590 passed, 1 skipped**, 34.61 seconds.
- Final full suite: **646 passed, 0 failed, 1 skipped**, 216.59 seconds.
  The 56 new cases cover planning, prompts, strict presentation validation,
  source/config tampering and revocation, numerical/answer/solution integrity,
  regeneration, bounded Direct fallback, persistence and zero-individual-review
  whole-exam approval. Normal tests use model doubles, without live Ollama.
- `ruff check src tests`: passed.
- `git diff --check`: passed; only existing Windows line-ending notices.
- The actual app.js harness was extended to check Direct display and Indirect
  display after regeneration. Its Python wrapper is the one skipped test because
  **Node is unavailable in this session**; the 14 JavaScript scenarios were not
  executed for this change. Run `node tests/ui/teacher_review.test.cjs` where Node
  is installed.
- One existing Starlette/httpx deprecation warning remains.
- Canonical bank SHA256 before and after:
  `12871bbe1b7823d89bfdcc8873c77f73d279f51593d31cdbdcccb6b1b9ac9276`.
  Canonical bank and student profiles remain read-only in this implementation.

## Human verification required before enabling real Indirect

A Data Lead / subject expert must review each proposed family over its supported
parameter domain, including edge cases and fixed conditions; establish a bijection
to the original counted objects; verify no extra/missing restrictions or different
reasoning demand; and approve its cognitive level independently of its source label.
The proposal may need revision or rejection, particularly where a list/catalogue
story is not educationally meaningful Indirect. After actual approval, supply the
review references and cognitive-preservation declaration, set `verified`, and keep
the exact reviewed source digest/pattern/version. If the source or pattern changes,
repeat that review. Do not activate entries merely to make UI labels alternate.
