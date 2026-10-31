"""Optional real Ollama smoke test; ordinary pytest never calls this module.

Run from the repository root: python -m eval.smoke_exam_generation --live
It reads the M3 bank and one explicitly synthetic spec, never stores drafts.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from src.ai.expression_planner import ExpressionPlanner
from src.ai.problem_spec import ProblemSpec, render_template
from src.ai.qwen_client import QwenClient
from src.api.data_adapter import ApiFailure, FixtureQuestion
from src.api.m3_adapter import M3DataAdapter
from src.api.schemas import GenerateExamRequest
from src.orchestration.exam_service import ExamService
from src.orchestration.question_generation import QuestionGenerationService


def main():
    # Windows terminals may otherwise use cp1252 for Vietnamese output.
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Explicitly call local Ollama"
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("Use --live to run actual local inference")
    client = QwenClient(timeout=45, attempts=2, exam_timeout=100)
    started = time.monotonic()
    results = []
    data = M3DataAdapter()
    student = data.list_students()[0].student_id
    request = GenerateExamRequest(
        student_id=student,
        generation_mode="adaptive",
        selected_topic_ids=["combinatorics"],
        total_questions=1,
        duration_minutes=15,
    )
    try:
        exam = ExamService(data, client).generate(request, data.get_profile(student))
        results.append(
            {
                "path": "legacy_exam",
                "status": exam.status,
                "validation": exam.questions[0].validation.auto_status,
                "source": exam.questions[0].source_ref.id,
                "question": exam.questions[0].content_latex,
            }
        )
    except ApiFailure as error:
        results.append(
            {"path": "legacy_exam", "error": error.code, "message": error.message}
        )
    fixture = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/structured_problem.json"
    )
    spec = ProblemSpec.model_validate_json(fixture.read_text(encoding="utf-8"))
    source = FixtureQuestion(
        question_id=spec.source_id,
        grade_level=10,
        skill_ids=["SYNTHETIC"],
        cognitive_level="understanding",
        generate_type="direct",
        problem_spec=spec,
        content=render_template(
            spec.supported_contexts[0].presentations[0].template, spec.parameters
        ),
        answer={
            "correct_answer": spec.verified_answer,
            "explanation": " ".join(spec.verified_solution),
        },
        solution_steps=spec.verified_solution,
        rubric_criteria=["Synthetic example; teacher review required"],
    )
    for context, kind in [("books", "direct"), ("students", "indirect")]:
        try:
            expression = ExpressionPlanner().plan_expression(
                source, context_id=context, generate_type=kind
            )
            candidate = QuestionGenerationService(client).generate(
                expression, deadline=time.monotonic() + 100
            )
            results.append(
                {
                    "path": f"synthetic_{context}_{kind}",
                    "validation": candidate.validation.status,
                    "question": candidate.content,
                }
            )
        except ApiFailure as error:
            results.append(
                {
                    "path": f"synthetic_{context}_{kind}",
                    "error": error.code,
                    "message": error.message,
                }
            )
    print(
        json.dumps(
            {
                "model": client.model,
                "live_inference": True,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return int(any("error" in result for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
