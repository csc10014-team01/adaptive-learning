"""Benchmark evidence and grading stay honest without requiring model inference."""

import csv
import io
import json
import time

import pytest

from src.exam_generator.ai.contracts import ExpressionSpec
from src.exam_generator.api.data_adapter import ApiFailure
from src.exam_generator.orchestration.question_generation import QuestionGenerationService
from tools import run_w06_experiment as runner
from tests.generator.unit.test_planner import make_data, profile

SOURCE = "There are 3 red pens and 5 blue pens. Select one pen."


def test_protocol_pairs_all_five_profiles_at_three_seeds():
    selection = json.loads((runner.ROOT / "eval/benchmarks/w06_selected_profiles.json").read_text(encoding="utf-8"))
    cases = runner.build_cases(selection)
    assert len(cases) == len({c["case_id"] for c in cases}) == 30
    assert {c["student_id"] for c in cases} == {"ST016", "ST003", "ST004", "ST008", "ST010"}
    for first, second in zip(cases[::2], cases[1::2]):
        assert (first["student_id"], first["seed"]) == (second["student_id"], second["seed"])
        assert [first["mode"], second["mode"]] == ["strict", "experimental"]


def test_trace_retains_rejected_attempt_raw_http_payload_and_validator_evidence(tmp_path, monkeypatch):
    raw = []
    calls = []

    def transport(request, **kwargs):
        calls.append(json.loads(request.data))
        text = SOURCE + " Add 99 pens." if len(calls) == 1 else SOURCE
        body = json.dumps({"done": True, "done_reason": "stop", "model": client.model,
                           "response": json.dumps({"question": text}), "eval_count": 12}).encode()
        raw.append(body)
        return io.BytesIO(body)

    monkeypatch.setattr(runner, "urlopen", transport)
    client = runner.RecordingQwenClient(tmp_path / "attempts")
    result = QuestionGenerationService(client, runner.RecordingValidator(client)).generate(
        ExpressionSpec(source_id="TEST", source_text=SOURCE), deadline=time.monotonic() + 10,
    )
    assert result.content == SOURCE and len(client.records) == 2
    assert client.records[0]["validation"]["status"] == "fail"
    assert client.records[1]["validation"]["status"] == "needs_review"
    assert calls[0]["options"]["temperature"] == 0 and client.records[1]["feedback"]
    assert (tmp_path / "attempts/001.response.bin").read_bytes() == raw[0]
    assert json.loads((tmp_path / "attempts/002.request.json").read_text(encoding="utf-8"))["payload"] == calls[1]


def test_transport_failure_still_preserves_the_original_envelope(tmp_path, monkeypatch):
    envelope = {"done": True, "done_reason": "length", "model": "qwen3:1.7b", "response": "{}"}
    raw = json.dumps(envelope).encode()
    monkeypatch.setattr(runner, "urlopen", lambda *a, **kw: io.BytesIO(raw))
    client = runner.RecordingQwenClient(tmp_path)
    with pytest.raises(ApiFailure):
        client.generate_one(SOURCE, deadline=time.monotonic() + 10)
    saved = json.loads((tmp_path / "001.json").read_text())
    assert saved["transport_status"] == "FAILED" and saved["error_code"] == "INVALID_QWEN_OUTPUT"
    assert (tmp_path / "001.response.bin").read_bytes() == raw


class EmptyMonitor:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def as_dict(self):
        return {"note": "test monitor"}


def generated_case(tmp_path, monkeypatch):
    data = make_data()
    data._profiles = {"S": profile()}
    monkeypatch.setattr(runner, "ResourceMonitor", EmptyMonitor)
    monkeypatch.setattr(runner, "urlopen", lambda *a, **kw: pytest.fail("Bank-only source must not invoke Qwen"))
    selection = {"request": {"generation_mode": "adaptive", "selected_topic_ids": ["combinatorics"],
                              "total_questions": 4, "duration_minutes": 45}}
    case = {"case_id": "C01_S", "student_id": "S", "seed": 42, "mode": "strict"}
    result = runner.run_case(tmp_path, case, selection, data, {})
    runner.write_json(tmp_path / "run.json", {"phase": "pilot", "status": "GENERATION_COMPLETE", "cases": [case]})
    return result


