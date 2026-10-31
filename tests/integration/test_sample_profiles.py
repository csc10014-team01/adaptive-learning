"""Sample-data scenarios exercise the real planner without any inference."""

import hashlib
import json
import shutil
import sqlite3

import pytest

from data.sample.memory.seed_sample_profiles import DEFAULT_DATABASE, SCENARIOS, seed_profiles
from src.adaptation.planner import RuleBasedPlanner
from src.api.m3_adapter import M3DataAdapter
from src.api.schemas import GenerateExamRequest


MANIFEST = json.loads(SCENARIOS.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", MANIFEST["students"], ids=lambda s: s["student_id"])
def test_sample_scenario_drives_expected_adaptive_strategy(scenario):
    # Explicitly exercise the historical seeded SQL fixture, never the default
    # authoritative Data Lead profile source.
    data = M3DataAdapter(student_path=DEFAULT_DATABASE)
    profile = data.get_profile(scenario["student_id"])
    assert {s.skill_id for s in profile.skill_mastery} == {s.skill_id for s in data.topic.skills}
    assert all(s.mastery_score is None and s.evidence_count == 0 for s in profile.skill_mastery
               if s.skill_id not in MANIFEST["skill_ids"])
    for count in (4, 10):
        request = GenerateExamRequest(student_id=profile.student_id, generation_mode="adaptive",
            selected_topic_ids=["combinatorics"], total_questions=count, duration_minutes=45)
        plan = RuleBasedPlanner(data).plan(request, profile)
        # The source manifest describes the former <3 policy. Keep its stored
        # scores/evidence untouched; only these two strategies change under <2.
        expected = {"ST005": "advanced_review", "ST012": "advanced_review"}.get(
            profile.student_id, scenario["expected_strategy"])
        # The new authoritative bank has A008/A009; old seven-skill profiles
        # lack their evidence, so achieved-only rows now include diagnostics.
        if expected == "advanced_review":
            expected = "diagnostic_review"
        assert plan.strategy == expected
        assert len(plan.questions) == len({(q.source_kind, q.source_key) for q in plan.questions}) == count
        if profile.student_id in ("ST017", "ST018"):
            assert plan.priority_skills and plan.personalized and plan.warnings
        elif plan.strategy == "focused_practice":
            assert plan.personalized


def test_seed_creates_backup_preserves_history_and_is_repeatable(tmp_path):
    database = tmp_path / "sample.db"
    shutil.copyfile(DEFAULT_DATABASE, database)
    with sqlite3.connect(database) as c:
        c.execute("DELETE FROM student_skill_mastery WHERE NOT (student_id='ST001' AND skill_id='A001')")
        c.execute("UPDATE student_skill_mastery SET mastery_score=2.3,evidence_count=1")
        original = {name: c.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
                    for name in ("Students", "Tests", "test_questions")}
    result = seed_profiles(database)
    assert result["updated"] and result["previous_mastery_rows"] == 1 and result["mastery_rows"] == 140
    with sqlite3.connect(result["backup"]) as c:
        assert c.execute("SELECT mastery_score,evidence_count FROM student_skill_mastery").fetchall() == [(2.3, 1)]
    with sqlite3.connect(database) as c:
        for name, rows in original.items():
            assert c.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall() == rows
        assert not c.execute("PRAGMA foreign_key_check").fetchall()
    before = hashlib.sha256(database.read_bytes()).digest()
    assert not seed_profiles(database)["updated"]
    assert hashlib.sha256(database.read_bytes()).digest() == before
    assert len(list((tmp_path / "backups").glob("*.db"))) == 1


def test_seed_rejects_catalogue_mismatch_without_writing(tmp_path):
    database = tmp_path / "sample.db"
    shutil.copyfile(DEFAULT_DATABASE, database)
    manifest = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    manifest["skill_ids"][0] = "SK01"
    scenarios = tmp_path / "invalid.json"
    scenarios.write_text(json.dumps(manifest), encoding="utf-8")
    before = database.read_bytes()
    with pytest.raises(ValueError, match="catalogue"):
        seed_profiles(database, scenarios=scenarios)
    assert database.read_bytes() == before and not (tmp_path / "backups").exists()
