// Exercise the shipped Figma views, including teacher review and grading handoff.
const assert = require('node:assert/strict');
const {harness, draft} = require('./teacher_review.test.cjs');

function setup() {
  const h = harness(); h.loadViews();
  const exam = draft();
  exam.topic_id = 'combinatorics';
  exam.questions.forEach(q => {q.answer.correct_answer = '8';});
  h.context.fixture = exam;
  h.evaluate("Object.assign(dr, {studentId: 'S', exam: fixture, profile: {student_name: 'Học sinh', grade_level: 10}, topics: []}); renderDraft();");
  return {h, exam};
}

async function run() {
  let passed = 0;
  {
    const {h, exam} = setup();
    assert.equal(h.get('dr-approve').disabled, false);
    assert.equal(h.get('dr-deliver').disabled, true);
    h.get('grading-criterion-1-0').value = 'Giáo viên xác nhận cách đếm.';
    const approved = structuredClone(exam);
    approved.status = 'approved'; approved.revision = 2;
    approved.questions.forEach(q => {q.grading_context = {reference_answer: '8', rubric: [{id: 'R1', description: 'Tiêu chí đã duyệt.', skill_ids: ['A001']}]};});
    h.responses.push({status: 200, body: approved});
    await h.get('dr-approve').fire('click');
    assert.equal(h.requests[0].url, '/api/v1/exams/EX_test/approve');
    assert.equal(h.requests[0].body.expected_revision, 1);
    assert.equal(h.requests[0].body.grading_contexts.length, 2);
    assert.equal(h.requests[0].body.grading_contexts[0].rubric[0].description, 'Giáo viên xác nhận cách đếm.');
    assert.deepEqual(h.requests[0].body.grading_contexts[0].rubric[0].skill_ids, ['A001']);
    assert.equal(h.get('dr-approve').hidden, true);
    assert.equal(h.get('dr-deliver').disabled, false);
    await h.get('dr-deliver').fire('click');
    assert.equal(h.navigation[0], '/grading?exam_id=EX_test&revision=2#token=synthetic-teacher-token'); passed++;
  }
  {
    const {h} = setup();
    h.responses.push({status: 409, body: {error: {code: 'EXAM_REVISION_CONFLICT', message: 'Reload latest'}}});
    await h.get('dr-approve').fire('click');
    assert.equal(h.get('dr-approve').disabled, true);
    assert.equal(h.get('dr-deliver').disabled, true);
    const count = h.requests.length;
    await h.get('dr-approve').fire('click'); assert.equal(h.requests.length, count); passed++;
  }
  {
    const {h, exam} = setup();
    exam.quality_report = {status: 'HARD_FAIL', approval_blocked: true, total_score: null};
    h.context.fixture = exam; h.evaluate('dr.exam = fixture; renderDraft();');
    assert.equal(h.get('dr-approve').disabled, true);
    assert.ok(h.get('dr-quality-status').textContent.includes('Cần xử lý lỗi'));
    await h.get('dr-approve').fire('click'); assert.equal(h.requests.length, 0); passed++;
  }
  {
    const {h, exam} = setup();
    const updated = structuredClone(exam); updated.revision = 2;
    updated.questions[0].question_id = 'Q1_NEW';
    h.responses.push({status: 200, body: updated});
    await h.evaluate("drReplace('Q1')");
    assert.equal(h.requests[0].body.expected_revision, 1);
    assert.equal(h.evaluate('dr.exam.questions[0].question_id'), 'Q1_NEW');
    assert.equal(h.get('dr-deliver').disabled, true); passed++;
  }
  console.log(JSON.stringify({passed}));
}
run().catch(e => {console.error(e); process.exitCode = 1;});
