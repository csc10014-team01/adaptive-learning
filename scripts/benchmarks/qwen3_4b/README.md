# Local Qwen3 4B benchmark for MIRA

Isolated experiment for N04's Phraser and experimental AI Step Parser. Python 3.11+
standard library only; no pip packages, cloud calls, production imports, database
writes, `.env` changes, model pulls, commits, or changes to global model settings.
Delete this directory to remove the experiment.

## Repository inspection and scope

The active checkout is `Main_Project/MIRA/adaptive-learning`. The benchmark is at
`scripts/benchmarks/qwen3_4b/` inside that checkout. Run the commands below from
the active checkout root; the test discovery path includes `scripts/`.
The benchmark uses its bundled fixtures and does not import production modules.

The architecture below was inspected in `Main_Project/MVP1/adaptive-learning`
for the original implementation. It records the origin of the conventions and
bank snapshot; it is not an inventory of the active MIRA checkout:

- `src/ai/qwen_client.py`: native `POST /api/generate`, question-only JSON schema,
  `think=false`, default `qwen3:1.7b`, `num_predict=1800`. Experimental Indirect
  uses temperature 0.7. These production settings remain unchanged.
- `src/ai/prompts.py`, `contracts.py`: `ExpressionSpec` selects Direct/Indirect
  wording; answers and reference solutions stay outside Phraser prompts.
- `src/ai/template_instantiator.py`: bounded deterministic rule interpreter;
  `TemplateDefinition` has `template_content`, `parameter_rules`, `answer_rule`,
  `solution_rule`; instantiated answers and `solution_steps` belong to the backend.
- `src/api/template_repository.py`: read-only SQLite template loading with skill
  mappings. The current bank is `../../pre-work/data/sample/dataset/question_bank.db`
  relative to the application root. Its `question_templates` table has 18 rows;
  `questions` and `answers` also exist. The reference explanation column is
  literally `answers.explaination`. Bank presence does not certify every row.
- `src/validation/math_validator.py`: numeric and limited constraint checks,
  explicitly not a proof of semantic equivalence.
- `config/template_presentations.json`: author-review registry; experimental
  Indirect wording still needs teacher review.

Reuse here is deliberately limited to the actual bank snapshot, source field names,
Vietnamese task conventions, question-only Phraser contract, and separation of
mathematics from wording. We do not call the production generation service or API,
instantiate its adapters, or run its database seed scripts. Benchmark prompts are
concise experimental prompts, **not a byte-identical replay of production**.

Missing data: no labeled student-step corpus or implemented production semantic
grading contract was found in the inspected pipeline. All parser traces and labels
here are synthetic benchmark data, not an official MIRA grading schema. There are
no teacher-certified Indirect fixtures or automated Vietnamese semantic oracle.

## Files

| File | Purpose |
|---|---|
| `runner.py` | Native local Ollama calls, configuration sweep, timing, checkpoints |
| `cases.py` | 10 Phraser cases, 12 synthetic parser cases, concise prompts |
| `source_templates.json` | Five actual bank rows, source path and SHA-256 |
| `contracts.py` | Closed output JSON schemas and strict local validation |
| `scoring.py` | Independent answer enumeration and deterministic label checks |
| `reporting.py` | JSON/CSV/Markdown exports, mode comparisons and consistency |
| `test_benchmark.py` | Offline validation, failure-path and HTTP integration tests |
| `.gitignore` | Keeps `results/` and bytecode out of Git |
| `README.md` | Architecture, commands, metric definitions and limitations |

## Windows PowerShell commands

From the workspace root:

```powershell
Set-Location 'D:\HCMUS\TDTT\TH\Main_Project\MIRA\adaptive-learning'

# Check the local service and installed models; do not change production settings.
Invoke-RestMethod 'http://localhost:11434/api/tags'

# Offline verification: no model calls.
python -m unittest discover -s scripts/benchmarks/qwen3_4b -p test_benchmark.py -v
python scripts/benchmarks/qwen3_4b/runner.py --dry-run

# Small paired smoke test: 3 cases, each twice, in both modes.
python scripts/benchmarks/qwen3_4b/runner.py --cases EA0012_direct P04 P10 --runs 2

# Full initial comparison: 22 cases, each 3 times, off first then on, 256-token cap.
python scripts/benchmarks/qwen3_4b/runner.py

# Controlled cap sweep; same inputs and seed for every configuration.
python scripts/benchmarks/qwen3_4b/runner.py --num-predict 256 512 1024 --runs 3

# Cold measurements: unload ONLY the selected target model between rounds.
# Each round measures cases[0] as a cold sentinel, then warms up before the suite.
python scripts/benchmarks/qwen3_4b/runner.py --cold --runs 3

# Optional installed 1.7B baseline; same benchmark prompts and options.
python scripts/benchmarks/qwen3_4b/runner.py --models qwen3:4b-q4_K_M qwen3:1.7b --num-predict 256 512

# Fast-only or parser-only follow-up.
python scripts/benchmarks/qwen3_4b/runner.py --thinking off --category parser
```

