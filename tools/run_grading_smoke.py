"""Run a synthetic real-Qwen example through the integrated protected API/worker.

No canonical student identities, database writes, benchmark labels or accuracy claims.
"""

import argparse
import json
import secrets
import sys
import time
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import create_app  # noqa: E402 -- Allow direct execution from tools/.
from src.grading.config import GradingConfig  # noqa: E402
from src.grading.qwen_client import QwenClient  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Required: call installed local Qwen"
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to run actual local inference")
    config = GradingConfig.from_env()
    model_client = QwenClient(config)
    tags = model_client.request("/api/tags", timeout=5)
    if config.model not in {m["name"] for m in tags.get("models", [])}:
        raise SystemExit(
            f"Required model {config.model} is not installed; no model substitution performed."
        )
    payload = json.loads(
        (ROOT / "src/ui/static/grading-example.json").read_text(encoding="utf-8")
    )
    payload["idempotency_key"] = "smoke-" + uuid4().hex
    token = secrets.token_urlsafe(32)
    headers = {"Authorization": "Bearer " + token}
    start = time.perf_counter()
    with TestClient(create_app(teacher_token=token, grading_config=config)) as client:
        response = client.post("/api/v1/grading/jobs", headers=headers, json=payload)
        if response.status_code != 202:
            raise SystemExit(response.text)
        job_id = response.json()["metadata"]["job_id"]
        print("Accepted", job_id, "model", config.model, flush=True)
        deadline = (
            time.monotonic()
            + len(payload["questions"])
            * config.timeout_seconds
            * (1 + config.max_repairs)
            + 30
        )
        while time.monotonic() < deadline:
            response = client.get(f"/api/v1/grading/jobs/{job_id}", headers=headers)
            response.raise_for_status()
            result = response.json()
            if result["metadata"]["state"] not in ("QUEUED", "RUNNING"):
                break
            time.sleep(0.2)
        else:
            raise SystemExit(
                "Smoke deadline exceeded; job remains stored for inspection"
            )
    folder = ROOT / "data/runtime/grading_smoke"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{job_id}.json"
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "job_id": job_id,
                "state": result["metadata"]["state"],
                "processed": result["metadata"]["completed_questions"],
                "uncertain": result["metadata"]["uncertain_questions"],
                "provider_failures": result["metadata"]["provider_failures"],
                "verdicts": [
                    s["grading_result"]["overall_result"]
                    for s in result["result"]["submissions"]
                ],
                "wall_seconds": round(time.perf_counter() - start, 3),
                "artifact": str(path),
            },
            ensure_ascii=True,
        ),
        flush=True,
    )
    if (
        result["metadata"]["state"] != "COMPLETED"
        or result["metadata"]["provider_failures"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
