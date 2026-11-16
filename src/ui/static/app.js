"use strict";

/* ═══════════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════════ */
const $ = (id) => document.getElementById(id);
const levels = {recognition: "Nhận biết", understanding: "Thông hiểu", application: "Vận dụng", advanced_application: "Vận dụng cao"};
const strategies = {focused_practice: "Luyện tập kỹ năng cần củng cố", diagnostic_review: "Thăm dò năng lực", advanced_review: "Ôn tập nâng cao", standard: "Đề chuẩn"};
const skillStates = {NO_DATA: "Chưa có dữ liệu", PARTIAL: "Cần thêm dữ liệu", WEAK: "Cần củng cố", ACHIEVED: "Đạt mục tiêu"};

/* ── Exam tool state ── */
const state = {token: "", connected: false, busy: false, students: [], topics: [], profile: null, config: null, exam: null, plan: null, tab: "exam"};
const initialExam = $("exam-pane").cloneNode(true);
const initialPlan = $("plan-pane").cloneNode(true);

function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (cls) node.className = cls;
  return node;
}

function announce(message, kind = "") {
  $("notice").textContent = message;
  $("notice").className = `notice ${kind}`;
  $("notice").hidden = !message;
  $("notice").setAttribute("role", kind === "error" ? "alert" : "status");
}

function setControls() {
  $("exam-fields").disabled = !state.connected || state.busy;
  $("teacher-token").disabled = state.busy;
  $("connect-button").disabled = state.busy;
  $("retrieve-button").disabled = !state.connected || state.busy;
  $("exam-id").disabled = state.busy;
  $("download-button").disabled = state.busy || !(state.tab === "exam" ? state.exam : state.plan);
  $("output").setAttribute("aria-busy", String(state.busy));
}

function syncLevels() {
  const locked = $("lock-levels").checked;
  $("level-inputs").hidden = !locked;
  $("level-help").textContent = locked ? "Nhập phần trăm cho từng mức. Tổng phải bằng 100%." : "Để planner tự phân bổ theo chế độ đã chọn.";
  let total = 0;
  for (const key of Object.keys(levels)) { $(key).disabled = !locked; total += Number($(key).value); }
  $("level-total").textContent = `Tổng: ${total}%`;
  $("level-total").classList.toggle("invalid", Math.abs(total - 100) > 0.0001);
}

/* ── Core fetch wrapper (shared by both screens) ── */
async function api(path, {method = "GET", body, timeout = 15000, token} = {}) {
  const usedToken = token !== undefined ? token : state.token;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {
      method, signal: controller.signal, cache: "no-store", credentials: "omit",
      headers: {Authorization: `Bearer ${usedToken}`, ...(body ? {"Content-Type": "application/json"} : {})},
      ...(body ? {body: JSON.stringify(body)} : {}),
    });
    let data;
    try { data = await response.json(); } catch { throw new Error(`Backend trả phản hồi không phải JSON (HTTP ${response.status}).`); }
    if (!response.ok) {
      const code = data.error?.code || `HTTP_${response.status}`;
      const help = {
        TEACHER_ACCESS_NOT_CONFIGURED: "Backend chưa có teacher token. Chạy bằng python -m src.ui hoặc đặt API_TEACHER_TOKEN.",
        TEACHER_ACCESS_DENIED: "Teacher token chưa đúng. Hãy kết nối lại.",
        TEACHER_AUTH_REQUIRED: "Hãy nhập teacher token để tiếp tục.",
        QWEN_UNAVAILABLE: "Không kết nối được Ollama. Hãy kiểm tra Ollama và model Qwen trên máy.",
        QWEN_PROVIDER_ERROR: "Ollama chưa phục vụ được model đã cấu hình. Kiểm tra model và thử lại.",
        QWEN_BUSY: "Qwen đang xử lý một yêu cầu khác. Chờ yêu cầu đó hoàn tất rồi thử lại.",
        QWEN_TIMEOUT: "Qwen đã hết thời gian xử lý. Bạn có thể thử tạo đề ít câu hơn.",
        INSUFFICIENT_QUESTION_BANK: "Ngân hàng chưa đủ câu phù hợp. Thử giảm số câu hoặc bỏ khóa phân bố độ khó.",
        INVALID_QWEN_OUTPUT: "Đầu ra Qwen chưa vượt qua kiểm tra. Không có đề dở được lưu.",
        EXAM_NOT_FOUND: "Không tìm thấy mã đề này. Đề demo sẽ mất khi khởi động lại server.",
      }[code];
      const details = (data.error?.details || []).map((d) => `${d.field}: ${d.reason}`).join("\n");
      const err = new Error([help || data.error?.message || "Yêu cầu chưa thực hiện được.", `[${code}]`, help ? data.error?.message : "", details].filter(Boolean).join("\n"));
      err.apiCode = code;
      throw err;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Chưa nhận được phản hồi trong thời gian chờ. Backend có thể vẫn đang xử lý; hãy chờ trước khi gửi lại.");
    if (error instanceof TypeError) throw new Error("Không kết nối được backend. Kiểm tra server còn chạy và mở UI từ cùng địa chỉ FastAPI.");
    throw error;
  } finally { clearTimeout(timer); }
}

async function operation(title, work, isGeneration = false) {
  if (state.busy) return;
  state.busy = true;
  announce("");
  setControls();
  $("loading").hidden = false;
  $("loading-title").textContent = title;
  $("loading-help").textContent = isGeneration ? "Đang chờ đề hoàn chỉnh. Qwen có thể cần vài phút." : "Vui lòng giữ trang mở.";
  const started = Date.now();
  $("elapsed").textContent = "0";
  const timer = setInterval(() => { $("elapsed").textContent = String(Math.floor((Date.now() - started) / 1000)); }, 1000);
  try { await work(); } catch (error) { announce(error.message, "error"); }
  finally { clearInterval(timer); state.busy = false; $("loading").hidden = true; setControls(); }
}

function skillName(id) {
  return state.topics.flatMap((t) => t.skills).find((s) => s.skill_id === id)?.name || id || "—";
}

async function loadProfile() {
  state.profile = null;
  $("profile").replaceChildren(el("p", "Đang tải hồ sơ…", "muted"));
  if (!$("student").value) { $("profile").replaceChildren(el("p", "Chưa có học sinh để chọn.", "muted")); return; }
  let profile;
  try { profile = await api(`/api/v1/students/${encodeURIComponent($("student").value)}/profile`); }
  catch (error) { $("profile").replaceChildren(el("p", "Không tải được hồ sơ. Hãy chọn lại học sinh hoặc kết nối lại.", "muted")); throw error; }
  state.profile = profile;
  const heading = el("div", null, "profile-header");
  heading.append(el("strong", profile.name), el("span", `Lớp ${profile.grade_level}`, "muted"));
  const rows = state.topics.find((t) => t.topic_id === $("topic").value)?.skills || [];
  $("profile").replaceChildren(heading);
  for (const skill of rows) {
    const record = profile.skill_mastery.find((s) => s.skill_id === skill.skill_id);
    const row = el("div", null, "skill-row");
    const label = el("div", skill.name);
    label.append(el("small", `${skill.skill_id} · ${record?.evidence_count || 0} evidence`));
    row.append(label, el("div", record && record.evidence_count > 0 ? `${record.mastery_score.toFixed(2)} / 4` : "Chưa có dữ liệu", "skill-score"));
    $("profile").append(row);
  }
  $("profile").append(el("p", `${profile.learning_history.length} bài trong lịch sử · Evidence được ghi theo từng kỹ năng.`, "field-help"));
}

