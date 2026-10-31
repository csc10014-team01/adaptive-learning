"""Issue #6 — local Qwen feasibility spike with honest hardware metrics.

Usage: python src/ai/qwen_spike.py --model qwen3:1.7b --runs 2
No paid/cloud API. Ollama REST listens locally at 127.0.0.1:11434.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "eval" / "results" / "baseline_spike_output.json"

# Two mathematically distinct, teacher-reviewed input structures.
CASES = [
    {
        "case_id": "C01",
        "task": "choose_group",
        "n": 8,
        "k": 3,
        "objects": "học sinh",
        "context": "một lớp học",
        "order_matters": False,
        "replacement": False,
    },
    {
        "case_id": "C02",
        "task": "assign_roles",
        "n": 7,
        "k": 3,
        "objects": "học sinh",
        "context": "một câu lạc bộ",
        "roles": ["trưởng nhóm", "phó nhóm", "thư ký"],
        "order_matters": True,
        "replacement": False,
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "question": {"type": "string"},
        "task": {"type": "string", "enum": ["choose_group", "assign_roles"]},
        "n": {"type": "integer"},
        "k": {"type": "integer"},
        "answer": {"type": "integer"},
    },
    "required": ["question", "task", "n", "k", "answer"],
}


def answer_for(case: dict) -> int:
    n, k = case["n"], case["k"]
    if not 0 <= k <= n:
        raise ValueError("Require 0 <= k <= n")
    if case["task"] == "choose_group":
        return math.comb(n, k)
    if case["task"] == "assign_roles":
        return math.perm(n, k)
    raise ValueError(f"Unsupported task {case['task']!r}")


def build_prompt(case: dict) -> str:
    result = answer_for(case)
    instruction = (
        "Bạn là người soạn đề Toán tổ hợp lớp 10. Viết đúng MỘT câu hỏi tự luận tiếng Việt "
        "tự nhiên, rõ ràng từ đặc tả sau. KHÔNG đổi n, k, đối tượng, bối cảnh, "
        "không thêm bất kỳ điều kiện đếm nào (giới tính, ít nhất, bắt buộc, cạnh nhau, ...), "
        "không thêm dữ kiện số khác, không đổi việc có phân biệt vai trò/thứ tự. "
        "Nếu là choose_group, chỉ chọn nhóm không phân vai, không thứ tự; "
        "nếu là assign_roles, phân công đúng các vai trò khác nhau. "
        "Không đưa lời giải vào trường question. "
        "Trả đúng JSON theo schema với các khóa question, task, n, k, answer. "
        "Chép nguyên các khóa task/n/k và đáp án chuẩn mà chương trình cung cấp.\n"
    )
    safe_case = dict(case)
    safe_case["expected_answer"] = result
    return instruction + "ĐẶC TẢ: " + json.dumps(safe_case, ensure_ascii=False)


def get_json(url: str, timeout: int = 6) -> dict:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict, timeout: int) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def model_metadata(base_url: str, model: str) -> dict:
    info = {"version": None, "digest": None, "size_bytes": None, "quantization": None}
    try:
        info["version"] = get_json(base_url + "/api/version").get("version")
        for item in get_json(base_url + "/api/tags").get("models", []):
            if item.get("name") == model or item.get("model") == model:
                info["digest"] = item.get("digest")
                info["size_bytes"] = item.get("size")
                info["quantization"] = (item.get("details") or {}).get(
                    "quantization_level"
                )
                break
    except Exception as exc:  # noqa: BLE001 -- Metadata collection is best-effort diagnostics.
        info["metadata_error"] = str(exc)
    return info


def gpu_inventory() -> list[dict]:
    """Only NVIDIA GPUs with nvidia-smi are discoverable here."""
    if not shutil.which("nvidia-smi"):
        return []
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=True,
        )
        found = []
        for line in proc.stdout.splitlines():
            name, size = line.rsplit(",", 1)
            found.append({"name": name.strip(), "total_vram_mib": int(size.strip())})
        return found
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def gpu_used_mib() -> int | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        p = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=4,
            check=True,
        )
        vals = [int(x.strip()) for x in p.stdout.splitlines() if x.strip().isdigit()]
        return sum(vals) if vals else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


class ResourceMonitor:
    """Sample total system RAM and total Nvidia GPU memory, not model-exclusive usage."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.stop = threading.Event()
        self.thread = None
        self.psutil = None
        try:
            import psutil

            self.psutil = psutil
        except ImportError:
            pass
        self.ram_before_mib = None
        self.gpu_before_mib = None
        self.ram_peak_mib = None
        self.gpu_peak_mib = None
        self.ram_total_mib = None

    def sample(self):
        if self.psutil:
            m = self.psutil.virtual_memory()
            used = m.used / (1024**2)
            self.ram_total_mib = round(m.total / (1024**2), 1)
            self.ram_peak_mib = max(self.ram_peak_mib or used, used)
            if self.ram_before_mib is None:
                self.ram_before_mib = used
        gpu = gpu_used_mib()
        if gpu is not None:
            self.gpu_peak_mib = max(self.gpu_peak_mib or gpu, gpu)
            if self.gpu_before_mib is None:
                self.gpu_before_mib = gpu

    def _loop(self):
        while not self.stop.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.sample()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop.set()
        self.thread.join(timeout=3)
        self.sample()

    def as_dict(self):
        return {
            "ram_system_total_mib": self.ram_total_mib,
            "ram_system_used_before_mib": round(self.ram_before_mib, 1)
            if self.ram_before_mib is not None
            else None,
            "ram_system_used_peak_mib": round(self.ram_peak_mib, 1)
            if self.ram_peak_mib is not None
            else None,
            "ram_system_peak_delta_mib": round(
                max(0, self.ram_peak_mib - self.ram_before_mib), 1
            )
            if self.ram_peak_mib is not None and self.ram_before_mib is not None
            else None,
            "nvidia_vram_used_before_mib": self.gpu_before_mib,
            "nvidia_vram_used_peak_mib": self.gpu_peak_mib,
            "nvidia_vram_peak_delta_mib": max(
                0, self.gpu_peak_mib - self.gpu_before_mib
            )
            if self.gpu_peak_mib is not None and self.gpu_before_mib is not None
            else None,
            "note": "System-wide sampled usage; NOT Ollama-exclusive. VRAM is null if nvidia-smi is unavailable. Peak may be missed between samples.",
        }


