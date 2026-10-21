# N03 – Algorithm & AI: Local Qwen Baseline and Profile-Driven Question Generation

**Related issues:** #6 (completed local baseline spike); #19 (Profile JSON / Blueprint pseudocode alignment)  
**Owner:** M4 – AI & Algorithms Lead  
**Reviewers for Issue #19:** Nhukei (Architecture Lead), Hoài Thương (Risk Lead)  
**Document status:** Baseline experiment completed; Issue #19 pseudocode aligned with the stated Decision Log rules; target generator architecture described as a proposed next implementation stage.  
**MVP subject / topic:** Grade 10 Mathematics / Combinatorics (`topic_id = "combinatorics"`). Keep `topic_id` in the interface to support additional topics later.

> **Scope and evidence.** Sections 2–3 and 6 record an actual local Qwen experiment performed on 2026-10-19. Section 4 implements the **agreed branching rule in pseudocode only** using M3's precomputed Profile JSON. Section 7 documents the planned end-to-end question-generation design; it is **not** a claim that these modules or the six-layer validator have already been implemented or tested.

## 1. Architectural decisions and responsibilities

The system prepares a personalized **practice exam** consisting of open-ended questions. The backend receives the student profile, the teacher-selected topic, and the requested number of questions. The components have distinct responsibilities:

1. **Backend / Rule-based Exam Planner:** determine Default versus Personalized mode using the profile's `evidence_count`; then plan the exam's difficulty and target skills, and select suitable mathematical problems from the dataset.
2. **Content & Expression Planner:** select a mathematically compatible real-world context and `generate_type` (`direct` or `indirect`).
3. **Local Qwen Generator:** verbalize an **already selected** mathematical problem as one Vietnamese question without altering the facts, constraints, or expected answer.
4. **Validator:** apply five automated validation layers; the sixth layer is teacher review. Reject, flag, or request bounded regeneration as appropriate.
5. **Exam Assembler:** number accepted candidates, associate answers from the dataset, and output an exam draft for teacher approval.

**Mathematics is deterministic where supported:** the reference answer comes from verified dataset data or a deterministic answer rule, **not from Qwen's guess**. The use of pretrained Qwen3-1.7B through local Ollama satisfies the baseline AI integration experiment; it is not a model trained by the team.

**Important separation:** `evidence_count` determines **whether there is enough profile evidence to enable the Personalized Blueprint**. It does **not** directly measure skill weakness. Skill prioritization is a separate planning decision using fields supplied by M3 / backend and an agreed priority policy.

## 2. Completed local Qwen baseline: setup and I/O contract

This section is a historical record of Issue #6; it does **not** define the final production Qwen JSON contract.

- **Local inference server:** `http://127.0.0.1:11434` (Ollama; no external inference API).
- **Model:** `qwen3:1.7b` (quantization `Q4_K_M`).
- **Baseline options:** `temperature=0`, `seed=42`, `num_predict=250`, `think=false`, `stream=false`.
- **C01:** choose three out of eight students, no replacement, order irrelevant; Python expected answer `C(8,3) = 56`.
- **C02:** assign three distinct roles among seven students without repeating a student; Python expected answer `A(7,3) = 210`.
- **Historical Qwen JSON schema:** `question: string`, `task: enum`, `n: int`, `k: int`, `answer: int`.
- **Runner:** `src/ai/qwen_spike.py`.
- **Evidence:** `eval/results/baseline_spike_output.json` (real run data, not simulated).

**Baseline prompt skeleton:**

```text
Bạn là người soạn đề Toán tổ hợp lớp 10.
Viết đúng MỘT câu hỏi tự luận bằng tiếng Việt từ đặc tả toán học.
Giữ nguyên số liệu, phép toán, quan hệ và mọi điều kiện.
Không tự ý thêm/bớt điều kiện làm thay đổi đáp án.
Trả JSON theo schema thử nghiệm: {question, task, n, k, answer}.
```

The baseline code checks JSON shape and simple metadata / numerical consistency, but **cannot prove that the entire Vietnamese word problem is mathematically equivalent**. Teacher review is required.