async function connect() {
  state.token = $("teacher-token").value.trim();
  state.connected = false;
  state.profile = null;
  clearResults();
  $("connection-state").textContent = "Chưa kết nối";
  $("connection-state").classList.remove("connected");
  $("demo-notice").hidden = true;
  try {
    const [students, topics, config] = await Promise.all([api("/api/v1/students"), api("/api/v1/topics"), api("/ui/config")]);
    state.students = students.items; state.topics = topics.items; state.config = config;
    $("student").replaceChildren(...state.students.map((s) => { const o = el("option", `${s.name} · ${s.student_id}`); o.value = s.student_id; return o; }));
    $("topic").replaceChildren(...state.topics.map((t) => { const o = el("option", t.topic_name); o.value = t.topic_id; return o; }));
    $("student-count").textContent = `(${state.students.length} hồ sơ)`;
    state.connected = true;
    $("connection-state").textContent = "Đã kết nối backend";
    $("connection-state").classList.add("connected");
    $("connection-title").textContent = "Phiên làm việc đã kết nối";
    $("connection-help").textContent = `${state.students.length} hồ sơ · Token chỉ giữ trong bộ nhớ trang. Tải lại trang cần nhập token hoặc mở lại từ launcher.`;
    $("runtime-label").textContent = config.backend === "qwen" ? `Model cấu hình: ${config.model}` : "Demo · Không gọi AI";
    $("demo-notice").hidden = config.backend !== "fake";
    $("teacher-token").value = "";
    $("teacher-token").placeholder = "Nhập token khác để kết nối lại";
    await loadProfile();
  } catch (error) {
    if (!state.connected) { state.token = ""; $("student").replaceChildren(el("option", "Kết nối để tải danh sách")); $("profile").replaceChildren(el("p", "Chưa tải hồ sơ.", "muted")); }
    throw error;
  }
}

function requestBody() {
  if (!$("exam-form").reportValidity()) return null;
  if (!state.profile || state.profile.student_id !== $("student").value) throw new Error("Hãy tải hồ sơ học sinh trước khi tạo đề.");
  let distribution = null;
  if ($("lock-levels").checked) {
    distribution = Object.fromEntries(Object.keys(levels).map((key) => [key, Number($(key).value)]));
    if (Math.abs(Object.values(distribution).reduce((a, b) => a + b, 0) - 100) > 0.0001) throw new Error("Tổng phân bố độ khó phải bằng 100%.");
  }
  return {student_id: $("student").value, generation_mode: $("mode").value, selected_topic_ids: [$("topic").value],
    total_questions: Number($("question-count").value), duration_minutes: Number($("duration").value), difficulty_distribution: distribution};
}

function switchTab(tab, focus = false) {
  state.tab = tab;
  for (const name of ["exam", "plan"]) {
    const selected = name === tab;
    $(`${name}-pane`).hidden = !selected;
    $(`${name}-tab`).classList.toggle("active", selected);
    $(`${name}-tab`).setAttribute("aria-selected", String(selected));
    $(`${name}-tab`).tabIndex = selected ? 0 : -1;
  }
  if (focus) $(`${tab}-tab`).focus();
  setControls();
}

function clearResults() {
  state.exam = null; state.plan = null;
  $("exam-pane").replaceChildren(...Array.from(initialExam.childNodes, (n) => n.cloneNode(true)));
  $("plan-pane").replaceChildren(...Array.from(initialPlan.childNodes, (n) => n.cloneNode(true)));
  setControls();
}

function badges(values) { const row = el("div", null, "badges"); for (const v of values) row.append(el("span", v, "badge")); return row; }
function warnDetails(items) {
  if (!items?.length) return document.createDocumentFragment();
  const details = el("details", null, "warnings");
  details.append(el("summary", `${items.length} lưu ý từ hệ thống`));
  const list = el("ul"); for (const item of items) list.append(el("li", item)); details.append(list); return details;
}

function renderExam(exam) {
  const body = el("div", null, "result-body");
  const heading = el("div", null, "exam-heading");
  heading.append(el("h3", exam.title));
  const student = state.students.find((s) => s.student_id === exam.student_id);
  heading.append(el("p", `${student?.name || exam.student_id} · ${exam.student_id} · Lớp ${exam.grade_level}`));
  heading.append(badges([`${exam.total_questions} câu`, `${exam.duration_minutes} phút`, `${exam.total_score} điểm`, exam.provenance.generator === "qwen" ? exam.provenance.model : "Demo · Không gọi AI"]));
  heading.append(el("p", `${exam.exam_id} · Phiên bản ${exam.revision || 1}`, "source-id"));
  const status = el("div", exam.status === "approved" ? "Giáo viên đã duyệt đề." : "Bản nháp chờ giáo viên kiểm tra câu hỏi, đáp án và rubric.", "notice warning");
  body.append(heading, status);
  for (const question of exam.questions) {
    const article = el("article", null, "question");
    const top = el("div", null, "question-top");
    top.append(el("strong", `Câu ${question.order_index}`), el("span", `${question.max_score} điểm`));
    article.append(top, badges([levels[question.cognitive_level] || question.cognitive_level, ...question.skill_ids.map(skillName)]), el("p", question.content_latex, "math-text"));
    article.append(el("p", `Nguồn: ${question.source_ref.id}`, "source-id"));
    const details = el("details"); details.append(el("summary", "Xem đáp án, lời giải và rubric"));
    const answer = el("div", null, "answer-block");
    answer.append(el("h4", "Đáp án"), el("p", question.answer.correct_answer, "math-text"), el("h4", "Giải thích"), el("p", question.answer.explanation, "math-text"));
    answer.append(el("h4", "Các bước giải"));
    const steps = el("ol");
    for (const step of question.step_solutions) steps.append(el("li", `${step.explanation} (${step.score} điểm)`));
    answer.append(steps, el("h4", "Rubric"));
    const rubric = el("ul"); for (const item of question.rubric) rubric.append(el("li", `${item.criteria} (${item.sub_score} điểm)`));
    answer.append(rubric, warnDetails(question.validation.review_notes)); details.append(answer); article.append(details); body.append(article);
  }
  $("exam-pane").replaceChildren(body);
}

function makeTable(headers, rows) {
  const wrapper = el("div", null, "table-wrap"); const node = el("table");
  const head = el("thead"); const tr = el("tr");
  for (const h of headers) tr.append(el("th", h)); head.append(tr); node.append(head);
  const body = el("tbody");
  for (const row of rows) { const tr = el("tr"); for (const v of row) tr.append(el("td", v)); body.append(tr); }
  node.append(body); wrapper.append(node); return wrapper;
}