If `python` is unavailable, use `py -3` in its place. The benchmark defaults to
`http://localhost:11434`, `qwen3:4b-q4_K_M`, `temperature=0`, `num_ctx=4096`,
`num_predict=256`, `seed=42`, 120-second HTTP timeout, and 3 repeats. Other options:
`--thinking off|on|both`, `--timeout 180`, `--base-url http://127.0.0.1:11434`.
Only loopback HTTP URLs are accepted; proxies and redirects are disabled. A missing
service/model produces a diagnostic report and exit code 2, without downloading
anything or using a fallback provider. Run `ollama serve` separately if needed.

Normal completion returns 0 even if model outputs fail quality checks: this is an
experiment, and failures are data. Exit code 0 does not mean accuracy acceptance.

## What is evaluated

Phraser cases cover addition (`EA0001`), multiplication (`EA0003`), forbidden
pairs (`EA0004`), unordered pairs (`EA0012`), and permutations (`EA0017`), each in
Direct and experimental Indirect mode. Actual template text/rules were snapshotted
read-only from the bank. Concrete parameter fixtures have expected answers checked
using independent Python enumeration. No arbitrary authored formula is executed.
The LLM returns only `{"question":"..."}`; backend-owned answers never enter the
Phraser prompt and the model is not asked to recalculate them.

Digit preservation, authored lexical guards, obvious answer/explanation leakage
and obvious Direct-style questions in Indirect mode are checked. Missing lexical
guards require review; absence of a particular phrase is not proof of a wrong
answer. All wording requires human checks for natural Vietnamese, all conditions,
extra assumptions, cognitive intent, and equivalence of the counted set/answer.
An unchanged backend answer does not prove that a rewritten question preserves it.

Parser cases cover reference matching, split steps, independent reordered steps,
two valid alternative methods (sum and complement), arithmetic errors, wrong
formula, misunderstood constraints, right answer with invalid reasoning,
incompleteness, ambiguity, and ignoring a nonmathematical comment. Inspect the
exported `cases.json` for each input and exact expected labels.

The parser receives a checked answer/rule and numbered reference steps, and is told
not to solve again. It returns mathematical expressions, purpose codes, source
line IDs, preliminary reference matches, uncertainty/error indicators and a review
request. It never returns scores or a final grading decision. A reference match is
a hypothesis, including when a later line propagates an earlier wrong number.

`flags` can contain `arithmetic`, `formula`, `constraint`, `incomplete`, `ambiguous`,
or `alternative`. Purpose codes are `count`, `exclude`, `combine`, `conclude`,
`setup`. Reference 0 means unmatched/alternative/unclear. Plausible different
methods must be flagged `alternative`; they are not automatically wrong.

## Timing, output caps and thinking

Every request uses Ollama's native `/api/generate` with top-level `think` set
explicitly, `stream=false`, the task JSON schema in `format`, and bounded options.
Invalid JSON is not repaired, Markdown fences are not stripped, duplicate keys and
extra schema fields are rejected. Outputs must be concise and cannot include a
student score or an explanation outside the schema.

Both modes receive identical prompts, schemas, seed, context and output cap.
Separate thinking text is counted only by presence/character length, not included
in parser scoring. Ollama's `eval_count` is recorded as supplied: it may include
thinking tokens, so do not interpret it as final JSON token count. Thinking can
consume a 256-token budget before producing any JSON; truncation and empty output
remain failures. Increase the controlled cap for **both** modes to investigate.
No silent cap increase, retry, thinking fallback or output repair hides a failure.

Each configuration has a recorded warm-up, excluded from measured case rates.
Warm-up uses the first test case in that round and can populate the prompt cache. Repeat case
order reverses on alternate rounds, but configuration order is fixed (off before
on for each cap), so timing still has order/caching limitations.

