"""Isolated native Ollama benchmark. Python standard library only."""

import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from cases import HERE, SNAPSHOT, all_cases, prompt_for
from contracts import PARSER, PHRASER, validate
from reporting import export
from scoring import check_fixture, score

METRICS = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
           "eval_count", "prompt_eval_count", "prompt_eval_cached_count")


def strict_json(text):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError(f"Duplicate JSON key: {k}")
            result[k] = v
        return result

    def nonfinite(value):
        raise ValueError(f"Nonfinite JSON: {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirects are disabled: local Ollama only")


class Ollama:
    def __init__(self, url, timeout):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment):
            raise ValueError("Use an HTTP loopback Ollama URL, e.g. http://localhost:11434")
        self.url, self.timeout = url.rstrip("/"), timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(self.url + path, data=data, headers={"Content-Type": "application/json"})
        with self.opener.open(req, timeout=self.timeout) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("Ollama response exceeds benchmark size limit")
        value = strict_json(raw)
        if not isinstance(value, dict) or value.get("error"):
            raise ValueError(f"Ollama error: {value}")
        return value

    def loaded(self, model):
        try:
            return any(m.get("name") == model or m.get("model") == model
                       for m in self.request("/api/ps").get("models", []))
        except (OSError, ValueError):
            return None

    def unload(self, model):
        self.request("/api/generate", {"model": model, "keep_alive": 0, "stream": False})
        if self.loaded(model) is not False:
            raise ValueError("Cannot verify target-model unload; refusing to label a cold run")


def payload_for(case, config):
    return {"model": config["model"], "prompt": prompt_for(case), "think": config["think"],
            "stream": False, "keep_alive": "10m",
            "format": PHRASER if case["category"] == "phraser" else PARSER,
            "options": {"temperature": config["temperature"], "num_ctx": config["num_ctx"],
                        "num_predict": config["num_predict"], "seed": config["seed"]}}