function renderPlan(plan) {
  const body = el("div", null, "result-body");
  const grid = el("div", null, "summary-grid");
  for (const [label, value] of [["Chiến lược", strategies[plan.strategy] || plan.strategy], ["Phân bố độ khó", plan.difficulty_locked ? "Theo yêu cầu giáo viên" : "Planner tự phân bổ"]]) {
    const box = el("div", null, "summary-box"); box.append(el("small", label), el("strong", value)); grid.append(box);
  }
  body.append(grid, el("h3", "Phân bố câu hỏi"));
  body.append(makeTable(["Mức độ", "Kế hoạch", "Đạt được"], Object.entries(levels).map(([key, name]) => [name, plan.quota_summary.requested_levels[key] || 0, plan.quota_summary.achieved_levels[key] || 0])));
  body.append(el("h3", "Đánh giá dữ liệu kỹ năng"));
  body.append(makeTable(["Kỹ năng", "Trạng thái"], Object.entries(plan.skill_classifications).map(([key, value]) => [skillName(key), skillStates[value] || value])));
  if (plan.questions?.length) {
    body.append(el("h3", "Các câu nguồn được chọn"));
    body.append(makeTable(["Câu", "Nguồn", "Kỹ năng chính", "Mức độ"], plan.questions.map((q, i) => [i + 1, q.source_id, skillName(q.target_skill_id), levels[q.cognitive_level]])));
    const reasons = plan.questions.flatMap((q, i) => (q.reasons || []).map((r) => `Câu ${i + 1}: ${r}`));
    body.append(warnDetails(reasons));
  }
  body.append(warnDetails(plan.warnings), el("p", `Policy: ${plan.policy_version}. Kế hoạch không tự xác nhận tính đúng toán học của câu nguồn.`, "field-help"));
  $("plan-pane").replaceChildren(body);
}

function acceptExam(exam) {
  state.exam = exam;
  renderExam(exam);
  state.plan = exam.planner_summary ? {...exam.planner_summary, questions: exam.questions.map((q) => ({source_id: q.source_ref.id, target_skill_id: q.target_skill_id, cognitive_level: q.cognitive_level}))} : null;
  if (state.plan) renderPlan(state.plan);
  else $("plan-pane").replaceChildren(el("div", "Đề này không kèm planner summary. Bạn có thể xem kế hoạch riêng từ cấu hình bên trái.", "result-body"));
  switchTab("exam");
}

/* ── Exam tool event listeners ── */
$("connect-form").addEventListener("submit", (e) => { e.preventDefault(); operation("Đang kết nối và tải hồ sơ…", connect); });
$("student").addEventListener("change", () => { clearResults(); operation("Đang tải hồ sơ học sinh…", loadProfile); });
$("topic").addEventListener("change", () => { clearResults(); operation("Đang tải dữ liệu kỹ năng…", loadProfile); });
$("exam-form").addEventListener("input", () => { clearResults(); syncLevels(); });
$("plan-button").addEventListener("click", () => {
  let body; try { body = requestBody(); } catch (e) { announce(e.message, "error"); return; } if (!body) return;
  operation("Đang lập kế hoạch chọn câu…", async () => { state.plan = await api("/api/v1/exams/plan", {method: "POST", body}); renderPlan(state.plan); switchTab("plan"); announce("Đã lập kế hoạch. Chưa gọi Qwen và chưa lưu đề."); });
});
$("exam-form").addEventListener("submit", (e) => {
  e.preventDefault(); let body; try { body = requestBody(); } catch (err) { announce(err.message, "error"); return; } if (!body) return;
  operation("Đang tạo đề ôn tập…", async () => {
    const timeout = (Number(state.config?.generation_timeout_seconds) || 180) * 1000 + 20000;
    const exam = await api("/api/v1/exams/generate", {method: "POST", body, timeout});
    acceptExam(exam); announce(`Đã tạo và lưu bản nháp ${exam.total_questions} câu. Mã đề: ${exam.exam_id}`);
  }, state.config?.backend === "qwen");
});
$("retrieve-form").addEventListener("submit", (e) => { e.preventDefault(); const id = $("exam-id").value.trim(); if (!id) return;
  operation("Đang mở đề đã lưu…", async () => { acceptExam(await api(`/api/v1/exams/${encodeURIComponent(id)}`)); announce("Đã mở đề đã lưu."); });
});
for (const tab of ["exam", "plan"]) {
  $(`${tab}-tab`).addEventListener("click", () => switchTab(tab));
  $(`${tab}-tab`).addEventListener("keydown", (e) => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) { e.preventDefault(); switchTab(e.key === "Home" ? "exam" : e.key === "End" ? "plan" : tab === "exam" ? "plan" : "exam", true); } });
}
$("download-button").addEventListener("click", () => {
  const data = state.tab === "exam" ? state.exam : state.plan; if (!data) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json;charset=utf-8"}));
  const link = el("a"); link.href = url; link.download = `${state.tab === "exam" ? state.exam.exam_id : "exam-plan"}.json`;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});

/* bootstrap token from launcher */
const bootstrapToken = new URLSearchParams(window.location.hash.slice(1)).get("token");
if (window.location.hash && bootstrapToken) history.replaceState(null, "", window.location.pathname + window.location.search);
syncLevels(); setControls();
if (bootstrapToken) { $("teacher-token").value = bootstrapToken; operation("Đang kết nối phiên local…", connect); }

/* ═══════════════════════════════════════════════════════════
   GIAO DIỆN GIÁO VIÊN THEO FIGMA: ROUTER + 3 MÀN
   Màn công cụ cũ (home) không đổi. Ba màn mới nằm trong #fg-shell:

     #/                                  home     (công cụ cũ: kết nối, chọn học sinh)
     #/students/{id}                     profile  → #view-profile  (Màn 1: hồ sơ)
     #/students/{id}/generate            config   → #view-config   (Màn 2: cấu hình sinh đề)
     #/students/{id}/exams/{examId}      draft    → #view-draft    (Màn 3: bản nháp, xem trước)

   Màn hiện tại luôn được ghi ở document.body.dataset.view.
═══════════════════════════════════════════════════════════ */

const AUTH_CODES = ["TEACHER_ACCESS_DENIED", "TEACHER_AUTH_REQUIRED", "TEACHER_ACCESS_NOT_CONFIGURED"];
const MIN_EVIDENCE = 3; // chỉ để hiển thị "n/3 câu". Việc phân loại kỹ năng do planner quyết định (README, ADR-003)
const LEVEL_KEYS = Object.keys(levels);
const LIMITS = {questions: {min: 1, max: 10}, duration: {min: 1, max: 180}};
const DEFAULTS = {questions: 4, duration: 45};
const VIEW_NAMES = ["profile", "config", "draft"];

const view = {current: "home", studentId: null};
const draftCtx = {request: null, examId: null}; // body của lần sinh đề gần nhất, dùng cho "Tạo lại toàn bộ đề"

