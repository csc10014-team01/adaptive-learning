"use strict";

const $ = (id) => document.getElementById(id);
const levels = {recognition: "Nhận biết", understanding: "Thông hiểu", application: "Vận dụng", advanced_application: "Vận dụng cao"};
const strategies = {focused_practice: "Luyện tập kỹ năng cần củng cố", diagnostic_review: "Thăm dò năng lực", advanced_review: "Ôn tập nâng cao", standard: "Đề chuẩn"};
const skillStates = {NO_DATA: "Chưa có dữ liệu", PARTIAL: "Cần thêm evidence", WEAK: "Cần củng cố", ACHIEVED: "Đạt mục tiêu"};
const state = {token: "", connected: false, busy: false, students: [], topics: [], profile: null, config: null, exam: null, plan: null, tab: "exam", acceptedQuestions: new Set(), reviewStale: false};
const initialExam = $("exam-pane").cloneNode(true);
const initialPlan = $("plan-pane").cloneNode(true);

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
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
  document.querySelectorAll(".review-control").forEach((node) => {
    node.disabled = !state.connected || state.busy || (state.reviewStale && node.id !== "refresh-draft-button");
  });
  const approve = $("approve-exam-button");
  if (approve) approve.disabled = !state.connected || state.busy || state.reviewStale ||
    !approvalReady(state.exam);
}

async function api(path, {method = "GET", body, timeout = 15000} = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {method, signal: controller.signal, cache: "no-store", credentials: "omit",
      headers: {Authorization: `Bearer ${state.token}`, ...(body ? {"Content-Type": "application/json"} : {})},
      ...(body ? {body: JSON.stringify(body)} : {})});
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
        INSUFFICIENT_QUESTION_BANK: "Ngân hàng chưa đủ câu phù hợp với hồ sơ và giới hạn độ khó. Thử giảm số câu hoặc bổ sung nguồn đã duyệt.",
        INVALID_QWEN_OUTPUT: "Đầu ra Qwen chưa vượt qua kiểm tra. Không có đề dở được lưu.",
        EXAM_REVISION_CONFLICT: "Đề đã thay đổi ở phiên khác. Bấm Tải lại bản mới nhất rồi kiểm tra lại từng câu trước khi duyệt.",
        REGENERATION_UNSUPPORTED: "Tạo lại câu cần backend Qwen. Đề demo không hỗ trợ thao tác này.",
        EXAM_NOT_FOUND: "Không tìm thấy mã đề này. Đề demo sẽ mất khi khởi động lại server."
      }[code];
      const details = (data.error?.details || []).map((d) => `${d.field}: ${d.reason}`).join("\n");
      const error = new Error([help || data.error?.message || "Yêu cầu chưa thực hiện được.", `[${code}]`, help ? data.error?.message : "", details].filter(Boolean).join("\n"));
      error.code = code;
      throw error;
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
  try { await work(); } catch (error) {
    if (error.code === "EXAM_REVISION_CONFLICT") { state.reviewStale = true; state.acceptedQuestions.clear(); renderExam(state.exam); }
    announce(error.message, "error");
  }
  finally { clearInterval(timer); state.busy = false; $("loading").hidden = true; setControls(); }
}

function skillName(id) {
  return state.topics.flatMap((t) => t.skills).find((s) => s.skill_id === id)?.name || id || "—";
}

function formatMastery(record) {
  if (!record) return "--/4";
  if (!Number.isInteger(record.evidence_count) || record.evidence_count < 0) throw new Error("Evidence trong hồ sơ không hợp lệ.");
  if (record.evidence_count === 0) return "--/4";
  if (!Number.isFinite(record.mastery_score)) throw new Error("Hồ sơ có evidence nhưng thiếu điểm mastery hợp lệ.");
  return `${record.mastery_score.toFixed(2)} / 4`;
}

