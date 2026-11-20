"""Honest denominators, paired mode comparisons and reviewable local exports."""

import csv
import json
import statistics
from collections import Counter, defaultdict


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def ratio(n, d):
    return n / d if d else None


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["config_id"], row["category"], row["phase"])].append(row)
    result = []
    for (cfg, category, phase), items in groups.items():
        expected = sum(r.get("expected_step_count", 0) for r in items)
        alternatives = [r for r in items if r.get("alternative_case")]
        latency = [r["wall_seconds"] for r in items]
        result.append({
            "config_id": cfg, "category": category, "phase": phase, "requests": len(items),
            "json_success_rate": ratio(sum(r["json_ok"] for r in items), len(items)),
            "schema_success_rate": ratio(sum(r["schema_ok"] for r in items), len(items)),
            "statuses": dict(Counter(r["status"] for r in items)),
            "mean_wall_seconds": mean(latency), "median_wall_seconds": statistics.median(latency),
            "mean_tokens_per_second": mean([r.get("tokens_per_second") for r in items]),
            "duration_means_ns": {k: mean([r.get(k) for r in items]) for k in
                                  ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")},
            "numeric_check_pass_rate": ratio(sum(r.get("numeric_ok", False) for r in items), len(items)) if category == "phraser" else None,
            "step_accuracy": ratio(sum(r.get("correct_steps", 0) if not r.get("truncated") else 0 for r in items), expected),
            "expression_accuracy": ratio(sum(r.get("correct_expressions", 0) for r in items), expected),
            "purpose_accuracy": ratio(sum(r.get("correct_purposes", 0) for r in items), expected),
            "reference_accuracy": ratio(sum(r.get("correct_references", 0) for r in items), expected),
            "flag_accuracy": ratio(sum(r.get("correct_flags", 0) for r in items), expected),
            "step_coverage": ratio(sum(r.get("covered_step_count", 0) for r in items), expected),
            "labeled_case_success_rate": ratio(sum(r.get("labeled_ok", False) for r in items), len(items)) if category == "parser" else None,
            "alternative_success_rate": ratio(sum(r.get("alternative_ok") is True and r.get("labeled_ok", False) for r in alternatives), len(alternatives)),
            "false_acceptance_proxy_count": sum(bool(r.get("false_acceptance_proxy")) for r in items),
            "missed_uncertainty_count": sum(r.get("missed_uncertainty", 0) for r in items),
            "unevaluable_requests": sum(not r["schema_ok"] or r.get("truncated", False) for r in items),
            "model_review_rate": ratio(sum(r.get("model_review") is True for r in items), len(items)) if category == "parser" else None,
            "required_review_rate": ratio(sum(r["requires_review"] for r in items), len(items)),
            "residency": dict(Counter(r["residency"] for r in items)),
            "violations": dict(Counter(v for r in items for v in r.get("violations", []))),
        })
    return result


def paired_comparison(rows):
    pairs = defaultdict(dict)
    for row in rows:
        if row["phase"] == "warmup":
            continue
        c = row["config"]
        key = (c["model"], c["num_predict"], row["case_id"], row["phase"], row["repeat"])
        pairs[key][c["think"]] = row
    results = []
    for (model, limit, case, phase, repeat), modes in pairs.items():
        if set(modes) != {False, True}:
            continue
        off, on = modes[False], modes[True]
        results.append({"model": model, "num_predict": limit, "case_id": case,
                        "phase": phase, "repeat": repeat,
                        "off_seconds": off["wall_seconds"], "on_seconds": on["wall_seconds"],
                        "off_status": off["status"], "on_status": on["status"],
                        "off_minus_on_seconds": off["wall_seconds"] - on["wall_seconds"],
                        "nonthinking_labeled_regression": on.get("labeled_ok", False) and not off.get("labeled_ok", False),
                        "alternative_nonthinking_regression": off.get("alternative_case", False) and on.get("alternative_ok") is True and off.get("alternative_ok") is not True,
                        "uncertainty_nonthinking_regression": off.get("missed_uncertainty", 0) > on.get("missed_uncertainty", 0),
                        "both_schema_valid": off["schema_ok"] and on["schema_ok"]})
    return results


def consistency(rows):
    groups = defaultdict(list)
    for r in rows:
        if r["phase"] == "warm":
            groups[(r["config_id"], r["case_id"])].append(r)
    return [{"config_id": cfg, "case_id": case, "runs": len(items),
             "distinct_outputs": len({json.dumps(r.get("output", r.get("raw_response", r.get("error"))), sort_keys=True, ensure_ascii=False) for r in items}),
             "statuses": dict(Counter(r["status"] for r in items)),
             "all_labeled_ok": all(r.get("labeled_ok", False) for r in items) if items[0]["category"] == "parser" else None}
            for (cfg, case), items in groups.items()]


def display(value):
    return "n/a" if value is None else f"{value:.3f}" if isinstance(value, float) else str(value)


def export(out, metadata, rows):
    summary = summarize(rows)
    paired = paired_comparison(rows)
    data = {"metadata": metadata, "summary": summary, "paired_modes": paired,
            "consistency": consistency(rows), "records": rows}
    (out / "results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = ["config_id", "case_id", "category", "scenario", "phase", "repeat", "residency",
               "model", "think", "num_predict", "temperature", "num_ctx", "seed", "status",
               "wall_seconds", "total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
               "eval_count", "prompt_eval_count", "tokens_per_second", "done_reason", "truncated",
               "thinking_present", "json_ok", "schema_ok", "labeled_ok", "numeric_ok", "correct_steps",
               "expected_step_count", "alternative_ok", "false_acceptance_proxy", "missed_uncertainty",
               "model_review", "requires_review", "violations", "error"]
    with (out / "results.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            merged = {**row, **row["config"]}
            merged["violations"] = json.dumps(row.get("violations", []), ensure_ascii=False)
            writer.writerow({k: merged.get(k) for k in columns})
    report = ["# MIRA local Qwen benchmark", "",
              "Experimental extraction and wording evidence only. No autonomous student-grading claim.", "",
              "Warm-up requests are recorded separately and excluded from warm/cold case metrics. "
              "Wall latency includes failed requests; do not rank a failing configuration by speed alone. "
              "Durations in JSON/CSV are Ollama nanoseconds; wall latency is seconds.", "",
              "| Configuration | Task | Phase | N | Schema rate | Labeled step accuracy | Alternative rate | Mean s | Median s | Tokens/s | Review rate |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in summary:
        values = [s["config_id"].replace("|", "; "), s["category"], s["phase"], s["requests"],
                  s["schema_success_rate"], s["step_accuracy"], s["alternative_success_rate"],
                  s["mean_wall_seconds"], s["median_wall_seconds"], s["mean_tokens_per_second"], s["required_review_rate"]]
        report.append("| " + " | ".join(display(x) for x in values) + " |")
    report += ["", "## Accuracy and uncertainty", "",
               "Phraser answer preservation, natural Vietnamese, hallucinated assumptions and full semantic "
               "equivalence require manual review. Digit and lexical checks are filters, not mathematical proof. "
               "Step accuracy is exact labeled line/expression/purpose/reference/flag agreement, with all "
               "expected steps (including failed requests) in the denominator. It is not general grading accuracy.", "",
               "Incorrect-answer false acceptance is a proxy: known-invalid reasoning extracted without an "
               "error/ambiguity flag or review request. Missing/invalid/truncated outputs are failures, never "
               "accepted solutions. A zero proxy count with unevaluable requests is not safety evidence.", ""]
    for s in summary:
        if s["phase"] == "warmup":
            continue
        report.append(f"- {s['config_id']} / {s['category']} / {s['phase']}: "
                      f"statuses={s['statuses']}; false acceptance proxy={s['false_acceptance_proxy_count']}; "
                      f"missed uncertainty={s['missed_uncertainty_count']}; "
                      f"unevaluable={s['unevaluable_requests']}; residency={s['residency']}; "
                      f"violations={s['violations']}")
    report += ["", "## Paired thinking comparison", "",
               f"Matched requests: {len(paired)}. Non-thinking labeled regressions: "
               f"{sum(p['nonthinking_labeled_regression'] for p in paired)}; "
               f"alternative-method regressions: {sum(p['alternative_nonthinking_regression'] for p in paired)}; "
               f"uncertainty regressions: {sum(p['uncertainty_nonthinking_regression'] for p in paired)}.", "",
               "See paired_modes in results.json for each case. These counts compare the same model, "
               "token cap, prompt, seed, phase and repeat. Both modes can fail; zero regressions does not "
               "establish equivalence. Thinking may consume the token budget before emitting JSON.", "",
               "## Limitations and selection", "",
               "Choose the fastest warm configuration only after inspecting failures, parser labels, "
               "alternative methods and uncertainty handling, and manually confirming Phraser semantics. "
               "No automatic production recommendation is made. This small synthetic corpus is not teacher "
               "certified and does not cover OCR, handwriting, all notation or unseen solution strategies. "
               "Lexically different equivalent expressions may need manual adjudication.", "",
               "Cold means the target model was observed absent from /api/ps before inference; it does not "
               "clear the OS disk cache. Warm observations do not imply a cold prompt cache. "
               "Concurrent Ollama users, hardware scheduling, fixed configuration order and prompt caching "
               "can affect comparisons. Model metadata and fixture/request hashes are recorded.", ""]
    if metadata.get("run_error"):
        report += ["Run error: " + metadata["run_error"], ""]
    if metadata.get("dry_run"):
        report += ["Dry run only: no inference and no measured accuracy or latency.", ""]
    (out / "summary.md").write_text("\n".join(report), encoding="utf-8")