/* ── Tiện ích ── */
const enc = encodeURIComponent;
const isAuthError = (err) => AUTH_CODES.includes(err?.apiCode || "");
const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));
const genTimeout = () => (Number(state.config?.generation_timeout_seconds) || 180) * 1000 + 20000;

function svgIcon(id, size = 13, cls = "ic") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", cls); svg.setAttribute("width", String(size)); svg.setAttribute("height", String(size)); svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${id}`); svg.append(use);
  return svg;
}
const skillNameIn = (topics, id) => topics.flatMap((t) => t.skills).find((s) => s.skill_id === id)?.name || id;
function generationBody(config) {
  const body = {
    student_id: config.student_id,
    generation_mode: config.mode ?? config.generation_mode ?? "adaptive",
    selected_topic_ids: config.selected_topic_ids ?? ["combinatorics"],
    total_questions: config.num_questions ?? config.total_questions,
    duration_minutes: config.duration ?? config.duration_minutes,
    difficulty_distribution: config.difficulty_distribution ?? null,
  };
  if (!body.student_id || !["adaptive", "default_blueprint", "standard"].includes(body.generation_mode)) throw new Error("Invalid student or generation mode.");
  if (!Number.isInteger(body.total_questions) || body.total_questions < 1 || body.total_questions > 10) throw new Error("Question count must be an integer from 1 to 10.");
  if (!Number.isInteger(body.duration_minutes) || body.duration_minutes < 1 || body.duration_minutes > 180) throw new Error("Duration must be an integer from 1 to 180.");
  if (config.advanced_options) body.advanced_options = {...config.advanced_options};
  return body;
}
const planBody = (studentId, totalQuestions, durationMinutes, mode = "adaptive") => generationBody({
  student_id: studentId, mode, num_questions: totalQuestions, duration: durationMinutes,
});
async function getStudentProfile(studentId) {
  const [profile, topicsResp, plan] = await Promise.all([
    api(`/api/v1/students/${enc(studentId)}/profile`), api("/api/v1/topics"),
    api("/api/v1/exams/plan", {method: "POST", body: planBody(studentId, DEFAULTS.questions, DEFAULTS.duration)}),
  ]);
  const skills = topicsResp.items.flatMap((topic) => topic.skills);
  const sufficient = skills.filter((skill) => ["WEAK", "ACHIEVED"].includes(plan.skill_classifications[skill.skill_id])).length;
  return {...profile, topics: topicsResp.items, plan, data_status: dataStatus(plan.skill_classifications),
    completed_tests: profile.learning_history.length, sufficient_skills: sufficient, total_skills: skills.length,
    sufficient_ratio: skills.length ? sufficient / skills.length : 0, assessment: buildAssessment(plan, topicsResp.items)};
}
function getExamPlan(config) {
  return api("/api/v1/exams/plan", {method: "POST", body: generationBody(config)});
}
async function generateDraft(config) {
  const body = generationBody(config);
  const exam = await api("/api/v1/exams/generate", {method: "POST", body, timeout: genTimeout()});
  draftCtx.request = body; draftCtx.examId = exam.exam_id;
  return exam;
}

/* Nhãn "Dữ liệu hồ sơ": API không có field này, suy ra từ phân loại kỹ năng của planner */
function dataStatus(classifications) {
  const values = Object.values(classifications || {});
  if (!values.length) return {label: "—", cls: "is-none"};
  if (values.every((v) => v === "NO_DATA")) return {label: "Chưa có", cls: "is-none"};
  if (values.some((v) => v === "NO_DATA" || v === "PARTIAL")) return {label: "Một phần", cls: "is-partial"};
  return {label: "Đầy đủ", cls: "is-full"};
}
function setDataStatus(prefix, classifications) {
  const status = dataStatus(classifications);
  $(`${prefix}-data-label`).textContent = `Dữ liệu hồ sơ: ${status.label}`;
  $(`${prefix}-data-icon`).setAttribute("class", `ic ${status.cls}`);
}

/* Câu đánh giá và khuyến nghị. API không có văn bản này, ghép theo mẫu từ phân loại và chiến lược */
function buildAssessment(plan, topics) {
  const cls = plan.skill_classifications || {};
  const idsOf = (value) => Object.entries(cls).filter(([, v]) => v === value).map(([k]) => k);
  const names = (ids) => ids.map((id) => skillNameIn(topics, id)).join(", ");
  const weak = idsOf("WEAK");
  const lacking = [...idsOf("NO_DATA"), ...idsOf("PARTIAL")];
  const total = Object.keys(cls).length;
  const result = {weakTitle: "[!] Cần cải thiện:", weakText: "", weakMuted: false, recText: ""};

  if (weak.length) {
    result.weakText = `Cần tập trung củng cố: ${names(weak)}.`;
    if (lacking.length) result.weakText += ` Chưa đủ dữ liệu để đánh giá: ${names(lacking)}.`;
  } else if (total && idsOf("NO_DATA").length === total) {
    Object.assign(result, {weakTitle: "Chưa đủ dữ liệu:", weakText: "Học sinh chưa có bài làm nào nên chưa thể đánh giá. Cần thêm bài kiểm tra.", weakMuted: true});
  } else if (lacking.length) {
    Object.assign(result, {weakTitle: "Chưa đủ dữ liệu để đánh giá:", weakText: `Cần từ ${MIN_EVIDENCE} câu đã làm mỗi kỹ năng. Còn thiếu: ${names(lacking)}.`, weakMuted: true});
  } else {
    Object.assign(result, {weakTitle: "Đạt mục tiêu:", weakText: "Học sinh đã đạt mục tiêu ở tất cả kỹ năng có đủ dữ liệu.", weakMuted: true});
  }

  const focus = plan.quota_summary?.requested_groups?.focus;
  if (plan.strategy === "focused_practice") {
    result.recText = weak.length
      ? `Tập trung ôn${focus ? ` ${focus} câu` : ""} vào ${names(weak)}. Các câu còn lại ôn lại kỹ năng đã đạt.`
      : "Tập trung ôn các kỹ năng cần củng cố.";
  } else if (plan.strategy === "diagnostic_review") {
    result.recText = "Đề thăm dò: ưu tiên câu chẩn đoán cho kỹ năng chưa đủ dữ liệu và câu duy trì cho kỹ năng đã đạt.";
  } else if (plan.strategy === "advanced_review") {
    result.recText = "Học sinh đã thành thạo: đề tập trung câu vận dụng và vận dụng cao.";
  } else {
    result.recText = strategies[plan.strategy] ? `Chiến lược: ${strategies[plan.strategy]}.` : "Đề chuẩn.";
  }
  return result;
}

