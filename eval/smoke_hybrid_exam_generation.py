"""Reproducible actual-SQL hybrid smoke test with mocked local Qwen wording.

Run from the application root: python -m eval.smoke_hybrid_exam_generation
Writes only report artifacts and an application-owned runtime draft database.
"""

from collections import Counter
import hashlib
import json
import sqlite3
from threading import BoundedSemaphore

from src.adaptation.planner import RuleBasedPlanner
from src.adaptation.skill_relationships import SkillRelationships
from src.ai.contracts import GenerationCandidate
from src.api.data_adapter import DEFAULT_BANK, ROOT
from src.api.exam_store import SQLiteExamStore
from src.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter
from src.api.schemas import ApproveExamRequest, GenerateExamRequest
from src.orchestration.exam_service import ExamService
from src.orchestration.review_service import approve_exam, validate_regeneration


class LocalEcho:
    model = "mock-local-ollama-hybrid-smoke"
    exam_timeout = 30
    attempts = 2

    def __init__(self):
        self.capacity = BoundedSemaphore(1)
        self.calls = 0

    def generate_one(self, expression, **kwargs):
        assert expression.template_context is not None
        self.calls += 1
        return GenerationCandidate(model=self.model, raw_response=json.dumps({"question": expression.source_text}))


def main():
    paths = (DEFAULT_BANK, DEFAULT_STUDENTS)
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    data, model = M3DataAdapter(), LocalEcho()
    relationships = SkillRelationships.load(ROOT / "config/skill_relationships_a001_a009.json")
    planner = RuleBasedPlanner(data, relationships=relationships)
    request = GenerateExamRequest(student_id="ST001", selected_topic_ids=["combinatorics"],
                                  total_questions=10, duration_minutes=45)
    profile = data.get_profile(request.student_id)
    preview = planner.plan(request, profile, seed=42)
    service = ExamService(data, model, planner=planner, instance_seed=42)
    exam = service.generate(request, profile)
    data.validate_exam_references(exam)
    assert preview.quota_summary == exam.planner_summary.quota_summary
    generation_calls = model.calls
    assert generation_calls == sum(q.source_ref.kind == "template" for q in exam.questions)
    store = SQLiteExamStore(ROOT / "data/runtime/hybrid_smoke_drafts.db")
    store.save(exam)
    approved = approve_exam(exam, ApproveExamRequest(expected_revision=1,
        accepted_question_ids=[q.question_id for q in exam.questions]))
    store.replace(approved, expected_revision=1)
    target = next(q for q in approved.questions if q.template_instance)
    updated = service.regenerate_question(approved, target.question_id)
    validate_regeneration(approved, updated, target.question_id)
    data.validate_exam_references(updated)
    store.replace(updated, expected_revision=2)
    assert store.get(exam.exam_id) == updated
    replacement = next(q for q in updated.questions if q.source_ref == target.source_ref and q.order_index == target.order_index)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before == after
    output = {
        "data_kind": "actual_confirmed_SQL_with_sample_student_and_mock_Ollama",
        "database": str(DEFAULT_BANK), "database_hashes_before": before, "database_hashes_after": after,
        "allocation_and_source_preview": preview.model_dump(mode="json"),
        "exam": exam.model_dump(mode="json"),
        "source_counts": dict(Counter(q.source_ref.kind for q in exam.questions)),
        "generation_model_calls": generation_calls,
        "regeneration": {"old": target.model_dump(mode="json"), "new": replacement.model_dump(mode="json"),
            "revision": updated.revision, "status": updated.status, "model_calls": model.calls - generation_calls,
            "persisted_and_retrieved": True, "unrelated_question_identity_and_scoring_preserved": True},
    }
    destination = ROOT / "eval/results/hybrid_exam_smoke_2026-10-29.json"
    destination.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with sqlite3.connect(DEFAULT_BANK.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        tables = connection.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        audit = {"database": str(DEFAULT_BANK), "sha256": before[str(DEFAULT_BANK)], "tables": {},
            "skills": [dict(r) for r in connection.execute("SELECT * FROM skills ORDER BY skill_id")],
            "templates": [dict(r) for r in connection.execute("SELECT * FROM question_templates ORDER BY template_id")],
            "question_examples": [dict(r) for r in connection.execute("SELECT * FROM questions ORDER BY question_id LIMIT 2")],
            "difficulty_counts": [list(r) for r in connection.execute("SELECT difficulty, COUNT(*) FROM questions GROUP BY difficulty")]}
        for table in tables:
            # Identifiers come from SQLite's own catalogue; quote them, never
            # interpolate rule strings into SQL or execute database definitions.
            quoted = '"' + table["name"].replace('"', '""') + '"'
            audit["tables"][table["name"]] = {"sql": table["sql"],
                "foreign_keys": [dict(r) for r in connection.execute("PRAGMA foreign_key_list(" + quoted + ")")],
                "count": connection.execute("SELECT COUNT(*) FROM " + quoted).fetchone()[0]}
        audit["template_skill_links"] = [dict(r) for r in connection.execute(
            "SELECT * FROM question_template_skills ORDER BY template_id, skill_id")]
        audit["question_skill_examples"] = [dict(r) for r in connection.execute(
            "SELECT * FROM question_skills ORDER BY question_id, skill_id LIMIT 12")]
    (ROOT / "docs/report/hybrid_sql_audit_2026-10-29.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(destination.relative_to(ROOT)), "sources": output["source_counts"],
        "levels": exam.planner_summary.quota_summary.achieved_levels, "model_calls": generation_calls,
        "sql_unchanged": before == after, "revision_after_approval_and_regeneration": updated.revision}, indent=2))


if __name__ == "__main__":
    main()
