"""Read-only canonical integration; all data corrections occur in test copies."""

import hashlib
import shutil
import sqlite3

import pytest

from src.api.data_adapter import ApiFailure, DEFAULT_BANK
from src.api.m3_adapter import M3DataAdapter, readonly
from src.api.main import create_app


@pytest.fixture
def bank_copy(tmp_path):
    before = hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest()
    path = tmp_path / "synthetic-bank.db"
    shutil.copyfile(DEFAULT_BANK, path)
    yield path
    assert hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest() == before


def test_new_schema_reads_authoritative_main_and_all_secondary_links(bank_copy):
    with sqlite3.connect(bank_copy) as c:
        c.execute("UPDATE QuestionMainSkill SET skill_id='A002' WHERE question_id='QA0019'")
        c.execute("ALTER TABLE questions ADD COLUMN primary_skill_id TEXT")
        c.execute("UPDATE questions SET primary_skill_id='A009' WHERE question_id='QA0019'")
    data = M3DataAdapter(bank_path=bank_copy)
    q = next(q for q in data.questions if q.question_id == "QA0019")
    assert q.primary_skill_id == "A002"  # deliberately not the first linked skill
    assert q.skill_ids == ["A001", "A002"]
    with readonly(bank_copy) as c:
        answer = c.execute("SELECT correct_answer, explaination FROM answers WHERE question_id='QA0019'").fetchone()
    assert (q.answer.correct_answer, q.answer.explanation) == tuple(answer)
    assert q.solution_steps == [answer[1]]
    assert any(len(q.skill_ids) > 1 for q in data.questions)


@pytest.mark.parametrize("mutation,reason", [
    ("DELETE FROM QuestionMainSkill WHERE question_id='QA0001'", "INVALID_MAIN_SKILL"),
    ("UPDATE QuestionMainSkill SET skill_id='A009' WHERE question_id='QA0001'", "INCONSISTENT_MAIN_SKILL"),
    ("UPDATE QuestionMainSkill SET skill_id='UNKNOWN' WHERE question_id='QA0001'", "UNKNOWN_MAIN_SKILL"),
    ("DELETE FROM question_skills WHERE question_id='QA0001'", "INVALID_SKILL_LINKS"),
    ("DELETE FROM answers WHERE question_id='QA0001'", "INVALID_ANSWER"),
    ("UPDATE answers SET explaination='' WHERE question_id='QA0001'", "INVALID_ANSWER"),
    ("UPDATE answers SET correct_answer='' WHERE question_id='QA0001'", "INVALID_ANSWER"),
    ("UPDATE questions SET content='' WHERE question_id='QA0001'", "MISSING_CONTENT"),
    ("UPDATE questions SET difficulty=99 WHERE question_id='QA0001'", "INVALID_DIFFICULTY"),
])
def test_incomplete_or_inconsistent_rows_are_excluded_with_specific_diagnostics(bank_copy, mutation, reason):
    with sqlite3.connect(bank_copy) as c:
        c.execute(mutation)
    data = M3DataAdapter(bank_path=bank_copy)
    assert "QA0001" not in {q.question_id for q in data.questions}
    assert "QA0002" in {q.question_id for q in data.questions}
    diagnostic = next(d for d in data.question_diagnostics if d["question_id"] == "QA0001")
    assert any(r.startswith(reason + ":") for r in diagnostic["reasons"])


