# Experimental Qwen Indirect — MVP1, 2026-10-30

## Product scope and activation

The local MVP now supports `experimental_indirect` for the currently executable
SQL L1/L2 Templates, without requiring an approved pattern. This is a presentation
experiment, NOT a claim of verified mathematical/semantic equivalence or preserved
educational difficulty of arbitrary wording. Backend mathematics and source
difficulty remain fixed; an experimental story can still introduce unintended
reasoning demands. Teacher review is explicit and whole-exam approval needs no
individual question checkboxes.

`python -m src.ui` enables `KORO_EXPERIMENTAL_INDIRECT=1` by default. An explicit
environment value is respected:

```powershell
# Local UI with experimental Indirect (default):
python -m src.ui
# Strict verified-only mode:
$env:KORO_EXPERIMENTAL_INDIRECT = '0'
python -m src.ui
# A plain API/uvicorn process is strict unless explicitly enabled:
$env:KORO_EXPERIMENTAL_INDIRECT = '1'
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

The application does not auto-load `.env`. `.env.example` documents the local
setting. Static/model-test registries default strict; enabling experimental mode
adds a separate capability without modifying proposal status. Explicit `0`
disables experimental selection and acceptance in source-integrity checks. Stored
experimental drafts remain readable, but strict mode will not approve/regenerate
them as though they were author-verified.

The Fake UI never labels an unchanged source sentence experimental Indirect: it
keeps the strict rendered path because it cannot generate contextual Qwen wording.
The default local launcher uses Qwen, so the experimental capability is usable.

## Provenance and selection

The presentation record carries:

```json
{
  "presentation_id": "experimental_indirect",
  "generate_type": "indirect",
  "verification_status": "experimental",
  "config_version": "experimental-indirect-v1",
  "context_id": "school",
  "fingerprint": "<fingerprint bound to Template definition and requested context hint>"
}
```

The context ID is a requested hint, not a classifier's assertion about the final
story. The fingerprint binds Template rules/scope and presentation settings; it
does not certify the wording's meaning. No human approval reference is fabricated.
Existing author-verified patterns remain preferred when available and retain exact
matching. None of the real SQL Indirect proposals was activated as `verified`.

ExpressionPlanner alternates Direct/Indirect across eligible Template slots,
starting Direct. An odd slot count can differ by one. Selection has no mastery
gate and no L1/Direct or L2/Indirect coupling. Both NO_DATA and PARTIAL students
can receive Indirect. Regeneration prefers the opposite type when available.
Context hints and sampling seeds vary reproducibly with the mathematical instance
and variant ordinal; the current question's previous wording is transient prompt
input. No completed-question history is stored.

The Source Selector and RuleBasedPlanner are unchanged. The eight executable
families (EA0001, EA0002, EA0004, EA0012, EA0013, EA0015, EA0017, EA0018) can reach
experimental wording. Existing unsupported rule/parameter families retain their
existing Question fallback; L3/L4 remain immutable Question Bank only.

## Prompting and bounded generation

Experimental prompts supply the finalized mathematical statement, fixed parameter
values/constraints, requested context and previous wording. They ask for a natural
grade-10 Vietnamese contextual outcome (days, attempts, events, catalogue pages,
etc.), not a decorative story plus an unchanged Direct counting request. They
forbid new parameter values, extra restrictions, changing the counting operation,
formula/technique names, answers and solutions. For the explicit `arrange_all`
parameter, prompts emphasize using all distinct objects in one row during EACH
event, rather than choosing one object per event. No authoritative answer/rule
or solution is passed as model output authority.

Only experimental Qwen requests use temperature **0.7** and a variation seed.
Direct and author-verified requests retain temperature 0 and existing seed policy.
Retry attempts vary the context suggestion and include the rejection feedback.
The same finalized mathematical instance is retained throughout wording retries.
Existing attempt count, single-request capacity and overall deadlines remain.

Instructions for the experimental branch are concise English with an explicit
Vietnamese-output requirement. Real local trials showed better instruction
following than long Vietnamese instructions on this installed model. Mathematical
source data stays Vietnamese. Previous wording's numerals are redacted in the
anti-repetition hint to avoid confusing old values with the new finalized instance.
Only fixed numerical facts are repeated in the system instruction; sampling
ranges are not supplied as alternative values. Thinking stays disabled; no broad
retuning or new provider was introduced.

## Minimal checks and explicitly postponed guarantees

Only experimental Indirect skips exact-pattern matching. It still checks JSON
with the single `question` field, nonempty bounded text, resolved placeholders,
source/provenance fingerprints, numeric facts and known contradictory constraints.
Original numerical facts must appear; new numeric values are blocked. Repetition
of an existing numeric fact is permitted. A whole copied Direct statement or a
stock 'có bao nhiêu cách sắp xếp/chọn...' request is rejected as a shallow rewrite.
For sources with explicit `arrange_all=true`, an explicit change to selecting one
object per event is blocked. Missing/implicit conditions are NOT forced through
an exact required-phrase allowlist. These are narrow quality/structure checks,
not a semantic classifier or mathematical proof.

Source-integrity validation recomputes parameters, answer, solution and source
scope from the unchanged deterministic engine before persistence/approval. Qwen
cannot overwrite these with its own answer. Question Bank wording, generate_type,
answers and fingerprints stay immutable.

Every accepted experimental candidate has `needs_review` and an explicit notice:

> Diễn đạt Indirect thử nghiệm — chưa kiểm chứng đầy đủ về ngữ nghĩa toán học.

Schema validation rejects labeling such a question `auto_status=pass` or claiming
its presentation is author-verified. The UI keeps this notice visible even after
a deliberate teacher whole-exam approval.

**Not implemented:** the six-layer Validator, a semantic-equivalence engine, LLM
judge, grading, or mathematical/cognitive correctness scoring. Number words,
unrecognized restrictions, omitted implicit conditions and a changed contextual
goal can still evade basic checks. Matching JSON/numbers/keywords is not proof of
equivalence. Teacher approval does not retroactively turn experimental provenance
into verified provenance.

## Regeneration and failure

Only Template questions can regenerate. The service checks the old source, picks
new valid parameters where available, recomputes authoritative answer/solution,
selects another presentation, and calls Qwen with previous wording. Source,
target skill, difficulty, order, score and unrelated questions stay unchanged.
On success the revision advances once, whole-exam approval is cleared, and existing
individual review flags reset as in the previous workflow. Failed generation does
not persist partial content or advance the revision.

When experimental output fails basic checks, bounded retries preserve its instance
and return rejection feedback. Exhaustion uses the existing safe SQL Direct
fallback with the same parameters and deadline, recording the blocking reason and
the final actual Direct provenance. Merely differing from SQL wording is not a
failure. Initial generation still has existing failed-Template / eligible Question
fallback. No new source-selection policy or difficulty substitution was added.

## Reproduction and evidence

Normal regression tests use mocked Qwen; no Ollama is required:

```powershell
python -m pytest -q tests/unit/test_experimental_indirect.py tests/integration/test_experimental_indirect_api.py
python -m pytest -q
ruff check src tests eval/experimental_indirect_smoke.py
```

The optional real local smoke uses SQL EA0017, creates no student records, and
keeps its temporary exam in memory:

```powershell
python -u -m eval.experimental_indirect_smoke
```

It records real model output, every attempted response/rejection, Direct/Indirect
provenance, computed answers, regeneration and before/after canonical hashes in
`eval/results/experimental_indirect_smoke_2026-10-30.json`. Model output quality
must be read and assessed separately from mock tests and mechanical checks.
Execution results and actual examples are recorded below after validation.

## Real local-Qwen results

The final real run used local Ollama **qwen3:1.7b**, without model doubles. It
accepted one Direct, two experimental Indirect outputs on the SAME n=5 instance,
and one genuine Direct-to-Indirect regeneration. The JSON artifact records all
actual attempts and elapsed times; `mocked=false`, `smoke_goals_met=true`, and
`semantic_equivalence_verified=false` explicitly distinguish these claims.

| Operation | Actual wording / outcome | Backend answer |
| --- | --- | --- |
| Direct, EA0017 n=5 | Original question asks the number of arrangements of all distinct objects in a row | 120 |
| Experimental Indirect A, same n=5 | A club with five different members uses a new full lineup at every meeting; asks the maximum number of meetings without repeating an order | 120 |
| Experimental Indirect B, same n=5 | A shop shows all five different products in a new order on each catalogue page; asks the maximum number of pages without repeating an order | 120 |
| Regeneration, n=5 → n=12 | Original Direct item becomes a club with twelve different members and a maximum-nonrepeating-meetings question; pending revision 1 → 2 | 120 → 479001600 |

Actual Indirect A:

> Một hội có 5 thành viên khác nhau. Mỗi buổi họp, tất cả thành viên đứng thành một hàng với thứ tự mới. Hỏi số buổi họp tối đa có thể tổ chức mà không có thứ tự nào bị lặp lại?

Actual Indirect B:

> Một cửa hàng có 5 sản phẩm khác nhau. Mỗi trang catalogue hiển thị tất cả 5 sản phẩm đứng thành một hàng với thứ tự khác nhau. Hỏi số trang catalogue tối đa có thể in ra mà không có thứ tự nào bị lặp lại?

The two contexts and practical goals differ, rather than only substituting
parameters. Manual inspection of these examples is encouraging, but is not an
author approval, educational-level certification, or general semantic guarantee.
Earlier trials also demonstrated failures: copied Direct wording, invented
numerical values, awkward literal translation and loss of mathematical conditions.
Blocking examples triggered bounded retries/Direct fallback; unrecognized semantic
mistakes can still pass as `needs_review`. This small model's quality remains
variable, particularly on other Template families and edge parameters.

Both canonical files were unchanged before/after real inference:

- Question bank SHA256: `12871bbe1b7823d89bfdcc8873c77f73d279f51593d31cdbdcccb6b1b9ac9276`.
- Student profiles SHA256: `beadded2b39db5c7e3962f272bd1139003361a4d2376abfe2babdce7eac9dede`.

## Files changed for this product decision

- `src/ai/template_presentations.py`, `src/ai/expression_planner.py`, `src/ai/contracts.py`
- `src/ai/prompts.py`, `src/ai/qwen_client.py`
- `src/validation/question_validator.py`, `src/validation/math_validator.py`
- `src/api/schemas.py`, `src/api/data_adapter.py`
- `src/orchestration/exam_service.py`, `src/orchestration/question_generation.py`, `src/orchestration/review_service.py`
- `src/ui/__main__.py`, `src/ui/static/app.js`
- New `tests/unit/test_experimental_indirect.py`, new `tests/integration/test_experimental_indirect_api.py`, `tests/ui/teacher_review.test.cjs`
- New `eval/experimental_indirect_smoke.py` and its generated JSON report
- `.env.example`, `README.md`, historical-report supersession note, this report

Canonical SQL, student profiles, nine-skill definitions, mastery scale, Planner,
Focus/Review ratios, difficulty allocation and source priorities were not modified.
Unrelated existing changes were preserved. No commit/push/merge/reset was performed.

## Final verification results

- Full final suite: **682 passed, 0 failed, 1 skipped**, 163.61 seconds.
- The 36 new cases cover real-SQL experimental eligibility, strict-mode opt-out,
  L1/L2 and NO_DATA/PARTIAL access, prompt/sampling behavior, meaningful rewrite
  acceptance, corruption/Direct-copy rejection, honest status, successful retry
  diagnostics, source/answer/solution integrity, atomic regeneration, persistence
  and whole-exam approval without individual acknowledgements.
- A focused generation/regeneration run also passed **72 tests**.
- `ruff check src tests eval/experimental_indirect_smoke.py`: passed.
- `git diff --check`: passed (existing Windows line-ending notices only).
- UI JavaScript harness now checks the experimental notice after regeneration
  and after approval. Its wrapper is the skipped test because Node is unavailable;
  the 14 JavaScript scenarios were not executed in this environment. The live UI
  serves the updated assets; browser interaction still benefits from manual review.
- One pre-existing Starlette/httpx deprecation warning remains.
- Real Ollama run: Direct + two distinct contextual experimental outputs +
  Direct-to-Indirect regeneration succeeded. Actual request times were approximately
  1.5, 7.2, 4.5 and 6.4 seconds, within existing local timeout bounds. Real-model
  success here is separate from mocked regression success and is not a semantic
  verification certificate.
