# N03 – Algorithm & AI: Local Qwen Baseline Spike

**Issue:** #6 · **Owner:** M4 / AI & Algorithms Lead · **Reviewer:** M5 / Architecture Lead  
**Status:** Local baseline completed; pending review.
**Scope:** only 1–2 baseline calls + resource monitoring + profile pseudocode. **No fine-tuning / database / UI needed.**

## 1. Architectural decision & problem framing

- **R4:** Test whether an already pretrained local Qwen model can transform a tightly specified combinatorics idea into a Vietnamese open-ended problem in JSON.
- **R2:** Math answer comes from deterministic Python (`math.comb`, `math.perm`) rather than LLM arithmetic.
- **R5/R7:** A malformed output or mismatched metadata is rejected; acceptable JSON is **still pending teacher review** because string/number checks cannot guarantee semantic equivalence.
- **Important:** `qwen3:1.7b` is a **baseline local model**, not an AI custom-trained by the group.

## 2. Setup, input & output contract

- Ollama server: `http://127.0.0.1:11434` (no cloud service).
- Model: `qwen3:1.7b` (use `qwen3:0.6b` only if hardware is insufficient; record the change).
- `temperature=0`, `seed=42`, `num_predict=250`, `think=false`, `stream=false`.
- Prompt 1: select 3 from 8 students without order/replacement. Expected answer `C(8,3) = 56`.
- Prompt 2: assign 3 **distinct roles** among 7 students (without repetition). Expected answer `A(7,3) = 210`.
- Response JSON: `question: string`, `task: enum`, `n: int`, `k: int`, `answer: int`.
- Script saves full records (including response, validation errors, Ollama metrics, machine details) to `eval/results/baseline_spike_output.json` **only after a real local run**.

**Prompt structure** (full prompt is built in `src/ai/qwen_spike.py`):

```text
Bạn là người soạn đề Toán tổ hợp lớp 10. Viết đúng MỘT câu hỏi tự luận tiếng Việt
... KHÔNG đổi n, k, không thêm điều kiện, không thay đổi ý nghĩa về thứ tự/vai trò.
Trả JSON {question, task, n, k, answer} đúng schema.
ĐẶC TẢ: {"task": "choose_group", "n": 8, "k": 3, ... ,"expected_answer": 56}
```

## 3. Hardware & latency – fill from actual experiment

| Field | Actual value |
|---|---|
| Test date, tester | 2026-10-19 · Pham Yen Tran (AI & Algorithm lead) |
| OS, Python, Ollama version | Windows 11 10.0.26200 · Python 3.14.4 · Ollama 0.40.6 |
| CPU | Intel64 Family 6 Model 186 Stepping 2, GenuineIntel (16 logical cores) |
| Installed RAM (GiB) | ~23.6 GiB (24 118.2 MiB total) |
| GPU model, installed VRAM, or `N/A` | N/A (no NVIDIA GPU detected; integrated graphics) |
| Model name, quantization, digest | `qwen3:1.7b` · Q4_K_M · `8f68893c…d1730e7` (1 359 293 444 B) |
| Run 1 (C01): wall time / model total / load (s) | 5.403 s / 5.388 s / 1.541 s |
| Run 1 (C01): system RAM before/peak (MiB) | 14 679.3 / 16 599.3 MiB (Δ +1 920.0 MiB) |
| Run 1 (C01): NVIDIA VRAM before/peak (MiB) or `N/A` | N/A (nvidia-smi unavailable) |
| Run 1 (C01): JSON validity, content/teacher check | JSON valid ✓ · metadata match ✓ · **needs_teacher_review** |
| Run 2 (C02): wall time / model total / load (s) | 4.208 s / 4.193 s / 0.005 s (model already loaded) |
| Run 2 (C02): system RAM before/peak (MiB) | 16 599.4 / 16 696.1 MiB (Δ +96.8 MiB) |
| Run 2 (C02): NVIDIA VRAM before/peak (MiB) or `N/A` | N/A (nvidia-smi unavailable) |
| Run 2 (C02): JSON validity, content/teacher check | JSON valid ✓ · metadata match ✓ · **needs_teacher_review** |

**Measurement notes:**

