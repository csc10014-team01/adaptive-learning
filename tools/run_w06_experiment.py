"""Run the frozen W06 live-model protocol and retain every generation attempt.

Examples:
  python -B tools/run_w06_experiment.py --phase pilot --limit 3
  python -B tools/run_w06_experiment.py --phase formal
  python -B tools/run_w06_experiment.py --resume eval/results/w06/<run>
  python -B tools/run_w06_experiment.py --summarize eval/results/w06/<run>

No fake mode, automatic teacher approval or source database writes are performed.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ai.qwen_spike import ResourceMonitor, get_json, gpu_inventory, model_metadata, post_json
from src.exam_generator.adaptation.planner import RuleBasedPlanner
from src.exam_generator.ai.qwen_client import QwenClient
from src.exam_generator.api.data_adapter import DEFAULT_BANK
from src.exam_generator.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter
from src.exam_generator.api.schemas import GenerateExamRequest
from src.exam_generator.orchestration.exam_service import ExamService
from src.exam_generator.validation.exam_quality import ExamQualityEvaluator
from src.exam_generator.validation.question_validator import QuestionValidator

LOCAL_TZ = timezone(timedelta(hours=7))
GRADING_FIELDS = ["case_id", "student_id", "seed", "mode", "exam_id", "content_fingerprint", "reviewer", "criterion_id",
                  "max_score", "score", "evidence", "hard_fail_confirmed", "hard_fail_reason"]
QUESTION_FIELDS = ["case_id", "question_id", "source_kind", "source_id", "generate_type",
                   "verification_status", "target_skill_id", "cognitive_level", "question",
                   "reference_answer", "math_correct", "meaning_preserved", "skill_aligned",
                   "difficulty_aligned", "duplicate_issue", "formatting_issue", "notes"]


def now():
    return datetime.now(LOCAL_TZ).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_hashes():
    files = sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "config").glob("*.json"))
    files.append(Path(__file__).resolve())
    return {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in files}


def safe_endpoint(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    if parsed.port:
        host += f":{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def build_cases(selection):
    cases = []
    for seed in selection["seeds"]:
        for selected in selection["selected_profiles"]:
            for mode in ("strict", "experimental"):
                sid = selected["student_id"]
                slug = re.sub(r"[^A-Za-z0-9_-]", "_", sid)
                cases.append({"case_id": f"C{len(cases)+1:02d}_{slug}_s{seed}_{mode}",
                              "student_id": sid, "seed": seed, "mode": mode})
    return cases


class ResponseRecorder:
    def __init__(self, response, target):
        self.response, self.target = response, target

    def __enter__(self):
        self.response.__enter__()
        self.output = self.target.open("wb")
        return self

    def read1(self, size):
        chunk = self.response.read1(size)
        self.output.write(chunk)
        self.output.flush()
        return chunk

    def __exit__(self, *args):
        self.output.close()
        return self.response.__exit__(*args)


class RecordingQwenClient(QwenClient):
    """Observe the existing transport without rebuilding or changing its prompt."""

    def __init__(self, directory, **kwargs):
        super().__init__(**kwargs)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.records = []
        self.current_record = None

    def save_record(self):
        write_json(self.directory / f"{self.current_record['sequence']:03d}.json", self.current_record)

    def generate_one(self, content, **kwargs):
        sequence = len(self.records) + 1
        record = {"sequence": sequence, "started_at": now(), "transport_status": "RUNNING",
                  "attempt_index": kwargs.get("attempt", 0), "feedback": kwargs.get("feedback", ""),
                  "source_id": getattr(content, "source_id", None),
                  "generate_type": getattr(content, "generate_type", "direct"), "validation": None}
        context = getattr(content, "template_context", None)
        if context is not None:
            record.update(template_id=context.definition.template_id,
                          template_instance=context.instance.model_dump(mode="json"),
                          presentation=context.presentation.model_dump(mode="json") if context.presentation else None,
                          source_text=content.source_text)
        self.records.append(record)
        self.current_record = record
        self.save_record()
        original_open = urlopen

        def record_open(request, **options):
            write_json(self.directory / f"{sequence:03d}.request.json", {
                "endpoint": safe_endpoint(request.full_url), "timeout_seconds": options.get("timeout"),
                "payload": json.loads(request.data.decode("utf-8")),
            })
            raw_path = self.directory / f"{sequence:03d}.response.bin"
            try:
                response = original_open(request, **options)
            except HTTPError as exc:
                raw_path.write_bytes(exc.read(1_000_001))
                record["http_status"] = exc.code
                raise
            record["http_status"] = getattr(response, "status", 200)
            return ResponseRecorder(response, raw_path)

        started = time.monotonic()
        try:
            # Dedicated sequential benchmark process: patch is limited to this
            # call and does not affect another API/server process.
            with patch("src.exam_generator.ai.qwen_client.urlopen", record_open):
                candidate = super().generate_one(content, **kwargs)
            record.update(transport_status="SUCCESS", raw_model_response=candidate.raw_response)
            return candidate
        except Exception as exc:
            record.update(transport_status="FAILED", error_type=type(exc).__name__,
                          error_code=getattr(exc, "code", None), error=str(exc))
            raise
        finally:
            record.update(elapsed_seconds=round(time.monotonic() - started, 6), finished_at=now())
            raw_path = self.directory / f"{sequence:03d}.response.bin"
            if raw_path.exists():
                try:
                    envelope = json.loads(raw_path.read_bytes())
                    record["ollama_metrics"] = {key: envelope.get(key) for key in (
                        "done", "done_reason", "total_duration", "load_duration", "prompt_eval_count",
                        "prompt_eval_cached_count", "prompt_eval_duration", "eval_count", "eval_duration")}
                except (ValueError, AttributeError):
                    pass
            self.save_record()


class RecordingValidator(QuestionValidator):
    def __init__(self, client):
        self.client = client

    def validate(self, expression, candidate):
        try:
            result = super().validate(expression, candidate)
        except Exception as exc:
            self.client.current_record["validation_error"] = f"{type(exc).__name__}: {exc}"
            self.client.save_record()
            raise
        self.client.current_record["validation"] = result.model_dump(mode="json")
        self.client.save_record()
        return result


def validate_inputs(selection_path):
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    for stored_path, expected in selection["source_sha256"].items():
        path = Path(stored_path)
        if not path.exists():
            path = DEFAULT_BANK if path.name == DEFAULT_BANK.name else DEFAULT_STUDENTS
        if sha256(path) != expected:
            raise ValueError(f"Source database changed since profile selection: {path.name}")
    data = M3DataAdapter()
    policy = RuleBasedPlanner(data).policy
    expected = selection["planner_policy"]
    if (policy.version, policy.min_evidence, policy.mastery_target) != (
        expected["version"], expected["min_evidence"], expected["mastery_target"]
    ) or expected["relationships_enabled"]:
        raise ValueError("Selected-profile planner policy differs from the frozen protocol")
    for item in selection["selected_profiles"]:
        actual = data.get_profile(item["student_id"]).model_dump(mode="json", exclude={"name"})
        if actual != item["profile_snapshot"]:
            raise ValueError(f"Profile snapshot changed: {item['student_id']}")
    return selection, data


def require_model(base_url, model):
    metadata = model_metadata(base_url, model)
    if metadata.get("metadata_error") or not metadata.get("version") or not metadata.get("digest"):
        raise RuntimeError(f"Ollama/model is unavailable: {metadata}")
    return metadata


def exam_text(exam):
    lines = [exam.title, f"{exam.exam_id} | student={exam.student_id} | revision={exam.revision}", ""]
    for q in exam.questions:
        lines.extend([f"Cau {q.order_index} ({q.max_score} diem) | {q.source_ref.kind}:{q.source_ref.id}",
                      f"{q.generate_type} | {q.cognitive_level} | skill={q.target_skill_id}",
                      q.content_latex, "DAP AN: " + q.answer.correct_answer,
                      "LOI GIAI: " + q.answer.explanation, ""])
    return "\n".join(lines)


def run_case(run_dir, case, selection, data, client_config):
    case_dir = run_dir / "cases" / case["case_id"]
    previous = sorted(case_dir.glob("execution_*")) if case_dir.exists() else []
    execution = case_dir / f"execution_{len(previous)+1:02d}"
    execution.mkdir(parents=True, exist_ok=False)
    result = {**case, "status": "RUNNING", "started_at": now(),
              "execution": execution.name, "previous_executions": [p.name for p in previous]}
    write_json(case_dir / "result.json", result)
    write_json(execution / "result.json", result)
    profile = data.get_profile(case["student_id"])
    selected = next((p for p in selection.get("selected_profiles", []) if p["student_id"] == profile.student_id), None)
    if selected and profile.model_dump(mode="json", exclude={"name"}) != selected["profile_snapshot"]:
        raise ValueError("Profile changed between preflight and case execution")
    profile.name = profile.student_id  # Anonymize display name; numeric inputs are unchanged.
    request = GenerateExamRequest(student_id=profile.student_id, **selection["request"])
    write_json(execution / "profile.json", profile.model_dump(mode="json"))
    write_json(execution / "request.json", request.model_dump(mode="json"))
    client = RecordingQwenClient(execution / "attempts", **client_config)
    validator = RecordingValidator(client)
    started = time.monotonic()
    try:
        with patch.dict(os.environ, {"KORO_EXPERIMENTAL_INDIRECT": "1" if case["mode"] == "experimental" else "0"}):
            plan = RuleBasedPlanner(data).plan(request, profile, seed=case["seed"])
            write_json(execution / "plan_preview.json", plan.model_dump(mode="json"))
            with ResourceMonitor() as resources:
                exam = ExamService(data, client, validator=validator, instance_seed=case["seed"]).generate(request, profile)
                data.validate_exam_references(exam)
                exam.quality_report = ExamQualityEvaluator().evaluate(exam, data=data, profile=profile, request=request)
            write_json(execution / "exam.json", exam.model_dump(mode="json"))
            (execution / "exam.txt").write_text(exam_text(exam), encoding="utf-8")
            sources = Counter(q.source_ref.kind for q in exam.questions)
            result.update(status="GENERATED", exam_id=exam.exam_id, revision=exam.revision,
                          sources=dict(sources), quality_status=exam.quality_report.status,
                          content_fingerprint=exam.quality_report.content_fingerprint,
                          automatic_w06_score=exam.quality_report.total_score,
                          quota_summary=exam.planner_summary.quota_summary.model_dump(mode="json"),
                          warnings=exam.planner_summary.warnings, resources=resources.as_dict(),
                          final_qwen_questions=sources["template"],
                          experimental_questions=sum(bool(q.template_presentation and q.template_presentation.verification_status == "experimental") for q in exam.questions))
    except Exception as exc:
        result.update(status="FAILED", error_type=type(exc).__name__, error_code=getattr(exc, "code", None), error=str(exc))
        (execution / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        result.update(elapsed_seconds=round(time.monotonic() - started, 6), finished_at=now(),
                      qwen_calls=len(client.records),
                      wording_retries=sum(r["attempt_index"] > 0 for r in client.records),
                      transport_failures=sum(r["transport_status"] == "FAILED" for r in client.records),
                      rejected_wordings=sum(r.get("validation", {}).get("status") == "fail" for r in client.records if r.get("validation")),
                      successful_validated_wordings=sum(r.get("validation", {}).get("status") in ("pass", "needs_review") for r in client.records if r.get("validation")))
        write_json(execution / "result.json", result)
        write_json(case_dir / "result.json", result)
    return result


def merge_csv(path, fields, incoming, keys):
    existing = []
    header = list(fields)
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames or not set(keys) <= set(reader.fieldnames):
                raise ValueError(f"Refusing to overwrite an unrecognized review sheet: {path.name}")
            header.extend(f for f in reader.fieldnames if f not in header)
            existing = list(reader)
    seen = {tuple(row.get(k, "") for k in keys) for row in existing}
    for row in incoming:
        key = tuple(str(row.get(k, "")) for k in keys)
        if key not in seen:
            existing.append(row)
            seen.add(key)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=header)
        writer.writeheader()
        writer.writerows(existing)
    temporary.replace(path)


def grading_summary(run_dir, results):
    reviewers = {}
    disagreements = []
    for reviewer in ("R1", "R2"):
        with (run_dir / f"grading_{reviewer}.csv").open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        cases = {}
        for result in results:
            if result["status"] != "GENERATED":
                continue
            selected = [row for row in rows if row["case_id"] == result["case_id"]]
            errors, points, flags = [], [], []
            if any(row.get("exam_id") != result["exam_id"] or row.get("content_fingerprint") != result["content_fingerprint"]
                   or row.get("reviewer") != reviewer for row in selected):
                cases[result["case_id"]] = {"status": "PENDING", "total_score": None,
                                            "errors": ["Review does not match this exam, fingerprint or reviewer"]}
                continue
            confirmed = [row for row in selected if row["hard_fail_confirmed"].strip().lower() == "yes" and row["hard_fail_reason"].strip()]
            if confirmed:
                # W06 defines a confirmed hard-fail as zero overall. Unassessed
                # criterion cells remain blank; they are never assigned points.
                cases[result["case_id"]] = {"status": "HARD_FAIL", "total_score": 0.0,
                                            "hard_fail_confirmed": True,
                                            "reasons": [row["hard_fail_reason"] for row in confirmed]}
                continue
            if len(selected) != 4 or {r["criterion_id"] for r in selected} != {"C1", "C2", "C3", "C4"}:
                errors.append("Missing or duplicate criterion rows")
            for row in selected:
                maximum = {"C1": 35, "C2": 25, "C3": 20, "C4": 20}.get(row["criterion_id"])
                try:
                    score = float(row["score"])
                    if maximum is None or not math.isfinite(score) or not 0 <= score <= maximum:
                        raise ValueError("Score outside approved maximum")
                    if not row["evidence"].strip():
                        raise ValueError("Evidence missing")
                    flag = row["hard_fail_confirmed"].strip().lower()
                    if flag not in ("yes", "no") or (flag == "yes" and not row["hard_fail_reason"].strip()):
                        raise ValueError("Confirm hard-fail yes/no and supply a reason for yes")
                    points.append(score)
                    flags.append(flag == "yes")
                except (ValueError, TypeError) as exc:
                    errors.append(f"{row['criterion_id']}: {exc}")
            if errors:
                cases[result["case_id"]] = {"status": "PENDING", "total_score": None, "errors": errors}
            else:
                total, hard = sum(points), any(flags)
                cases[result["case_id"]] = {"status": "HARD_FAIL" if hard else "PASS" if total >= 80 else "QUALITY_FAIL",
                                            "total_score": total, "hard_fail_confirmed": hard}
        scored = [r for r in cases.values() if r["status"] != "PENDING"]
        reviewers[reviewer] = {"assessed_cases": len(scored), "generated_cases": len(cases),
                               "mean_score": sum(r["total_score"] for r in scored) / len(scored) if scored else None,
                               "pass_cases": sum(r["status"] == "PASS" for r in scored), "cases": cases}
    for case_id, first in reviewers["R1"]["cases"].items():
        second = reviewers["R2"]["cases"][case_id]
        if first["status"] != "PENDING" and second["status"] != "PENDING":
            if first["status"] != second["status"]:
                disagreements.append(case_id)
    all_complete = bool(reviewers["R1"]["generated_cases"]) and all(
        r["assessed_cases"] == r["generated_cases"] for r in reviewers.values()
    )
    return {"status": "NEEDS_ADJUDICATION" if disagreements else "COMPLETE" if all_complete else "PENDING",
            "reviewers": reviewers, "verdict_disagreements": disagreements}


def summarize(run_dir):
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    rows, grading, questions = [], [], []
    for case in manifest["cases"]:
        case_dir = run_dir / "cases" / case["case_id"]
        result_path = case_dir / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {**case, "status": "NOT_RUN"}
        rows.append(result)
        if result["status"] != "GENERATED":
            continue
        exam = json.loads((case_dir / result["execution"] / "exam.json").read_text(encoding="utf-8"))
        for reviewer in ("R1", "R2"):
            for cid, maximum in (("C1", 35), ("C2", 25), ("C3", 20), ("C4", 20)):
                grading.append({**{k:str(case[k]) for k in ("case_id", "student_id", "seed", "mode")},
                                "exam_id": result["exam_id"], "content_fingerprint": result["content_fingerprint"],
                                "reviewer": reviewer, "criterion_id": cid, "max_score": str(maximum),
                                "score": "", "evidence": "", "hard_fail_confirmed": "", "hard_fail_reason": ""})
        for q in exam["questions"]:
            def spreadsheet_text(value):
                return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

            questions.append({"case_id": case["case_id"], "question_id": q["question_id"],
                              "source_kind": q["source_ref"]["kind"], "source_id": q["source_ref"]["id"],
                              "generate_type": q["generate_type"], "verification_status": (q.get("template_presentation") or {}).get("verification_status", "bank_source"),
                              "target_skill_id": q.get("target_skill_id"), "cognitive_level": q["cognitive_level"],
                              "question": spreadsheet_text(q["content_latex"]), "reference_answer": spreadsheet_text(q["answer"]["correct_answer"])})
    for reviewer in ("R1", "R2"):
        merge_csv(run_dir / f"grading_{reviewer}.csv", GRADING_FIELDS,
                  [row for row in grading if row["reviewer"] == reviewer], ("case_id", "criterion_id", "reviewer"))
        merge_csv(run_dir / f"question_review_{reviewer}.csv", QUESTION_FIELDS, questions, ("case_id", "question_id"))
    status = Counter(row["status"] for row in rows)
    completed = [row for row in rows if row["status"] in ("GENERATED", "FAILED")]
    human = grading_summary(run_dir, rows)
    summary = {"phase": manifest["phase"], "run_status": manifest["status"], "planned_cases": len(rows),
               "case_statuses": dict(status), "attempted_cases": len(completed),
               "qwen_calls": sum(row.get("qwen_calls", 0) for row in completed),
               "transport_failures": sum(row.get("transport_failures", 0) for row in completed),
               "rejected_wordings": sum(row.get("rejected_wordings", 0) for row in completed),
               "bank_only_generated_cases": sum(row["status"] == "GENERATED" and row.get("final_qwen_questions", 0) == 0 for row in rows),
               "human_quality_assessment": human["status"], "human_reviews": human,
               "w06_mean_score": None, "cases": rows}
    for group_field, output_key in (("mode", "by_mode"), ("student_id", "by_profile")):
        summary[output_key] = {}
        for group in sorted({r[group_field] for r in rows}):
            members = [r for r in completed if r[group_field] == group]
            summary[output_key][group] = {
                "attempted": len(members), "generated": sum(r["status"] == "GENERATED" for r in members),
                "failed": sum(r["status"] == "FAILED" for r in members),
                "qwen_calls": sum(r.get("qwen_calls", 0) for r in members),
                "wording_retries": sum(r.get("wording_retries", 0) for r in members),
                "mean_seconds_all_attempted": sum(r["elapsed_seconds"] for r in members) / len(members) if members else None,
            }
    write_json(run_dir / "summary.json", summary)
    report = ["# W06 experiment — " + manifest["phase"], "", f"Run status: {manifest['status']}",
              f"Planned: {len(rows)}; generated: {status['GENERATED']}; failed: {status['FAILED']}; not run: {status['NOT_RUN']}.",
              f"Actual Qwen calls: {summary['qwen_calls']}; transport failures: {summary['transport_failures']}; rejected wordings: {summary['rejected_wordings']}.",
              "", f"Human W06 assessment: {human['status']}. No mean score or quality pass rate has been inferred from automatic checks.",
              "Pilot runs are separate from the formal sample. Question occurrences are not necessarily unique questions.",
              "", "| Case | Status | Seconds | Qwen calls | Quality status |", "|---|---|---:|---:|---|"]
    report.extend(f"| {r['case_id']} | {r['status']} | {r.get('elapsed_seconds','')} | {r.get('qwen_calls',0)} | {r.get('quality_status','')} |" for r in rows)
    report.extend(["", "## Configuration comparison (descriptive)", "", "| Mode | Attempted | Generated | Failed | Qwen calls | Wording retries | Mean seconds, all attempted |",
                   "|---|---:|---:|---:|---:|---:|---:|"])
    report.extend(f"| {mode} | {r['attempted']} | {r['generated']} | {r['failed']} | {r['qwen_calls']} | {r['wording_retries']} | {r['mean_seconds_all_attempted']} |" for mode, r in summary["by_mode"].items())
    report.extend(["", "## Independent human reviews", "", "| Reviewer | Assessed/generated | Mean score on assessed cases | Pass cases |",
                   "|---|---|---|---|"])
    report.extend(f"| {name} | {r['assessed_cases']}/{r['generated_cases']} | {r['mean_score'] if r['mean_score'] is not None else 'PENDING'} | {r['pass_cases']} |" for name, r in human["reviewers"].items())
    (run_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, default=ROOT / "eval/benchmarks/w06_selected_profiles.json")
    parser.add_argument("--phase", choices=("pilot", "formal"), default="pilot")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--summarize", type=Path)
    parser.add_argument("--base-url", default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--model", default=os.getenv("QWEN_MODEL", "qwen3:1.7b"))
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--exam-timeout", type=float, default=180)
    parser.add_argument("--attempts", type=int, default=2)
    args = parser.parse_args(argv)
    if args.summarize:
        print(json.dumps(summarize(args.summarize), ensure_ascii=True))
        return 0
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.phase == "formal" and args.limit is not None:
        parser.error("Formal sample cannot be silently reduced; use --phase pilot")
    client_config = {"base_url": args.base_url.rstrip("/"), "model": args.model,
                     "timeout": args.timeout, "exam_timeout": args.exam_timeout, "attempts": args.attempts}
    QwenClient(**client_config)  # Validate limits before creating output artifacts.
    selection, data = validate_inputs(args.selection)
    cases = build_cases(selection)
    if args.phase == "pilot":
        cases = cases[:args.limit or 3]
    run_dir = args.resume or args.output or ROOT / "eval/results/w06" / (datetime.now(LOCAL_TZ).strftime("%Y%m%d_%H%M%S") + "_" + args.phase)
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "run.json"
    frozen = {"selection_sha256": sha256(args.selection), "source_code_sha256": code_hashes(),
              "rubric_sha256": sha256(ROOT / "docs/notes/W06_Rubric.md"),
              "client_config": {**client_config, "base_url": safe_endpoint(args.base_url)},
              "source_sha256": selection["source_sha256"], "python": platform.python_version(),
              "platform": platform.platform(), "gpu_inventory": gpu_inventory(),
              "presentation_registry": data.presentation_registry.model_dump(mode="json"),
              "sampling": {"strict_temperature": 0, "experimental_temperature": 0.7, "num_predict": 1800,
                           "transport_seed": "42 + instance variation + attempt index, per existing QwenClient"}}
    if args.resume:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["frozen"] != frozen:
            raise ValueError("Resume refused: code, source, runtime or client configuration changed")
        cases = manifest["cases"]
    else:
        if run_dir.exists() and any(run_dir.iterdir()):
            raise ValueError("Output directory is not empty; use a new directory or explicit --resume")
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {"protocol_version": "w06-live-v1", "phase": args.phase, "started_at": now(),
                    "status": "PREPARING", "frozen": frozen, "cases": cases,
                    "generation_timing_scope": "Core generation, source validation and W06 evaluation; excludes warmup and API/auth network overhead",
                    "human_grading_status": "PENDING", "source_databases_read_only": True}
        write_json(run_dir / "selection.json", selection)
        (run_dir / "rubric_snapshot.md").write_text((ROOT / "docs/notes/W06_Rubric.md").read_text(encoding="utf-8"), encoding="utf-8")
    write_json(manifest_path, manifest)
    try:
        metadata = require_model(args.base_url, args.model)
        if manifest.get("ollama") and manifest["ollama"] != metadata:
            raise ValueError("Ollama model digest/version changed; start a separate run")
        manifest["ollama"] = metadata
        write_json(manifest_path, manifest)
        warmup_payload = {"model": args.model, "prompt": "Reply only: OK", "stream": False, "think": False,
                          "keep_alive": "5m", "options": {"temperature": 0, "seed": 42, "num_predict": 16}}
        warmup_started = time.monotonic()
        write_json(run_dir / "warmup_request.json", warmup_payload)
        warmup = post_json(args.base_url.rstrip("/") + "/api/generate", warmup_payload, 180)
        write_json(run_dir / f"warmup_{datetime.now(LOCAL_TZ).strftime('%Y%m%d_%H%M%S')}.json",
                   {"excluded_from_case_metrics": True, "request": warmup_payload, "response": warmup,
                    "elapsed_seconds": time.monotonic() - warmup_started})
        if warmup.get("done") is not True or warmup.get("model") != args.model:
            raise ValueError("Warmup did not complete with the configured model")
        manifest["running_models_after_warmup"] = get_json(args.base_url.rstrip("/") + "/api/ps")
        manifest["status"] = "RUNNING"
        write_json(manifest_path, manifest)
        summarize(run_dir)
        for case in cases:
            result_path = run_dir / "cases" / case["case_id"] / "result.json"
            if result_path.exists() and json.loads(result_path.read_text(encoding="utf-8"))["status"] in ("GENERATED", "FAILED"):
                continue
            validate_inputs(args.selection)
            if code_hashes() != frozen["source_code_sha256"]:
                raise ValueError("Source code changed during experiment; batch stopped")
            if require_model(args.base_url, args.model) != metadata:
                raise ValueError("Model identity changed during experiment; batch stopped")
            print("RUN " + case["case_id"], flush=True)
            result = run_case(run_dir, case, selection, data, client_config)
            print(json.dumps({k:result.get(k) for k in ("case_id", "status", "elapsed_seconds", "qwen_calls", "quality_status")}), flush=True)
            summarize(run_dir)
            validate_inputs(args.selection)
            if code_hashes() != frozen["source_code_sha256"] or sha256(ROOT / "docs/notes/W06_Rubric.md") != frozen["rubric_sha256"]:
                raise ValueError("Code or rubric changed during experiment; batch stopped")
            if require_model(args.base_url, args.model) != metadata:
                raise ValueError("Model identity changed during case execution; batch stopped")
        manifest.update(status="GENERATION_COMPLETE", finished_at=now())
    except KeyboardInterrupt:
        manifest.update(status="INTERRUPTED", interruption_at=now())
    except Exception as exc:
        manifest.update(status="BLOCKED", blocked_at=now(), blocked_reason=f"{type(exc).__name__}: {exc}")
    finally:
        write_json(manifest_path, manifest)
        summary = summarize(run_dir)
    print(json.dumps({"run_directory": str(run_dir), "status": manifest["status"],
                      "case_statuses": summary["case_statuses"], "human_grading_status": "PENDING"}), flush=True)
    return 0 if manifest["status"] == "GENERATION_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
