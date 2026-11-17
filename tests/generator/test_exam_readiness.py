"""The preflight retains failures and never equates fake generation with Qwen quality."""

import io
import json

import pytest

from tools.check_exam_readiness import check_ollama, run_matrix
from tests.generator.unit.test_planner import make_data, profile


def test_offline_matrix_retains_failures_and_does_not_mutate_profiles():
    data = make_data()
    student = profile()
    data._profiles = {student.student_id: student}
    before = student.model_dump_json()
    report = run_matrix(data, [1, 4], [42])
    assert report["cases"] == report["passed"] == 2
    assert report["deterministic_replays"] == 1 and not report["failures"]
    assert report["qwen_inference_calls"] == 0
    assert report["quality_outcomes"] == {"NEEDS_REVIEW": 2}
    assert student.model_dump_json() == before
    data._questions = []
    failed = run_matrix(data, [1, 4], [42])
    assert failed["passed"] == 0 and len(failed["failures"]) == 2
    assert all(case["code"] == "INSUFFICIENT_QUESTION_BANK" for case in failed["failures"])


@pytest.mark.parametrize("catalogue,expected", [
    ({"models": [{"name": "qwen3:1.7b", "digest": "observed-digest"}]}, "AVAILABLE"),
    ({"models": []}, "MODEL_MISSING"),
    ({"models": ["malformed"]}, "UNAVAILABLE"),
    ({"models": None}, "UNAVAILABLE"),
])
def test_ollama_probe_checks_installed_model_without_running_inference(monkeypatch, catalogue, expected):
    paths = []

    def response(url, **kwargs):
        paths.append(url)
        value = {"version": "test-version"} if url.endswith("/api/version") else catalogue
        return io.BytesIO(json.dumps(value).encode())

    monkeypatch.setattr("tools.check_exam_readiness.urlopen", response)
    report = check_ollama("http://127.0.0.1:11434", "qwen3:1.7b")
    assert report["status"] == expected and report["inference_executed"] is False
    assert len(paths) == 2 and all("/api/generate" not in path for path in paths)
