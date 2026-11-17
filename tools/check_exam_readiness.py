"""Read-only generation preflight. This does not measure real-model quality.

Run from the repository: python -B tools/check_exam_readiness.py [--offline]
Only the JSON report is written; generated exams remain in memory.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.exam_generator.api.data_adapter import DEFAULT_BANK
from src.exam_generator.adaptation.planner import RuleBasedPlanner
from src.exam_generator.adaptation.skill_relationships import SkillRelationships
from src.exam_generator.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter
from src.exam_generator.api.schemas import GenerateExamRequest
from src.exam_generator.orchestration.exam_service import ExamService
from src.exam_generator.orchestration.review_service import validate_regeneration
from src.exam_generator.validation.exam_quality import ExamQualityEvaluator


def source_signature(exam):
    """Ignore new exam/question UUIDs when comparing seeded generation."""
    return [
        (q.source_ref.model_dump(), q.template_instance.model_dump() if q.template_instance else None,
         q.template_presentation.model_dump() if q.template_presentation else None,
         q.content_latex, q.answer.model_dump(), q.target_skill_id, q.skill_ids,
         q.cognitive_level, q.max_score, [s.model_dump() for s in q.step_solutions],
         [r.model_dump() for r in q.rubric])
        for q in exam.questions
    ]


def run_matrix(data, counts, seeds, progress=None, relationships=None):
    counts, seeds = tuple(counts), tuple(seeds)
    failures, strategies, sources, outcomes = [], Counter(), Counter(), Counter()
    completed, replayed, regenerated, regeneration_unavailable = 0, 0, 0, 0
    profiles = data.profiles
    for student_id, student in sorted(profiles.items()):
        for count in counts:
            for seed in seeds:
                case = {"student_id": student_id, "total_questions": count, "seed": seed}
                try:
                    request = GenerateExamRequest(
                        student_id=student_id, generation_mode="adaptive",
                        selected_topic_ids=["combinatorics"], total_questions=count,
                        duration_minutes=45,
                    )
                    service = ExamService(
                        data, None, fake=True, instance_seed=seed,
                        planner=RuleBasedPlanner(data, relationships=relationships),
                    )
                    exam = service.generate(request, student)
                    data.validate_exam_references(exam)
                    report = ExamQualityEvaluator().evaluate(
                        exam, data=data, profile=student, request=request,
                    )
                    if report.status not in ("PASS", "NEEDS_REVIEW"):
                        reasons = [check.evidence for c in report.criteria for check in c.checks
                                   if check.status in ("HARD_FAIL", "QUALITY_FAIL", "RETRYABLE_FAIL")]
                        raise ValueError(f"{report.status}: {reasons}")
                    if count == max(counts) and seed == seeds[0]:
                        repeated = service.generate(request, student)
                        if source_signature(exam) != source_signature(repeated):
                            raise ValueError("Same seed/profile/source produced different examination content")
                        replayed += 1
                        target = next((q for q in exam.questions if q.source_ref.kind == "template"), None)
                        if target is not None:
                            from src.exam_generator.api.data_adapter import ApiFailure

                            try:
                                updated = service.regenerate_question(exam, target.question_id)
                            except ApiFailure as exc:
                                if exc.code != "TEMPLATE_INSTANTIATION_FAILED":
                                    raise
                                regeneration_unavailable += 1
                            else:
                                validate_regeneration(exam, updated, target.question_id, data=data)
                                data.validate_exam_references(updated)
                                updated_report = ExamQualityEvaluator().evaluate(
                                    updated, data=data, profile=student, request=request,
                                )
                                if updated_report.status not in ("PASS", "NEEDS_REVIEW"):
                                    raise ValueError(f"Regeneration quality check failed: {updated_report.status}")
                                regenerated += 1
                    strategies[exam.planner_summary.strategy] += 1
                    sources.update(q.source_ref.kind for q in exam.questions)
                    outcomes[report.status] += 1
                except Exception as exc:
                    # A doctor report must retain every failed case, including
                    # unexpected implementation exceptions; it never treats them as passes.
                    failures.append({**case, "error_type": type(exc).__name__,
                                     "code": getattr(exc, "code", None), "reason": str(exc)})
                completed += 1
                if progress and completed % 50 == 0:
                    progress(completed)
    return {
        "profiles": len(profiles), "counts": list(counts), "seeds": list(seeds),
        "cases": completed, "passed": completed - len(failures), "failures": failures,
        "deterministic_replays": replayed, "strategies": dict(strategies),
        "regeneration_checks": regenerated, "regeneration_capacity_exhausted": regeneration_unavailable,
        "question_sources": dict(sources), "quality_outcomes": dict(outcomes),
        "qwen_inference_calls": 0,
    }


def check_ollama(base_url, model):
    try:
        with urlopen(base_url.rstrip("/") + "/api/version", timeout=3) as response:
            version = json.load(response)["version"]
        with urlopen(base_url.rstrip("/") + "/api/tags", timeout=3) as response:
            models = json.load(response)["models"]
        if not isinstance(version, str) or not version.strip() or not isinstance(models, list) or any(not isinstance(m, dict) for m in models):
            raise ValueError("Malformed Ollama version/model catalogue")
        installed = next((item for item in models if model in (item.get("name"), item.get("model"))), None)
        return {"status": "AVAILABLE" if installed else "MODEL_MISSING", "model": model,
                "version": version, "digest": installed.get("digest") if installed else None,
                "inference_executed": False}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"status": "UNAVAILABLE", "model": model, "reason": str(exc), "inference_executed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Skip Ollama connectivity check")
    parser.add_argument("--counts", nargs="+", type=int, choices=range(1, 11), default=list(range(1, 11)))
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 42, 2026])
    parser.add_argument("--output", type=Path, default=ROOT / "eval/results/exam_generation_preflight.json")
    args = parser.parse_args(argv)

    def project_path(value):
        path = Path(value)
        return path if path.is_absolute() else ROOT / path

    bank = project_path(os.getenv("M3_QUESTION_DB", str(DEFAULT_BANK)))
    students = project_path(os.getenv("M3_STUDENT_DB", str(DEFAULT_STUDENTS)))
    model = os.getenv("QWEN_MODEL", "qwen3:1.7b")
    paths = [bank, students]
    started = time.monotonic()
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "real_model_quality": "NOT_EVALUATED"}
    try:
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        data = M3DataAdapter(bank_path=bank, student_path=students)
        relationship_file = os.getenv("SKILL_RELATIONSHIPS_FILE")
        relationships = SkillRelationships.load(project_path(relationship_file)) if relationship_file else None
        report["relationship_policy"] = relationships.version if relationships else None
        report["eligible_questions"] = len(data.questions)
        report["template_definitions"] = len(data.templates)
        report["matrix"] = run_matrix(data, args.counts, args.seeds,
                                      progress=lambda n: print(f"Checked {n} offline cases", flush=True),
                                      relationships=relationships)
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        report["source_sha256"] = before
        report["source_databases_unchanged"] = before == after
        offline_ok = before == after and not report["matrix"]["failures"]
    except Exception as exc:
        report["source_error"] = f"{type(exc).__name__}: {exc}"
        offline_ok = False
    report["ollama"] = {"status": "NOT_CHECKED", "inference_executed": False} if args.offline else check_ollama(
        os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), model,
    )
    report["offline_checks_passed"] = offline_ok
    report["ready_to_attempt_live_generation"] = offline_ok and report["ollama"]["status"] == "AVAILABLE"
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    code_paths = sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "config").glob("*.json"))
    code_paths += [Path(__file__).resolve()]
    report["code_sha256"] = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in code_paths}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    report["commit"] = commit.stdout.strip() if commit.returncode == 0 else None
    changes = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False)
    report["working_tree_dirty"] = bool(changes.stdout.strip()) if changes.returncode == 0 else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "offline_checks_passed": offline_ok,
                      "ollama": report["ollama"]["status"], "real_model_quality": "NOT_EVALUATED"}))
    return 0 if offline_ok and (args.offline or report["ready_to_attempt_live_generation"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