/* Chip trọng tâm, đoạn mô tả, khối "Phù hợp với hồ sơ hiện tại" dùng chung cho màn 2 và màn 3 */
function renderStrategy(prefix, plan, topics, levelCounts) {
  const cls = plan?.skill_classifications || {};
  const weak = Object.entries(cls).filter(([, v]) => v === "WEAK").map(([k]) => skillNameIn(topics, k));
  const chips = $(`${prefix}-focus`);
  chips.replaceChildren();
  if (!plan) { chips.append(el("span", "Chưa có thông tin kế hoạch", "fg-chip is-muted")); $(`${prefix}-strategy-text`).textContent = ""; $(`${prefix}-fit`).hidden = true; return; }
  if (weak.length) for (const name of weak) chips.append(el("span", name, "fg-chip"));
  else chips.append(el("span", strategies[plan.strategy] || "Chưa có kỹ năng yếu đủ dữ liệu", "fg-chip is-muted"));
  $(`${prefix}-strategy-text`).textContent = buildAssessment(plan, topics).recText;

  const warnings = plan.warnings || [];
  $(`${prefix}-fit`).hidden = false;
  $(`${prefix}-fit-title`).textContent = warnings.length ? "Lưu ý từ hệ thống" : "Phù hợp với hồ sơ hiện tại";
  const noAdvanced = levelCounts && (levelCounts.advanced_application || 0) === 0;
  $(`${prefix}-fit-text`).textContent = warnings.length ? "" : (weak.length && noAdvanced
    ? `Chưa đưa câu vận dụng cao vào đề để tập trung củng cố ${weak.join(", ")}.`
    : `Đề được lập theo hồ sơ hiện tại của học sinh (${strategies[plan.strategy] || "đề chuẩn"}).`);
  $(`${prefix}-fit-text`).hidden = warnings.length > 0;
  const list = $(`${prefix}-fit-list`);
  list.replaceChildren(...warnings.map((w) => el("li", w)));
  list.hidden = warnings.length === 0;
}

/* Thanh phân bố 4 mức + danh sách ô. counts = số câu mỗi mức, total = tổng số câu */
function renderBar(bar, counts, total) {
  bar.replaceChildren(...LEVEL_KEYS.map((key, i) => {
    const seg = el("span", null, `s${i + 1}`);
    seg.style.width = total > 0 ? `${(counts[key] / total) * 100}%` : "0%";
    return seg;
  }));
}
const pctOf = (n, total) => (total > 0 ? `${Math.round((n / total) * 100)}%` : "—");

/* ── Quản lý màn hình ── */
function setLoading(name, on) { $(`view-${name}`).dataset.loading = String(on); }

function showView(name, studentId) {
  view.current = name;
  if (studentId !== undefined) view.studentId = studentId;
  document.body.dataset.view = name;
  $("view-home").hidden = name !== "home";
  $("fg-shell").hidden = name === "home";
  for (const v of VIEW_NAMES) $(`view-${v}`).hidden = v !== name;
  $("fg-forbidden").hidden = true;
  $("fg-error").hidden = true;
  if (name === "home") return;

  const id = view.studentId ? enc(view.studentId) : "";
  $("fg-shell").dataset.nav = name === "profile" ? "track" : "create";
  $("fg-steps").hidden = name === "profile";
  $("fg-back").href = name === "profile" ? "#/" : `#/students/${id}`;
  $("fg-back-text").textContent = name === "profile" ? "Quay lại Danh sách học sinh" : "Quay lại Hồ sơ học sinh";
  $("nav-create").href = `#/students/${id}/generate`;
  $("nav-track").href = `#/students/${id}`;
  $("step-1-link").href = `#/students/${id}/generate`;
  window.scrollTo(0, 0);
}

function showFull(kind, message, retry) {
  for (const v of VIEW_NAMES) $(`view-${v}`).hidden = true;
  $("fg-forbidden").hidden = kind !== "forbidden";
  $("fg-error").hidden = kind !== "error";
  if (kind === "error") {
    $("fg-error-msg").textContent = message || "Đã có lỗi xảy ra khi tải dữ liệu.";
    $("fg-error-retry").onclick = retry || handleRoute;
  }
}

function handleLoadError(err) {
  if (isAuthError(err)) showFull("forbidden", err.message);
  else showFull("error", err.message, handleRoute);
}

function setAlert(prefix, kind, message) {
  const box = $(`${prefix}-alert`);
  box.hidden = !message;
  box.classList.toggle("is-error", kind === "error");
  box.classList.toggle("is-ok", kind === "ok");
  $(`${prefix}-alert-msg`).textContent = message || "";
  if (prefix === "cf") $("cf-retry").hidden = kind !== "error";
}

/* ═══════════════════════════════════════════════════════════
   MÀN 1: HỒ SƠ HỌC SINH
═══════════════════════════════════════════════════════════ */
const pf = {seq: 0};

function skillRow(name, record, classification) {
  const evidence = record?.evidence_count || 0;
  const hasData = evidence > 0 && record;
  const pct = hasData ? clamp(Math.round((record.mastery_score / 4) * 100), 0, 100) : null;
  const kind = classification || (hasData ? "PARTIAL" : "NO_DATA");
  const row = el("div", null, `fg-skill${kind === "PARTIAL" ? " is-partial" : kind === "NO_DATA" ? " is-nodata" : ""}`);
  const label = el("div");
  const sub = {
    NO_DATA: "Chưa có dữ liệu",
    PARTIAL: `Cần thêm dữ liệu · ${evidence}/${MIN_EVIDENCE} câu`,
    WEAK: `${evidence} câu đã làm · Cần củng cố`,
    ACHIEVED: `${evidence} câu đã làm · Đạt mục tiêu`,
  }[kind] || `${evidence} câu đã làm`;
  label.append(el("div", `${name}:`, "fg-skill-n"), el("div", sub, "fg-skill-s"));
  const bar = el("div", null, "fg-mbar"); bar.setAttribute("aria-hidden", "true");
  const fill = el("i"); fill.style.width = `${kind === "NO_DATA" ? 0 : pct ?? 0}%`; bar.append(fill);
  row.append(label, bar, el("div", kind === "NO_DATA" || pct === null ? "—" : `${pct}%`, "fg-skill-p"));
  row.setAttribute("role", "group");
  row.setAttribute("aria-label", `${name}: ${kind === "NO_DATA" ? "chưa có dữ liệu" : `${pct}%, ${sub}`}`);
  return row;
}

function renderProfile(profile, topics, plan) {
  const skills = topics.flatMap((t) => t.skills);
  const cls = plan.skill_classifications || {};
  $("pf-name").textContent = profile.name;
  $("pf-grade").textContent = `Lớp ${profile.grade_level}`;
  setDataStatus("pf", cls);
  $("pf-exams").textContent = `${profile.learning_history.length} bài`;
  const sufficient = skills.filter((s) => ["WEAK", "ACHIEVED"].includes(cls[s.skill_id])).length;
  $("pf-ratio").textContent = `${sufficient}/${skills.length}`;

  const list = $("pf-skills");
  list.replaceChildren();
  const noneHasData = skills.every((s) => (cls[s.skill_id] || "NO_DATA") === "NO_DATA");
  if (noneHasData) list.append(el("p", "Chưa có dữ liệu năng lực. Học sinh cần làm thêm bài kiểm tra để hệ thống đánh giá.", "fg-empty"));
  for (const skill of skills) {
    list.append(skillRow(skill.name, profile.skill_mastery.find((r) => r.skill_id === skill.skill_id), cls[skill.skill_id]));
  }

  const a = buildAssessment(plan, topics);
  $("pf-weak-title").textContent = a.weakTitle;
  $("pf-weak-text").textContent = a.weakText;
  $("pf-weak").classList.toggle("fg-note-warn", !a.weakMuted);
  $("pf-rec-text").textContent = a.recText;

  const history = profile.learning_history;
  $("pf-log-count").textContent = String(history.length);
  $("pf-log-list").replaceChildren(...(history.length
    ? history.map((h) => { const li = el("li", `Bài ${h.test_id} `); li.append(el("span", `· ${h.wrong_questions.length} câu sai`)); return li; })
    : [el("li", "Chưa có bài kiểm tra nào.")]));
}

