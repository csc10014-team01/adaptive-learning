"""Read-only latest SQL audit and mocked-Qwen whole-exam approval smoke.

Run: python -m eval.latest_schema_approval_audit
Only the JSON report and a temporary application draft database are written.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore

from fastapi.testclient import TestClient

from src.adaptation.skill_relationships import SkillRelationships
from src.ai.contracts import GenerationCandidate
from src.ai.template_instantiator import TemplateInstantiator
from src.api.data_adapter import DEFAULT_BANK, ROOT
from src.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter, readonly
from src.api.main import create_app
from src.api.schemas import LEVELS


class WordingDouble:
    model, attempts, exam_timeout = "mock-local-qwen-schema-audit", 2, 30

    def __init__(self):
        self.capacity = BoundedSemaphore(1)
        self.calls = 0

    def generate_one(self, expression, **kwargs):
        assert expression.template_context is not None
        self.calls += 1
        return GenerationCandidate(
            model=self.model,
            raw_response=json.dumps({"question": expression.source_text}),
        )


def main():
    paths = (DEFAULT_BANK, DEFAULT_STUDENTS)
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    data = M3DataAdapter(bank_path=DEFAULT_BANK)
    bank = data.questions
    with readonly(DEFAULT_BANK) as c:
        schema = {}
        for row in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ):
            name = row[0]
            quoted = '"' + name.replace('"', '""') + '"'
            schema[name] = {
                "count": c.execute("SELECT COUNT(*) FROM " + quoted).fetchone()[0],
                "columns": [
                    dict(r) for r in c.execute("PRAGMA table_info(" + quoted + ")")
                ],
            }
        statuses = dict(
            c.execute("SELECT status, COUNT(*) FROM questions GROUP BY status")
        )
        raw_templates = {
            r["template_id"]: dict(r)
            for r in c.execute("SELECT * FROM question_templates ORDER BY template_id")
        }
    templates = []
    for definition in data.templates:
        detail = {
            "definition": raw_templates[definition.template_id],
            "skill_ids": definition.skill_ids,
        }
        if definition.difficulty not in (1, 2):
            detail.update(
                executable=False, reason="MVP permits Templates only at L1/L2"
            )
        else:
            try:
                instances = TemplateInstantiator().instances(definition, 10, seed=0)
                sample = instances[0]
                detail.update(
                    executable=True,
                    bounded_instance_count=len(instances),
                    sample_parameters=sample.record.parameters,
                    sample_statement=sample.content,
                    computed_answer=sample.answer.model_dump(),
                    verified_solution=sample.solution_steps,
                )
            except (ValueError, SyntaxError, TypeError, KeyError, OverflowError) as exc:
                detail.update(executable=False, reason=str(exc))
        templates.append(detail)
    relationships = SkillRelationships.load(
        ROOT / "config/skill_relationships_a001_a009.json"
    )
    model, token = WordingDouble(), "audit-only-local-teacher-token"
    with TemporaryDirectory(prefix="koro-schema-approval-") as temporary:
        draft_db = Path(temporary) / "drafts.db"
        app = create_app(
            backend="qwen",
            bank_path=DEFAULT_BANK,
            exam_db=draft_db,
            qwen_client=model,
            teacher_token=token,
            relationships=relationships,
        )
        app.state.data = data
        with TestClient(app, headers={"Authorization": "Bearer " + token}) as client:
            body = {
                "student_id": "ST011",
                "selected_topic_ids": ["combinatorics"],
                "total_questions": 10,
                "duration_minutes": 45,
            }
            preview = client.post("/api/v1/exams/plan", json=body)
            generated = client.post("/api/v1/exams/generate", json=body)
            assert preview.status_code == generated.status_code == 200
            plan, draft = preview.json(), generated.json()
            assert plan["quota_summary"] == draft["planner_summary"]["quota_summary"]
            assert all(
                not q["validation"]["teacher_approved"] for q in draft["questions"]
            )
            url = "/api/v1/exams/" + draft["exam_id"]
            approved_response = client.post(
                url + "/approve", json={"expected_revision": 1}
            )
            assert approved_response.status_code == 200, approved_response.text
            approved = approved_response.json()
            assert approved["status"] == "approved" and approved["revision"] == 2
            assert all(
                not q["validation"]["teacher_approved"] for q in approved["questions"]
            )
            assert approved["questions"] == draft["questions"]
            assert client.get(url).json() == approved
        restarted = create_app(
            backend="qwen",
            bank_path=DEFAULT_BANK,
            exam_db=draft_db,
            teacher_token=token,
            relationships=relationships,
        )
        with TestClient(
            restarted, headers={"Authorization": "Bearer " + token}
        ) as client:
            assert client.get(url).json() == approved
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before == after
    output = {
        "database": str(DEFAULT_BANK),
        "requested_canonical_path_exists": (
            ROOT.parents[1] / "pre-work/data/sample/questionbank.db"
        ).exists(),
        "hashes_before": before,
        "hashes_after": after,
        "schema": schema,
        "sql_source_statuses": statuses,
        "eligible_questions": len(bank),
        "eligible_multi_skill_questions": sum(len(q.skill_ids) > 1 for q in bank),
        "invalid_rows": data.question_diagnostics,
        "eligible_question_capacities": {
            s.skill_id: {
                lv: sum(
                    q.primary_skill_id == s.skill_id and q.cognitive_level == lv
                    for q in bank
                )
                for lv in LEVELS
            }
            for s in data.topic.skills
        },
        "templates": templates,
        "preview": plan,
        "draft": draft,
        "approved": approved,
        "source_counts": dict(
            Counter(q["source_ref"]["kind"] for q in draft["questions"])
        ),
        "model_calls": model.calls,
        "individually_reviewed_before": 0,
        "individually_reviewed_after": 0,
        "persisted_and_retrieved_after_restart": True,
    }
    destination = ROOT / "eval/results/latest_schema_approval_2026-10-30.json"
    destination.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "report": str(destination.relative_to(ROOT)),
                "eligible_questions": len(bank),
                "eligible_multi_skill_questions": output[
                    "eligible_multi_skill_questions"
                ],
                "excluded": [r["question_id"] for r in data.question_diagnostics],
                "sources": output["source_counts"],
                "requested": plan["quota_summary"]["requested_levels"],
                "achieved": plan["quota_summary"]["achieved_levels"],
                "approved_revision": approved["revision"],
                "manually_reviewed_questions": 0,
                "persisted_after_restart": True,
                "canonical_hashes_unchanged": before == after,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
