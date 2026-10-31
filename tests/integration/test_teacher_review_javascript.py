"""Run actual UI workflow code where Node is available; no browser dependencies."""

from pathlib import Path
import json
import shutil
import subprocess

import pytest


def test_teacher_review_javascript_workflows():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable; run tests/ui/teacher_review.test.cjs in a JavaScript runtime")
    script = Path(__file__).resolve().parents[1] / "ui/teacher_review.test.cjs"
    result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["passed"] == 18
