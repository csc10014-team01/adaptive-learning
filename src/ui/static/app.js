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
   PROFILE SCREEN — ROUTING & RENDERING
═══════════════════════════════════════════════════════════ */

/* ── Profile screen state ── */
const profileState = {
  studentId: null,
  loading: false,
  profile: null,
  topics: null,
  plan: null,
};

/* ── Route parser ──
   #/                        → exam tool
   #/students/{id}           → profile screen
   #/students/{id}/generate  → navigate to generate (future)
*/
function parseHash() {
  const raw = location.hash;
  // Launcher token format: #token=... — handled above, not a route
  if (raw.startsWith("#token=") || (!raw || raw === "#")) return {screen: "exam"};
  const path = raw.slice(1); // remove leading #
  if (path.startsWith("/students/")) {
    const parts = path.split("/"); // ["", "students", "{id}", ...]
    const id = parts[2] || "";
    if (!id) return {screen: "exam"};
    if (parts[3] === "generate") return {screen: "generate", studentId: id};
    return {screen: "profile", studentId: id};
  }
  return {screen: "exam"};
}

/* ── Screen switcher ── */
function showScreen(name) {
  $("screen-exam").hidden = name !== "exam";
  $("screen-profile").hidden = name !== "profile";
}

/* ── Skeleton helpers ── */
function spShowSkeleton() {
  $("sp-skeleton-header").hidden = false;
  $("sp-skeleton-skills").hidden = false;
  $("sp-skeleton-assess").hidden = false;
  $("sp-content").hidden = false;
  // hide real content
  $("sp-name-badge").style.visibility = "hidden";
  $("sp-header-left").style.visibility = "hidden";
  $("sp-header-stats").style.visibility = "hidden";
  $("sp-skill-list").hidden = true;
  $("sp-assess-content").hidden = true;
  $("sp-cta-bar").hidden = true;
  $("sp-403").hidden = true;
  $("sp-error").hidden = true;
}

function spHideSkeleton() {
  $("sp-skeleton-header").hidden = true;
  $("sp-skeleton-skills").hidden = true;
  $("sp-skeleton-assess").hidden = true;
  $("sp-name-badge").style.visibility = "";
  $("sp-header-left").style.visibility = "";
  $("sp-header-stats").style.visibility = "";
}

/* ── Data status label derived from plan skill_classifications ── */
function deriveDataStatus(classifications) {
  if (!classifications || Object.keys(classifications).length === 0) {
    return {label: "Chưa có dữ liệu", dotClass: "none"};
  }
  const vals = Object.values(classifications);
  const noData = vals.filter((v) => v === "NO_DATA").length;
  const partial = vals.filter((v) => v === "PARTIAL").length;
  const total = vals.length;
  if (noData === total) return {label: "Chưa có dữ liệu", dotClass: "none"};
  if (noData + partial === total) return {label: "Một phần", dotClass: "partial"};
  if (noData > 0 || partial > 0) return {label: "Một phần", dotClass: "partial"};
  return {label: "Đầy đủ", dotClass: "full"};
}

/* ── Assessment text generation ── */
const strategyLabels = {
  focused_practice: "luyện tập kỹ năng cần củng cố",
  diagnostic_review: "thăm dò năng lực",
  advanced_review: "ôn tập nâng cao",
  standard: "đề chuẩn",
};