## 3. Actual hardware and latency measurements

**Test date:** 2026-10-19  
**Tester:** Phạm Yến Trân (AI & Algorithms Lead)

| Measurement | Actual result |
|---|---|
| Operating system | Windows 11 (`10.0.26200`) |
| Python / Ollama | Python `3.14.4` / Ollama `0.40.6` |
| CPU | Intel64 Family 6 Model 186 Stepping 2, GenuineIntel; 16 logical CPU cores |
| Installed system RAM | `24,118.2 MiB` (about `23.55 GiB`) |
| NVIDIA GPU / VRAM | No NVIDIA GPU detected by the measurement script; `nvidia-smi` unavailable, VRAM recorded as `N/A` |
| Model / quantization | `qwen3:1.7b` / `Q4_K_M` |
| Model digest | `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` |
| Model file size | `1,359,293,444 bytes` |
| C01: API wall time / Ollama total / model load | `5.403 s` / `5.388 s` / `1.541 s` |
| C01: RAM before / sampled peak / increase | `14,679.3 MiB` / `16,599.3 MiB` / `+1,920.0 MiB` |
| C01: JSON / metadata validation | Passed; teacher review not completed |
| C02: API wall time / Ollama total / model load | `4.208 s` / `4.193 s` / `0.005 s` |
| C02: RAM before / sampled peak / increase | `16,599.4 MiB` / `16,696.1 MiB` / `+96.8 MiB` |
| C02: JSON / metadata validation | Passed; teacher review not completed |

**Measurement caveats:**

- API wall time uses Python `time.perf_counter`; Ollama timing fields were converted from nanoseconds to seconds.
- `psutil` samples **total system-used RAM**, not memory exclusively owned by the Qwen process.
- NVIDIA VRAM entries are `null`/`N/A` because the measurement method was unavailable; **do not interpret this as zero VRAM usage or proof that no other GPU exists**.
- Sampling can miss transient peaks. The second call is a warm-model observation; only two cases were tested, so no broad speed or quality claim is justified.

## 4. Profile JSON and rule-based Blueprint pseudocode (Issue #19)

### 4.1. Contract and scope

**Source of truth:** M3 provides a **static Student Profile JSON** with `evidence_count` and skill-related `mastery_score` values already available. This module **does not** iterate over `graded_records`, calculate normalized marks, update mastery, or perform AI-based grading.

For the MVP branch decision, `evidence_count` is read as a **student-level evidence count supplied by M3**. If M3's actual profile stores counts only per skill, M3 and the backend must expose one agreed student-level value **before** calling this branching function; M4 must not silently invent an aggregation formula.

