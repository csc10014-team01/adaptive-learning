"""Explicit offline sample-data update. The application remains read-only on M3."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from uuid import uuid4


HERE = Path(__file__).resolve().parent
DEFAULT_DATABASE = HERE / "student_profiles_sample.db"
DEFAULT_BANK = HERE.parent / "dataset/question_bank.db"
SCENARIOS = HERE / "profile_scenarios.json"


def seed_profiles(database=DEFAULT_DATABASE, *, bank=DEFAULT_BANK, scenarios=SCENARIOS, backup_dir=None):
    database, bank = Path(database).resolve(), Path(bank).resolve()
    if database == bank:
        raise ValueError("Profile and question-bank databases must be separate")
    manifest = json.loads(Path(scenarios).read_text(encoding="utf-8"))
    if manifest.get("fixture_kind") != "synthetic_planner_testing":
        raise ValueError("Only explicitly synthetic testing scenarios may be seeded")
    skills = manifest["skill_ids"]
    with sqlite3.connect(bank.as_uri() + "?mode=ro", uri=True) as source:
        source.execute("PRAGMA query_only=ON")
        known = {row[0] for row in source.execute("SELECT skill_id FROM skills")}
    if len(skills) != len(set(skills)) or set(skills) != known:
        raise ValueError("Scenario catalogue does not match the question bank")
    desired, student_ids = {}, set()
    for student in manifest["students"]:
        sid = student["student_id"]
        if sid in student_ids or len(student["scores"]) != len(skills) or len(student["evidence"]) != len(skills):
            raise ValueError("Scenarios require unique students and one entry per skill")
        student_ids.add(sid)
        for skill, score, evidence in zip(skills, student["scores"], student["evidence"]):
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 4:
                raise ValueError("Mastery must be finite and on the 0–4 scale")
            if type(evidence) is not int or evidence < 0:
                raise ValueError("Evidence must be a nonnegative integer")
            if evidence == 0 and score != 0:
                raise ValueError("No-evidence sample rows must use the documented zero placeholder")
            desired[sid, skill] = (float(score), evidence)
    connection = sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, timeout=10)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        if {r[0] for r in connection.execute("SELECT student_id FROM Students")} != student_ids:
            raise ValueError("Scenario student IDs do not exactly match this sample database")
        current = {(sid, skill): (score, count) for sid, skill, score, count in connection.execute(
            "SELECT student_id, skill_id, mastery_score, evidence_count FROM student_skill_mastery")}
        if any(key not in desired for key in current):
            raise ValueError("Unexpected mastery rows; refusing to discard or remap data")
        if current == desired:
            return {"updated": False, "students": len(student_ids), "mastery_rows": len(current), "backup": None}
        # SQLite's backup API captures a consistent copy, including committed WAL data.
        folder = Path(backup_dir) if backup_dir else database.parent / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = folder / f"{database.stem}.before_diversity_{stamp}_{uuid4().hex[:8]}.db"
        with sqlite3.connect(backup) as destination:
            connection.backup(destination)
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            unchanged = {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
                         for table in ("Students", "Tests", "test_questions")}
            connection.executemany(
                "INSERT INTO student_skill_mastery(student_id, skill_id, mastery_score, evidence_count) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(student_id, skill_id) DO UPDATE SET "
                "mastery_score=excluded.mastery_score, evidence_count=excluded.evidence_count",
                [(sid, skill, score, evidence) for (sid, skill), (score, evidence) in desired.items()],
            )
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Foreign-key check failed; rolled back")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("SQLite integrity check failed; rolled back")
            for table, rows in unchanged.items():
                if connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall() != rows:
                    raise ValueError("Student identity or history unexpectedly changed; rolled back")
        return {"updated": True, "students": len(student_ids), "mastery_rows": len(desired),
                "previous_mastery_rows": len(current), "backup": str(backup)}
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Back up and seed diverse synthetic mastery in the sample DB")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    print(json.dumps(seed_profiles(args.database), indent=2, ensure_ascii=False))
