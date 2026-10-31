# Verified problem specifications and teacher review UI

Date: 2026-10-27. Extends ADR-004's expression and validation stages and completes
its teacher UI work. Existing source layout, eight business routes, synchronous
responses, generation requests, cognitive labels, retry budgets and read-only
M3 access are retained.

## Optional authored data

`FixtureQuestion.problem_spec` defaults to null. JSON sources may supply a
`ProblemSpec`; the existing M3 adapter also reads an optional author-provided
`questions.problem_spec_json` column. The application never creates that column
or annotates canonical databases. Missing metadata keeps the legacy direct /
preserve-source path. Invalid metadata is `DATA_SOURCE_ERROR`, not silent fallback.

The Pydantic model in `src/ai/problem_spec.py` requires:

- Source ID, explicit synthetic/approved-data provenance, verified status and
  an author verification reference.
- Supported counting structure, bounded integer parameters, explicit order and
  replacement flags, verified integer answer, and reference solution steps.
- A source context and unique supported contexts containing authored direct
  and/or indirect statement templates and required/forbidden phrase guards.

Supported mathematics is deliberately bounded: combinations without replacement,
arrangements with or without replacement, and permutations. `1 <= n <= 100`,
`0 <= k <= 100`; without replacement `k <= n`. Permutations use only n. Other
M3 prose problems, including addition/multiplication rules, keep the legacy path.
Every template represents all specified parameters, and permits only plain
`{n}` / `{k}` substitutions. No executable expressions or attribute substitutions
are accepted. The source identity, content, answer and solution steps must match
the specification. Author verification remains a data trust boundary; a boolean
or model self-assessment does not independently establish prose correctness.

`tests/fixtures/structured_problem.json` is explicitly synthetic. It provides
C(8,3)=56, two contexts and a direct/indirect pair. It is neither migrated M3
content nor a claim of approved production structured coverage.

## Presentation and generation

The default `ExpressionPlanner()` retains direct/source-context behavior. With
matching curated sources a backend can inject a presentation policy:

```python
planner = ExpressionPlanner(generate_type="indirect", context_id="students")
service = ExamService(data, qwen_client, expression_planner=planner)
```

`plan_expression(source, context_id="books", generate_type="direct")` also
supports explicit per-source use. A requested context or presentation must be
listed in that source's verified metadata; incompatible requests fail. The
planner chooses presentation only and never computes answers. There is no new
public context-selection request field or UI selector. Canonical M3 sources
continue to work without configuration.

For structured requests, the same `QwenClient.generate_one` receives the typed
expression; legacy callers may still pass strings. The prompt uses an explicit
allowlist: prepared statement, presentation, context, structure, parameters,
constraints and phrase guards. It excludes verified answers, solutions, author
references and student data. Output remains exactly JSON `{question: string}`.
Single-attempt transport and centralized bounded retry/deadline handling remain
unchanged. Unknown rewrite-only injected clients cannot handle structured input
and fail explicitly rather than dropping constraints.

## Acceptance criteria

The validator checks JSON shape, text length, signed numeric facts and an explicit
Vietnamese constraint vocabulary (order, replacement, distinctness, bounds, parity). Legacy
explicit contradictions fail; other legacy semantic uncertainty stays
`needs_review`. Structured candidates additionally require authored phrase guards
and no detected contradiction with order/replacement flags. Changed/removed known
conditions, changed quantities, and independently inconsistent answers fail and
use the existing retry budget.

The deterministic verifier computes C(n,k), permutations or arrangements from
the supplied structure and checks the verified answer. **Internal `pass` requires
an exact authored statement** after case/whitespace normalization plus those
checks. This is acceptance against the author's verified presentation, not a
general proof of natural-language equivalence or every solution step. Free
paraphrases and unknown extra prose remain `needs_review`, even if numbers match.
Arbitrary constraint wording is not exhaustively parsed. Known phrase guards can
reject equivalent paraphrases conservatively. Production data authors must
verify the mathematical meaning of every compatible context and presentation.

Public exam questions retain `auto_status=needs_review`: source labels and the
generic scoring rubric still require human acceptance. Every completed exam is
`pending_teacher_review`, including one containing internally passing statements.

## Assembly, compatibility and review

The assembler independently checks request identity, source metadata, selected
source uniqueness, accepted candidate content, achieved/requested quota totals,
per-skill levels and teacher difficulty locks. Soft quota deviations remain
allowed and reported. It preserves every reference solution step and distributes
existing quarter-point scoring units across them; it does not repeat the
mathematical validator.

Duplicate source/generated IDs are hard errors. Same/near-identical wording
across distinct source IDs receives a teacher review note. Rejecting all repeated
legacy wording would break supported synthetic banks and is not proof that two
problems have the same mathematical meaning. This is conservative detection,
not a guarantee of semantic deduplication. Regeneration applies the same wording
warning without modifying unrelated questions.

`ExamQuestion.expression_context_id` is additive and defaults to null for old
drafts. Together with existing `generate_type` it preserves a structured
presentation during regeneration, including after a service restart. Source
fingerprints omit the new null ProblemSpec field for legacy sources so existing
fingerprinted drafts remain regeneratable. Structured fingerprints include the
entire specification; changes are rejected by the existing source-integrity gate.
Revision CAS, approval reset, failure preservation and durable history are intact.

The existing UI now offers current-status display, reference answers/solutions,
optional per-question acceptance, whole-exam approval without individual clicks,
Qwen-only individual regeneration, and latest-revision refresh. Mutations send
`expected_revision` and replace the rendered draft from the full API response.
Regeneration and refresh clear local acceptance. Conflicts disable mutations
until refresh. Provider failures preserve the visible draft. Review controls are
disabled while an operation is running. Approved exams can be regenerated into
a pending draft. Shared-token identity limitations remain unchanged.

## Data and verification limits

The operational bank remains the seven-skill M3 catalogue. The existing nine-skill
relationship policy is tested with a matching synthetic catalogue, never mapped
onto M3. An approved nine-skill bank, primary annotations and matching profiles
must be supplied by the Data team. No mastery/evidence is fabricated or updated.

Automated Python tests mock Ollama. `tests/ui/teacher_review.test.cjs` executes the
actual app.js with a minimal DOM and mocked HTTP to test eight workflow scenarios;
it is not a browser layout/screenshot test. Run it with Node, or through the
available JavaScript runtime. The pytest bridge skips when Node is absent.

Optional live test: `python -m eval.smoke_exam_generation --live`. It reads M3 and
the marked synthetic fixture, calls local `qwen3:1.7b`, and never stores drafts.
On 2026-10-27, all three live paths succeeded in 7.04 seconds: M3 source QA0001
produced a pending/needs-review draft; books/direct and students/indirect matched
approved templates and internally passed. This small smoke test establishes
local integration, not broad model quality or semantic accuracy. Captured output:
`eval/results/personalized_exam_smoke_2026-10-27.json`.
