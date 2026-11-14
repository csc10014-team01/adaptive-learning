# MIRA local Qwen benchmark

Experimental extraction and wording evidence only. No autonomous student-grading claim.

Warm-up requests are recorded separately and excluded from warm/cold case metrics. Wall latency includes failed requests; do not rank a failing configuration by speed alone. Durations in JSON/CSV are Ollama nanoseconds; wall latency is seconds.

| Configuration | Task | Phase | N | Schema rate | Labeled step accuracy | Alternative rate | Mean s | Median s | Tokens/s | Review rate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|

## Accuracy and uncertainty

Phraser answer preservation, natural Vietnamese, hallucinated assumptions and full semantic equivalence require manual review. Digit and lexical checks are filters, not mathematical proof. Step accuracy is exact labeled line/expression/purpose/reference/flag agreement, with all expected steps (including failed requests) in the denominator. It is not general grading accuracy.

Incorrect-answer false acceptance is a proxy: known-invalid reasoning extracted without an error/ambiguity flag or review request. Missing/invalid/truncated outputs are failures, never accepted solutions. A zero proxy count with unevaluable requests is not safety evidence.


## Paired thinking comparison

Matched requests: 0. Non-thinking labeled regressions: 0; alternative-method regressions: 0; uncertainty regressions: 0.

See paired_modes in results.json for each case. These counts compare the same model, token cap, prompt, seed, phase and repeat. Both modes can fail; zero regressions does not establish equivalence. Thinking may consume the token budget before emitting JSON.

## Limitations and selection

Choose the fastest warm configuration only after inspecting failures, parser labels, alternative methods and uncertainty handling, and manually confirming Phraser semantics. No automatic production recommendation is made. This small synthetic corpus is not teacher certified and does not cover OCR, handwriting, all notation or unseen solution strategies. Lexically different equivalent expressions may need manual adjudication.

Cold means the target model was observed absent from /api/ps before inference; it does not clear the OS disk cache. Warm observations do not imply a cold prompt cache. Concurrent Ollama users, hardware scheduling, fixed configuration order and prompt caching can affect comparisons. Model metadata and fixture/request hashes are recorded.

Dry run only: no inference and no measured accuracy or latency.
