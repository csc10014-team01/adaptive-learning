// Execute the shipped grading UI with a minimal DOM, mocked fetch and manual timers.
// These verify actual event handlers, safe text rendering and request/download data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Node {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.listeners = {}; this.attributes = {};
    this.value = ''; this.hidden = false; this.disabled = false; this._text = '';
  }
  set textContent(text) { this._text = String(text); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  addEventListener(event, listener) { (this.listeners[event] ||= []).push(listener); }
  async fire(event) { for (const fn of this.listeners[event] || []) await fn({preventDefault() {}}); }
  click() { this.clicked = true; }
}

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'src/ui/static/grading.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'src/ui/static/grading.html'), 'utf8');
const example = JSON.parse(fs.readFileSync(path.join(root, 'src/ui/static/grading-example.json'), 'utf8'));

function harness(location = {}) {
  const nodes = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], new Node()]));
  nodes.mode.value = 'experimental';
  const created = [], requests = [], responses = [], timers = new Map(), blobs = [];
  let timerId = 0;
  const context = vm.createContext({
    document: {getElementById: id => nodes[id], createElement: tag => {const n = new Node(tag); created.push(n); return n;}},
    window: {location: {hash: '', pathname: '/grading', search: '', ...location}}, history: {}, URLSearchParams,
    URL: {createObjectURL: b => {blobs.push(b); return 'blob:synthetic';}, revokeObjectURL() {}},
    Blob, AbortController, crypto: {randomUUID: () => `SYN_KEY_${++timerId}`},
    setTimeout: (fn, ms) => {const id = ++timerId; timers.set(id, {fn, ms}); return id;},
    clearTimeout: id => timers.delete(id),
    fetch: async (url, options = {}) => {
      requests.push({url, ...options, body: options.body ? JSON.parse(options.body) : undefined});
      assert.ok(responses.length, `Unexpected HTTP request ${url}`);
      const data = responses.shift();
      return {ok: data.status < 400, status: data.status, json: async () => structuredClone(data.body)};
    }, console,
  });
  vm.runInContext(source, context);
  const state = vm.runInContext('state', context);
  state.connected = true; state.token = 'synthetic-token';
  return {nodes, state, context, created, requests, responses, blobs,
    apply: data => {nodes['input-json'].value = JSON.stringify(data); vm.runInContext('applyInput()', context);},
    render: data => {context.fixture = data; vm.runInContext('render(fixture)', context);},
    body: () => vm.runInContext('requestBody()', context),
    async tick() {const next = [...timers].find(([, t]) => t.ms === 1000); assert.ok(next, 'poll timer'); timers.delete(next[0]); await next[1].fn();},
  };
}

function job(state = 'COMPLETED') {
  return {metadata: {job_id: 'G_SYN', state, experimental: true, completed_questions: state === 'COMPLETED' ? 2 : 0,
    total_questions: 2, definite_questions: 1, uncertain_questions: 1, provider_failures: 1, elapsed_seconds: 1.2,
    questions: [{question_id: 'Q1', seconds: .4, issue: null}, {question_id: 'Q2', seconds: .8, issue: 'provider_failure'}]},
    result: {test_id: 'SYN', student_id: 'SYN', submissions: state === 'COMPLETED' ? [
      {question_id: 'Q1', answer: [{step: 1, description: '<img src=x onerror=alert(1)>', start: 0, end: 4}],
        grading_result: {overall_result: 'CORRECT', errors: []}},
      {question_id: 'Q2', answer: [], grading_result: {overall_result: 'UNCERTAIN', errors: []}},
    ] : [], feedback: state === 'COMPLETED' ? 'Whole-exam feedback.' : null}};
}