function buildAssessment(plan, topicSkills) {
  const cls = plan.skill_classifications || {};
  const weakIds = Object.entries(cls).filter(([, v]) => v === "WEAK").map(([k]) => k);
  const noDataIds = Object.entries(cls).filter(([, v]) => v === "NO_DATA").map(([k]) => k);
  const partialIds = Object.entries(cls).filter(([, v]) => v === "PARTIAL").map(([k]) => k);

  // Helper: id → name
  const name = (id) => topicSkills.find((s) => s.skill_id === id)?.name || id;

  /* ─ Weak block ─ */
  let weakTitle = "Cần cải thiện:";
  let weakText = "";
  let weakBlockMuted = false;

  if (weakIds.length > 0) {
    weakTitle = "[!] Cần cải thiện:";
    weakText = `Kỹ năng ${weakIds.map(name).join(", ")} cần được tập trung củng cố thêm.`;
  } else if (noDataIds.length > 0 && partialIds.length === 0) {
    weakTitle = "Chưa đủ dữ liệu:";
    weakText = "Chưa đủ dữ liệu để đánh giá. Cần thêm bài kiểm tra để xác định kỹ năng cần cải thiện.";
    weakBlockMuted = true;
  } else if (partialIds.length > 0 && weakIds.length === 0) {
    weakTitle = "Dữ liệu chưa đầy đủ:";
    weakText = `Kỹ năng ${partialIds.map(name).join(", ")} cần thêm dữ liệu để đánh giá chính xác.`;
    weakBlockMuted = true;
  } else {
    weakTitle = "Không có kỹ năng yếu:";
    weakText = "Học sinh đã đạt mục tiêu ở tất cả kỹ năng có đủ dữ liệu.";
    weakBlockMuted = true;
  }

  /* ─ Recommendation block ─ */
  let recText = "";
  const stratLabel = strategyLabels[plan.strategy] || plan.strategy;
  const priorityNames = (plan.priority_skills || []).map(name);
  const focusCount = plan.target_count || 0;

  if (plan.strategy === "focused_practice" && priorityNames.length > 0) {
    recText = `Chiến lược ${stratLabel}: tập trung ${focusCount} câu vào kỹ năng ${priorityNames.join(", ")}. Các câu còn lại ôn tập kỹ năng đã đạt.`;
  } else if (plan.strategy === "diagnostic_review") {
    recText = `Chiến lược ${stratLabel}: đề bao gồm câu chẩn đoán cho kỹ năng chưa đủ dữ liệu và câu duy trì cho kỹ năng đã đạt.`;
  } else if (plan.strategy === "advanced_review") {
    recText = `Chiến lược ${stratLabel}: học sinh đã thành thạo, đề tập trung câu vận dụng và vận dụng cao.`;
  } else if (plan.strategy === "standard") {
    recText = "Đề chuẩn theo phân bố giáo viên yêu cầu.";
  } else {
    recText = `Chiến lược: ${stratLabel}.`;
  }

  return {weakTitle, weakText, weakBlockMuted, recText};
}

/* ── Main render function ── */
function spRenderProfile(profile, topics, plan) {
  const topicSkills = topics.flatMap((t) => t.skills);

  /* Header */
  $("sp-student-name").textContent = profile.name;
  $("sp-grade").textContent = `Lớp ${profile.grade_level}`;

  const cls = plan.skill_classifications || {};
  const {label: statusLabel, dotClass} = deriveDataStatus(cls);
  $("sp-data-label").textContent = `Dữ liệu hồ sơ: ${statusLabel}`;
  $("sp-data-dot").className = `sp-data-dot ${dotClass}`;

  $("sp-exam-count").textContent = `${profile.learning_history.length} bài`;

  const totalSkills = topicSkills.length;
  const sufficientSkills = Object.values(cls).filter((v) => v === "WEAK" || v === "ACHIEVED").length;
  $("sp-skill-ratio").textContent = `${sufficientSkills}/${totalSkills}`;

  /* Skill list */
  const listEl = $("sp-skill-list");
  listEl.replaceChildren();
  for (const skill of topicSkills) {
    const record = profile.skill_mastery.find((s) => s.skill_id === skill.skill_id);
    const classification = cls[skill.skill_id] || "NO_DATA";
    const evidenceCount = record?.evidence_count ?? 0;
    const masteryScore = record?.mastery_score ?? 0;
    const pct = classification === "NO_DATA" ? 0 : Math.round((masteryScore / 4) * 100);

    const row = document.createElement("div");
    row.className = "sp-skill-row";

    /* Label */
    const labelDiv = document.createElement("div");
    labelDiv.className = "sp-skill-label";
    const nameStrong = document.createElement("strong");
    nameStrong.textContent = skill.name + ":";
    const evidenceSmall = document.createElement("small");

    let evidenceText = "";
    if (classification === "NO_DATA") {
      evidenceText = "Chưa có dữ liệu";
    } else if (classification === "PARTIAL") {
      evidenceText = `${evidenceCount} câu đã làm`;
    } else {
      evidenceText = `${evidenceCount} câu đã làm`;
    }
    evidenceSmall.textContent = evidenceText;
    labelDiv.append(nameStrong, evidenceSmall);

    /* Bar wrap */
    const barWrap = document.createElement("div");
    barWrap.className = "sp-skill-bar-wrap";
    const bar = document.createElement("div");
    bar.className = "sp-skill-bar";
    // Assign color class
    if (classification === "ACHIEVED") bar.classList.add("sp-bar-achieved");
    else if (classification === "WEAK") bar.classList.add("sp-bar-weak");
    else if (classification === "PARTIAL") bar.classList.add("sp-bar-partial");
    else bar.classList.add("sp-bar-no-data");
    bar.style.width = `${pct}%`;
    barWrap.append(bar);

    /* Percentage */
    const pctDiv = document.createElement("div");
    pctDiv.className = "sp-skill-pct" + (classification === "NO_DATA" ? " pct-muted" : "");
    pctDiv.textContent = classification === "NO_DATA" ? "—" : `${pct}%`;

    row.append(labelDiv, barWrap, pctDiv);
    listEl.append(row);
  }

  /* Assessment */
  const {weakTitle, weakText, weakBlockMuted, recText} = buildAssessment(plan, topicSkills);
  $("sp-weak-title").textContent = weakTitle;
  $("sp-weak-text").textContent = weakText;
  const weakBlock = $("sp-weak-block");
  weakBlock.classList.toggle("sp-assess-block--muted", weakBlockMuted);
  // Hide warn icon if muted
  const warnIcon = weakBlock.querySelector(".sp-assess-warn");
  if (warnIcon) warnIcon.classList.toggle("sp-assess-warn", !weakBlockMuted);
  $("sp-rec-text").textContent = recText;

  /* Show everything */
  spHideSkeleton();
  $("sp-skill-list").hidden = false;
  $("sp-assess-content").hidden = false;
  $("sp-cta-bar").hidden = false;
}

