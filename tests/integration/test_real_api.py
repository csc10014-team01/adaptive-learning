"""Real M3 reader/planner/storage with an HTTP Ollama double (no model download)."""

from collections import Counter
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sqlite3
from threading import Thread
import time
from urllib.error import URLError

from fastapi.testclient import TestClient
import pytest

from src.adaptation.planner import RuleBasedPlanner
from src.ai.qwen_client import QwenClient
from src.api.data_adapter import ApiFailure, DEFAULT_BANK, StaticDataAdapter
from src.api.main import create_app
from src.api.m3_adapter import DEFAULT_STUDENTS, M3DataAdapter
from src.api.schemas import ExamResponse, GenerateExamRequest, StudentProfileResponse

HEADERS = {"Authorization": "Bearer teacher-test"}


def payload(student_id="ST001", **changes):
    value = dict(student_id=student_id, generation_mode="adaptive", selected_topic_ids=["combinatorics"],
                 total_questions=4, duration_minutes=45,
                 difficulty_distribution=dict(recognition=20, understanding=40, application=30, advanced_application=10))
    value.update(changes)
    return value


def profile(skill="A001", mastery=1.5, evidence=1, wrong=()):
    return StudentProfileResponse(student_id="S", name="Student", grade_level=10,
        skill_mastery=[{"skill_id": skill, "mastery_score": mastery, "evidence_count": evidence}],
        learning_history=[{"test_id": "T", "wrong_questions": list(wrong)}])


def single_request(**changes):
    return GenerateExamRequest.model_validate(payload("S", total_questions=1,
        difficulty_distribution=dict(recognition=100, understanding=0, application=0, advanced_application=0), **changes))


