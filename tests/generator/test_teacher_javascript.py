"""Run actual UI workflow code where Node is available; no browser dependencies."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_teacher_review_javascript_workflows():
    node = shutil.which("node")
    if node is None:
        pytest.skip(
            "Node is unavailable; run tests/ui/teacher_review.test.cjs in a JavaScript runtime"
        )
    script = Path(__file__).resolve().parents[1] / "ui/teacher_review.test.cjs"
    result = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=20, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["passed"] == 20


def test_new_teacher_views_review_and_grading_handoff():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node unavailable for teacher workflow checks")
    script = Path(__file__).resolve().parents[1] / "ui/teacher_workflow.test.cjs"
    result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["passed"] == 4