/* ── Error / 403 screens ── */
function spShowError(msg, retryFn) {
  spHideSkeleton();
  $("sp-content").hidden = true;
  $("sp-error-msg").textContent = msg || "Đã có lỗi xảy ra khi tải hồ sơ học sinh.";
  $("sp-error").hidden = false;
  $("sp-cta-bar").hidden = true;
  // rebind retry
  const btn = $("sp-retry-btn");
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);
  newBtn.addEventListener("click", retryFn);
}

function spShow403() {
  spHideSkeleton();
  $("sp-content").hidden = true;
  $("sp-403").hidden = false;
  $("sp-cta-bar").hidden = true;
}

/* ── Load profile data ── */
async function spLoadStudentData(studentId) {
  if (!state.token) {
    spShow403();
    return;
  }

  spShowSkeleton();
  $("sp-403").hidden = true;
  $("sp-error").hidden = true;

  /* Update nav/back link */
  $("sp-back-btn").href = "#/";
  $("sp-nav-profile").href = `#/students/${encodeURIComponent(studentId)}`;

  const planRequest = {
    student_id: studentId,
    generation_mode: "adaptive",
    selected_topic_ids: ["combinatorics"],
    total_questions: 4,
    duration_minutes: 45,
    difficulty_distribution: null,
  };

  try {
    const [profile, topicsResp, plan] = await Promise.all([
      api(`/api/v1/students/${encodeURIComponent(studentId)}/profile`),
      api("/api/v1/topics"),
      api("/api/v1/exams/plan", {method: "POST", body: planRequest}),
    ]);

    // Cache topics globally for exam tool reuse
    if (!state.topics.length) state.topics = topicsResp.items;

    spRenderProfile(profile, topicsResp.items, plan);

    // Store for navigate-to-generate
    profileState.profile = profile;
    profileState.plan = plan;
  } catch (err) {
    const code = err.apiCode || "";
    if (code === "TEACHER_ACCESS_DENIED" || code === "TEACHER_AUTH_REQUIRED" || code === "TEACHER_ACCESS_NOT_CONFIGURED") {
      spShow403();
    } else {
      spShowError(err.message, () => spLoadStudentData(studentId));
    }
  }
}

/* ── Navigate to profile screen ── */
function navigateToProfile(studentId) {
  if (!studentId) return;
  profileState.studentId = studentId;
  showScreen("profile");
  spLoadStudentData(studentId);
}

/* ── CTA button: go to generate ── */
$("sp-generate-btn").addEventListener("click", () => {
  if (!profileState.studentId) return;
  location.hash = `#/students/${encodeURIComponent(profileState.studentId)}/generate`;
});

/* ── Hash-based routing ── */
function handleRoute() {
  const route = parseHash();

  if (route.screen === "profile") {
    navigateToProfile(route.studentId);
    return;
  }

  if (route.screen === "generate") {
    // Navigate to exam tool and pre-select student if connected
    showScreen("exam");
    if (state.connected && route.studentId) {
      const opt = Array.from($("student").options).find((o) => o.value === route.studentId);
      if (opt) {
        $("student").value = route.studentId;
        $("student").dispatchEvent(new Event("change"));
      }
    }
    return;
  }

  // Default: exam tool
  showScreen("exam");
}

window.addEventListener("hashchange", handleRoute);
// Initial route on page load (after bootstrap token is consumed)
// Use setTimeout to let bootstrap token connection run first
setTimeout(handleRoute, 0);
