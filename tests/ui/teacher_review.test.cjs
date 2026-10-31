// Execute the shipped app.js with a minimal DOM and mocked HTTP responses.
// No browser, packages, live Qwen, or production credentials are required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Node {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.attributes = {}; this.listeners = {};
    this.value = ''; this.disabled = false; this.checked = false; this.hidden = false;
    this.className = ''; this._text = '';
    this.classList = {
      contains: name => this.className.split(' ').includes(name),
      toggle: (name, force) => {
        const values = new Set(this.className.split(' ').filter(Boolean));
        const add = force === undefined ? !values.has(name) : force;
        if (add) values.add(name); else values.delete(name);
        this.className = [...values].join(' ');
      },
      add: name => this.classList.toggle(name, true),
      remove: name => this.classList.toggle(name, false),
    };
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(''); }
  get childNodes() { return this.children; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this._text = ''; this.children = nodes; }
  cloneNode() { return new Node(this.tagName); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener(event, listener) { (this.listeners[event] ||= []).push(listener); }
  async fire(event) { for (const listener of this.listeners[event] || []) await listener({preventDefault() {}}); }
  reportValidity() { return true; }
  focus() {}
}

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'src/ui/static/app.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'src/ui/static/index.html'), 'utf8');

function harness(generator = 'qwen') {
  const roots = [...html.matchAll(/id="([^"]+)"/g)].map(match => {
    const node = new Node(); node.id = match[1]; return node;
  });
  function all() {
    const result = [];
    function visit(node) { result.push(node); for (const child of node.children) visit(child); }
    for (const node of roots) visit(node);
    return result;
  }
  const document = {
    getElementById: id => all().find(n => n.id === id) || null,
    createElement: tag => new Node(tag), createDocumentFragment: () => new Node('fragment'),
    querySelectorAll: selector => all().filter(n => n.classList.contains(selector.slice(1))),
  };
  const requests = [], responses = [];
  const context = vm.createContext({document, window: {location: {hash: ''}},
    history: {}, URLSearchParams, URL, Blob, AbortController, setTimeout, clearTimeout,
    setInterval, clearInterval, console,
    fetch: async (url, options) => {
      requests.push({url, ...options, body: options.body ? JSON.parse(options.body) : undefined});
      assert.ok(responses.length, `Unexpected HTTP call: ${url}`);
      const entry = responses.shift();
      const value = typeof entry === 'function' ? await entry() : entry;
      return {ok: value.status < 400, status: value.status, json: async () => value.body};
    }});
  vm.runInContext(source, context, {filename: 'app.js'});
  const state = vm.runInContext('state', context);
  state.connected = true; state.token = 'synthetic-teacher-token'; state.config = {backend: generator};
  function present(exam) {
    context.fixture = exam;
    vm.runInContext('acceptExam(fixture)', context);
  }
  const get = id => document.getElementById(id);
  const buttons = () => all().filter(n => n.tagName === 'button');
  const accepts = () => all().filter(n => n.tagName === 'input' && n.type === 'checkbox');
  const regenerate = () => buttons().find(n => n.attributes['aria-label'] === 'Tạo lại câu 1');
  return {state, requests, responses, present, get, all, buttons, accepts, regenerate,
    loadProfile: () => vm.runInContext('loadProfile()', context),
    requestBody: () => vm.runInContext('requestBody()', context)};
}

function draft(generator = 'qwen') {
  return {exam_id: 'EX_test', student_id: 'S', grade_level: 10, title: 'Synthetic exam',
    total_questions: 2, duration_minutes: 30, total_score: 10, revision: 1,
    status: 'pending_teacher_review', provenance: {generator, model: generator === 'qwen' ? 'mock' : null},
    questions: [1, 2].map(i => ({question_id: `Q${i}`, order_index: i, max_score: 5,
      content_latex: `Câu hỏi mẫu ${i}`, skill_ids: ['A001'], cognitive_level: 'recognition', generate_type: 'direct',
      source_ref: {kind: generator === 'qwen' ? 'template' : 'question', id: `SOURCE${i}`},
      template_instance: generator === 'qwen' ? {instance_id: `TI${i}`, parameters: {n: 5}, signature: `SIG${i}`} : null,
      answer: {correct_answer: '<img src=x onerror=alert(1)>', explanation: 'Reference'},
      step_solutions: [{step_number: 1, explanation: 'Reference', score: 5}], rubric: [{criteria: 'Reference', sub_score: 5}],
      validation: {auto_status: generator === 'fake' ? 'not_evaluated' : 'needs_review', review_notes: [], teacher_approved: false}}))};
}