async function loadProfileView(studentId) {
  const seq = ++pf.seq;
  setLoading("profile", true);
  try {
    const profile = await getStudentProfile(studentId);
    if (seq !== pf.seq || view.current !== "profile") return;
    renderProfile(profile, profile.topics, profile.plan);
    setLoading("profile", false);
  } catch (err) {
    if (seq === pf.seq && view.current === "profile") handleLoadError(err);
  }
}
$("pf-generate").addEventListener("click", () => { if (view.studentId) location.hash = `#/students/${enc(view.studentId)}/generate`; });

/* ═══════════════════════════════════════════════════════════
   MÀN 2: CẤU HÌNH SINH ĐỀ
═══════════════════════════════════════════════════════════ */
const cf = {studentId: null, topics: [], plan: null, status: "loading", seq: 0, loadSeq: 0, timer: null, busy: false};

function readInt(inputId, limits, label) {
  const raw = $(inputId).value.trim();
  if (raw === "") return {error: `${label} không được để trống.`};
  if (!/^\d+$/.test(raw)) return {error: `${label} phải là số nguyên.`};
  const value = Number(raw);
  if (value < limits.min || value > limits.max) return {error: `${label} phải từ ${limits.min} đến ${limits.max}.`};
  return {value};
}

/* Trả về {total_questions, duration_minutes} nếu hợp lệ, ngược lại null và hiện lỗi dưới ô sai */
function cfValidate() {
  const q = readInt("cf-questions", LIMITS.questions, "Số câu");
  const d = readInt("cf-duration", LIMITS.duration, "Thời lượng");
  $("cf-questions-err").textContent = q.error || "";
  $("cf-duration-err").textContent = d.error || "";
  $("cf-questions").closest(".fg-stepper").classList.toggle("is-invalid", Boolean(q.error));
  $("cf-duration").closest(".fg-stepper").classList.toggle("is-invalid", Boolean(d.error));
  $("cf-questions").setAttribute("aria-invalid", String(Boolean(q.error)));
  $("cf-duration").setAttribute("aria-invalid", String(Boolean(d.error)));
  return q.error || d.error ? null : {total_questions: q.value, duration_minutes: d.value};
}

function cfBody(values) {
  return {...planBody(cf.studentId, values.total_questions, values.duration_minutes), selected_topic_ids: [cf.topics[0]?.topic_id || "combinatorics"]};
}

function cfUpdate() {
  const valid = cfValidate() !== null;
  for (const id of ["cf-questions", "cf-duration", "cf-q-minus", "cf-q-plus", "cf-d-minus", "cf-d-plus", "cf-cancel"]) $(id).disabled = cf.busy;
  $("cf-start").disabled = cf.busy || !valid || cf.status !== "ok";
  $("cf-start-text").textContent = cf.busy ? "Đang tạo đề…" : "Bắt đầu tạo đề";
  $("cf-dist").classList.toggle("is-stale", cf.status !== "ok");
  const q = readInt("cf-questions", LIMITS.questions, ""), d = readInt("cf-duration", LIMITS.duration, "");
  $("cf-sum-q").textContent = q.error ? "—" : `${q.value} câu`;
  $("cf-sum-d").textContent = d.error ? "—" : `${d.value} phút`;
}

/* Vẽ phân bố và cột chiến lược. Trả về chuỗi lỗi nếu dữ liệu phân bố không hợp lệ */
function cfRenderPlan(plan, values) {
  const requested = plan.quota_summary?.requested_levels || {};
  const counts = Object.fromEntries(LEVEL_KEYS.map((k) => [k, Number(requested[k]) || 0]));
  const sum = LEVEL_KEYS.reduce((a, k) => a + counts[k], 0);
  const total = values.total_questions;

  renderBar($("cf-dist-bar"), counts, total);
  $("cf-dist-cells").replaceChildren(...LEVEL_KEYS.map((key) => {
    const cell = el("div", null, "fg-cell");
    const box = el("div", pctOf(counts[key], total), "fg-cell-v");
    cell.append(el("div", levels[key], "fg-cell-l"), box, el("div", `${counts[key]} câu`, "fg-cell-n"));
    return cell;
  }));
  renderStrategy("cf", plan, cf.topics, counts);
  setDataStatus("cf", plan.skill_classifications);

  /* Kiểm tra phòng thủ: các mức phải cộng đúng bằng số câu yêu cầu */
  if (sum !== total) {
    $("cf-dist-total").textContent = "Tổng: không hợp lệ";
    return `Dữ liệu phân bố không hợp lệ: các mức cộng lại ${sum} câu, trong khi yêu cầu ${total} câu.`;
  }
  $("cf-dist-total").textContent = "Tổng: 100%";
  return "";
}

async function cfRefreshPlan() {
  const values = cfValidate();
  if (!values) { cf.status = "invalid"; $("cf-plan-status").textContent = ""; $("cf-plan-retry").hidden = true; cfUpdate(); return; }
  const seq = ++cf.seq;
  cf.status = "loading";
  $("cf-plan-status").textContent = "Đang cập nhật kế hoạch…";
  $("cf-plan-retry").hidden = true;
  cfUpdate();
  try {
    const plan = await getExamPlan(cfBody(values));
    if (seq !== cf.seq || view.current !== "config") return; // đã có yêu cầu mới hơn, bỏ kết quả cũ
    cf.plan = plan;
    const problem = cfRenderPlan(plan, values);
    cf.status = problem ? "error" : "ok";
    $("cf-plan-status").textContent = problem;
  } catch (err) {
    if (seq !== cf.seq || view.current !== "config") return;
    if (isAuthError(err)) { showFull("forbidden", err.message); return; }
    cf.status = "error";
    $("cf-plan-status").textContent = err.message;
    $("cf-plan-retry").hidden = false;
  }
  cfUpdate();
}

async function loadConfigView(studentId) {
  const loadSeq = ++cf.loadSeq;
  const isNew = cf.studentId !== studentId; // quay lại cùng học sinh thì giữ nguyên cấu hình đã nhập
  cf.studentId = studentId;
  if (isNew) {
    $("cf-questions").value = String(DEFAULTS.questions);
    $("cf-duration").value = String(DEFAULTS.duration);
    setAlert("cf", "", "");
    cf.plan = null;
  }
  cf.status = "loading";
  setLoading("config", true);
  try {
    const [profile, topicsResp] = await Promise.all([api(`/api/v1/students/${enc(studentId)}/profile`), api("/api/v1/topics")]);
    if (loadSeq !== cf.loadSeq || view.current !== "config") return;
    cf.topics = topicsResp.items;
    $("cf-name").textContent = profile.name;
    $("cf-grade").textContent = `Lớp ${profile.grade_level}`;
    $("cf-sum-subject").textContent = `Toán · Lớp ${profile.grade_level}`;
    setLoading("config", false);
    cfUpdate();
    await cfRefreshPlan();
  } catch (err) {
    if (loadSeq === cf.loadSeq && view.current === "config") handleLoadError(err);
  }
}

