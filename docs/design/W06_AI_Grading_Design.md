# W06 — AI Grading Design (Draft)

**Project:** MIRA — Mastery-Informed Review Assistant  
**Use case:** UC-03 — Grade Submitted Practice Exam  
**Owner:** N04 — AI & Algorithms Lead (Phạm Yến Trân)  
**Status:** Draft for Data / Architecture / Product review  
**Scope:** Grading rules, input/output contracts, automatic-versus-manual decisions. **No model implementation or validated grading benchmark is claimed.**

## 1. Goal and boundaries

Define a conservative grading interface for open-ended Grade 10 combinatorics submissions. The grading component attempts to evaluate each answer against the **approved, immutable exam snapshot**, including the problem statement, reference solution, marking scheme and maximum score. It returns either:

1. `GRADED` — a verified final score, rubric breakdown and feedback; or
2. `NEEDS_TEACHER` — no automatic final score and an explicit reason for mandatory manual grading.

The grading component **does not update mastery directly**. Only a finalized grading record can be forwarded to the separately designed Mastery Update module.

### UC-03 alignment

1. Backend receives and durably stores the submission.
2. Backend retrieves the approved snapshot used by that student, including question versions and rubrics.
3. Grading is attempted independently for each answer. Successfully verified results are finalized at the **answer level**.
4. Any unresolved answer is flagged for teacher grading; other completed answer results are retained.
5. When every answer has a final result (automatic or teacher-entered), backend finalizes the examination result and updates the student profile from the final grading record.
6. Teachers may optionally correct automatically graded answers after finalization; affected stored results and skill profiles must be reconciled without counting the same evidence twice.

**Important distinction:** `GRADED` for an individual answer does not mean the *entire examination* is finalized.

## 2. Required input

| Field | Required | Purpose and constraint |
| --- | --- | --- |
| `submission_id`, `student_id` | Yes | Identify a specific submission and student; authorization is checked by backend. |
| `exam_id`, `snapshot_id`, `question_instance_id` | Yes | Identify the exact approved version the student received; never grade against a later regenerated question. |
| `question_text` | Yes | Exact question from the approved snapshot. |
| `student_answer` | Yes, may be empty | Submitted answer as-is; preserve original text separately. |
| `reference_answer` | Yes | Approved answer, with permitted equivalent forms if known. |
| `reference_solution` | Yes | Approved solution steps and mathematical constraints. |
| `rubric` | Yes | Explicit grading criteria, per-step maximum scores and partial-credit conditions. |
| `max_score` | Yes | Maximum score for this exact question snapshot, non-negative and consistent with rubric. |
| `score_increment` | Yes | Allowed granularity (draft proposal: `0.25` points; team approval needed). |
| `difficulty`, `skill_ids` | Yes | Question metadata used later for skill evidence; *not* direct instructions to award or deduct points. |
| `grading_policy_version` | Yes | Traceable version of scoring and validation policy. |

**Preconditions:** The exam snapshot has been teacher-approved, the student is authorized to submit, the submission is not already finalized under a conflicting version, and the rubric is internally consistent. Missing or invalid essential grading context is a **system/setup error**, not a zero score for the student.

## 3. Evaluation strategy and order

### 3.1 Deterministic checks first

Use mathematical or structured checks when reliable: numeric equivalence, combinatorial identities and safely normalized forms (e.g., `C(8,3)` and `56` where the prompt asks for a count). Do not evaluate arbitrary submitted expressions as executable Python code. Equivalence must honor the actual problem's conditions and the allowed answer format.

### 3.2 AI-assisted interpretation

When evaluating an open-ended written solution, the local model may help identify steps, compare reasoning against the approved rubric and suggest feedback. It must not be the sole justification for a final score when the equivalence of a novel method cannot be verified reliably.

### 3.3 Multiple valid approaches

Accept any mathematically sound method meeting the rubric's learning objective, even if its presentation or order of steps differs from the reference solution. If an alternative method appears valid but cannot be confirmed with sufficient evidence, return `NEEDS_TEACHER` rather than `INCORRECT` or an invented score.

### 3.4 Partial credit

Assess rubric criteria independently, based on demonstrated work. Award credit for valid intermediate reasoning even if a later arithmetic step is wrong, subject to any documented rubric dependency. Do not award points merely because the final number happens to match; check whether the rubric requires a demonstrated method. Avoid double-counting the same evidence across overlapping rubric items.

**Never use the separate question-generation quality rubric (e.g., a generator evaluation score) to mark student answers.**

## 4. Draft scoring policy