async function run() {
  let passed = 0;
  {
    const h = harness(); h.apply(example);
    assert.equal(h.state.editors.length, 2);
    h.state.editors[0].editor.value = 'Edited raw answer\nwith exact spacing.';
    const body = h.body();
    assert.equal(body.answers[0].student_answer, 'Edited raw answer\nwith exact spacing.');
    assert.equal(body.mode, 'experimental'); assert.equal(body.questions[0].reference_answer, '5'); passed++;
  }
  {
    const h = harness(); h.responses.push({status: 200, body: example});
    await h.nodes.example.fire('click'); assert.equal(h.state.editors.length, 2);
    assert.equal(h.requests[0].url, '/ui/assets/grading-example.json'); passed++;
  }
  {
    const h = harness(); h.nodes.import.files = [{size: 2000, text: async () => JSON.stringify(example)}];
    await h.nodes.import.fire('change'); assert.equal(h.state.context.test_id, example.test_id);
    h.nodes.import.files = [{size: 600000}]; await h.nodes.import.fire('change');
    assert.equal(h.nodes.notice.attributes.role, 'alert'); passed++;
  }
  {
    const h = harness(); h.apply(example); const a = h.body(); const b = h.body();
    assert.equal(a.idempotency_key, b.idempotency_key);
    h.state.editors[0].editor.value += 'changed'; assert.notEqual(h.body().idempotency_key, a.idempotency_key); passed++;
  }
  {
    const h = harness(); h.apply(example); h.responses.push({status: 202, body: job('QUEUED')});
    await h.nodes.start.fire('click'); assert.equal(h.requests[0].url, '/api/v1/grading/jobs');
    assert.equal(h.requests[0].headers.Authorization, 'Bearer synthetic-token');
    assert.equal(h.state.busy, true); assert.equal(h.nodes.progress.value, 0);
    h.responses.push({status: 200, body: job()}); await h.tick();
    assert.equal(h.requests[1].url, '/api/v1/grading/jobs/G_SYN');
    assert.equal(h.state.busy, false); assert.equal(h.nodes.progress.value, 2); passed++;
  }
  {
    const h = harness(); h.render(job());
    assert.ok(h.nodes.status.textContent.includes('Đã xử lý hết các câu'));
    assert.ok(h.nodes.status.textContent.includes('1 câu chưa kết luận'));
    assert.ok(!h.nodes.status.textContent.includes('Tất cả câu đã có kết luận xác định'));
    assert.ok(h.nodes.results.textContent.includes('CORRECT'));
    assert.ok(h.nodes.results.textContent.includes('UNCERTAIN · Chưa kết luận'));
    assert.ok(h.nodes.results.textContent.includes('Dịch vụ AI không sẵn sàng'));
    assert.equal(h.nodes.feedback.hidden, false); passed++;
  }
  {
    const h = harness(); h.render(job());
    assert.ok(h.nodes.results.textContent.includes('<img src=x onerror=alert(1)>'));
    assert.ok(!h.created.some(n => n.tagName === 'img' || n.tagName === 'script'));
    assert.ok(!source.includes('innerHTML')); passed++;
  }
  {
    const h = harness(); h.apply(example); h.responses.push({status: 409, body: {error: {
      code: 'GRADING_CONTEXT_NOT_READY', message: 'Cần rubric id, description, skill_ids.'}}});
    await h.nodes.start.fire('click');
    assert.ok(h.nodes.notice.textContent.includes('GRADING_CONTEXT_NOT_READY'));
    assert.ok(h.nodes.notice.textContent.includes('skill_ids')); assert.equal(h.state.busy, false); passed++;
  }
  {
    const h = harness(); h.render(job()); await h.nodes.download.fire('click');
    assert.equal(h.blobs.length, 1); const downloaded = JSON.parse(await h.blobs[0].text());
    assert.deepEqual(downloaded, job().result); assert.equal(downloaded.metadata, undefined);
    assert.ok(h.created.some(n => n.tagName === 'a' && n.download === 'G_SYN.json' && n.clicked)); passed++;
  }
  {
    const h = harness(); h.nodes['job-id'].value = 'G_SYN'; h.responses.push({status: 200, body: job()});
    await h.nodes['reopen-form'].fire('submit'); assert.equal(h.requests[0].url, '/api/v1/grading/jobs/G_SYN');
    assert.equal(h.nodes.download.disabled, false); passed++;
  }
  {
    const h = harness(); h.nodes.mode.value = 'approved_snapshot'; await h.nodes.mode.fire('change');
    assert.equal(h.nodes['experimental-fields'].hidden, true); assert.equal(h.nodes['approved-fields'].hidden, false);
    h.nodes['exam-id'].value = 'EX_SYN'; h.nodes.revision.value = '3'; h.nodes['student-id'].value = 'SYN';
    h.nodes['approved-answers'].value = JSON.stringify([{question_id: 'Q1', student_answer: ''}]);
    const body = h.body(); assert.equal(body.exam_revision, 3); assert.equal(body.questions, undefined);
    assert.equal(body.answers[0].student_answer, ''); passed++;
  }
  {
    const h = harness(); const invalid = structuredClone(example); invalid.answers.pop();
    assert.throws(() => h.apply(invalid), /answer/); passed++;
  }
  {
    const h = harness();
    h.nodes.mode.value = 'approved_snapshot';
    h.nodes['exam-id'].value = 'EX_SYN'; h.nodes.revision.value = '2';
    h.responses.push({status: 200, body: {exam_id: 'EX_SYN', exam_revision: 2, student_id: 'SERVER_STUDENT',
      questions: [{question_id: 'Q1', question_text: 'Câu hỏi đã duyệt.'}], answers: [{question_id: 'Q1', student_answer: ''}]}});
    await h.nodes['load-approved'].fire('click');
    assert.equal(h.requests[0].url, '/api/v1/exams/EX_SYN/grading-context?revision=2');
    assert.equal(h.nodes['student-id'].value, 'SERVER_STUDENT');
    h.state.editors[0].editor.value = 'Bài làm nguyên văn.';
    assert.equal(h.body().answers[0].student_answer, 'Bài làm nguyên văn.');
    assert.equal(h.body().questions, undefined);
    h.responses.push({status: 200, body: {exam_id: 'EX_SYN', exam_revision: 2, student_id: 'SERVER_STUDENT',
      questions: [{question_id: 'Q1', question_text: 'Câu hỏi đã duyệt.'}], answers: [{question_id: 'Q1', student_answer: ''}]}});
    await h.nodes['load-approved'].fire('click');
    assert.equal(h.state.editors[0].editor.value, 'Bài làm nguyên văn.');
    h.nodes['approved-answers'].value = 'unapplied invalid JSON';
    assert.equal(h.body().answers[0].student_answer, 'Bài làm nguyên văn.');
    h.nodes.revision.value = '3'; assert.throws(() => h.body(), /Nạp lại/); passed++;
  }
  {
    const h = harness(); h.state.approved = {exam_id: 'EX_SYN', exam_revision: 2, student_id: 'S',
      questions: [{question_id: 'Q1', question_text: 'Đề đã duyệt.'}], answers: [{question_id: 'Q1', student_answer: ''}]};
    h.nodes['approved-answers'].value = JSON.stringify([{question_id: 'Q1', student_answer: 'Nội dung từ JSON.'}]);
    await h.nodes['import-approved'].fire('click');
    assert.equal(h.state.editors[0].editor.value, 'Nội dung từ JSON.');
    h.nodes['approved-answers'].value = JSON.stringify([{question_id: 'WRONG', student_answer: ''}]);
    await h.nodes['import-approved'].fire('click');
    assert.equal(h.nodes.notice.attributes.role, 'alert');
    assert.equal(h.state.editors[0].question_id, 'Q1'); passed++;
  }
  {
    const h = harness(); h.state.approved = {exam_id: 'EX_SYN'};
    h.responses.push({status: 200, body: {items: [{job_id: 'G_SYN', test_id: 'EX_SYN', state: 'COMPLETED', created_at: '2026-11-21'}]}});
    await h.nodes['load-history'].fire('click');
    assert.equal(h.requests[0].url, '/api/v1/grading/jobs?exam_id=EX_SYN');
    const button = h.nodes['job-history'].children[0].children[0];
    h.responses.push({status: 200, body: job()}); await button.fire('click');
    assert.equal(h.nodes['job-id'].value, 'G_SYN'); assert.equal(h.nodes.download.disabled, false); passed++;
  }
  {
    const h = harness({search: '?exam_id=EX_SYN&revision=2'});
    assert.equal(h.nodes.mode.value, 'approved_snapshot');
    h.nodes.token.value = 'session-secret';
    h.responses.push({status: 200, body: {}}, {status: 200, body: {exam_id: 'EX_SYN', exam_revision: 2, student_id: 'S',
      questions: [{question_id: 'Q1', question_text: 'Đề.'}], answers: [{question_id: 'Q1', student_answer: ''}]}});
    await h.nodes['connect-form'].fire('submit');
    assert.equal(h.state.editors.length, 1);
    assert.ok(h.nodes['back-to-exam'].href.includes('route=%2Fstudents%2FS%2Fexams%2FEX_SYN'));
    assert.ok(h.requests.every(r => !r.url.includes('session-secret'))); passed++;
  }
  {
    const h = harness({search: '?exam_id=EX_OLD&revision=2'});
    h.nodes.token.value = 'session-secret';
    h.responses.push({status: 200, body: {}}, {status: 409, body: {error: {code: 'GRADING_CONTEXT_NOT_READY', message: 'Snapshot cũ thiếu rubric.'}}});
    await h.nodes['connect-form'].fire('submit');
    assert.equal(h.state.connected, true);
    assert.equal(h.nodes.connection.textContent, 'Đã kết nối');
    assert.ok(h.nodes.notice.textContent.includes('GRADING_CONTEXT_NOT_READY')); passed++;
  }
  console.log(JSON.stringify({passed}));
}

run().catch(error => {console.error(error); process.exitCode = 1;});