- `wall time` = measured Python HTTP request duration (`time.perf_counter`).
- `total_duration`, `load_duration`, `eval_duration` = **Ollama** metrics, converted from nanoseconds to seconds.
- Python `psutil` samples total **system-wide used RAM** during request, not exclusively the model.
- `nvidia-smi` samples **total NVIDIA VRAM used**, not the Qwen process alone. If absent (e.g., Intel integrated graphics), store `null / N/A`, **not 0**.
- Peak sampling may miss short-lived maxima; keep other apps stable for comparison.
- Record both cold model load and any subsequent warm run when comparing; 2 prompts are only a spike, not a reliable performance benchmark.
- Prompt acceptance: valid JSON + matching numeric metadata + **human semantic review** for not adding/removing conditions.

## 4. Deterministic learner profile pseudocode

> **Design status: Pending team decisions.** This section describes the deterministic data flow, not an approved learner-mastery formula. The team has **not yet decided** how to combine results into `mastery_score`, how much evidence is sufficient, or how many questions each blueprint category should contain. The pseudocode deliberately leaves these as configurable/TBD rules.
>
> **Important distinction:** `score / max_score` is a **normalized score for an individual graded record**, **not** the student's final `mastery_score`. The labels `sufficient`, `partial`, and `no_data` describe **evidence availability**, not whether the student is strong or weak.

### 4.1 Collect teacher-verified evidence and normalize individual scores

**Input:** Teacher-graded question results, linked skill IDs, and teacher-selected error tags.  
**Output:** Valid evidence for each skill, optional normalized record scores, evidence count, and data sufficiency status. **Do not recalculate mastery yet.**

```text
FUNCTION skill_evidence_summary(student_id, skill_id, graded_records):
    evidence = []
    normalized_scores = []

    FOR each record IN graded_records:
        IF record.student_id != student_id:
            CONTINUE
        IF skill_id NOT IN record.skill_ids:
            CONTINUE
        IF record.teacher_verified != TRUE:
            CONTINUE  // Unreviewed answers are not assessed evidence

        evidence.append({
            question_id: record.question_id,
            result: record.result,       // correct / partial / incorrect
            error_tags: record.error_tags // Errors confirmed by teacher
        })

        IF is_number(record.score) AND is_number(record.max_score)
           AND record.max_score > 0
           AND 0 <= record.score <= record.max_score:
            normalized_scores.append({
                question_id: record.question_id,
                value: record.score / record.max_score
            })
        ELSE:
            log_missing_or_invalid_score(record)
            // Do NOT substitute score = 0 for missing/invalid marks.
            // Teacher-confirmed correctness/errors can still be retained.

    evidence_count = COUNT_DISTINCT(question_id IN evidence)

    IF evidence_count == 0:
        data_status = "no_data"
    ELSE IF meets_sufficiency_policy(evidence, POLICY_TBD):
        data_status = "sufficient"
    ELSE:
        data_status = "partial"

    // TODO: Define the team's learner-mastery calculation policy.
    // Do not derive mastery_score from normalized_scores at this stage.
    RETURN {
        skill_id, evidence, normalized_scores,
        evidence_count, data_status,
        mastery_update: "pending_policy"
    }
END FUNCTION
```

**Design notes:**

- `record.score / record.max_score` allows comparison of *individual marked records* on a 0–1 scale. It is **not** automatically averaged or treated as mastery.
- `evidence_count` counts distinct teacher-reviewed questions for the skill, **not** the number of error tags. One question can be linked to multiple skills, but evidence is recorded separately for each related skill.
- `meets_sufficiency_policy(...)` is a **placeholder**. Criteria and thresholds require team approval; no hard-coded `MIN_EVIDENCE = 3` is assumed.
- If there is no verified evidence, use `no_data`; **unknown ability must not be treated as 0% mastery**.

### 4.2 Select a safe exam blueprint when learner data is incomplete

**Goal:** Select a suitable *mode* for preparing a practice exam without inventing a mastery score or fixed question distribution.

