# MIRA local Qwen benchmark

Experimental extraction and wording evidence only. No autonomous student-grading claim.

Warm-up requests are recorded separately and excluded from warm/cold case metrics. Wall latency includes failed requests; do not rank a failing configuration by speed alone. Durations in JSON/CSV are Ollama nanoseconds; wall latency is seconds.

| Configuration | Task | Phase | N | Schema rate | Labeled step accuracy | Alternative rate | Mean s | Median s | Tokens/s | Review rate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3:4b-q4_K_M; think=false; limit=256 | parser | warmup | 1 | 1.000 | 0.667 | n/a | 25.466 | 25.466 | 11.757 | 1.000 |
| qwen3:4b-q4_K_M; think=false; limit=256 | parser | warm | 12 | 1.000 | 0.280 | 0.500 | 12.332 | 12.009 | 11.893 | 0.917 |

## Accuracy and uncertainty

Phraser answer preservation, natural Vietnamese, hallucinated assumptions and full semantic equivalence require manual review. Digit and lexical checks are filters, not mathematical proof. Step accuracy is exact labeled line/expression/purpose/reference/flag agreement, with all expected steps (including failed requests) in the denominator. It is not general grading accuracy.

Incorrect-answer false acceptance is a proxy: known-invalid reasoning extracted without an error/ambiguity flag or review request. Missing/invalid/truncated outputs are failures, never accepted solutions. A zero proxy count with unevaluable requests is not safety evidence.

- qwen3:4b-q4_K_M|think=false|limit=256 / parser / warm: statuses={'incorrect_result': 11, 'pass_labeled': 1}; false acceptance proxy=2; missed uncertainty=3; unevaluable=0; residency={'warm_observed': 12}; violations={'purpose:2': 6, 'reference:1': 4, 'reference:2': 3, 'purpose:3': 1, 'purpose:4': 1, 'flags:2': 2, 'purpose:1': 1, 'flags:1': 4, 'invented_or_nonmathematical_lines:[2]': 1, 'invented_or_nonmathematical_lines:[2, 3]': 1, 'missing_teacher_review': 1, 'duplicate_line:2': 1}

## Paired thinking comparison

Matched requests: 0. Non-thinking labeled regressions: 0; alternative-method regressions: 0; uncertainty regressions: 0.

See paired_modes in results.json for each case. These counts compare the same model, token cap, prompt, seed, phase and repeat. Both modes can fail; zero regressions does not establish equivalence. Thinking may consume the token budget before emitting JSON.

## Limitations and selection

Choose the fastest warm configuration only after inspecting failures, parser labels, alternative methods and uncertainty handling, and manually confirming Phraser semantics. No automatic production recommendation is made. This small synthetic corpus is not teacher certified and does not cover OCR, handwriting, all notation or unseen solution strategies. Lexically different equivalent expressions may need manual adjudication.

Cold means the target model was observed absent from /api/ps before inference; it does not clear the OS disk cache. Warm observations do not imply a cold prompt cache. Concurrent Ollama users, hardware scheduling, fixed configuration order and prompt caching can affect comparisons. Model metadata and fixture/request hashes are recorded.
