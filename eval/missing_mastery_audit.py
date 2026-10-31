"""Read-only profile-source and missing-mastery audit; never runs offline seeding."""

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from src.adaptation.planner import RuleBasedPlanner
from src.api.data_adapter import DEFAULT_BANK, ROOT
from src.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter
from src.api.schemas import GenerateExamRequest


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sql_rows(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as c:
        c.execute("PRAGMA query_only=ON")
        return {(sid, skill): (score, evidence) for sid, skill, score, evidence in c.execute(
            "SELECT student_id,skill_id,mastery_score,evidence_count FROM student_skill_mastery")}


def audit():
    seeded = ROOT / "data/sample/memory/student_profiles_sample.db"
    paths = (DEFAULT_STUDENTS, DEFAULT_BANK, seeded)
    before = {str(p): digest(p) for p in paths}
    source, fixture = sql_rows(DEFAULT_STUDENTS), sql_rows(seeded)
    manifest = json.loads((seeded.parent / "profile_scenarios.json").read_text(encoding="utf-8"))
    desired = {(s["student_id"], skill): (float(score), evidence) for s in manifest["students"]
        for skill, score, evidence in zip(manifest["skill_ids"], s["scores"], s["evidence"])}
    data = M3DataAdapter(student_path=DEFAULT_STUDENTS, bank_path=DEFAULT_BANK)
    profiles = data.profiles
    planner = RuleBasedPlanner(data)
    skills = sorted(s.skill_id for s in data.topic.skills)
    evidence_preserved = all(
        (r.mastery_score, r.evidence_count) == ((source[sid, r.skill_id][0], source[sid, r.skill_id][1])
            if source.get((sid, r.skill_id), (None, 0))[1] > 0 else (None, 0))
        for sid, p in profiles.items() for r in p.skill_mastery)
    classifications, strategies, unassessed = Counter(), Counter(), []
    for sid, student in profiles.items():
        statuses = planner.classify(student, skills)
        classifications.update(statuses.values())
        if set(statuses.values()) == {"NO_DATA"}:
            unassessed.append(sid)
        req = GenerateExamRequest(student_id=sid, generation_mode="adaptive", selected_topic_ids=["combinatorics"],
            total_questions=10, duration_minutes=45)
        strategies[planner.build_allocation_plan(req, student).strategy] += 1
    after = {str(p): digest(p) for p in paths}
    return {
        "authoritative_student_db": str(DEFAULT_STUDENTS), "student_count": len(profiles),
        "skill_count": len(skills), "stored_mastery_rows": len(source),
        "response_skill_rows": sum(len(p.skill_mastery) for p in profiles.values()),
        "null_masteries": sum(r.mastery_score is None for p in profiles.values() for r in p.skill_mastery),
        "all_assessed_sql_values_preserved": evidence_preserved,
        "classification_counts": dict(classifications), "strategy_counts": dict(strategies),
        "students_without_any_evidence": unassessed,
        "examples": {sid: profiles[sid].model_dump(mode="json") for sid in ("ST001", "ST004", "ST011", "ST012")},
        "old_seeded_copy": {"path": str(seeded), "rows": len(fixture),
            "matches_offline_scenario_manifest_exactly": fixture == desired,
            "automatically_used_as_fallback": False},
        "hashes_before": before, "hashes_after": after, "all_databases_unchanged": before == after,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k not in ("examples", "hashes_before", "hashes_after")}))
    else:
        print(text)


if __name__ == "__main__":
    main()