```text
FUNCTION select_exam_blueprint(student_id, target_skills, question_count):
    summaries = []

    FOR each skill_id IN target_skills:
        summaries.append(skill_evidence_summary(student_id, skill_id))

    IF EVERY summary.data_status == "no_data":
        mode = "default_diagnostic"
        blueprint = load_teacher_approved_default(question_count)

    ELSE IF ANY summary.data_status != "sufficient":
        mode = "partial_data"
        blueprint = load_teacher_approved_partial_blueprint(question_count)
        IF blueprint IS NOT AVAILABLE:
            blueprint = load_teacher_approved_default(question_count)

    ELSE IF mastery_policy_is_approved() AND mastery_values_are_available():
        mode = "personalized"
        blueprint = apply_approved_adaptive_rules(summaries, question_count)

    ELSE:
        // Enough evidence, but the mastery algorithm is still undecided.
        mode = "default_pending_mastery_policy"
        blueprint = load_teacher_approved_default(question_count)

    IF blueprint IS NOT AVAILABLE:
        RETURN {status: "needs_configuration", reason: "No approved blueprint"}

    VALIDATE total_questions(blueprint) == question_count
    RETURN {status: "ready", mode, blueprint}
END FUNCTION
```

**Design notes:**

- A **default blueprint** is a teacher-approved structure for an initial practice/diagnostic exam. Its skill/difficulty distribution is **TBD**, not fixed at 2–2–1 or any other ratio.
- With **partial data**, the system may use a teacher-approved mixed diagnostic/review blueprint; if none is defined, it falls back to the approved default.
- `personalized` mode is only activated **after** the mastery formula and adaptive selection rules have been approved and implemented. Sufficient evidence alone does not imply mastery is available.
- `question_count` is supplied by the teacher. Do not assume every exam contains five questions.

### 4.3 Example scenarios and pending decisions

| Scenario | Available evidence | Data status | Safe behavior |
|---|---|---|---|
| A: New student | No teacher-verified question results | `no_data` | Use the approved default diagnostic blueprint |
| B: Some graded work | At least one valid teacher-reviewed result, but the future sufficiency policy is not met | `partial` | Use a teacher-approved partial-data blueprint or fall back to default |
| C: Sufficient graded work | Evidence meets the future team-approved sufficiency policy | `sufficient` | Personalize only if mastery/adaptive rules are approved; otherwise use the default |

**Decisions deferred to the team:** (1) how `mastery_score` is calculated and updated; (2) whether/how difficulty, recency, and teacher-selected errors affect it; (3) sufficiency thresholds by skill; (4) blueprint proportions and adaptive rules. None of these decisions is claimed to be implemented in the current Qwen baseline spike.

## 5. Risks, fallbacks and validation

| Risk | Mitigation |
|---|---|
| Model unavailable, out of memory, timeout | Log `runtime_error`; lower model size (with recorded change), or stop spike; never invent success |
| JSON syntax/type wrong | Structured schema request + local validation; record failure |
| Correct JSON but mathematically changed word problem | Numeric/metadata checks **plus teacher manual review**; baseline does NOT ensure semantic equivalence |
| Missing marks, `max_score=0` | Exclude invalid item with log; status partial/no_data from remaining evidence |
| No student history | Default diagnostic blueprint, mastery=null, not 0 |
| `nvidia-smi` absent | Report VRAM not measurable / `N/A`, record GPU type manually |


## 6. Results & next steps

**Status:** Local baseline experiment completed.

The Qwen3-1.7B model was successfully tested locally using Ollama.

**Experimental results:**
- Successfully generated 2 combinatorics questions.
- Both outputs passed JSON and metadata validation.
- C01 inference latency: 5.403 seconds.
- C02 inference latency: 4.208 seconds.
- System RAM usage was recorded successfully.
- NVIDIA VRAM measurements were unavailable.
- Generated questions are pending teacher review.

**Limitations:**
- Only 2 test cases were evaluated.
- Valid JSON does not guarantee mathematical correctness.
- RAM measurements represent system-wide usage, not model-exclusive memory.

**Next steps:**
- Conduct additional tests with more question types.
- Evaluate the mathematical accuracy and linguistic quality of generated questions.
- Finalize the mastery calculation method through team discussion.
- Integrate the validated question generation module into the system.

**Future work beyond Issue #6:** Larger benchmark dataset, question templates, generator integration, teacher review UI, and fine-tuning if justified.
