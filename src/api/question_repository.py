"""Validate SQL rows independently without repairing Data Lead records."""

import json

from src.api.data_adapter import FixtureQuestion


def read_questions(connection, known, difficulty_levels):
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    authoritative = "QuestionMainSkill" in tables
    main, links = {}, {}
    if authoritative:
        for row in connection.execute("SELECT question_id, skill_id FROM QuestionMainSkill ORDER BY question_id, skill_id"):
            main.setdefault(row["question_id"], []).append(row["skill_id"])
    for row in connection.execute("SELECT question_id, skill_id FROM question_skills ORDER BY question_id, skill_id"):
        links.setdefault(row["question_id"], []).append(row["skill_id"])
    result, diagnostics = [], []
    for row in connection.execute("SELECT * FROM questions ORDER BY question_id"):
        qid, reasons = row["question_id"], []
        if row["question_type"] != "essay" or row["grade_level"] != 10 or row["status"] not in ("draft", "active"):
            reasons.append("SOURCE_NOT_ELIGIBLE: requires essay, grade 10, and source status draft/active")
        skills = links.get(qid, [])
        if not skills or len(skills) != len(set(skills)) or not set(skills).issubset(known):
            reasons.append("INVALID_SKILL_LINKS: missing, duplicate, or unknown question_skills")
        primary = row["primary_skill_id"] if "primary_skill_id" in row.keys() else None
        if authoritative:
            mapped = main.get(qid, [])
            primary = mapped[0] if len(mapped) == 1 else None
            if len(mapped) != 1:
                reasons.append("INVALID_MAIN_SKILL: requires exactly one QuestionMainSkill mapping")
            elif primary not in known:
                reasons.append("UNKNOWN_MAIN_SKILL: main skill is outside the approved catalogue")
            elif primary not in skills:
                reasons.append("INCONSISTENT_MAIN_SKILL: main skill is absent from question_skills")
        if row["difficulty"] not in difficulty_levels:
            reasons.append("INVALID_DIFFICULTY: unsupported SQL difficulty")
        if not isinstance(row["content"], str) or not row["content"].strip():
            reasons.append("MISSING_CONTENT: question content must be nonempty")
        answers = connection.execute(
            "SELECT correct_answer, explaination FROM answers WHERE question_id=? ORDER BY answer_id", (qid,)
        ).fetchall()
        if len(answers) != 1 or any(not isinstance(v, str) or not v.strip() for r in answers for v in r):
            reasons.append("INVALID_ANSWER: requires one nonempty answer and explaination")
        parts = []
        if "question_parts" in tables:
            if "answer_parts" in tables:
                parts = connection.execute(
                    "SELECT p.label,p.content,a.correct_answer,a.explanation FROM question_parts p "
                    "LEFT JOIN answer_parts a USING(part_id) WHERE p.question_id=? ORDER BY p.label", (qid,)
                ).fetchall()
                if any(not isinstance(v, str) or not v.strip() for p in parts for v in p):
                    reasons.append("INVALID_PART: incomplete question part, answer, or explanation")
            elif connection.execute("SELECT 1 FROM question_parts WHERE question_id=?", (qid,)).fetchone():
                reasons.append("INVALID_PART: answer_parts table is missing")
        if not reasons:
            try:
                content = row["content"] + "".join(f"\n{p['label']}) {p['content']}" for p in parts)
                answer, explanation = answers[0]
                if parts:
                    answer += "\n" + "\n".join(f"{p['label']}) {p['correct_answer']}" for p in parts)
                    explanation += "\n" + "\n".join(f"{p['label']}) {p['explanation']}" for p in parts)
                result.append(FixtureQuestion(
                    question_id=qid, grade_level=row["grade_level"], skill_ids=skills, primary_skill_id=primary,
                    cognitive_level=difficulty_levels[row["difficulty"]], generate_type="direct", content=content,
                    answer={"correct_answer": answer, "explanation": explanation}, solution_steps=[explanation],
                    rubric_criteria=["Lập luận đúng phương pháp và kết luận phù hợp đáp án nguồn M3."],
                    problem_spec=json.loads(row["problem_spec_json"]) if "problem_spec_json" in row.keys()
                        and row["problem_spec_json"] is not None else None))
            except (ValueError, TypeError, KeyError) as exc:
                reasons.append(f"INVALID_QUESTION: {exc}")
        if reasons:
            diagnostics.append({"question_id": qid, "reasons": reasons})
    warnings = [f"Excluded {d['question_id']}: {'; '.join(d['reasons'])}." for d in diagnostics]
    if not authoritative:
        warnings.insert(0, "Legacy schema: QuestionMainSkill is absent; using explicit legacy primary_skill_id "
                        "or documented sole-skill migration. Multi-skill sources without a primary remain ineligible.")
    return result, diagnostics, warnings
