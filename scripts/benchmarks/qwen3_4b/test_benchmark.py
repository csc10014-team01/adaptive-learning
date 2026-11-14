"""Offline safety/metric checks. No live inference needed."""

import contextlib
import csv
import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import runner
from cases import all_cases, prompt_for
from contracts import PARSER, PHRASER, validate
from reporting import paired_comparison, summarize
from scoring import check_fixture, parser_score, phraser_score

CASES = {c["id"]: c for c in all_cases()}
CONFIG = {"id": "test", "model": "qwen3:4b-q4_K_M", "think": False,
          "temperature": 0, "num_ctx": 4096, "num_predict": 256, "seed": 42}


def expected_output(case):
    return {"steps": [{"line": e["line"], "expression": e["expressions"][0],
                       "purpose": e["purposes"][0], "reference": e["references"][0],
                       "flags": e["required_flags"]} for e in case["expected_steps"]],
            "review": case["review_required"]}


class FakeClient:
    def __init__(self, output, **extra):
        self.output, self.extra = output, extra

    def loaded(self, model):
        return True

    def request(self, path, payload):
        return {"model": CONFIG["model"], "done": True, "done_reason": "stop",
                "response": json.dumps(self.output), "eval_count": 10,
                "eval_duration": 2_000_000_000, **self.extra}