**Illustrative interface** (field layout is an integration example, not a claim about M3's finalized JSON):

```json
{
  "student_id": "HS001",
  "grade_level": 10,
  "evidence_count": 3,
  "skill_mastery": [
    {"skill_id": "SK02", "mastery_score": 2.0},
    {"skill_id": "SK04", "mastery_score": 3.5}
  ],
  "priority_skill_ids": ["SK02"]
}
```

Here the numbers `2.0` and `3.5` are **illustrative input values only**. This document does not define their scale or compute them. The priority list is optional upstream planning metadata; if it is not supplied, the Exam Planner must use a separately specified interpretation of the mastery-score scale rather than assume that a particular number means “weak.”

**Issue #19's mandatory branching rule:**

| Student-level `evidence_count` | Evidence category | Blueprint branch |
|---:|---|---|
| `0` | `no_data` | `default` |
| `1` or `2` | `partial` | `default` |
| `>= 3` | `sufficient` | `personalized` |

The three categories describe **data availability**, not a student's absolute knowledge or proficiency.

### 4.2. Pseudocode: classify evidence and select Blueprint

```text
FUNCTION classify_evidence(student_profile):
    count = student_profile.evidence_count  // Provided by M3

    IF count IS MISSING OR count IS NOT A NONNEGATIVE INTEGER:
        RETURN {status: "invalid_profile", reason: "Invalid evidence_count"}

    IF count == 0:
        RETURN {status: "no_data", mode: "default"}

    IF count <= 2:
        RETURN {status: "partial", mode: "default"}

    RETURN {status: "sufficient", mode: "personalized"}
END FUNCTION


FUNCTION select_exam_blueprint(student_profile, topic_id, question_count):
    IF student_profile IS MISSING OR student_profile.student_id IS MISSING:
        RETURN {status: "invalid_request", reason: "Student profile required"}

    IF question_count IS NOT A POSITIVE INTEGER:
        RETURN {status: "invalid_request", reason: "Invalid question_count"}

    IF topic_id IS MISSING OR topic_id IS NOT SUPPORTED:
        RETURN {status: "invalid_request", reason: "Unsupported topic"}

    category = classify_evidence(student_profile)
    IF category.status == "invalid_profile":
        RETURN category  // Do not infer or fabricate evidence

    IF category.mode == "default":
        blueprint = DEFAULT_BLUEPRINT(topic_id, question_count)
    ELSE:
        // evidence_count >= 3: use the Personalized branch.
        // Read mastery_score / skill priorities from M3's profile;
        // never recalculate mastery inside this module.
        blueprint = PERSONALIZED_BLUEPRINT(
            student_profile, topic_id, question_count
        )

    IF blueprint CANNOT SATISFY question_count OR topic REQUIREMENTS:
        RETURN {
            status: "insufficient_question_bank",
            missing_slots: blueprint.missing_slots
        }

    RETURN {
        status: "ready",
        student_id: student_profile.student_id,
        topic_id: topic_id,
        evidence_status: category.status,
        generation_mode: category.mode,
        blueprint: blueprint
    }
END FUNCTION
```

`DEFAULT_BLUEPRINT` and `PERSONALIZED_BLUEPRINT` represent the planners' interfaces, not completed implementations in `qwen_spike.py`. The **threshold and branch names above are fixed by Issue #19**; policy details inside those planners are described separately in Section 7.

### 4.3. Branch tests and examples

| Case | Profile input | Expected result |
|---|---|---|
| New student | `evidence_count = 0` | `no_data` → Default Blueprint |
| Some evidence | `evidence_count = 1` | `partial` → Default Blueprint |
| Some evidence | `evidence_count = 2` | `partial` → Default Blueprint |
| Enough evidence | `evidence_count = 3` | `sufficient` → Personalized Blueprint |
| More evidence | `evidence_count = 5` | `sufficient` → Personalized Blueprint |
| Invalid profile | negative, missing or non-integer count | `invalid_profile`; request corrected data |

**Boundary:** The student may need substantial support even with `evidence_count >= 3`, and may show strengths even with only two evidence records. `evidence_count` selects the branch; the separate skill information influences **what the personalized branch does**.

## 5. Risks and fallback behavior

| Risk / edge case | Handling / limitation |
|---|---|
| Missing or invalid student-level `evidence_count` | Reject/flag malformed profile and request M3/backend correction; no invented aggregation |
| `evidence_count` is 0, 1 or 2 | Always use Default Blueprint, as required by Issue #19 |
| Sufficient evidence but missing/undocumented skill priorities or score scale | The Personalized branch is selected; flag its missing input rather than invent skill rankings |
| Requested topic or question count unsupported by bank | Return `insufficient_question_bank` / explicit error, not an incorrect substitute |
| Local model unavailable, out of memory, timeout | Log runtime error; allow configured fallback or stop; never fabricate generated content |
| Qwen produces invalid JSON or changes constraints | Validator rejects or flags for review; bounded retry through backend orchestration |
| Correct syntax but incorrect mathematical semantics | Automated checks are incomplete; require teacher review before release |
| Repeated surface paraphrases | Diversity checker compares candidates and already-used items; do not assume new wording means new mathematics |
| Non-NVIDIA VRAM cannot be sampled | Report `N/A`, not `0` |
| Student data in Qwen prompt | Send only required mathematical facts and minimal non-sensitive context; do not include identifying student information |

## 6. Actual results and interpretation

**Baseline status: completed on local hardware on 2026-10-19.**

- Two Vietnamese combinatorics questions were generated by local Qwen3-1.7B.
- Both outputs passed the baseline JSON and metadata checks (`2/2`).
- Their deterministic Python reference answers were `56` and `210`, respectively.
- Measured API wall times were `5.403 s` and `4.208 s`.
- System RAM was sampled; NVIDIA VRAM metrics were unavailable.
- **Teacher semantic review has not been recorded**. Results do not establish a general mathematical-correctness rate.
- The Profile-driven branching pseudocode is aligned to Issue #19 but is **not** evidence of an integrated runtime with M3's real Profile JSON.

## 7. Planned MVP question-generation architecture (product-design proposal)

> This section captures the team's developing product idea, **not additional acceptance criteria stated by Issue #19**. It also does not overwrite the measured baseline in Sections 2–3.

### 7.1. Input and ordered pipeline

The backend receives: `student_profile`, `question_count`, and `topic_id` selected by the teacher. The current MVP supports `topic_id = "combinatorics"`, but the field remains for future subjects/topics.

```text
Student Profile + Teacher Request (topic_id, question_count)
    -> Rule-based Exam Planner (Section 4: Default / Personalized)
    -> Choose suitable mathematical problems from Dataset
    -> Content & Expression Planner (context + direct / indirect)
    -> Local Qwen Generator (Vietnamese question candidates)
    -> Validator (five automated layers)
    -> Exam Assembler (draft + numbered questions + stored answers)
    -> Teacher review (sixth validation layer)
    -> Approved exam, or revision / rejection
```

**Dataset-side mathematical problem record (illustrative):** retain `question_id` (or a corresponding stable problem identifier), `topic_id`, `skill_ids`, four-level `difficulty`, machine-readable mathematical conditions and parameters, plus a **verified reference answer and solution method**. A finished Vietnamese `content` string and `generate_type` are **not required in the mathematical source record**. If the existing SQL `Questions` table continues to store rendered `content`, the dataset/backend team should distinguish **source mathematical data** from **generated wording** in its storage model.

### 7.2. Rule-based planning policy: skills and difficulty

**Seven agreed skill groups** (IDs below are suggested interface labels, not pre-existing canonical SQL IDs):

| Example ID | Skill group |
|---|---|
| `SK01` | Basic calculation ability (Năng lực tính toán cơ bản) |
| `SK02` | Understanding and representing problems (Khả năng hiểu và biểu diễn bài toán) |
| `SK03` | Addition and multiplication rules (Quy tắc cộng, quy tắc nhân) |
| `SK04` | Permutations, arrangements, combinations (Hoán vị, chỉnh hợp, tổ hợp) |
| `SK05` | Conditions and constraints analysis (Phân tích điều kiện và ràng buộc) |
| `SK06` | Solution strategy selection (Lựa chọn chiến lược giải) |
| `SK07` | Checking and evaluating results (Kiểm tra và đánh giá kết quả) |

**Four agreed difficulty labels:**

- `recognition` – Nhận biết
- `comprehension` – Thông hiểu
- `application` – Vận dụng
- `advanced_application` – Vận dụng cao

The previously mentioned 1–6 `difficulty` scale is **not used** in this target design.

**Default difficulty distribution proposed for the project:** 20% / 40% / 30% / 10%, respectively. With 10 questions this becomes 2 / 4 / 3 / 1. For other requested counts, use a deterministic rounding rule that always sums to `question_count`; a category may receive zero questions for very short exams. This distribution reflects the product design discussed by M4, **not a numerical threshold introduced by Issue #19**.

**Personalized policy proposal:** initially keep the same four-level difficulty distribution but **prioritize skills identified for additional practice**. The backend consumes priority information from the profile or an approved policy interpreting M3's `mastery_score`; **it does not compute mastery**. A pilot split could be 60% priority-skills coverage and 40% other skill coverage, provided the bank can meet it; this is an adjustable planning policy, not an Issue #19 rule.

Planning should prefer topic and skill alignment, adequate cognitive-level distribution, and avoidance of excessive repeats. Do not label a question with a skill unless solving it genuinely exercises that skill. If the bank cannot satisfy the plan, report the missing slots.

### 7.3. Content & Expression Planner

The backend selects a compatible **context** (e.g., choosing distinct students for a group, assigning committee roles) **after** selecting the mathematical problem. Context choices must preserve the original mathematical meaning; an unconstrained random noun may change whether objects are distinguishable or whether order matters.

The finalized `generate_type` enumeration has **exactly two values**:

- `direct`: state useful numerical facts and constraints clearly; make the problem structure readily recognizable.
- `indirect`: use an understandable situation requiring the learner to identify the mathematical structure; **do not** insert new mathematical conditions or irrelevant distractors.

`generate_type` is independent of the four-level `difficulty` label.

**Expression-personalization proposal:** for a skill requiring stronger support, initially choose more `direct` questions and fewer `indirect` questions (e.g., a configurable 80/20 split). This is a **presentation policy** determined before calling Qwen, **not** a property inferred from `evidence_count` and **not** a rule that Qwen should choose on its own. If no reliable support-level indicator exists, use an explicit configured default rather than infer student weakness from evidence volume.

### 7.4. Pseudocode: local Qwen generator (Module 4 only)

```text
FUNCTION qwen_generate_question(
    problem_data,
    context,
    generate_type,
    model_config,
    previous_validation_errors = []
):
    IF problem_data IS MISSING OR context IS MISSING:
        RETURN {status: "generation_error", reason: "Missing input"}

    IF generate_type NOT IN ["direct", "indirect"]:
        RETURN {status: "generation_error", reason: "Invalid generate_type"}

    IF generate_type == "direct":
        expression_instruction =
            "State the provided mathematical facts clearly and explicitly."
    ELSE:
        expression_instruction =
            "Use a natural situation so students must identify the math structure."

    prompt = BUILD_PROMPT(
        mathematical_facts = problem_data,
        approved_context = context,
        expression_instruction = expression_instruction,
        feedback = previous_validation_errors,
        constraints = [
            "Write exactly one Vietnamese open-ended question",
            "Preserve ALL original mathematical quantities and constraints",
            "Do not add/remove mathematical conditions or irrelevant facts",
            "Do not change the operation, order rules or object distinctions",
            "Do not generate or recalculate the reference answer",
            "Return JSON containing only a question string"
        ]
    )

    start_time = CURRENT_TIME()

    TRY:
        raw_response = OLLAMA_GENERATE(
            model = model_config.model_name,
            prompt = prompt,
            temperature = model_config.temperature,
            seed = model_config.seed,
            stream = FALSE,
            format = "json"
        )
    CATCH inference_error:
        RETURN {status: "generation_error", reason: inference_error}

    RETURN {
        status: "pending_validation",
        raw_response: raw_response,
        generate_type: generate_type,
        model: model_config.model_name,
        latency_seconds: CURRENT_TIME() - start_time
    }
END FUNCTION
```

**Qwen's proposed response contract:** `{"question": "..."}`. The wrapping application retains `problem_data`, the verified answer, `skill_ids`, `difficulty`, and the requested `generate_type`. Qwen does **not** author those authoritative fields. The first validator layer parses/checks Qwen's returned JSON.

### 7.5. Validation and bounded retry (Backend orchestration)

**Six validation layers:** (1) JSON structure, (2) mathematical facts and constraints, (3) direct/indirect expression fidelity, (4) answer equivalence against the reference mathematical problem, (5) diversity / near-duplicate checks, and (6) human teacher review. Layers 1–5 are intended for automated screening. Layer 6 is approval of the prepared draft; automated `pass` does not equal `teacher_approved`.

**Answer-checking rule:** do not simply ask the same Qwen model to solve its own generated question and trust agreement. Where supported, parse/verify constraints and evaluate with deterministic code; if semantic equivalence cannot be established, flag for teacher review. Another AI may help extract conditions as a secondary signal, not as sole mathematical proof.

```text
FUNCTION create_candidate_with_retry(problem_data, context, generate_type, config):
    errors = []

    FOR attempt FROM 1 TO config.max_attempts:
        attempt_config = COPY(config)
        attempt_config.seed = config.seed + attempt - 1

        candidate = qwen_generate_question(
            problem_data, context, generate_type,
            attempt_config, previous_validation_errors = errors
        )

        IF candidate.status == "generation_error":
            errors = [candidate.reason]
            CONTINUE

        verdict = VALIDATE_AUTOMATED_LAYERS_1_TO_5(
            original_problem = problem_data,
            approved_context = context,
            requested_generate_type = generate_type,
            generated_response = candidate.raw_response
        )

        IF verdict.status == "pass":
            RETURN {status: "pending_teacher_review", candidate: candidate}

        IF verdict.status == "needs_review":
            RETURN {status: "pending_teacher_review", candidate: candidate,
                    review_notes: verdict.errors}

        errors = verdict.errors  // FAIL: retry with a bounded attempt count

    RETURN {status: "generation_failed", reasons: errors}
END FUNCTION
```

This retry function belongs to **backend orchestration**, not to the Qwen inference component itself. Repeated seeds can increase variation but **do not guarantee** a distinct or correct output. Diversity generation for multiple alternative phrasings is a separate optional feature.

### 7.6. Proposed exam JSON output and release gate

The **teacher/backend version** of an assembled exam contains numbered question text, original source identifiers, difficulty, skill IDs, generate type, stored reference answers, validator results, and teacher-review status. The **student version must not contain reference answers or internal validation metadata**.

```json
{
  "exam_id": "EXAM001",
  "student_id": "HS001",
  "topic_id": "combinatorics",
  "question_count": 1,
  "generation_mode": "personalized",
  "status": "pending_teacher_review",
  "questions": [
    {
      "question_order": 1,
      "question_id": "Q001",
      "skill_ids": ["SK02", "SK04"],
      "difficulty": "comprehension",
      "generate_type": "indirect",
      "content": "Một lớp có 8 học sinh. Giáo viên muốn lập nhóm 3 bạn; hai nhóm chỉ khác nhau khi có ít nhất một thành viên khác nhau. Có bao nhiêu nhóm?",
      "answer": {
        "correct_answer": "56",
        "explanation": "C(8,3) = 56"
      },
      "validation": {
        "auto_status": "pass",
        "teacher_approved": false
      }
    }
  ]
}
```

This one-question JSON is an **interface example**, not a recorded Qwen output and not an example of the 20/40/30/10 distribution (which applies when the count allows it). The actual exam assembler must use the requested number of questions or report unsatisfied slots. Source dataset identities and generated-question identities should remain traceable even if they are stored as separate records.

## 8. Implementation boundaries and next steps

**Already demonstrated (Issue #6):** local Qwen inference for two sample cases, a repeatable result JSON, latency measurements, and system RAM sampling.

**Documentation aligned for Issue #19:** no `graded_records` loop; use M3's static Profile JSON, mandatory 0/1–2/default and >=3/personalized branches; keep completed baseline numbers. This alignment is a **document/pseudocode change**, not a claim of integrated code.

**Next engineering steps (separate implementation work):**

1. Agree with M3/backend on the real Profile JSON field paths, the meaning of the **student-level** `evidence_count`, and the interpretation scale of incoming `mastery_score`.
2. Define machine-readable mathematical problem records and context-compatibility rules; do not require production Qwen to invent question IDs or answers.
3. Implement the two-branch Exam Planner and deterministic distribution of requested question counts.
4. Implement the Content & Expression Planner, with only `direct` and `indirect`.
5. Adapt `qwen_spike.py` into a standalone generation adapter matching Section 7.4, without changing historical baseline evidence.
6. Build an error-focused test corpus for all five automated validators, including deliberate new-condition, changed-number, order/replacement, duplicate, and unclear-wording cases; obtain teacher review labels for semantic correctness.
7. Integrate bounded retries, exam assembly, and teacher approval; keep answers out of student-facing responses.

**Excluded from this stage:** teacher grading of completed student solutions, AI updating learner mastery, automatic fine-tuning, or unrestricted invention of mathematical structures.