async function acceptAll(h) {
  for (const node of h.accepts()) { node.checked = true; await node.fire('change'); }
}

async function run() {
  let passed = 0;
  {
    const h = harness(); const exam = draft(); h.present(exam);
    assert.ok(h.get('exam-pane').textContent.includes('Direct (trực tiếp)'));
    assert.equal(h.get('approve-exam-button').disabled, false);
    assert.equal(h.state.acceptedQuestions.size, 0);
    const approved = {...exam, revision: 2, status: 'approved', teacher_review: {notes: 'Checked'}};
    h.responses.push({status: 200, body: approved});
    await h.get('approve-exam-button').fire('click');
    assert.equal(h.requests[0].url, '/api/v1/exams/EX_test/approve');
    assert.deepEqual(h.requests[0].body, {expected_revision: 1});
    assert.equal(h.requests[0].headers.Authorization, 'Bearer synthetic-teacher-token');
    assert.equal(h.state.exam.revision, 2); assert.equal(h.accepts().length, 0);
    assert.ok(h.get('exam-pane').textContent.includes('Giáo viên đã duyệt đề.'));
    assert.ok(h.state.exam.questions.every(q => !q.validation.teacher_approved));
    passed++;
  }
  {
    const h = harness(); const exam = draft(); h.present(exam); await acceptAll(h);
    const updated = {...exam, revision: 2, questions: [{...exam.questions[0], question_id: 'Q1_NEW', content_latex: 'New wording', generate_type: 'indirect',
      template_presentation: {presentation_id: 'experimental_indirect', verification_status: 'experimental'}}, exam.questions[1]]};
    h.responses.push({status: 200, body: updated});
    await h.regenerate().fire('click');
    assert.equal(h.requests[0].url, '/api/v1/exams/EX_test/questions/Q1/regenerate');
    assert.deepEqual(h.requests[0].body, {expected_revision: 1});
    assert.equal(h.state.exam.questions[0].question_id, 'Q1_NEW');
    assert.ok(h.get('exam-pane').textContent.includes('Indirect (gián tiếp)'));
    assert.ok(h.get('exam-pane').textContent.includes('chưa kiểm chứng đầy đủ về ngữ nghĩa toán học'));
    assert.deepEqual(h.state.exam.questions[1], exam.questions[1]);
    assert.equal(h.state.acceptedQuestions.size, 0);
    assert.equal(h.get('approve-exam-button').disabled, false);
    passed++;
  }
  {
    const h = harness(); const exam = draft(); h.present(exam); await acceptAll(h);
    h.responses.push({status: 502, body: {error: {code: 'INVALID_QWEN_OUTPUT', message: 'Failed'}}});
    await h.regenerate().fire('click');
    assert.equal(h.state.exam, exam); assert.equal(h.state.acceptedQuestions.size, 2);
    assert.ok(h.get('notice').textContent.includes('INVALID_QWEN_OUTPUT'));
    passed++;
  }
  {
    const h = harness(); const exam = draft(); h.present(exam); await acceptAll(h);
    h.responses.push({status: 409, body: {error: {code: 'EXAM_REVISION_CONFLICT', message: 'Stale'}}});
    await h.get('approve-exam-button').fire('click');
    assert.equal(h.state.reviewStale, true); assert.equal(h.state.acceptedQuestions.size, 0);
    assert.equal(h.regenerate().disabled, true); assert.equal(h.get('approve-exam-button').disabled, true);
    assert.equal(h.get('refresh-draft-button').disabled, false);
    h.responses.push({status: 200, body: {...exam, revision: 3}});
    await h.get('refresh-draft-button').fire('click');
    assert.equal(h.requests[1].method, 'GET');
    assert.equal(h.state.exam.revision, 3); assert.equal(h.state.reviewStale, false);
    assert.equal(h.get('approve-exam-button').disabled, false);
    passed++;
  }
  {
    const h = harness(); const exam = draft(); h.present(exam);
    let resolve;
    h.responses.push(() => new Promise(done => { resolve = done; }));
    const pending = h.regenerate().fire('click');
    assert.equal(h.state.busy, true); assert.equal(h.regenerate().disabled, true);
    assert.equal(h.get('refresh-draft-button').disabled, true);
    resolve({status: 200, body: {...exam, revision: 2}});
    await pending;
    assert.equal(h.state.busy, false); assert.equal(h.regenerate().disabled, false);
    passed++;
  }
  {
    const h = harness('fake'); h.present(draft('fake'));
    assert.equal(h.regenerate(), undefined); await acceptAll(h);
    assert.equal(h.get('approve-exam-button').disabled, false);
    passed++;
  }
  {
    const h = harness(); const exam = draft(); exam.status = 'approved'; exam.revision = 2;
    exam.questions[0].generate_type = 'indirect';
    exam.questions[0].template_presentation = {presentation_id: 'experimental_indirect', verification_status: 'experimental'};
    h.present(exam);
    assert.ok(h.get('exam-pane').textContent.includes('chưa kiểm chứng đầy đủ về ngữ nghĩa toán học'));
    assert.equal(h.get('approve-exam-button'), null); assert.equal(h.accepts().length, 0);
    h.responses.push({status: 200, body: {...draft(), revision: 3}});
    await h.regenerate().fire('click');
    assert.equal(h.requests[0].body.expected_revision, 2);
    assert.equal(h.state.exam.status, 'pending_teacher_review');
    assert.equal(h.get('approve-exam-button').disabled, false);
    passed++;
  }
  {
    const h = harness(); h.present(draft());
    assert.ok(h.get('exam-pane').textContent.includes('<img src=x onerror=alert(1)>'));
    assert.equal(h.all().some(n => n.tagName === 'img'), false);
    passed++;
  }
  {
    const h = harness();
    for (const id of ['mode', 'lock-levels', 'recognition', 'understanding', 'application', 'advanced_application']) {
      assert.equal(h.get(id), null, `Manual configuration remains: ${id}`);
    }
    assert.ok(html.includes('độ khó được xác định tự động'));
    h.state.profile = {student_id: 'S'};
    for (const [id, value] of Object.entries({student: 'S', topic: 'combinatorics', 'question-count': '10', duration: '45'})) h.get(id).value = value;
    const body = JSON.parse(JSON.stringify(h.requestBody()));
    assert.deepEqual(body, {student_id: 'S', generation_mode: 'adaptive', selected_topic_ids: ['combinatorics'], total_questions: 10, duration_minutes: 45});
    assert.equal(Object.hasOwn(body, 'difficulty_distribution'), false);
    passed++;
  }
  {
    const h = harness(); h.state.profile = {student_id: 'S'};
    for (const [id, value] of Object.entries({student: 'S', topic: 'combinatorics', 'question-count': '2', duration: '30'})) h.get(id).value = value;
    const quotas = {recognition: 1, understanding: 1, application: 0, advanced_application: 0};
    h.responses.push({status: 200, body: {strategy: 'diagnostic_review', difficulty_locked: false, skill_classifications: {A001: 'NO_DATA'},
      quota_summary: {requested_levels: quotas, achieved_levels: quotas}, questions: [], warnings: [], policy_version: 'fixture'}});
    await h.get('plan-button').fire('click');
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(h.requests[0].url, '/api/v1/exams/plan');
    assert.equal(h.requests[0].body.generation_mode, 'adaptive');
    assert.equal(Object.hasOwn(h.requests[0].body, 'difficulty_distribution'), false);
    assert.ok(h.get('plan-pane').textContent.includes('Tự động theo mastery'));
    h.responses.push({status: 200, body: draft()});
    await h.get('exam-form').fire('submit');
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(h.requests[1].url, '/api/v1/exams/generate');
    assert.deepEqual(h.requests[1].body, h.requests[0].body);
    passed++;
  }
  {
    const h = harness(); const exam = draft();
    exam.questions[0].source_ref.kind = 'question';
    exam.questions[0].template_instance = null;
    h.present(exam);
    assert.equal(h.buttons().filter(n => n.attributes['aria-label'] === 'Tạo lại câu 1').length, 0);
    assert.equal(h.buttons().filter(n => n.attributes['aria-label'] === 'Tạo lại câu 2').length, 1);
    passed++;
  }
  {
    const h = harness('fake'); const exam = draft('fake');
    exam.questions[0].source_ref.kind = 'template';
    exam.questions[0].template_instance = {instance_id: 'DEMO_TI', parameters: {n: 4}};
    h.present(exam);
    assert.equal(h.buttons().filter(n => n.attributes['aria-label'] === 'Tạo lại câu 1').length, 1);
    assert.equal(h.buttons().filter(n => n.attributes['aria-label'] === 'Tạo lại câu 2').length, 0);
    passed++;
  }
  {
    const h = harness(); const exam = draft(); h.present(exam);
    const first = h.accepts()[0]; first.checked = true; await first.fire('change');
    assert.equal(h.get('approve-exam-button').disabled, false);
    h.responses.push({status: 200, body: {...exam, revision: 2, status: 'approved'}});
    await h.get('approve-exam-button').fire('click');
    assert.deepEqual(h.requests[0].body, {expected_revision: 1, accepted_question_ids: ['Q1']});
    passed++;
  }
  {
    for (const mutate of [e => e.questions.pop(), e => e.questions[0].answer.correct_answer = '',
      e => e.questions[0].validation.blocking_errors = ['Unresolved generation error'],
      e => e.questions[0].validation.auto_status = 'not_evaluated']) {
      const h = harness(); const exam = draft(); mutate(exam); h.present(exam);
      assert.equal(h.get('approve-exam-button').disabled, true);
      await h.get('approve-exam-button').fire('click');
      assert.equal(h.requests.length, 0);
    }
    passed++;
  }
  {
    const h = harness();
    const skills = Array.from({length: 9}, (_, i) => ({skill_id: `A00${i + 1}`, name: `Skill ${i + 1}`}));
    h.state.topics = [{topic_id: 'combinatorics', skills}];
    h.get('topic').value = 'combinatorics'; h.get('student').value = 'MIRA_TEST';
    h.responses.push({status: 200, body: {student_id: 'MIRA_TEST', name: 'No records', grade_level: 10, skill_mastery: [], learning_history: []}});
    await h.loadProfile();
    assert.deepEqual(h.all().filter(n => n.classList.contains('skill-score')).map(n => n.textContent), Array(9).fill('--/4'));
    assert.equal((h.get('profile').textContent.match(/0 evidence/g) || []).length, 9);
    passed++;
  }
  {
    const h = harness();
    const skills = [1, 2, 3].map(i => ({skill_id: `A00${i}`, name: `Skill ${i}`}));
    h.state.topics = [{topic_id: 'combinatorics', skills}];
    h.get('topic').value = 'combinatorics'; h.get('student').value = 'MIRA_TEST';
    h.responses.push({status: 200, body: {student_id: 'MIRA_TEST', name: 'Unassessed', grade_level: 10,
      skill_mastery: [null, 0, 2].map((score, i) => ({skill_id: `A00${i + 1}`, mastery_score: score, evidence_count: 0})), learning_history: []}});
    await h.loadProfile();
    assert.deepEqual(h.all().filter(n => n.classList.contains('skill-score')).map(n => n.textContent), ['--/4', '--/4', '--/4']);
    assert.equal(/null\/4|NaN\/4|2\.0.*\/4/.test(h.get('profile').textContent), false);
    passed++;
  }
  {
    const h = harness();
    // The Python API regression verifies this SAME expected response against
    // an isolated authoritative SQLite reader before the UI consumes it here.
    const profile = JSON.parse(fs.readFileSync(path.join(root, 'tests/fixtures/missing_mastery_profile.json'), 'utf8'));
    h.state.topics = [{topic_id: 'combinatorics', skills: profile.skill_mastery.map(s => ({skill_id: s.skill_id, name: s.skill_id}))}];
    h.get('topic').value = 'combinatorics'; h.get('student').value = profile.student_id;
    h.responses.push({status: 200, body: profile});
    await h.loadProfile();
    assert.deepEqual(h.all().filter(n => n.classList.contains('skill-score')).map(n => n.textContent),
      ['0.00 / 4', '3.25 / 4', '1.13 / 4', ...Array(6).fill('--/4')]);
    assert.ok(h.get('profile').textContent.includes('A001 · 6 evidence'));
    assert.ok(h.get('profile').textContent.includes('A004 · 0 evidence'));
    assert.equal(h.state.profile.skill_mastery[0].mastery_score, 0);
    assert.equal(h.state.profile.skill_mastery[2].mastery_score, 1.125);
    passed++;
  }
  {
    const h = harness();
    h.state.topics = [{topic_id: 'combinatorics', skills: [{skill_id: 'A001', name: 'Skill'}]}];
    h.get('topic').value = 'combinatorics'; h.get('student').value = 'MIRA_TEST';
    h.responses.push({status: 200, body: {student_id: 'MIRA_TEST', name: 'Invalid', grade_level: 10,
      skill_mastery: [{skill_id: 'A001', mastery_score: null, evidence_count: 3}], learning_history: []}});
    await assert.rejects(h.loadProfile(), /evidence.*mastery/);
    assert.equal(h.state.profile, null);
    assert.equal(h.all().filter(n => n.classList.contains('skill-score')).length, 0);
    passed++;
  }
  return {passed, description: 'Teacher review and missing-mastery UI scenarios with actual app.js and mocked HTTP'};
}

module.exports = run;
if (require.main === module) run().then(result => console.log(JSON.stringify(result))).catch(error => {
  console.error(error); process.exitCode = 1;
});