Before each request, `/api/ps` observes target-model residency. `warm_observed`
means resident before inference; `cold_observed` means absent. Without `--cold`,
there is no forced cold sample, although the warm-up may observe a cold load.
With `--cold`, the first selected case is the cold sentinel in every round; these
samples are comparable between configurations but are not a full cold-case suite.
To measure a particular case cold, select only that case with `--cases`. Case
subsets otherwise preserve fixture order. This unloads only the benchmark target model, temporarily
affecting other local users of that same model; it never changes model defaults.
This is model-load cold, not OS-disk-cache cold. Unconfirmed residency gets a
separate phase and must not be mixed into confirmed warm/cold latency.

Wall seconds measure the native generation HTTP request only, excluding preflight,
residency queries, unloads and report writes. Raw `total_duration`, `load_duration`,
`prompt_eval_duration`, `eval_duration`, `eval_count`, `prompt_eval_count` and
`prompt_eval_cached_count` are recorded when supplied; missing metrics stay null.
Tokens/second = `eval_count * 1e9 / eval_duration`. Duration means, average/median
wall latency and mean per-request tokens/second are reported separately by model,
cap, thinking mode, task and phase.

Native API behavior follows [Ollama generate documentation](https://docs.ollama.com/api/generate),
[thinking controls](https://docs.ollama.com/capabilities/thinking), and
[resident-model inspection](https://docs.ollama.com/api/ps).

## Reading the results

Each run writes an ignored, timestamped directory under `results/`:

- `summary.md`: compact metrics, failures, paired thinking regressions and limitations.
- `results.json`: full metadata, raw responses, validation findings, per-step counts,
  paired comparisons, consistency across repeats, and grouped summaries.
- `results.csv`: one request per row, UTF-8 with BOM for Excel on Windows.
- `cases.json`: concrete inputs **and private expected labels**, for review.
- `requests.json`: exact prompts, schemas and options for reproducibility; labels
  never appear in model requests. Code, fixture and request hashes are recorded.

Open the latest report:

```powershell
$benchResult = Get-ChildItem 'scripts/benchmarks/qwen3_4b/results' -Directory |
    Sort-Object Name -Descending | Select-Object -First 1
Get-Content -Encoding UTF8 (Join-Path $benchResult.FullName 'summary.md')
Import-Csv (Join-Path $benchResult.FullName 'results.csv') |
    Select-Object case_id, phase, status, wall_seconds, eval_count, requires_review
```

`generation_failure`, `invalid_json`, `schema_failure`, `truncated`,
`thinking_control_violation` and `incorrect_result` are distinct outcomes.
`needs_review` is not a mathematical pass. `pass_labeled` means agreement with a
small synthetic fixture only. `done_reason` and `truncated` are recorded even when
the main outcome is invalid JSON. All failures remain in rate denominators.

Step accuracy = steps matching every labeled expression, purpose, reference and
flag / total expected steps. Expression, purpose, reference and flag accuracies and
step coverage are also available. Extra/duplicate steps fail the case. Strict
notation matching can undercount equivalent expressions; manually adjudicate them.
Case success includes the review requirement; a correct expression alone cannot
hide an omitted uncertainty flag. Alternatives have their own success denominator.

The false-acceptance **proxy** counts known-invalid reasoning extracted without an
error/ambiguity flag or review request. It is not a production acceptance rate,
because the model makes no final grading decision. Failures and missing lines are
unevaluable, never automatically accepted. Read the unevaluable count alongside
the proxy; zero false acceptances with widespread failures proves nothing.

`model_review_rate` records model requests. `required_review_rate` also includes
detected failures; all Phraser outputs require review. `missed_uncertainty_count`
counts missed labeled uncertainty and missing review requests (multiple indicators
may occur in one request). Check case-level records rather than interpreting this
count as a percentage of students.

`paired_modes` compares the same model/cap/case/repeat/phase and explicitly records
whether turning thinking off introduces labeled, alternative-method or uncertainty
regressions. Zero regressions does not establish safety if both modes fail.
`consistency` records distinct structured outputs and outcome counts across warm
repeats; deterministic settings do not guarantee identical hardware results.

Choose a configuration only after establishing acceptable accuracy criteria for
your use case and inspecting all safety/uncertainty failures. Compare warm median
latency among configurations meeting those criteria, then confirm Phraser
semantics with a teacher. This benchmark makes no automatic recommendation or
production change. A two-repeat smoke test cannot establish a stable ranking.

Reports are checkpointed after each measured warm request; final reports are also
written on normal completion, preflight error or Ctrl+C. Avoid editing a report
while that run is active. Hardware load, shared Ollama use, model eviction, context
size, prompt caching and temperature affect measurements. No OCR, handwriting,
deployment integration or unseen-method generalization is evaluated. These results
cannot establish readiness for autonomous student grading.
