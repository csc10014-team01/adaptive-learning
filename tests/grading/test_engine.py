import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.grading import engine
from src.grading.config import GradingConfig
from src.grading.qwen_client import QwenClient
from tools.grading_provenance import ProvenanceError, verify_repository

ROOT = Path(__file__).resolve().parents[2]
REPLAYS = json.loads(
    (ROOT / "tests/fixtures/grading_v11/recorded_replays.json").read_text(
        encoding="utf-8"
    )
)
MODEL = "qwen3:4b-q4_K_M"


def envelope(proposal, model=MODEL):
    return {
        "model": model,
        "done": True,
        "done_reason": "stop",
        "response": json.dumps(proposal, ensure_ascii=False),
    }


@pytest.mark.parametrize("saved", REPLAYS, ids=lambda x: x["name"])
def test_recorded_payloads_and_compact_outcomes_match_frozen_standalone(saved):
    calls = []

    def transport(path, payload, timeout):
        index = len(calls)
        assert path == "/api/generate" and timeout == 120
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        assert digest == saved["payload_sha256"][index]
        calls.append(payload)
        return {
            "model": MODEL,
            "done": True,
            "done_reason": "stop",
            "response": saved["responses"][index],
        }

    case = copy.deepcopy(saved["case"])
    row = engine.grade_question(
        case, MODEL, client=QwenClient(GradingConfig(), transport=transport)
    )
    assert len(calls) == len(saved["responses"]) <= 2
    formatted = engine.exam_payload([row], 1, 1)
    assert formatted["submissions"] == [saved["expected_submission"]]
    assert formatted["feedback"] == saved["expected_feedback"]
    assert case == saved["case"]
    for payload in calls:
        data = json.loads(payload["prompt"].split("\nDATA:\n")[-1])
        assert set(data) <= {
            "question_text",
            "rubric",
            "reference_answer",
            "student_answer",
            "skill_ids",
            "rejected_quote",
            "issue",
        }
        assert "gold" not in data and "case_id" not in data


def test_all_extracted_definitions_match_frozen_ast_except_explicit_injection():
    try:
        assert verify_repository(ROOT) == 38
    except ProvenanceError as exc:
        pytest.fail(str(exc), pytrace=False)


def test_extraction_repair_only_changes_quote_and_uses_160_token_budget():
    case = REPLAYS[0]["case"]
    proposal = {
        "steps": [
            {
                "evidence": case["student_answer"],
                "description": "Học sinh dùng quy tắc cộng.",
                "rubric_ids": ["R1"],
                "decision": "CORRECT",
                "skill_errors": [],
            }
        ],
        "final_answer_quote": "absent",
    }
    # Use a nonterminal conclusion so the frozen explicit-conclusion fallback cannot repair locally.
    case = {**case, "student_answer": "Hai nhóm không giao nhau nên 5 + 9 = 14 cách."}
    proposal["steps"][0]["evidence"] = case["student_answer"]
    calls = []

    def transport(path, payload, timeout):
        calls.append(payload)
        return envelope(
            proposal if len(calls) == 1 else {"final_answer_quote": "14 cách"}
        )

    row = engine.grade_question(
        case, MODEL, client=QwenClient(GradingConfig(), transport=transport)
    )
    assert row["grading_result"]["overall_result"] == "CORRECT"
    assert len(calls) == 2 and calls[1]["options"]["num_predict"] == 160
    assert "reference_answer" not in json.loads(
        calls[1]["prompt"].split("\nDATA:\n")[1]
    )
    assert row["proposal"]["steps"] == proposal["steps"]


def test_unresolved_invalid_evidence_never_becomes_student_error_or_third_call():
    case = REPLAYS[0]["case"]
    proposal = {
        "steps": [
            {
                "evidence": "Invented evidence",
                "description": "Mô tả.",
                "rubric_ids": ["R1"],
                "decision": "INCOMPLETE_SOLUTION",
                "skill_errors": [],
            }
        ],
        "final_answer_quote": "14",
    }
    calls = []

    def transport(path, payload, timeout):
        calls.append(payload)
        return envelope(proposal)

    row = engine.grade_question(
        case, MODEL, client=QwenClient(GradingConfig(), transport=transport)
    )
    assert len(calls) == 2
    assert row["grading_result"]["overall_result"] == "UNCERTAIN"
    assert row["grading_result"]["errors"] == []
    assert engine.exam_payload([row], 1, 1)["submissions"][0]["answer"] == []


@pytest.mark.parametrize(
    "failure", [TimeoutError("private timeout"), OSError("private unavailable")]
)
def test_provider_failures_never_retry_or_blame_student(failure):
    calls = []

    def transport(*args):
        calls.append(args)
        raise failure

    row = engine.grade_question(
        REPLAYS[0]["case"],
        MODEL,
        client=QwenClient(GradingConfig(), transport=transport),
    )
    assert len(calls) == 1
    assert row["grading_result"]["overall_result"] == "UNCERTAIN"
    assert row["grading_result"]["errors"] == []


@pytest.mark.parametrize(
    "settings",
    [
        {"max_repairs": 2},
        {"timeout_seconds": float("nan")},
        {"num_ctx": 0},
        {"timeout_seconds": float("inf")},
        {"base_url": "http://secret@localhost:11434"},
        {"model": " "},
        {"db_path": ROOT / "data/sample/dataset/question_bank.db"},
    ],
)
def test_configuration_rejects_invalid_settings(settings):
    with pytest.raises(ValueError):
        GradingConfig(**settings)
