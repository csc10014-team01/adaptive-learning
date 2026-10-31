"""Optional LOCAL Ollama demonstration; never part of normal regression tests."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from src.ai.qwen_client import QwenClient
from src.ai.template_instantiator import TemplateInstantiator, template_digest
from src.ai.template_presentations import is_experimental
from src.api.data_adapter import DEFAULT_BANK
from src.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter
from src.api.schemas import ExamResponse
from src.orchestration.exam_service import ExamService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="eval/results/experimental_indirect_smoke_2026-10-30.json")
    parser.add_argument("--template", choices=("EA0013", "EA0017"), default="EA0017")
    args = parser.parse_args()
    data = M3DataAdapter()
    data._presentation_registry = data.presentation_registry.model_copy(update={"experimental_indirect": True})
    attempts = []

    class RecordingQwen(QwenClient):
        def generate_one(self, expression, **kwargs):
            started = time.monotonic()
            candidate = super().generate_one(expression, **kwargs)
            attempts.append({"generate_type": expression.generate_type,
                "parameters": expression.template_context.instance.parameters,
                "attempt": kwargs.get("attempt"), "feedback": kwargs.get("feedback", ""),
                "raw_response": candidate.raw_response, "elapsed_seconds": round(time.monotonic() - started, 3)})
            return candidate

    model = RecordingQwen(timeout=90, exam_timeout=240)
    service = ExamService(data, model)
    definition = next(t for t in data.templates if t.template_id == args.template)
    parameters = ({"team_count": 5, "matches_per_pair": 2} if args.template == "EA0013"
        else {"n": 5, "arrange_all": True, "distinct": True})
    instance = TemplateInstantiator().materialize(definition, parameters)
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (DEFAULT_BANK, DEFAULT_STUDENTS)}
    report = {"model": model.model, "mocked": False, "template_id": definition.template_id,
              "semantic_equivalence_verified": False, "cases": [], "hashes_before": before}

    def record(name, candidate, source):
        item = {"case": name, "content": candidate.content,
            "generate_type": candidate.expression.generate_type,
            "presentation": candidate.expression.template_context.presentation.model_dump(mode="json"),
            "parameters": source.record.parameters, "authoritative_answer": source.answer.correct_answer,
            "validation_status": candidate.validation.status, "notes": candidate.validation.reasons}
        report["cases"].append(item)
        print(name + ": " + candidate.expression.generate_type, flush=True)

    direct = None
    for name, ordinal in (("direct", 0), ("indirect_context_a", 1), ("indirect_context_b", 3)):
        try:
            previous = report["cases"][-1].get("content", "") if report["cases"] else ""
            expression = service._expression(instance, eligible_index=ordinal, variant_index=ordinal // 2,
                previous_wording=previous)
            candidate = service._word_template(instance, time.monotonic() + 240, expression=expression)
            record(name, candidate, instance)
            if name == "direct":
                direct = candidate
        except Exception as exc:
            report["cases"].append({"case": name, "error": str(exc), "code": getattr(exc, "code", type(exc).__name__)})
            print(name + ": FAILED " + str(exc), flush=True)

    if direct:
        question = dict(question_id="SMOKE_TEMPLATE", order_index=1, topic_tag="combinatorics",
            skill_ids=definition.skill_ids, target_skill_id=definition.skill_ids[0],
            cognitive_level=definition.cognitive_level, generate_type="direct", content_latex=direct.content,
            max_score=10.0, source_ref={"kind": "template", "id": definition.template_id},
            template_instance=instance.record.model_dump(), template_presentation=direct.expression.template_context.presentation.model_dump(),
            source_digest=template_digest(definition), answer=instance.answer.model_dump(),
            step_solutions=[{"step_number": i, "explanation": text, "score": 5.0}
                for i, text in enumerate(instance.solution_steps, 1)],
            rubric=[{"criteria": "Teacher review required", "sub_score": 10.0}],
            validation={"auto_status": "needs_review", "teacher_approved": False, "review_notes": direct.validation.reasons})
        exam = ExamResponse(exam_id="SMOKE_IN_MEMORY", student_id="SMOKE_NO_PROFILE_WRITES", grade_level=10,
            topic_id="combinatorics", title="Local Qwen experimental smoke", generation_mode="adaptive",
            total_questions=1, duration_minutes=45, total_score=10.0, status="pending_teacher_review",
            provenance={"generator": "qwen", "model": model.model}, questions=[question])
        try:
            regenerated = service.regenerate_question(exam, "SMOKE_TEMPLATE")
            data.validate_exam_references(regenerated)
            target = regenerated.questions[0]
            report["regeneration"] = {"before": exam.questions[0].model_dump(mode="json"),
                "after": target.model_dump(mode="json"), "revision": [exam.revision, regenerated.revision],
                "status": regenerated.status, "experimental": is_experimental(target.template_presentation)}
            print("regeneration: " + target.generate_type, flush=True)
        except Exception as exc:
            report["regeneration"] = {"error": str(exc), "code": getattr(exc, "code", type(exc).__name__)}
            print("regeneration: FAILED " + str(exc), flush=True)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (DEFAULT_BANK, DEFAULT_STUDENTS)}
    report["hashes_after"] = after
    report["attempts"] = attempts
    report["canonical_data_unchanged"] = before == after
    indirect = [x for x in report["cases"] if x.get("presentation", {}).get("verification_status") == "experimental"]
    report["two_indirect_outputs_are_different"] = len(indirect) == 2 and indirect[0]["content"] != indirect[1]["content"]
    report["smoke_goals_met"] = bool(direct and len(indirect) == 2 and report["two_indirect_outputs_are_different"]
        and report.get("regeneration", {}).get("experimental") and before == after)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Report: " + str(output) + "; smoke_goals_met=" + str(report["smoke_goals_met"]), flush=True)


if __name__ == "__main__":
    main()