def test_bank_only_completion_and_pending_human_scores_are_reported_honestly(tmp_path, monkeypatch):
    result = generated_case(tmp_path, monkeypatch)
    assert result["status"] == "GENERATED" and result["qwen_calls"] == 0
    assert result["final_qwen_questions"] == 0 and result["automatic_w06_score"] is None
    summary = runner.summarize(tmp_path)
    assert summary["bank_only_generated_cases"] == 1
    assert summary["human_quality_assessment"] == "PENDING" and summary["w06_mean_score"] is None
    with (tmp_path / "grading_R1.csv").open(encoding="utf-8-sig", newline="") as source:
        assert all(row["score"] == "" for row in csv.DictReader(source))


def test_summary_preserves_completed_human_cells_and_reports_raters_separately(tmp_path, monkeypatch):
    generated_case(tmp_path, monkeypatch)
    runner.summarize(tmp_path)
    for reviewer, scores in (("R1", [35, 25, 18, 18]), ("R2", [20, 20, 15, 15])):
        path = tmp_path / f"grading_{reviewer}.csv"
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        for row, score in zip(rows, scores):
            row.update(score=str(score), evidence="Reviewed all subcriteria and findings.", hard_fail_confirmed="no")
        with path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=runner.GRADING_FIELDS)
            writer.writeheader(); writer.writerows(rows)
    summary = runner.summarize(tmp_path)
    assert summary["human_reviews"]["status"] == "NEEDS_ADJUDICATION"
    assert summary["human_reviews"]["reviewers"]["R1"]["mean_score"] == 96
    assert summary["human_reviews"]["reviewers"]["R2"]["mean_score"] == 70
    assert summary["w06_mean_score"] is None
    assert "96" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_confirmed_hard_failure_is_zero_total_without_filling_unassessed_cells(tmp_path, monkeypatch):
    generated_case(tmp_path, monkeypatch)
    runner.summarize(tmp_path)
    path = tmp_path / "grading_R1.csv"
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    rows[0].update(hard_fail_confirmed="yes", hard_fail_reason="Confirmed wrong mathematical answer.")
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=runner.GRADING_FIELDS)
        writer.writeheader(); writer.writerows(rows)
    summary = runner.summarize(tmp_path)
    first = summary["human_reviews"]["reviewers"]["R1"]["cases"]["C01_S"]
    assert first["status"] == "HARD_FAIL" and first["total_score"] == 0
    with path.open(encoding="utf-8-sig", newline="") as source:
        assert all(row["score"] == "" for row in csv.DictReader(source))


def test_unrecognized_review_sheet_is_not_overwritten(tmp_path):
    path = tmp_path / "review.csv"
    original = "private notes\nKeep this content\n"
    path.write_text(original, encoding="utf-8-sig")
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        runner.merge_csv(path, ["case_id", "score"], [], ["case_id"])
    assert path.read_text(encoding="utf-8-sig") == original


def test_missing_model_records_not_run_instead_of_manufacturing_results(tmp_path, monkeypatch):
    selection = {"source_sha256": {}, "seeds": [42], "selected_profiles": [{"student_id": "S"}]}
    selected_path = tmp_path / "selection.json"
    runner.write_json(selected_path, selection)
    monkeypatch.setattr(runner, "validate_inputs", lambda p: (selection, make_data()))
    monkeypatch.setattr(runner, "require_model", lambda *a: (_ for _ in ()).throw(RuntimeError("model unavailable")))
    monkeypatch.setattr(runner, "gpu_inventory", lambda: [])
    output = tmp_path / "blocked"
    code = runner.main(["--selection", str(selected_path), "--phase", "pilot", "--output", str(output)])
    summary = json.loads((output / "summary.json").read_text())
    assert code == 2 and summary["run_status"] == "BLOCKED"
    assert summary["case_statuses"] == {"NOT_RUN": 2} and summary["qwen_calls"] == 0
