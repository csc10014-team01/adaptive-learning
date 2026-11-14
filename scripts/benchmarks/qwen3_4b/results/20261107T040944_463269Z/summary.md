# MIRA local Qwen benchmark

Experimental extraction and wording evidence only. No autonomous student-grading claim.

Warm-up requests are recorded separately and excluded from warm/cold case metrics. Wall latency includes failed requests; do not rank a failing configuration by speed alone. Durations in JSON/CSV are Ollama nanoseconds; wall latency is seconds.

| Configuration | Task | Phase | N | Schema rate | Labeled step accuracy | Alternative rate | Mean s | Median s | Tokens/s | Review rate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3:4b-q4_K_M; think=false; limit=256 | phraser | cold | 2 | 1.000 | n/a | n/a | 9.773 | 9.773 | 14.798 | 1.000 |
| qwen3:4b-q4_K_M; think=false; limit=256 | phraser | warmup | 1 | 1.000 | n/a | n/a | 3.692 | 3.692 | 15.024 | 1.000 |
| qwen3:4b-q4_K_M; think=false; limit=256 | phraser | warm | 2 | 1.000 | n/a | n/a | 3.578 | 3.578 | 15.951 | 1.000 |
| qwen3:4b-q4_K_M; think=false; limit=256 | parser | warm | 4 | 1.000 | 0.667 | 1.000 | 12.265 | 12.022 | 13.384 | 0.500 |
| qwen3:4b-q4_K_M; think=false; limit=256 | parser | warmup | 1 | 1.000 | 0.000 | n/a | 16.448 | 16.448 | 13.692 | 1.000 |
| qwen3:4b-q4_K_M; think=true; limit=256 | phraser | cold | 2 | 0.000 | n/a | n/a | 24.929 | 24.929 | 14.034 | 1.000 |
| qwen3:4b-q4_K_M; think=true; limit=256 | phraser | warmup | 1 | 0.000 | n/a | n/a | 20.741 | 20.741 | 13.779 | 1.000 |
| qwen3:4b-q4_K_M; think=true; limit=256 | phraser | warm | 2 | 0.000 | n/a | n/a | 20.628 | 20.628 | 13.853 | 1.000 |
| qwen3:4b-q4_K_M; think=true; limit=256 | parser | warm | 4 | 0.000 | 0.000 | 0.000 | 23.208 | 22.097 | 13.198 | 1.000 |
| qwen3:4b-q4_K_M; think=true; limit=256 | parser | warmup | 1 | 0.000 | 0.000 | n/a | 27.022 | 27.022 | 13.106 | 1.000 |

## Accuracy and uncertainty

Phraser answer preservation, natural Vietnamese, hallucinated assumptions and full semantic equivalence require manual review. Digit and lexical checks are filters, not mathematical proof. Step accuracy is exact labeled line/expression/purpose/reference/flag agreement, with all expected steps (including failed requests) in the denominator. It is not general grading accuracy.

Incorrect-answer false acceptance is a proxy: known-invalid reasoning extracted without an error/ambiguity flag or review request. Missing/invalid/truncated outputs are failures, never accepted solutions. A zero proxy count with unevaluable requests is not safety evidence.

- qwen3:4b-q4_K_M|think=false|limit=256 / phraser / cold: statuses={'needs_review': 2}; false acceptance proxy=0; missed uncertainty=0; unevaluable=0; residency={'cold_observed': 2}; violations={'missing_constraint_guard:không phân biệt thứ tự|không xét thứ tự': 2}
- qwen3:4b-q4_K_M|think=false|limit=256 / phraser / warm: statuses={'needs_review': 2}; false acceptance proxy=0; missed uncertainty=0; unevaluable=0; residency={'warm_observed': 2}; violations={'missing_constraint_guard:không phân biệt thứ tự|không xét thứ tự': 2}
- qwen3:4b-q4_K_M|think=false|limit=256 / parser / warm: statuses={'pass_labeled': 2, 'incorrect_result': 2}; false acceptance proxy=0; missed uncertainty=4; unevaluable=0; residency={'warm_observed': 4}; violations={'flags:1': 2, 'invented_or_nonmathematical_lines:[2, 3]': 2, 'missing_teacher_review': 2}
- qwen3:4b-q4_K_M|think=true|limit=256 / phraser / cold: statuses={'invalid_json': 2}; false acceptance proxy=0; missed uncertainty=0; unevaluable=2; residency={'cold_observed': 2}; violations={}
- qwen3:4b-q4_K_M|think=true|limit=256 / phraser / warm: statuses={'invalid_json': 2}; false acceptance proxy=0; missed uncertainty=0; unevaluable=2; residency={'warm_observed': 2}; violations={}
- qwen3:4b-q4_K_M|think=true|limit=256 / parser / warm: statuses={'invalid_json': 4}; false acceptance proxy=0; missed uncertainty=0; unevaluable=4; residency={'warm_observed': 4}; violations={}

## Paired thinking comparison

Matched requests: 8. Non-thinking labeled regressions: 0; alternative-method regressions: 0; uncertainty regressions: 2.

See paired_modes in results.json for each case. These counts compare the same model, token cap, prompt, seed, phase and repeat. Both modes can fail; zero regressions does not establish equivalence. Thinking may consume the token budget before emitting JSON.

## Limitations and selection

Choose the fastest warm configuration only after inspecting failures, parser labels, alternative methods and uncertainty handling, and manually confirming Phraser semantics. No automatic production recommendation is made. This small synthetic corpus is not teacher certified and does not cover OCR, handwriting, all notation or unseen solution strategies. Lexically different equivalent expressions may need manual adjudication.

Cold means the target model was observed absent from /api/ps before inference; it does not clear the OS disk cache. Warm observations do not imply a cold prompt cache. Concurrent Ollama users, hardware scheduling, fixed configuration order and prompt caching can affect comparisons. Model metadata and fixture/request hashes are recorded.