- For each criterion `i`, require `0 <= awarded_i <= max_i`.
- `final_score = sum(awarded_i)` and `0 <= final_score <= max_score`.
- `sum(max_i) == max_score` for an additive rubric; otherwise the rubric must explicitly declare its aggregation rule.
- Proposed `score_increment = 0.25` points, configurable and subject to approval by N03 (Data Lead), N05 (Backend Lead), and Product Lead. Allow only valid multiples of the approved increment, with floating-point-safe comparisons or decimal arithmetic.
- A `GRADED` result must include scores per criterion, final score, concise explanation and traceable grading method.
- A `NEEDS_TEACHER` result must **not** include a final numeric score. An uncertain answer must not automatically become `0`.
- `max_score` belongs to the approved question snapshot; it is not a mastery score on a 0–4 scale.

### Example rubric (illustrative, total 2.0 points)

Question: “Choose 3 students from 8 students, without order. How many choices?”

| Criterion ID | Evidence | Max points |
| --- | --- | ---: |
| `r1` | Identifies combinations, without order | 0.50 |
| `r2` | Sets up `C(8,3)` correctly | 0.50 |
| `r3` | Obtains and justifies the result `56` | 1.00 |
| **Total** | | **2.00** |

These are draft grading values for demonstrating the interface, not a finalized project-wide score distribution.

## 5. Output contract

### 5.1 Automatically finalized answer: `GRADED`

Required fields:

- `submission_id`, `question_instance_id`, `snapshot_id`
- `status: "GRADED"`
- `grading_method` (`DETERMINISTIC`, `AI_ASSISTED_VERIFIED`, or `TEACHER`)
- `rubric_results[]` containing `criterion_id`, `awarded`, `max`, and `reason`
- `final_score`, `max_score`, `feedback`
- `grading_policy_version`; optional traceable grader/model version

The backend validates the output against the approved snapshot before persisting it as a final answer-level result. `AI_ASSISTED_VERIFIED` is allowed only if the implementation has an explicit, testable verification path; otherwise use `NEEDS_TEACHER`.

### 5.2 Manual review required: `NEEDS_TEACHER`

Required fields:

- `submission_id`, `question_instance_id`, `snapshot_id`
- `status: "NEEDS_TEACHER"`
- `reason_code`, `reason_detail` (safe, teacher-readable)
- `final_score: null`, `feedback` (optional diagnostic note, not a final judgment)
- `grading_policy_version`

Suggested reason codes: `AMBIGUOUS_METHOD`, `UNVERIFIED_EQUIVALENCE`, `INSUFFICIENT_WORK`, `INVALID_RUBRIC`, `MODEL_UNAVAILABLE`, `TIMEOUT`, `OUTPUT_VALIDATION_FAILED`, `UNSUPPORTED_FORMAT`, `EMPTY_ANSWER_POLICY_PENDING`.

Separate **technical/configuration failures** (`INVALID_RUBRIC`, missing snapshot, etc.) from **content requiring teacher judgment**. The former may need administrator intervention or retry, not a teacher to guess a grade.

## 6. Example outputs

### Example A — Auto-graded, 2.0/2.0

Student answer: “Vì thứ tự không quan trọng, chọn 3 bạn trong 8 bạn có C(8,3) = 56 cách.”

```json
{
  "submission_id": "SUB001",
  "question_instance_id": "QINST001",
  "snapshot_id": "SNAP001",
  "status": "GRADED",
  "grading_method": "DETERMINISTIC",
  "rubric_results": [
    {"criterion_id": "r1", "awarded": 0.5, "max": 0.5, "reason": "Uses unordered selection."},
    {"criterion_id": "r2", "awarded": 0.5, "max": 0.5, "reason": "Correct combination expression C(8,3)."},
    {"criterion_id": "r3", "awarded": 1.0, "max": 1.0, "reason": "Correct result 56."}
  ],
  "final_score": 2.0,
  "max_score": 2.0,
  "feedback": "Correct combinatorial approach and calculation.",
  "grading_policy_version": "draft-v0.1"
}
```

### Example B — Cannot finalize automatically

Student answer: “Em chia thành nhiều trường hợp và ra 56, nhưng em không ghi chi tiết.” The final number is correct, but the approved rubric requires evidence of method; the component cannot verify the omitted reasoning.

```json
{
  "submission_id": "SUB001",
  "question_instance_id": "QINST002",
  "snapshot_id": "SNAP001",
  "status": "NEEDS_TEACHER",
  "reason_code": "INSUFFICIENT_WORK",
  "reason_detail": "The final answer matches, but the required reasoning cannot be verified from the submission.",
  "final_score": null,
  "feedback": "Teacher to determine partial credit under the approved rubric.",
  "grading_policy_version": "draft-v0.1"
}
```

The sample IDs, grading values and example rubric are illustrative. No live AI grading performance is claimed.

## 7. Validation before saving a final score

The backend must reject an automatically finalizable result if any of these checks fail:

1. Submitted identifiers reference the correct student, approved exam snapshot and question instance.
2. Status, score fields, required feedback and rubric structure match the declared schema.
3. All criterion IDs exist in the approved rubric, with no missing or duplicated criteria.
4. Scores are finite, within allowed criterion bounds, and conform to the approved increment.
5. `final_score` equals the verified rubric aggregation and stays within `[0, max_score]`.
6. A claimed equivalence or method judgment is supported by a reliable verification path; otherwise route to review.
7. No untrusted model text can alter `max_score`, `rubric`, `skill_ids` or approved snapshot facts.
8. Persistence is idempotent: retries must not create duplicate final results.

An invalid output is **not** a student error and must not silently become an incorrect answer.

## 8. Manual grading and exam finalization

- Teacher work queue contains only unresolved answers (plus optionally reviewable auto-graded answers).
- Teacher can enter a final score and criterion feedback according to the approved snapshot rubric.
- The examination remains `PENDING_TEACHER_REVIEW` while any answer lacks a valid final result.
- When all answers are finalized, the backend saves the consolidated grading record, then invokes profile update (transactional or idempotently recoverable).
- A teacher adjustment after examination finalization must supersede the affected grading result, preserve audit history, and trigger a consistent recomputation of impacted mastery/evidence rather than appending duplicate evidence.
- Access control: only an authorized teacher can finalize or override a manual/automatic grade.

## 9. Skill-level evidence and Data collaboration

The grading score and the mastery score serve **different purposes**. A numeric question score must **not** directly be converted to the student's `mastery_score` by this grading module.

The final grading record is the source for the separately developed `MasteryUpdater`. If there is reliable evidence for specific skills, it may attach per-skill observations such as `CORRECT`, `INCORRECT`, or `NOT_ASSESSED` with an evidence source. Merely having multiple `skill_ids` on a question does not mean every tagged skill should be marked incorrect when the overall answer is wrong.

**Items to confirm with N03 / Data Lead and N05 / Architecture Lead:**

- Where graded answer records, rubric breakdowns and final grading versions are stored in the existing schema.
- Whether skill-level observations are stored inside the final grading record or referenced separately; avoid duplicate storage.
- How `question_instance_id`, `skill_ids`, `difficulty` and an approved snapshot are linked immutably.
- Which finalized observations increment `evidence_count`, and how unknown mastery (`null`) remains distinguishable from assessed `0.0`.
- How to replay or recompute profile updates after a teacher grade correction without double counting.
- How `score_increment`, `max_score`, rubric criteria and grading policy versions are represented.

**Out of scope here:** Finalizing the 0–4 mastery update formula, question exposure policy, and database migrations.

## 10. Open decisions for team review

| Topic | Draft recommendation | Final decision |
| --- | --- | --- |
| Empty/whitespace-only answer | Record as `UNANSWERED`; decide whether to assign a verified zero automatically or require teacher review. Do not assume policy. | **Open** |
| Retry on transient model/network error | Bounded retry only for transient technical failures; proposal: at most 1 retry before routing to retry queue/manual handling. | **Open** |
| Grading timeout | Set a measurable per-answer timeout based on local-model benchmark; do not invent a latency SLA. | **Open** |
| Scoring increment | Propose 0.25 points per criterion/answer; verify against stored rubrics and existing API. | **Open** |
| AI-assisted finalization threshold | Establish explicit independent verification standards and evaluate error rate before enabling unattended final scores. | **Open** |
| Alternative valid method | Deterministic verification if possible; otherwise teacher review rather than penalizing different wording. | **Proposed** |
| Regrading after teacher override | Replace prior grading version and reconcile mastery/evidence idempotently. | **Proposed; Data/API review needed** |

## 11. Acceptance checklist

- [x] Required inputs named: question, answer, approved reference answer/solution, rubric, approved snapshot maximum score.
- [x] Outputs specified for automatically graded and manual-review cases, with reasons.
- [x] Draft partial-credit, score bounds and score increment policy provided.
- [x] Multiple correct methods explicitly supported.
- [x] Manual-review conditions and output validation defined.
- [x] Retry/timeout and unanswered-policy decisions flagged as open.
- [x] Data/Architecture alignment requirements documented.
- [x] At least one example for each output pathway.
- [ ] Review against the canonical W06 workflow file and actual repository API/schema (not available for direct inspection in this draft).
- [ ] N03 Data, N05 Architecture, and Product Lead review.

---

**Reference:** UC-03 — *Grade Submitted Practice Exam* in the team's midterm project report; issue-provided workflow reference: `W06_Grading_Workflow_and_Acceptance_Criteria.md`. This draft follows the issue's acceptance criteria and does not assert that the linked workflow file was inspected.