async function loadProfile() {
  state.profile = null;
  $("profile").replaceChildren(element("p", "Đang tải hồ sơ…", "muted"));
  if (!$("student").value) { $("profile").replaceChildren(element("p", "Chưa có học sinh để chọn.", "muted")); return; }
  let profile;
  try {
    profile = await api(`/api/v1/students/${encodeURIComponent($("student").value)}/profile`);
    profile.skill_mastery.forEach(formatMastery);
  }
  catch (error) { $("profile").replaceChildren(element("p", "Không tải được hồ sơ. Hãy chọn lại học sinh hoặc kết nối lại.", "muted")); throw error; }
  state.profile = profile;
  const heading = element("div", null, "profile-header");
  heading.append(element("strong", profile.name), element("span", `Lớp ${profile.grade_level}`, "muted"));
  const rows = state.topics.find((t) => t.topic_id === $("topic").value)?.skills || [];
  $("profile").replaceChildren(heading);
  for (const skill of rows) {
    const record = profile.skill_mastery.find((s) => s.skill_id === skill.skill_id);
    const row = element("div", null, "skill-row");
    const label = element("div", skill.name);
    label.append(element("small", `${skill.skill_id} · ${record?.evidence_count ?? 0} evidence`));
    row.append(label, element("div", formatMastery(record), "skill-score"));
    $("profile").append(row);
  }
  $("profile").append(element("p", `${profile.learning_history.length} bài trong lịch sử · Evidence được ghi theo từng kỹ năng.`, "field-help"));
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
    $("student").replaceChildren(...state.students.map((s) => { const option = element("option", `${s.name} · ${s.student_id}`); option.value = s.student_id; return option; }));
    $("topic").replaceChildren(...state.topics.map((t) => { const option = element("option", t.topic_name); option.value = t.topic_id; return option; }));
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
    if (!state.connected) { state.token = ""; $("student").replaceChildren(element("option", "Kết nối để tải danh sách")); $("profile").replaceChildren(element("p", "Chưa tải hồ sơ.", "muted")); }
    throw error;
  }
}

function requestBody() {
  if (!$("exam-form").reportValidity()) return null;
  if (!state.profile || state.profile.student_id !== $("student").value) throw new Error("Hãy tải hồ sơ học sinh trước khi tạo đề.");
  return {student_id: $("student").value, generation_mode: "adaptive", selected_topic_ids: [$("topic").value],
    total_questions: Number($("question-count").value), duration_minutes: Number($("duration").value)};
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
  state.acceptedQuestions.clear(); state.reviewStale = false;
  $("exam-pane").replaceChildren(...Array.from(initialExam.childNodes, (n) => n.cloneNode(true)));
  $("plan-pane").replaceChildren(...Array.from(initialPlan.childNodes, (n) => n.cloneNode(true)));
  setControls();
}

function badges(values) { const row = element("div", null, "badges"); for (const value of values) row.append(element("span", value, "badge")); return row; }
function warnings(items) {
  if (!items?.length) return document.createDocumentFragment();
  const details = element("details", null, "warnings");
  details.append(element("summary", `${items.length} lưu ý từ hệ thống`));
  const list = element("ul"); for (const item of items) list.append(element("li", item)); details.append(list); return details;
}

function approvalReady(exam) {
  return exam?.status === "pending_teacher_review" && exam.questions?.length === exam.total_questions &&
    exam.questions.length > 0 && exam.questions.every(q => q.content_latex?.trim() && q.answer?.correct_answer?.trim() &&
      q.step_solutions?.length > 0 && q.rubric?.length > 0 && q.validation &&
      !q.validation.blocking_errors?.length &&
      (exam.provenance.generator === "fake" || ["pass", "needs_review"].includes(q.validation.auto_status)) &&
      (q.source_ref.kind !== "template" || q.template_instance));
}