def measure(client, case, config, phase, repeat):
    payload = payload_for(case, config)
    before = client.loaded(config["model"])
    if (phase == "cold" and before is not False) or (phase == "warm" and before is not True):
        phase += "_unconfirmed"
    row = {"config_id": config["id"], "case_id": case["id"], "category": case["category"],
           "scenario": case.get("scenario", case.get("mode")), "phase": phase, "repeat": repeat,
           "residency": "warm_observed" if before is True else "cold_observed" if before is False else "unknown",
           "config": dict(config), "json_ok": False, "schema_ok": False,
           "alternative_case": case.get("alternative", False),
           "expected_step_count": len(case.get("expected_steps", [])),
           "requires_review": True, "model_review": None,
           "request_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}
    started = time.perf_counter()
    try:
        envelope = client.request("/api/generate", payload)
        row["wall_seconds"] = time.perf_counter() - started
        row.update({k: envelope.get(k) for k in METRICS})
        row["done_reason"] = envelope.get("done_reason")
        row["thinking_present"] = bool(envelope.get("thinking"))
        row["thinking_characters"] = len(envelope.get("thinking") or "")
        if envelope.get("done") is not True or not isinstance(envelope.get("response"), str):
            raise ValueError("Incomplete or malformed Ollama envelope")
        if envelope.get("model") != config["model"]:
            raise ValueError("Ollama returned an unexpected model")
        row["raw_response"] = envelope["response"]
        count, duration = row.get("eval_count"), row.get("eval_duration")
        row["tokens_per_second"] = count * 1e9 / duration if count is not None and duration else None
        row["truncated"] = envelope.get("done_reason") == "length"
        try:
            output = strict_json(envelope["response"])
            row["json_ok"] = True
        except (ValueError, TypeError) as exc:
            row.update(status="invalid_json", error=str(exc))
            return row
        try:
            validate(output, payload["format"])
            row["schema_ok"] = True
            row["output"] = output
        except ValueError as exc:
            row.update(status="schema_failure", error=str(exc))
            return row
        if row["truncated"]:
            row.update(status="truncated", requires_review=True, labeled_ok=False)
            return row
        if not config["think"] and row["thinking_present"]:
            row.update(status="thinking_control_violation", requires_review=True, labeled_ok=False)
            return row
        row.update(score(case, output))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        row.update(status="generation_failure", error=f"{type(exc).__name__}: {exc}")
    finally:
        row.setdefault("wall_seconds", time.perf_counter() - started)
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://localhost:11434")
    ap.add_argument("--models", nargs="+", default=["qwen3:4b-q4_K_M"])
    ap.add_argument("--thinking", choices=["both", "off", "on"], default="both")
    ap.add_argument("--num-predict", type=int, nargs="+", default=[256])
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--temperature", type=float, default=0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--category", choices=["all", "phraser", "parser"], default="all")
    ap.add_argument("--cases", nargs="+", help="Exact case IDs; same selection for every configuration")
    ap.add_argument("--cold", action="store_true", help="Measure a cold sentinel per round, unloading only the selected model")
    ap.add_argument("--dry-run", action="store_true", help="Export requests/fixtures without contacting Ollama")
    args = ap.parse_args(argv)
    if args.runs < 1 or args.timeout <= 0 or args.num_ctx < 512 or any(n < 1 for n in args.num_predict):
        ap.error("runs, timeout and token limits must be positive; num-ctx must be >=512")
    cases = all_cases()
    for case in cases:
        if case["category"] == "phraser":
            check_fixture(case)
    known = {c["id"] for c in cases}
    if args.cases and set(args.cases) - known:
        ap.error("Unknown case IDs: " + str(sorted(set(args.cases) - known)))
    cases = [c for c in cases if (args.category == "all" or c["category"] == args.category)
             and (not args.cases or c["id"] in args.cases)]
    if not cases:
        ap.error("No cases selected")
    # Do not read or set production environment/model defaults.
    client = Ollama(args.base_url, args.timeout)
    models = list(dict.fromkeys(args.models))
    if any("cloud" in m.casefold() or "/" in m for m in models):
        ap.error("Only installed local Qwen model names are supported")
    modes = [False, True] if args.thinking == "both" else [args.thinking == "on"]
    configs = []
    for model in models:
        for limit in dict.fromkeys(args.num_predict):
            for think in modes:
                configs.append({"id": f"{model}|think={str(think).lower()}|limit={limit}",
                                "model": model, "think": think, "num_predict": limit,
                                "temperature": args.temperature, "num_ctx": args.num_ctx, "seed": args.seed})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = HERE / "results" / stamp
    out.mkdir(parents=True)
    meta = {"started_utc": stamp, "python": sys.version, "platform": platform.platform(),
            "arguments": vars(args), "configurations": configs,
            "source_bank": SNAPSHOT, "case_count": len(cases), "models": {},
            "fixture_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob("*.py")}}
    (out / "cases.json").write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
    rows = []
    requests = [{"case_id": c["id"], "config_id": cfg["id"], "payload": payload_for(c, cfg)}
                for cfg in configs for c in cases]
    (out / "requests.json").write_text(json.dumps(requests, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.dry_run:
        meta["dry_run"] = True
    else:
        try:
            meta["ollama_version"] = client.request("/api/version")
            tags = client.request("/api/tags").get("models", [])
            for model in models:
                tag = next((m for m in tags if m.get("name") == model or m.get("model") == model), None)
                if tag is None:
                    raise ValueError(f"Model not installed: {model}. No model download was attempted.")
                show = client.request("/api/show", {"model": model})
                if show.get("remote_host") or show.get("remote_model"):
                    raise ValueError("Remote-backed models are not allowed")
                if "qwen" not in (tag.get("details", {}).get("family") or "").casefold():
                    raise ValueError("This benchmark expects a local Qwen model")
                meta["models"][model] = {"tag": tag, "capabilities": show.get("capabilities"),
                                          "thinking": show.get("thinking"), "parameters": show.get("parameters")}
            for config in configs:
                for repeat in range(args.runs):
                    # Reverse case order on alternate rounds to reduce a fixed case-order bias.
                    ordered = cases if repeat % 2 == 0 else list(reversed(cases))
                    if repeat == 0 or args.cold:
                        if args.cold:
                            client.unload(config["model"])
                            row = measure(client, cases[0], config, "cold", repeat)
                            rows.append(row)
                            print(f"{config['id']} cold {row['case_id']}: {row['status']} ({row['wall_seconds']:.2f}s)", flush=True)
                        warmup = measure(client, ordered[0], config, "warmup", repeat)
                        rows.append(warmup)
                        print(f"{config['id']} warmup: {warmup['status']} ({warmup['wall_seconds']:.2f}s)", flush=True)
                    for case in ordered:
                        row = measure(client, case, config, "warm", repeat)
                        rows.append(row)
                        # Checkpoint after every request, so interruption does not lose a long run.
                        export(out, meta, rows)
                        print(f"{config['id']} warm {repeat+1}/{args.runs} {case['id']}: {row['status']} ({row['wall_seconds']:.2f}s)", flush=True)
        except (OSError, ValueError, KeyboardInterrupt) as exc:
            meta["run_error"] = f"{type(exc).__name__}: {exc}"
            export(out, meta, rows)
            print(f"Benchmark stopped: {meta['run_error']}\nResults: {out}", file=sys.stderr)
            return 2
    export(out, meta, rows)
    print(f"Results: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