class Checks(unittest.TestCase):
    def test_all_bank_fixture_answers_independently_enumerated(self):
        for case in CASES.values():
            if case["category"] == "phraser":
                check_fixture(case)
        tampered = {**CASES["EA0012_direct"], "expected_answer": 56}
        with self.assertRaises(ValueError):
            check_fixture(tampered)

    def test_labeled_traces_and_alternatives_are_self_consistent(self):
        for case in CASES.values():
            if case["category"] != "parser":
                continue
            output = expected_output(case)
            validate(output, PARSER)
            result = parser_score(case, output)
            self.assertTrue(result["labeled_ok"], case["id"])
            self.assertFalse(result["false_acceptance_proxy"], case["id"])
            self.assertEqual(result["correct_steps"], len(case["expected_steps"]))
            if case["alternative"]:
                self.assertTrue(result["alternative_ok"])

    def test_correct_final_answer_does_not_hide_invalid_reasoning(self):
        case = CASES["P08"]
        output = expected_output(case)
        for step in output["steps"]:
            step["flags"] = []
        result = parser_score(case, output)
        self.assertFalse(result["labeled_ok"])
        self.assertTrue(result["false_acceptance_proxy"])

    def test_uncertainty_and_teacher_review_are_required(self):
        case = CASES["P10"]
        output = expected_output(case)
        output["review"] = False
        output["steps"][0]["flags"] = []
        result = parser_score(case, output)
        self.assertGreater(result["missed_uncertainty"], 0)
        self.assertTrue(result["requires_review"])

    def test_invented_and_duplicate_lines_fail(self):
        case = CASES["P12"]
        output = expected_output(case)
        output["steps"].append({**output["steps"][0], "line": 1})
        self.assertFalse(parser_score(case, output)["labeled_ok"])
        output["steps"][-1]["line"] = 2
        self.assertFalse(parser_score(case, output)["labeled_ok"])

    def test_spurious_error_flag_is_not_a_missed_uncertainty_flag(self):
        case = CASES["P10"]
        output = expected_output(case)
        output["steps"][0]["flags"].append("arithmetic")
        result = parser_score(case, output)
        self.assertFalse(result["labeled_ok"])
        self.assertEqual(result["missed_uncertainty"], 0)

    def test_numeric_changes_fail_but_lexical_omissions_need_review(self):
        case = CASES["EA0012_direct"]
        changed = {"question": "Có 9 đối tượng phân biệt. Hỏi số cặp không phân biệt thứ tự?"}
        self.assertEqual(phraser_score(case, changed)["status"], "incorrect_result")
        brief = {"question": "Có bao nhiêu cặp từ 8 đối tượng phân biệt?"}
        self.assertEqual(phraser_score(case, brief)["status"], "needs_review")
        self.assertIsNone(phraser_score(case, brief)["math_correct"])
        repeated = {"question": "Có 8 đối tượng phân biệt. Chọn cặp từ 8 đối tượng, không phân biệt thứ tự."}
        self.assertTrue(phraser_score(case, repeated)["numeric_ok"])

    def test_strict_schema_and_json_do_not_repair_outputs(self):
        for text in ('```json\n{}\n```', '{"question":"a","question":"b"}', '{"x":NaN}'):
            with self.assertRaises(ValueError):
                runner.strict_json(text)
        with self.assertRaises(ValueError):
            validate({"question": "A sufficiently long question", "answer": 28}, PHRASER)
        output = expected_output(CASES["P01"])
        output["steps"][0]["line"] = True
        with self.assertRaises(ValueError):
            validate(output, PARSER)

    def test_prompts_keep_labels_private_and_do_not_ask_to_resolve(self):
        payload = runner.payload_for(CASES["P04"], CONFIG)
        self.assertIs(payload["think"], False)
        self.assertEqual(payload["options"]["num_predict"], 256)
        self.assertIn("DO NOT solve", payload["prompt"])
        self.assertNotIn("expected_steps", payload["prompt"])
        self.assertNotIn("review_required", payload["prompt"])
        self.assertNotIn("expected_answer", prompt_for(CASES["EA0012_direct"]))

    def test_remote_urls_and_redirects_are_rejected(self):
        for url in ("https://localhost:11434", "http://example.com", "http://localhost.evil:11434",
                    "http://localhost:11434/remote", "http://user@localhost:11434"):
            with self.assertRaises(ValueError):
                runner.Ollama(url, 1)
        with self.assertRaises(ValueError):
            runner.NoRedirect().redirect_request(None, None, 302, "", {}, "http://example.com")

    def test_truncation_does_not_earn_accuracy_credit(self):
        row = runner.measure(FakeClient(expected_output(CASES["P01"]), done_reason="length"),
                             CASES["P01"], CONFIG, "warm", 0)
        self.assertTrue(row["schema_ok"])
        self.assertEqual(row["status"], "truncated")
        summary = summarize([row])[0]
        self.assertEqual(summary["step_accuracy"], 0)
        self.assertEqual(summary["expression_accuracy"], 0)

    def test_generation_failures_stay_in_accuracy_denominator(self):
        row = runner.measure(FakeClient(expected_output(CASES["P01"]), done=False),
                             CASES["P01"], CONFIG, "warm", 0)
        self.assertEqual(row["status"], "generation_failure")
        self.assertEqual(summarize([row])[0]["step_accuracy"], 0)
        self.assertTrue(row["requires_review"])

    def test_missing_metrics_stay_null_and_tokens_per_second_uses_nanoseconds(self):
        row = runner.measure(FakeClient(expected_output(CASES["P01"])), CASES["P01"], CONFIG, "warm", 0)
        self.assertEqual(row["tokens_per_second"], 5)
        self.assertIsNone(row["load_duration"])
        self.assertTrue(row["schema_ok"])

    def test_thinking_control_violation_is_not_success(self):
        row = runner.measure(FakeClient(expected_output(CASES["P01"]), thinking="unexpected"),
                             CASES["P01"], CONFIG, "warm", 0)
        self.assertEqual(row["status"], "thinking_control_violation")
        self.assertFalse(row["labeled_ok"])

    def test_paired_comparison_detects_alternative_regression(self):
        cfg = {**CONFIG, "think": True}
        on = runner.measure(FakeClient(expected_output(CASES["P04"])), CASES["P04"], cfg, "warm", 0)
        wrong = expected_output(CASES["P04"])
        wrong["steps"][0]["flags"] = ["formula"]
        off = runner.measure(FakeClient(wrong), CASES["P04"], CONFIG, "warm", 0)
        pair = paired_comparison([on, off])[0]
        self.assertTrue(pair["alternative_nonthinking_regression"])
        self.assertTrue(pair["nonthinking_labeled_regression"])

    def test_native_http_orchestration_cold_warm_and_exports(self):
        calls = []
        model = CONFIG["model"]
        state = {"loaded": True}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.reply(None)

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.reply(payload)

            def reply(self, payload):
                calls.append((self.path, payload))
                if self.path == "/api/version":
                    value = {"version": "test"}
                elif self.path == "/api/tags":
                    value = {"models": [{"name": model, "details": {"family": "qwen3"}}]}
                elif self.path == "/api/show":
                    value = {"capabilities": ["completion", "thinking"]}
                elif self.path == "/api/ps":
                    value = {"models": [{"name": model}] if state["loaded"] else []}
                elif payload.get("keep_alive") == 0:
                    state["loaded"] = False
                    value = {"done": True}
                else:
                    state["loaded"] = True
                    value = {"done": True, "model": model, "done_reason": "stop",
                             "response": json.dumps(expected_output(CASES["P10"])),
                             "total_duration": 12, "load_duration": 3, "prompt_eval_duration": 4,
                             "eval_duration": 5, "eval_count": 2}
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix="qwen_bench_") as directory:
                with patch.object(runner, "HERE", Path(directory)), contextlib.redirect_stdout(io.StringIO()):
                    status = runner.main(["--base-url", f"http://127.0.0.1:{server.server_port}",
                                          "--cases", "P10", "--runs", "2", "--cold"])
                self.assertEqual(status, 0)
                out = next((Path(directory) / "results").iterdir())
                data = json.loads((out / "results.json").read_text(encoding="utf-8"))
                rows = data["records"]
                self.assertEqual(len(rows), 12)  # 2 modes * 2 rounds * (cold, warmup, warm)
                self.assertEqual(len(data["paired_modes"]), 4)
                self.assertEqual({r["residency"] for r in rows if r["phase"] == "cold"}, {"cold_observed"})
                self.assertEqual({r["residency"] for r in rows if r["phase"] == "warm"}, {"warm_observed"})
                with (out / "results.csv").open(encoding="utf-8-sig", newline="") as f:
                    self.assertEqual(len(list(csv.DictReader(f))), len(rows))
                self.assertTrue((out / "requests.json").exists())
                self.assertIn("false acceptance", (out / "summary.md").read_text(encoding="utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        generated = [p for path, p in calls if path == "/api/generate" and "prompt" in p]
        self.assertEqual({p["think"] for p in generated}, {False, True})
        self.assertTrue(all(p["options"]["num_predict"] == 256 for p in generated))


if __name__ == "__main__":
    unittest.main()