def validate_ai_output(output: dict, case: dict) -> list[str]:
    problems = []
    if not isinstance(output, dict):
        return ["Output is not a JSON object"]
    if set(output) != {"question", "task", "n", "k", "answer"}:
        problems.append("Unexpected/missing JSON keys")
    for name in ("n", "k", "answer"):
        if type(output.get(name)) is not int or output.get(name) != (
            answer_for(case) if name == "answer" else case[name]
        ):
            problems.append(f"{name} mismatches specification")
    if output.get("task") != case["task"]:
        problems.append("task mismatches specification")
    question = output.get("question")
    if not isinstance(question, str) or len(question.strip()) < 25:
        problems.append("question missing/too short")
    # Intentionally do not claim full semantic equivalence; must be teacher-reviewed.
    return problems


def run_case(
    base_url: str, model: str, case: dict, timeout: int, interval: float
) -> dict:
    payload = {
        "model": model,
        "prompt": build_prompt(case),
        "format": OUTPUT_SCHEMA,
        "stream": False,
        "think": False,
        "keep_alive": "5m",
        "options": {"temperature": 0, "seed": 42, "num_predict": 250},
    }
    record = {
        "case_id": case["case_id"],
        "input": case,
        "expected_answer": answer_for(case),
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    with ResourceMonitor(interval) as mon:
        start = time.perf_counter()
        try:
            response = post_json(base_url + "/api/generate", payload, timeout)
            record["api_duration_s"] = round((time.perf_counter() - start), 3)
            record["ollama_metrics"] = {
                "total_duration_s": round(response.get("total_duration", 0) / 1e9, 3),
                "load_duration_s": round(response.get("load_duration", 0) / 1e9, 3),
                "prompt_eval_count": response.get("prompt_eval_count"),
                "eval_count": response.get("eval_count"),
                "eval_duration_s": round(response.get("eval_duration", 0) / 1e9, 3),
            }
            try:
                answer = json.loads(response.get("response", ""))
                record["model_output"] = answer
                record["validation_errors"] = validate_ai_output(answer, case)
                record["json_valid"] = isinstance(answer, dict)
                record["status"] = (
                    "needs_teacher_review"
                    if not record["validation_errors"]
                    else "failed_validation"
                )
            except (json.JSONDecodeError, TypeError) as exc:
                record.update(
                    {
                        "model_raw_output": response.get("response", ""),
                        "json_valid": False,
                        "status": "failed_json",
                        "validation_errors": [f"JSON decode: {exc}"],
                    }
                )
        except (URLError, HTTPError, OSError, ValueError, TimeoutError) as exc:
            record.update(
                {
                    "api_duration_s": round(time.perf_counter() - start, 3),
                    "status": "runtime_error",
                    "error": str(exc),
                }
            )
    record["resources"] = mon.as_dict()
    return record


def main():
    p = argparse.ArgumentParser(description="Local Qwen baseline feasibility spike")
    p.add_argument("--model", default="qwen3:1.7b")
    p.add_argument("--runs", type=int, choices=[1, 2], default=2)
    p.add_argument("--base-url", default="http://127.0.0.1:11434")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--interval", type=float, default=0.5)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    if args.interval < 0.2:
        p.error("--interval should be >= 0.2 seconds")
    # Fail cleanly when Ollama is not available; never fabricate an output.
    try:
        get_json(args.base_url + "/api/version")
    except Exception as exc:  # noqa: BLE001 -- Report any failed service probe before running the spike.
        print(
            "ERROR: Ollama local service unavailable. Start Ollama, then run 'ollama pull "
            + args.model
            + "'.",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 2
    report = {
        "experiment": "Issue #6 local Qwen baseline spike",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "model": args.model,
        "ollama": model_metadata(args.base_url, args.model),
        "machine": {
            "os": platform.platform(),
            "cpu": platform.processor() or platform.machine(),
            "python_version": platform.python_version(),
            "logical_cpu_cores": os.cpu_count(),
            "nvidia_gpus": gpu_inventory(),
            "hostname_redacted": True,
        },
        "measurement_limitations": "Only this machine's real run; system-level RAM/VRAM sampling is approximate, not model-specific.",
        "runs": [],
    }
    for case in CASES[: args.runs]:
        print("Running", case["case_id"], "...", flush=True)
        record = run_case(args.base_url, args.model, case, args.timeout, args.interval)
        report["runs"].append(record)
        print("  ", record["status"], "wall:", record.get("api_duration_s"), "s")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Saved real results to:", args.output)
    return (
        0 if all(r["status"] == "needs_teacher_review" for r in report["runs"]) else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