def test_pending_rows_become_eligible_after_corrected_synthetic_data_is_reloaded(bank_copy):
    data = M3DataAdapter(bank_path=bank_copy)
    pending = [f"QA{i:04}" for i in range(114, 122)]
    assert set(pending).isdisjoint(q.question_id for q in data.questions)
    # These are explicitly synthetic mathematical fixtures, not proposed fixes
    # to the real Data Lead answers or mappings.
    with sqlite3.connect(bank_copy) as c:
        for qid in pending:
            c.execute("UPDATE questions SET content='Synthetic: choose one item from disjoint groups of 3 and 4.', "
                      "difficulty=1 WHERE question_id=?", (qid,))
            c.execute("DELETE FROM question_skills WHERE question_id=?", (qid,))
            c.execute("INSERT INTO question_skills VALUES (?, 'A005')", (qid,))
            c.execute("DELETE FROM QuestionMainSkill WHERE question_id=?", (qid,))
            c.execute("INSERT INTO QuestionMainSkill VALUES (?, 'A005')", (qid,))
            c.execute("DELETE FROM answers WHERE question_id=?", (qid,))
            c.execute("INSERT INTO answers(answer_id,question_id,correct_answer,explaination) VALUES (?,?,'7','3+4=7')",
                      ("SYN_" + qid, qid))
    data.reload_bank()
    loaded = {q.question_id: q for q in data.questions}
    assert set(pending).issubset(loaded)
    assert all(loaded[qid].primary_skill_id == "A005" and loaded[qid].answer.correct_answer == "7" for qid in pending)
    assert set(pending).isdisjoint(d["question_id"] for d in data.question_diagnostics)


def test_source_status_draft_is_eligible_and_never_changed_by_reading(bank_copy):
    before = hashlib.sha256(bank_copy.read_bytes()).hexdigest()
    data = M3DataAdapter(bank_path=bank_copy)
    with readonly(bank_copy) as c:
        assert c.execute("SELECT status FROM questions WHERE question_id='QA0001'").fetchone()[0] == "draft"
    assert "QA0001" in {q.question_id for q in data.questions}
    assert hashlib.sha256(bank_copy.read_bytes()).hexdigest() == before


def test_missing_configured_path_fails_without_creating_or_switching_database(tmp_path, monkeypatch):
    path = tmp_path / "missing-questionbank.db"
    monkeypatch.setenv("M3_QUESTION_DB", str(path))
    app = create_app(backend="qwen", exam_db=tmp_path / "drafts.db")
    assert app.state.bank_path == path
    with pytest.raises(ApiFailure):
        _ = M3DataAdapter(bank_path=app.state.bank_path).questions
    assert not path.exists()


def test_relative_question_database_configuration_is_resolved_from_application_root(monkeypatch, tmp_path):
    monkeypatch.setenv("M3_QUESTION_DB", "../../pre-work/data/sample/dataset/question_bank.db")
    app = create_app(backend="qwen", exam_db=tmp_path / "drafts.db")
    assert app.state.bank_path.resolve() == DEFAULT_BANK.resolve()


def test_legacy_schema_is_explicit_and_never_overrides_new_schema(bank_copy):
    with sqlite3.connect(bank_copy) as c:
        c.execute("DROP TABLE QuestionMainSkill")
        c.execute("ALTER TABLE questions ADD COLUMN primary_skill_id TEXT")
        c.execute("UPDATE questions SET primary_skill_id='A002' WHERE question_id='QA0019'")
    data = M3DataAdapter(bank_path=bank_copy)
    assert next(q for q in data.questions if q.question_id == "QA0019").primary_skill_id == "A002"
    assert any("Legacy schema" in w for w in data.question_warnings)


def test_preview_and_generation_cannot_mix_cached_questions_with_changed_template_bank(bank_copy):
    data = M3DataAdapter(bank_path=bank_copy)
    original = data.questions
    with sqlite3.connect(bank_copy) as c:
        c.execute("UPDATE question_templates SET solution_rule=solution_rule || ' Synthetic correction.' WHERE template_id='EA0001'")
    with pytest.raises(ApiFailure) as failure:
        _ = data.templates
    assert failure.value.code == "SOURCE_CHANGED"
    with pytest.raises(ApiFailure):
        _ = data.questions
    data.reload_bank()
    assert data.questions == original
    assert next(t for t in data.templates if t.template_id == "EA0001").solution_rule.endswith("Synthetic correction.")
