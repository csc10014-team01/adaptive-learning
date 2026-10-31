"""Read the Data Lead's template schema and its explicit skill relationships."""

import json
import sqlite3
from contextlib import closing

from src.ai.template_instantiator import TemplateDefinition


def load_templates(path):
    templates, warnings = [], []
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "question_templates" not in tables:
            return [], ["Template Bank unavailable: question_templates is missing; using Question Bank."]
        if "question_template_skills" not in tables:
            return [], ["Template Bank unavailable: verified question_template_skills mappings are missing; using Question Bank."]
        required = {"template_id", "template_content", "parameter_rules", "answer_rule", "solution_rule", "difficulty"}
        columns = {r["name"] for r in connection.execute("PRAGMA table_info(question_templates)")}
        if not required.issubset(columns):
            return [], ["Template Bank unavailable: missing columns " + ", ".join(sorted(required - columns))]
        skills = {r["skill_id"]: dict(r) for r in connection.execute("SELECT * FROM skills")}
        links = {}
        for row in connection.execute("SELECT template_id, skill_id FROM question_template_skills ORDER BY template_id, skill_id"):
            links.setdefault(row["template_id"], []).append(row["skill_id"])
        for row in connection.execute("SELECT * FROM question_templates ORDER BY template_id"):
            tid = row["template_id"]
            try:
                ids = links.get(tid, [])
                if not ids or any(s not in skills for s in ids):
                    raise ValueError("missing or invalid verified skill mappings")
                scopes = {(skills[s]["grade_level"], skills[s]["topic"]) for s in ids}
                if len(scopes) != 1:
                    raise ValueError("linked skills do not identify one verified grade/topic")
                grade, topic = scopes.pop()
                if "grade_level" in row.keys() and row["grade_level"] != grade:
                    raise ValueError("template grade conflicts with its verified linked skills")
                if "topic_id" in row.keys() and row["topic_id"] != "combinatorics":
                    raise ValueError("template topic conflicts with its verified linked skills")
                if topic != "Đại số tổ hợp":
                    raise ValueError("unsupported topic")
                rules = json.loads(row["parameter_rules"])
                if not isinstance(rules, dict):
                    raise ValueError("parameter_rules must be a JSON object")
                templates.append(TemplateDefinition(template_id=tid, template_content=row["template_content"],
                    parameter_rules=rules, answer_rule=row["answer_rule"], solution_rule=row["solution_rule"],
                    difficulty=row["difficulty"], skill_ids=ids, grade_level=grade, topic_id="combinatorics"))
            except (ValueError, TypeError, KeyError) as exc:
                warnings.append(f"Template {tid} excluded: {exc}")
    return templates, warnings