function renderExam(exam) {
  const body = element("div", null, "result-body");
  const heading = element("div", null, "exam-heading");
  heading.append(element("h3", exam.title));
  const student = state.students.find((s) => s.student_id === exam.student_id);
  heading.append(element("p", `${student?.name || exam.student_id} · ${exam.student_id} · Lớp ${exam.grade_level}`));
  heading.append(badges([`${exam.total_questions} câu`, `${exam.duration_minutes} phút`, `${exam.total_score} điểm`, exam.provenance.generator === "qwen" ? exam.provenance.model : (exam.provenance.generator === "question_bank" ? "Ngân hàng câu hỏi · Không gọi AI" : "Demo · Không gọi AI")]));
  heading.append(element("p", `${exam.exam_id} · Phiên bản ${exam.revision || 1}`, "source-id"));
  const status = element("div", exam.status === "approved" ? "Giáo viên đã duyệt đề." : "Bản nháp chờ giáo viên kiểm tra câu hỏi, đáp án và rubric.", "notice warning");
  status.setAttribute("role", "status");
  if (exam.status === "approved") status.classList.remove("warning");
  body.append(heading, status);
  const reviewActions = element("div", null, "review-actions");
  const refresh = element("button", "Tải lại bản mới nhất", "secondary review-control");
  refresh.type = "button"; refresh.id = "refresh-draft-button";
  refresh.addEventListener("click", () => operation("Đang tải bản mới nhất…", async () => {
    acceptExam(await api(`/api/v1/exams/${encodeURIComponent(state.exam.exam_id)}`));
    announce("Đã tải bản mới nhất. Hãy kiểm tra lại các câu trước khi duyệt.");
  }));
  reviewActions.append(refresh);
  if (exam.status === "pending_teacher_review") {
    const approve = element("button", "Duyệt toàn bộ đề", "primary review-control");
    approve.id = "approve-exam-button"; approve.type = "button";
    approve.addEventListener("click", () => operation("Đang duyệt đề…", async () => {
      if (state.reviewStale || !approvalReady(state.exam)) throw new Error("Cần bản nháp đầy đủ, hợp lệ và mới nhất để duyệt đề.");
      const current = state.exam;
      const body = {expected_revision: current.revision || 1};
      if (state.acceptedQuestions.size) body.accepted_question_ids = [...state.acceptedQuestions];
      acceptExam(await api(`/api/v1/exams/${encodeURIComponent(current.exam_id)}/approve`, {method: "POST",
        body}));
      announce("Đã duyệt đề. Trạng thái và phiên bản đã được cập nhật.");
    }));
    reviewActions.append(approve);
  }
  body.append(reviewActions);
  if (exam.status === "pending_teacher_review") body.append(element("p", "Có thể duyệt toàn bộ đề sau khi xem; đánh dấu kiểm tra từng câu là tùy chọn.", "field-help"));
  if (state.reviewStale) body.append(element("p", "Phiên bản đã cũ. Tải lại bản mới nhất để tiếp tục.", "notice warning"));
  if (exam.teacher_review?.notes) body.append(element("p", exam.teacher_review.notes, "field-help"));
  for (const question of exam.questions) {
    const article = element("article", null, "question");
    const top = element("div", null, "question-top");
    top.append(element("strong", `Câu ${question.order_index}`), element("span", `${question.max_score} điểm`));
    article.append(top, badges([levels[question.cognitive_level] || question.cognitive_level, ...question.skill_ids.map(skillName)]), element("p", question.content_latex, "math-text"));
    article.append(element("p", `Nguồn: ${question.source_ref.kind} · ${question.source_ref.id}`, "source-id"));
    if (question.source_ref.kind === "template") article.append(element("p",
      `Cách trình bày: ${question.generate_type === "indirect" ? "Indirect (gián tiếp)" : "Direct (trực tiếp)"}`, "source-id"));
    if (question.template_presentation?.verification_status === "experimental") article.append(element("p",
      "Diễn đạt Indirect thử nghiệm — chưa kiểm chứng đầy đủ về ngữ nghĩa toán học.", "notice warning"));
    if (question.template_instance) article.append(element("p", `Tham số: ${JSON.stringify(question.template_instance.parameters)}`, "source-id"));
    const details = element("details"); details.append(element("summary", "Xem đáp án, lời giải và rubric"));
    const answer = element("div", null, "answer-block");
    answer.append(element("h4", "Đáp án"), element("p", question.answer.correct_answer, "math-text"), element("h4", "Giải thích"), element("p", question.answer.explanation, "math-text"));
    answer.append(element("h4", "Các bước giải"));
    const steps = element("ol");
    for (const step of question.step_solutions) steps.append(element("li", `${step.explanation} (${step.score} điểm)`));
    answer.append(steps, element("h4", "Rubric"));
    const rubric = element("ul"); for (const item of question.rubric) rubric.append(element("li", `${item.criteria} (${item.sub_score} điểm)`));
    answer.append(rubric, warnings(question.validation.review_notes)); details.append(answer); article.append(details);
    const actions = element("div", null, "review-actions");
    if (exam.status === "pending_teacher_review") {
      const label = element("label", null, "check-row review-accept");
      const checkbox = element("input", null, "review-control"); checkbox.type = "checkbox";
      checkbox.checked = state.acceptedQuestions.has(question.question_id);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.acceptedQuestions.add(question.question_id);
        else state.acceptedQuestions.delete(question.question_id);
        setControls();
      });
      label.append(checkbox, element("span", "Đã kiểm tra câu hỏi, đáp án và rubric (tùy chọn)")); actions.append(label);
    }
    if (question.source_ref.kind === "template" && question.template_instance) {
      const regenerate = element("button", "Tạo lại câu này", "secondary review-control");
      regenerate.type = "button";
      regenerate.setAttribute("aria-label", `Tạo lại câu ${question.order_index}`);
      regenerate.addEventListener("click", () => operation(`Đang tạo lại câu ${question.order_index}…`, async () => {
        if (state.reviewStale) throw new Error("Tải lại bản mới nhất trước khi tạo lại câu.");
        const current = state.exam;
        const timeout = (Number(state.config?.generation_timeout_seconds) || 180) * 1000 + 20000;
        acceptExam(await api(`/api/v1/exams/${encodeURIComponent(current.exam_id)}/questions/${encodeURIComponent(question.question_id)}/regenerate`,
          {method: "POST", body: {expected_revision: current.revision || 1}, timeout}));
        announce("Đã tạo lại câu và tải bản nháp mới. Hãy kiểm tra lại các câu trước khi duyệt.");
      }, true));
      actions.append(regenerate);
    }
    article.append(actions); body.append(article);
  }
  $("exam-pane").replaceChildren(body);
}

