# Modular generation pipeline and teacher review

Date: 2026-10-26. This implements the modular boundaries and review workflow
from the two-person implementation proposal while retaining existing API contracts.

## Internal boundaries

| Stage | Implementation | Output |
|---|---|---|
| Allocation | `src/adaptation/planner.py::build_allocation_plan` | Pydantic `AllocationPlan`, no source IDs |
| Selection | `src/adaptation/question_selector.py` | Selected sources; planner exposes the existing `ExamPlan` blueprint |
| Expression | `src/ai/expression_planner.py` | `ExpressionSpec`, direct wording and preserved source context |
| Model transport | `src/ai/qwen_client.py::generate_one` | `GenerationCandidate`, exactly one HTTP attempt |
| Candidate checks | `src/validation/question_validator.py` | `ValidationResult`: definite failure or needs teacher review |
| Retry orchestration | `src/orchestration/question_generation.py` | Accepted `ValidatedQuestion` or typed failure |
| Assembly | `src/orchestration/exam_assembler.py` | Complete pending teacher draft with source answers |
| Exam orchestration | `src/orchestration/exam_service.py` | Synchronous plan-to-draft execution |
| Teacher review | `src/orchestration/review_service.py` | Explicit approval and revision invariants |

`src/api/real_generator.py::QwenExamGenerator` remains a compatibility entry point.
Existing SQLite/JSON adapters continue to provide the data boundary; the source
tree is not relocated solely to match the Word document's example directory.

## Retry and validation semantics

One question uses at most `QWEN_MAX_ATTEMPTS` transport calls. The generation
service owns retries; `generate_one` never retries internally. `rewrite` remains
a compatibility wrapper around that same service. Legacy injected clients that
only expose `rewrite` are called once and their output is checked.

The shared exam deadline, per-call timeout, bounded response size and one-request
model capacity remain in effect. Invalid envelopes or candidate content may be
retried; connection/provider errors retain existing explicit failure behavior.
An exhausted definite failure returns 502, never a successful needs-review draft.
No partial exam is stored. Regeneration failures leave the existing draft intact.

Checks cover JSON shape, text length, numeric preservation, source references,
question count, uniqueness, score totals and teacher difficulty constraints.
They do not prove semantic equivalence or source-answer correctness. Existing
M3 source answers, difficulty mappings and generic rubrics still need review.
The expression policy does not guess structured mathematics from prose. Context
changes, indirect generation and a mathematical verifier require curated data.

## Relationship policy and data compatibility

`SkillRelationships` is an optional typed policy loaded with
`SKILL_RELATIONSHIPS_FILE`, or injected into `RuleBasedPlanner` / `create_app`.
Its catalogue must exactly match the active data catalogue; mismatch is an error.
Unconfigured M3 retains the existing seven-skill behavior and thresholds.

For configured Focus/Review planning, related skills are ranked by the maximum
P3/P2/P1 relationship to either focus skill, then skill ID. Relationships are
directional and not summed. Related Review receives at most `floor(review / 2)`
questions. At least one review skill remains available for balanced coverage.
If no related skills exist, their quota goes to balanced review. Selector fallback
cannot exceed the related cap or violate explicit teacher difficulty totals;
if no valid candidate remains, the request fails rather than fabricating a slot.
Other skill/group preferences remain soft and report achieved quotas and warnings.

`tests/fixtures/nine_skill_relationships.json` transcribes the proposal's nine-skill
matrix solely for synthetic tests. No A001–A007 to SK01–SK09 mapping is inferred,
no student mastery is migrated, and no M3 database is modified. The Data team
must supply the approved catalogue, source annotations and profile migration.
Available history still records wrong questions only; novelty is limited to that
subset, not complete prior exposure.

## Public API compatibility and review lifecycle

Existing `/api/v1/exams/plan`, `/generate` and `/{exam_id}` keep their request
contracts and synchronous responses. No jobs, queues, new field aliases or
replacement `/drafts` API are introduced. Additive response fields are `revision`
(default 1 for older snapshots) and `teacher_review` (default null).

Teacher-only additions:

- `POST /api/v1/exams/{exam_id}/approve`: `expected_revision`, all current
  `accepted_question_ids`, optional `notes`. It changes pending to approved,
  records UTC approval time and marks every question teacher-approved.
- `POST /api/v1/exams/{exam_id}/questions/{question_id}/regenerate`:
  `expected_revision`. The Qwen pipeline rewrites the same source, keeps its
  answer/scoring/metadata, creates a new question ID, and returns the complete
  draft. A changed/unavailable source is rejected using a stored content fingerprint.
  Older drafts without a fingerprint remain readable but must be generated anew
  before regeneration. The entire exam's approval is
  reset after a successful regeneration, requiring a new explicit review.

Generation cannot return an already-approved exam. Regeneration cannot alter
trusted exam identity, unrelated questions, source references or scoring.
Each mutation increments the revision. SQLite compare-and-swap runs in an
immediate transaction; concurrent/stale updates return 409
`EXAM_REVISION_CONFLICT`. The in-memory demo store provides the same revision
guard, but remains ephemeral and does not provide durable revision history.

SQLite stores snapshots in an application-owned `exam_revisions` table so the
previous approved record survives regeneration. Existing draft JSON without the
new fields remains readable. This is separate from canonical M3 databases.
The shared teacher token records the access method, not an individual teacher's
identity. Student authentication, delivery, submissions, grading and mastery
updates are not implemented by this change.

## Verification

Regression tests cover the existing fake and Qwen API paths. New tests cover
allocation before source selection, nine-skill policy on synthetic data, related
quota caps, candidate failures, retry feedback and exhaustion, review access,
complete acceptance, durable snapshots, stale writes and regeneration failure.
Provider tests use a local HTTP Ollama double. They are not live Qwen quality or
latency evidence.
