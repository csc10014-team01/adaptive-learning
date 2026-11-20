import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_grading_ui_event_workflows():
    node = shutil.which("node")
    if node is None:
        pytest.skip(
            "Node unavailable; run node tests/ui/grading.test.cjs to verify UI workflows"
        )
    result = subprocess.run(
        [node, str(Path(__file__).resolve().parents[1] / "ui/grading.test.cjs")],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["passed"] == 12