/* Bấm "Bắt đầu tạo đề". Lỗi thì giữ nguyên form và cho thử lại */
async function cfStart() {
  if (cf.busy) return; // chống bấm đúp
  const values = cfValidate();
  if (!values || cf.status !== "ok") return;
  const studentId = cf.studentId;
  const body = cfBody(values);
  cf.busy = true;
  setAlert("cf", "", "");
  $("cf-busy").hidden = false;
  $("cf-elapsed").textContent = "0";
  cfUpdate();
  const started = Date.now();
  const timer = setInterval(() => { $("cf-elapsed").textContent = String(Math.floor((Date.now() - started) / 1000)); }, 1000);
  try {
    const exam = await generateDraft(body);
    state.exam = exam;
    if (view.current === "config" && cf.studentId === studentId) location.hash = `#/students/${enc(studentId)}/exams/${enc(exam.exam_id)}`;
  } catch (err) {
    if (isAuthError(err)) { showFull("forbidden", err.message); return; }
    setAlert("cf", "error", err.message); // form giữ nguyên, không reset
  } finally {
    clearInterval(timer);
    cf.busy = false;
    $("cf-busy").hidden = true;
    cfUpdate();
  }
}

function cfStep(inputId, delta, limits, fallback) {
  const current = Number($(inputId).value);
  const base = Number.isInteger(current) && $(inputId).value.trim() !== "" ? current : fallback;
  $(inputId).value = String(clamp(base + delta, limits.min, limits.max));
  cfOnInput();
}

function cfOnInput() {
  ++cf.seq;
  clearTimeout(cf.timer);
  const valid = cfValidate() !== null;
  cf.status = valid ? "loading" : "invalid";
  cfUpdate();
  if (valid) cf.timer = setTimeout(cfRefreshPlan, 400); // chờ người dùng ngừng gõ rồi mới cập nhật kế hoạch
}

$("cf-q-minus").addEventListener("click", () => cfStep("cf-questions", -1, LIMITS.questions, DEFAULTS.questions));
$("cf-q-plus").addEventListener("click", () => cfStep("cf-questions", 1, LIMITS.questions, DEFAULTS.questions));
$("cf-d-minus").addEventListener("click", () => cfStep("cf-duration", -5, LIMITS.duration, DEFAULTS.duration));
$("cf-d-plus").addEventListener("click", () => cfStep("cf-duration", 5, LIMITS.duration, DEFAULTS.duration));
$("cf-questions").addEventListener("input", cfOnInput);
$("cf-duration").addEventListener("input", cfOnInput);
$("cf-start").addEventListener("click", cfStart);
$("cf-retry").addEventListener("click", cfStart);
$("cf-plan-retry").addEventListener("click", cfRefreshPlan);
$("cf-cancel").addEventListener("click", () => { location.hash = cf.studentId ? `#/students/${enc(cf.studentId)}` : "#/"; });

/* ═══════════════════════════════════════════════════════════
   MÀN 3: BẢN NHÁP & XEM TRƯỚC
═══════════════════════════════════════════════════════════ */
const dr = {studentId: null, exam: null, profile: null, topics: [], seq: 0, busy: false};

function questionCard(q, topics) {
  const card = el("article", null, "fg-q");
  card.dataset.questionId = q.question_id;
  const head = el("div", null, "fg-q-head");
  head.append(el("span", `Câu ${q.order_index}`, "fg-q-n"), el("span", levels[q.cognitive_level] || q.cognitive_level, "fg-chip fg-chip-sm"));
  head.append(el("span", `${q.max_score} \u0111i\u1ec3m`, "fg-chip fg-chip-sm"));
  const skillId = q.target_skill_id || q.skill_ids[0];
  if (skillId) head.append(el("span", skillNameIn(topics, skillId), "fg-chip fg-chip-sm"));

  const answerId = `ans-${q.question_id}`;
  const answer = el("div", null, "fg-answer"); answer.id = answerId; answer.hidden = true;
  answer.append(el("h5", "Đáp án"), el("p", q.answer.correct_answer), el("h5", "Giải thích"), el("p", q.answer.explanation), el("h5", "Các bước giải"));
  const steps = el("ol");
  for (const s of q.step_solutions) steps.append(el("li", `${s.explanation} (${s.score} điểm)`));
  answer.append(steps, el("h5", "Rubric"));
  const rubric = el("ul");
  for (const r of q.rubric) rubric.append(el("li", `${r.criteria} (${r.sub_score} điểm)`));
  answer.append(rubric);
  const notes = q.validation?.review_notes || [];
  if (notes.length) answer.append(el("h5", "Lưu ý khi duyệt"), ...notes.map((n) => el("p", n)));

  const toggle = el("button", null, "fg-act"); toggle.type = "button";
  toggle.dataset.act = "toggle"; toggle.setAttribute("aria-expanded", "false"); toggle.setAttribute("aria-controls", answerId);
  toggle.append(el("span", "Đáp án"), svgIcon("i-chevron"));
  const replace = el("button", null, "fg-act"); replace.type = "button"; replace.dataset.act = "replace";
  replace.append(svgIcon("i-refresh"), el("span", "Thay câu"));
  const actions = el("div", null, "fg-q-actions"); actions.append(toggle, replace);

  card.append(head, el("p", q.content_latex, "fg-q-body"), actions, answer);
  return card;
}

function renderDraft() {
  const {exam, profile, topics} = dr;
  const plan = exam.planner_summary || null;
  $("dr-name").textContent = profile.name;
  $("dr-grade").textContent = `Lớp ${profile.grade_level}`;
  if (plan) setDataStatus("dr", plan.skill_classifications);
  else { $("dr-data-label").textContent = "Dữ liệu hồ sơ: —"; $("dr-data-icon").setAttribute("class", "ic is-none"); }
  $("dr-subject").textContent = `Toán · Lớp ${exam.grade_level}`;
  $("dr-subject-sub").textContent = `Tự luận · ${exam.total_questions} câu · ${exam.duration_minutes} phút`;
  $("dr-meta").textContent = [
    exam.status === "approved" ? "Đã duyệt" : "Bản nháp · chờ giáo viên duyệt",
    `Mã đề ${exam.exam_id} · phiên bản ${exam.revision || 1}`,
    exam.provenance?.generator === "qwen" ? `Tạo bởi ${exam.provenance.model}` : "Đề demo: ghép từ câu có sẵn, không gọi AI và chưa cá nhân hóa",
  ].join("  ·  ");

  $("dr-questions").replaceChildren(...exam.questions.map((q) => questionCard(q, topics)));

  /* Tóm tắt: số liệu tính từ chính các câu trong đề, không lấy từ kế hoạch */
  const counts = Object.fromEntries(LEVEL_KEYS.map((k) => [k, exam.questions.filter((q) => q.cognitive_level === k).length]));
  $("dr-sum-subject").textContent = `Toán · Lớp ${exam.grade_level}`;
  $("dr-sum-qd").textContent = `${exam.total_questions} câu · ${exam.duration_minutes} phút`;
  $("dr-sum-score").textContent = `${exam.total_score} điểm`;
  renderBar($("dr-dist-bar"), counts, exam.total_questions);
  $("dr-dist-list").replaceChildren(...LEVEL_KEYS.map((k) => {
    const row = el("div"); row.append(el("dt", levels[k]), el("dd", `${pctOf(counts[k], exam.total_questions)} · ${counts[k]} câu`)); return row;
  }));
  renderStrategy("dr", plan, topics, counts);
  $("dr-edit").href = `#/students/${enc(exam.student_id)}/generate`;
}