@pytest.fixture
def ollama():
    calls = []
    state = {"kind": "valid"}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(value)
            if state["kind"] == "http_error":
                self.send_error(503)
                return
            content = json.loads(value["prompt"].split("DỮ LIỆU NGUỒN:\n")[1])["question"]
            question = content + (" Có thêm 999 đối tượng." if state["kind"] == "numbers" else "")
            output = "broken" if state["kind"] == "json" else json.dumps({"question": question})
            raw = json.dumps({"model": value["model"], "done": state["kind"] != "truncated", "response": output}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = QwenClient(base_url=f"http://127.0.0.1:{server.server_port}", timeout=2)
    try:
        yield client, calls, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_m3_reader_matches_sql_and_normalizes_history():
    data = M3DataAdapter()
    p = data.get_profile("ST001")
    with sqlite3.connect(DEFAULT_STUDENTS) as c:
        assert len(data.list_students()) == c.execute("SELECT COUNT(*) FROM Students").fetchone()[0]
        assert [(s.skill_id, s.mastery_score, s.evidence_count) for s in p.skill_mastery] == c.execute(
            "SELECT skill_id, mastery_score, evidence_count FROM student_skill_mastery WHERE student_id='ST001' ORDER BY skill_id"
        ).fetchall()
    assert p.learning_history and "wrongs" not in p.model_dump_json()
    assert all(s in {k.skill_id for k in data.topic.skills} for q in data.questions for s in q.skill_ids)
    assert len(data.questions) >= 80


def test_m3_refreshes_profiles_without_restarting(tmp_path):
    import shutil
    path = tmp_path / "students.db"
    shutil.copyfile(DEFAULT_STUDENTS, path)
    data = M3DataAdapter(student_path=path)
    before = data.get_profile("ST001").skill_mastery[0].mastery_score
    with sqlite3.connect(path) as c:
        c.execute("UPDATE student_skill_mastery SET mastery_score=0.25 WHERE student_id='ST001'")
    assert data.get_profile("ST001").skill_mastery[0].mastery_score == 0.25 != before


def test_m3_subquestions_and_answers_preserved():
    data = M3DataAdapter()
    with sqlite3.connect(DEFAULT_BANK) as c:
        for qid, label, content, answer in c.execute(
            "SELECT q.question_id, p.label, p.content, a.correct_answer FROM questions q "
            "JOIN question_parts p USING(question_id) JOIN answer_parts a USING(part_id)"
        ):
            q = next((q for q in data.questions if q.question_id == qid), None)
            if q:
                assert content in q.content and answer in q.answer.correct_answer


def test_m3_reads_author_supplied_primary_without_modifying_canonical_bank(tmp_path):
    import shutil

    path = tmp_path / "annotated-bank.db"
    shutil.copyfile(DEFAULT_BANK, path)
    # Synthetic author annotation in an isolated copy, deliberately using the
    # second linked skill. Production must never infer from link order.
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE questions ADD COLUMN primary_skill_id TEXT")
        connection.execute("UPDATE questions SET primary_skill_id='A002' WHERE question_id='QA0019'")
    questions = {q.question_id: q for q in M3DataAdapter(bank_path=path).questions}
    assert questions["QA0019"].primary_skill_id == "A002"
    assert questions["QA0019"].skill_ids == ["A001", "A002"]


def test_sufficient_evidence_targets_the_weak_primary_skill():
    planner = RuleBasedPlanner(StaticDataAdapter())
    request = GenerateExamRequest.model_validate(payload("S", total_questions=3,
        difficulty_distribution=dict(recognition=67, understanding=33, application=0, advanced_application=0)))
    a = planner.plan(request, profile("A001", evidence=3))
    b = planner.plan(request, profile("A003", evidence=3))
    assert a.personalized and b.personalized
    assert [q.source_id for q in a.questions if q.targeted] == ["DEMO_Q01"]
    assert [q.source_id for q in b.questions if q.targeted] == ["DEMO_Q02"]


@pytest.mark.parametrize("evidence,mastery,mode,expected", [
    (0, 0, "adaptive", False), (1, 1.5, "adaptive", False),
    (2, 1.5, "adaptive", False), (3, 1.5, "adaptive", True),
    (3, 3.0, "adaptive", False),
    (1, 1.5, "default_blueprint", False),
])
def test_evidence_is_per_skill(evidence, mastery, mode, expected):
    plan = RuleBasedPlanner(StaticDataAdapter()).plan(
        GenerateExamRequest.model_validate(payload("S", generation_mode=mode)),
        profile(mastery=mastery, evidence=evidence))
    assert plan.personalized is expected


def test_history_does_not_override_mastery_or_invent_evidence():
    planner = RuleBasedPlanner(StaticDataAdapter())
    achieved = planner.plan(single_request(), profile(mastery=3.5, evidence=3, wrong=["DEMO_Q01"]))
    assert not achieved.priority_skills and achieved.skill_classifications["A001"] == "ACHIEVED"
    assert not planner.plan(single_request(), profile(mastery=0, evidence=0, wrong=["DEMO_Q01"])).personalized
    unknown = planner.plan(single_request(), profile(mastery=3.5, wrong=["UNKNOWN"]))
    assert not unknown.personalized and unknown.warnings


def test_quota_shortage_is_explicit_and_distribution_preserved():
    request = GenerateExamRequest.model_validate(payload("S"))
    plan = RuleBasedPlanner(StaticDataAdapter()).plan(request, profile(evidence=3))
    assert plan.target_count == 2 and plan.achieved_target_count == 1
    assert any("1/2" in warning for warning in plan.warnings)
    assert Counter(q.cognitive_level for q in plan.questions) == {
        "recognition": 1, "understanding": 2, "application": 1}
    assert len({q.source_id for q in plan.questions}) == 4


def test_two_evidence_never_outranks_an_eligible_weak_skill():
    p = profile(mastery=1.5, evidence=3)
    p.skill_mastery.append(type(p.skill_mastery[0])(skill_id="A003", mastery_score=1.5, evidence_count=2))
    plan = RuleBasedPlanner(StaticDataAdapter()).plan(GenerateExamRequest.model_validate(payload("S")), p)
    assert plan.priority_skills == ["A001"]
    assert plan.skill_classifications["A003"] == "PARTIAL"


def test_real_api_m3_to_http_qwen_to_durable_draft(tmp_path, ollama):
    qwen, calls, _ = ollama
    hashes = {p: hashlib.sha256(p.read_bytes()).digest() for p in (DEFAULT_STUDENTS, DEFAULT_BANK)}
    db = tmp_path / "exams.db"
    app = create_app(backend="qwen", teacher_token="teacher-test", qwen_client=qwen, exam_db=db)
    with TestClient(app, headers=HEADERS) as c:
        plan = c.post("/api/v1/exams/plan", json=payload())
        assert plan.status_code == 200 and not calls
        # The diversified sample gives ST001 sufficient evidence and a weak addition skill.
        assert plan.json()["personalized"]
        assert plan.json()["skill_classifications"]["A001"] == "WEAK"
        result = c.post("/api/v1/exams/generate", json=payload())
        assert result.status_code == 200, result.text
        exam = ExamResponse.model_validate(result.json())
        assert exam.planner_summary.policy_version == plan.json()["policy_version"]
        assert exam.provenance.generator == "qwen" and exam.provenance.model == qwen.model
        assert [q.source_ref.id for q in exam.questions] == [q["source_id"] for q in plan.json()["questions"]]
        bank = {q.question_id: q for q in app.state.data.questions}
        for q in exam.questions:
            assert q.validation.auto_status == "needs_review" and not q.validation.teacher_approved
            assert q.answer == bank[q.source_ref.id].answer
            assert q.target_skill_id == bank[q.source_ref.id].primary_skill_id
            assert q.skill_ids == bank[q.source_ref.id].skill_ids
        assert len(calls) == 4
        assert all("ST001" not in call["prompt"] and "Gia Han" not in call["prompt"] for call in calls)
        assert c.get(f"/api/v1/exams/{exam.exam_id}").json() == result.json()
    with TestClient(create_app(backend="qwen", teacher_token="teacher-test", exam_db=db), headers=HEADERS) as c:
        assert c.get(f"/api/v1/exams/{exam.exam_id}").json() == result.json()
    assert hashes == {p: hashlib.sha256(p.read_bytes()).digest() for p in hashes}


@pytest.mark.parametrize("kind,code,status,calls_count", [
    ("numbers", "INVALID_QWEN_OUTPUT", 502, 2), ("json", "INVALID_QWEN_OUTPUT", 502, 2),
    ("truncated", "INVALID_QWEN_OUTPUT", 502, 2), ("http_error", "QWEN_PROVIDER_ERROR", 503, 1),
])
def test_provider_failure_never_saves_partial_exam(tmp_path, ollama, kind, code, status, calls_count):
    qwen, calls, state = ollama
    state["kind"] = kind
    path = tmp_path / "no_partial.db"
    app = create_app(backend="qwen", teacher_token="teacher-test", qwen_client=qwen, exam_db=path)
    with TestClient(app, headers=HEADERS) as c:
        result = c.post("/api/v1/exams/generate", json=payload())
    assert result.status_code == status and result.json()["error"]["code"] == code
    assert len(calls) == calls_count and not path.exists()


def test_qwen_timeout_unavailable_and_deadline(monkeypatch):
    qwen = QwenClient()
    for failure, status in [(TimeoutError(), 504), (URLError("offline"), 503)]:
        def fail(*args, **kwargs):
            raise failure
        monkeypatch.setattr("src.ai.qwen_client.urlopen", fail)
        with pytest.raises(ApiFailure) as exc:
            qwen.rewrite("Có 3 đối tượng phân biệt.", deadline=time.monotonic() + 2)
        assert exc.value.status == status
    with pytest.raises(ApiFailure) as exc:
        qwen.rewrite("Có 3 đối tượng phân biệt.", deadline=0)
    assert exc.value.status == 504


def test_busy_and_plan_auth(tmp_path, ollama):
    qwen, calls, _ = ollama
    app = create_app(backend="qwen", teacher_token="teacher-test", qwen_client=qwen, exam_db=tmp_path / "e.db")
    with TestClient(app) as c:
        assert c.post("/api/v1/exams/plan", json=payload()).status_code == 401
        qwen.capacity.acquire()
        try:
            assert c.post("/api/v1/exams/generate", headers=HEADERS, json=payload()).status_code == 503
        finally:
            qwen.capacity.release()
        assert c.post("/api/v1/exams/plan", headers=HEADERS, json=payload()).status_code == 200
        assert not calls


def test_json_profile_real_backend_still_uses_m3_bank(tmp_path):
    app = create_app(backend="qwen", profile_source="json", teacher_token="teacher-test", exam_db=tmp_path / "e.db")
    with TestClient(app, headers=HEADERS) as c:
        result = c.post("/api/v1/exams/plan", json=payload("DEMO_PARTIAL_002"))
        assert result.status_code == 200, result.text
        assert result.json()["priority_skills"] == []
        assert result.json()["skill_classifications"]["A001"] == "PARTIAL"
        assert all(q["source_id"].startswith("QA") for q in result.json()["questions"])


def test_cannot_store_drafts_in_canonical_m3_database():
    for path in (DEFAULT_STUDENTS, DEFAULT_BANK):
        with pytest.raises(ValueError, match="separate"):
            create_app(backend="qwen", exam_db=path)


def test_no_candidates_for_priority_does_not_claim_personalization():
    plan = RuleBasedPlanner(StaticDataAdapter()).plan(
        GenerateExamRequest.model_validate(payload("S")), profile("A005", evidence=3))
    assert not plan.personalized
    assert plan.target_count == 2 and plan.achieved_target_count == 0
    assert any("0/2" in warning for warning in plan.warnings)


def test_missing_grade_or_distribution_fails_before_qwen(tmp_path, ollama):
    qwen, calls, _ = ollama
    app = create_app(backend="qwen", teacher_token="teacher-test", qwen_client=qwen, exam_db=tmp_path / "e.db")
    with TestClient(app, headers=HEADERS) as c:
        result = c.post("/api/v1/exams/generate", json=payload(total_questions=11))
        assert result.status_code == 422 and not calls