function table(headers, rows) {
  const wrapper = element("div", null, "table-wrap"); const node = element("table");
  const head = element("thead"); const tr = element("tr");
  for (const header of headers) tr.append(element("th", header)); head.append(tr); node.append(head);
  const body = element("tbody");
  for (const row of rows) { const tr = element("tr"); for (const value of row) tr.append(element("td", value)); body.append(tr); }
  node.append(body); wrapper.append(node); return wrapper;
}

function renderPlan(plan) {
  const body = element("div", null, "result-body");
  const grid = element("div", null, "summary-grid");
  for (const [label, value] of [["Chiến lược", strategies[plan.strategy] || plan.strategy], ["Phân bố độ khó", "Tự động theo mastery và evidence của từng kỹ năng"]]) {
    const box = element("div", null, "summary-box"); box.append(element("small", label), element("strong", value)); grid.append(box);
  }
  body.append(grid, element("h3", "Phân bố câu hỏi"));
  body.append(table(["Mức độ", "Kế hoạch", "Đạt được"], Object.entries(levels).map(([key, name]) => [name, plan.quota_summary.requested_levels[key] || 0, plan.quota_summary.achieved_levels[key] || 0])));
  body.append(element("h3", "Đánh giá dữ liệu kỹ năng"));
  body.append(table(["Kỹ năng", "Trạng thái"], Object.entries(plan.skill_classifications).map(([key, value]) => [skillName(key), skillStates[value] || value])));
  if (plan.questions?.length) {
    body.append(element("h3", "Các câu nguồn được chọn"));
    body.append(table(["Câu", "Loại nguồn", "Nguồn", "Kỹ năng chính", "Mức độ", "Trạng thái"], plan.questions.map((q, i) => [i + 1, q.source_kind || "question", q.source_id, skillName(q.target_skill_id), levels[q.cognitive_level], q.source_status === "pending_wording" ? "Chờ sinh lời văn" : "Đã có nội dung"])));
    const reasons = plan.questions.flatMap((q, i) => (q.reasons || []).map((r) => `Câu ${i + 1}: ${r}`));
    body.append(warnings(reasons));
  }
  body.append(warnings(plan.warnings), element("p", `Policy: ${plan.policy_version}. Kế hoạch không tự xác nhận tính đúng toán học của câu nguồn.`, "field-help"));
  $("plan-pane").replaceChildren(body);
}