function drBusy(on, message) {
  dr.busy = on;
  for (const b of $("view-draft").querySelectorAll("[data-act]")) b.disabled = on;
  $("dr-regen-all").disabled = on;
  $("dr-save").disabled = on;
  if (on) setAlert("dr", "ok", message);
}

async function loadDraftView(studentId, examId) {
  const seq = ++dr.seq;
  dr.studentId = studentId;
  setAlert("dr", "", "");
  setLoading("draft", true);
  try {
    const cached = state.exam && state.exam.exam_id === examId ? state.exam : null;
    const [exam, profile, topicsResp] = await Promise.all([
      cached || api(`/api/v1/exams/${enc(examId)}`),
      api(`/api/v1/students/${enc(studentId)}/profile`),
      api("/api/v1/topics"),
    ]);
    if (seq !== dr.seq || view.current !== "draft") return;
    if (exam.student_id !== studentId) throw new Error("Mã đề này không thuộc học sinh đang xem.");
    state.exam = exam;
    Object.assign(dr, {exam, profile, topics: topicsResp.items});
    renderDraft();
    setLoading("draft", false);
  } catch (err) {
    if (seq === dr.seq && view.current === "draft") handleLoadError(err);
  }
}

async function drReplace(questionId) {
  if (dr.busy) return;
  const number = dr.exam.questions.find((q) => q.question_id === questionId)?.order_index;
  drBusy(true, `Đang thay câu ${number}… Qwen có thể cần vài phút.`);
  try {
    const exam = await api(`/api/v1/exams/${enc(dr.exam.exam_id)}/questions/${enc(questionId)}/regenerate`, {method: "POST", body: {expected_revision: dr.exam.revision}, timeout: genTimeout()});
    state.exam = exam; dr.exam = exam;
    renderDraft();
    setAlert("dr", "ok", `Đã thay câu ${number}. Đề quay về trạng thái chờ giáo viên duyệt (phiên bản ${exam.revision}).`);
  } catch (err) {
    if (isAuthError(err)) { showFull("forbidden", err.message); return; }
    setAlert("dr", "error", err.message);
  } finally { drBusy(false); }
}

async function drRegenerateAll() {
  if (dr.busy || !dr.exam) return;
  const exam = dr.exam;
  // Older/reopened drafts do not expose the original percentages. Preserve
  // their locked level quotas using equivalent percentages from the plan.
  const lockedLevels = exam.planner_summary?.difficulty_locked
    ? Object.fromEntries(LEVEL_KEYS.map((key) => [key, 100 * (exam.planner_summary.quota_summary.requested_levels[key] || 0) / exam.total_questions]))
    : null;
  const body = draftCtx.request && draftCtx.examId === exam.exam_id
    ? draftCtx.request
    : {...planBody(exam.student_id, exam.total_questions, exam.duration_minutes), generation_mode: exam.generation_mode, selected_topic_ids: [exam.topic_id], difficulty_distribution: lockedLevels};
  drBusy(true, "Đang tạo lại toàn bộ đề… Qwen có thể cần vài phút.");
  try {
    const fresh = await generateDraft(body);
    state.exam = fresh;
    if (view.current === "draft") location.hash = `#/students/${enc(fresh.student_id)}/exams/${enc(fresh.exam_id)}`;
  } catch (err) {
    if (isAuthError(err)) { showFull("forbidden", err.message); return; }
    setAlert("dr", "error", err.message);
  } finally { drBusy(false); }
}

$("dr-questions").addEventListener("click", (e) => {
  const button = e.target.closest("[data-act]");
  if (!button) return;
  const card = button.closest(".fg-q");
  if (button.dataset.act === "toggle") {
    const answer = $(button.getAttribute("aria-controls"));
    answer.hidden = !answer.hidden;
    button.setAttribute("aria-expanded", String(!answer.hidden));
  } else if (button.dataset.act === "replace") drReplace(card.dataset.questionId);
});
$("dr-regen-all").addEventListener("click", drRegenerateAll);
$("dr-save").addEventListener("click", () => {
  if (dr.exam) setAlert("dr", "ok", `Bản nháp đã được lưu tự động khi tạo đề. Mở lại bất cứ lúc nào bằng mã ${dr.exam.exam_id} (phiên bản ${dr.exam.revision || 1}).`);
});

/* ═══════════════════════════════════════════════════════════
   ROUTER
═══════════════════════════════════════════════════════════ */
function parseRoute() {
  const raw = location.hash;
  if (!raw || raw === "#" || raw.startsWith("#token=")) return {name: "home"};
  const parts = raw.slice(1).split("/"); // ["", "students", id, "generate" | "exams", examId]
  if (parts[1] === "students" && parts[2]) {
    const studentId = decodeURIComponent(parts[2]);
    if (!parts[3]) return {name: "profile", studentId};
    if (parts[3] === "generate") return {name: "config", studentId};
    if (parts[3] === "exams" && parts[4]) return {name: "draft", studentId, examId: decodeURIComponent(parts[4])};
  }
  return {name: "home"};
}

function handleRoute() {
  ++pf.seq; ++cf.seq; ++cf.loadSeq; ++dr.seq;
  clearTimeout(cf.timer);
  const route = parseRoute();
  showView(route.name, route.studentId);
  if (route.name === "home") return;
  if (!state.token) { showFull("forbidden", "Phiên làm việc chưa có teacher token (hoặc đã mất do tải lại trang). Hãy kết nối lại từ màn đầu."); return; }
  if (route.name === "profile") loadProfileView(route.studentId);
  else if (route.name === "config") loadConfigView(route.studentId);
  else loadDraftView(route.studentId, route.examId);
}

/* Màn công cụ cũ: link mở nhanh hồ sơ của học sinh đang chọn */
$("open-profile").addEventListener("click", (e) => {
  const id = $("student").value;
  if (!id) { e.preventDefault(); return; }
  e.currentTarget.href = `#/students/${enc(id)}`;
});

window.addEventListener("hashchange", handleRoute);
setTimeout(handleRoute, 0); // chạy sau khi token từ launcher được xử lý