function acceptExam(exam) {
  state.exam = exam;
  state.acceptedQuestions.clear(); state.reviewStale = false;
  renderExam(exam);
  state.plan = exam.planner_summary ? {...exam.planner_summary, questions: exam.questions.map((q) => ({source_id: q.source_ref.id, source_kind: q.source_ref.kind, source_status: "stored", target_skill_id: q.target_skill_id, cognitive_level: q.cognitive_level}))} : null;
  if (state.plan) renderPlan(state.plan);
  else $("plan-pane").replaceChildren(element("div", "Đề này không kèm planner summary. Bạn có thể xem kế hoạch riêng từ cấu hình bên trái.", "result-body"));
  switchTab("exam");
}

$("connect-form").addEventListener("submit", (event) => { event.preventDefault(); operation("Đang kết nối và tải hồ sơ…", connect); });
$("student").addEventListener("change", () => { clearResults(); operation("Đang tải hồ sơ học sinh…", loadProfile); });
$("topic").addEventListener("change", () => { clearResults(); operation("Đang tải dữ liệu kỹ năng…", loadProfile); });
$("exam-form").addEventListener("input", clearResults);
$("plan-button").addEventListener("click", () => {
  let body; try { body = requestBody(); } catch (error) { announce(error.message, "error"); return; } if (!body) return;
  operation("Đang lập kế hoạch chọn câu…", async () => { state.plan = await api("/api/v1/exams/plan", {method: "POST", body}); renderPlan(state.plan); switchTab("plan"); announce("Đã lập kế hoạch. Chưa gọi Qwen và chưa lưu đề."); });
});
$("exam-form").addEventListener("submit", (event) => {
  event.preventDefault(); let body; try { body = requestBody(); } catch (error) { announce(error.message, "error"); return; } if (!body) return;
  operation("Đang tạo đề ôn tập…", async () => {
    const timeout = (Number(state.config?.generation_timeout_seconds) || 180) * 1000 + 20000;
    const exam = await api("/api/v1/exams/generate", {method: "POST", body, timeout});
    acceptExam(exam); announce(`Đã tạo và lưu bản nháp ${exam.total_questions} câu. Mã đề: ${exam.exam_id}`);
  }, state.config?.backend === "qwen");
});
$("retrieve-form").addEventListener("submit", (event) => { event.preventDefault(); const id = $("exam-id").value.trim(); if (!id) return;
  operation("Đang mở đề đã lưu…", async () => { acceptExam(await api(`/api/v1/exams/${encodeURIComponent(id)}`)); announce("Đã mở đề đã lưu."); });
});
for (const tab of ["exam", "plan"]) {
  $(`${tab}-tab`).addEventListener("click", () => switchTab(tab));
  $(`${tab}-tab`).addEventListener("keydown", (event) => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) { event.preventDefault(); switchTab(event.key === "Home" ? "exam" : event.key === "End" ? "plan" : tab === "exam" ? "plan" : "exam", true); } });
}
$("download-button").addEventListener("click", () => {
  const data = state.tab === "exam" ? state.exam : state.plan; if (!data) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json;charset=utf-8"}));
  const link = element("a"); link.href = url; link.download = `${state.tab === "exam" ? state.exam.exam_id : "exam-plan"}.json`;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});

const bootstrapToken = new URLSearchParams(window.location.hash.slice(1)).get("token");
if (window.location.hash) history.replaceState(null, "", window.location.pathname + window.location.search);
setControls();
if (bootstrapToken) { $("teacher-token").value = bootstrapToken; operation("Đang kết nối phiên local…", connect); }
