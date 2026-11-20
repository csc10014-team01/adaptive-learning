/* ═══════════════════════════════════════════════════════════
   GIAO DIỆN GIÁO VIÊN THEO FIGMA: ROUTER + 3 MÀN
   Màn công cụ cũ (home) không đổi. Ba màn mới nằm trong #fg-shell:

     #/                                  home     (công cụ cũ: kết nối, chọn học sinh)
     #/students/{id}                     profile  → #view-profile  (Màn 1: hồ sơ)
     #/students/{id}/generate            config   → #view-config   (Màn 2: cấu hình sinh đề)
     #/students/{id}/exams/{examId}      draft    → #view-draft    (Màn 3: bản nháp, xem trước)

   Màn hiện tại luôn được ghi ở document.body.dataset.view.
═══════════════════════════════════════════════════════════ */

const el = element;
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
const isAuthError = (err) => AUTH_CODES.includes(err?.code || "");
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
const planBody = (studentId, totalQuestions, durationMinutes) => ({
  student_id: studentId, generation_mode: "adaptive", selected_topic_ids: ["combinatorics"],
  total_questions: totalQuestions, duration_minutes: durationMinutes, difficulty_distribution: null, // phân bố do planner quyết định
});

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
      ? `Ôn tập tập trung${focus ? ` ${focus} câu` : ""} vào ${names(weak)}. Các câu còn lại ôn lại kỹ năng đã đạt.`
      : "Ôn tập tập trung vào các kỹ năng cần củng cố.";
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
  $("pf-name").textContent = profile.student_name;
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
    const [profile, topicsResp, plan] = await Promise.all([
      api(`/api/v1/students/${enc(studentId)}/profile`),
      api("/api/v1/topics"),
      api("/api/v1/exams/plan", {method: "POST", body: planBody(studentId, DEFAULTS.questions, DEFAULTS.duration)}),
    ]);
    if (seq !== pf.seq || view.current !== "profile") return;
    renderProfile(profile, topicsResp.items, plan);
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
    const plan = await api("/api/v1/exams/plan", {method: "POST", body: cfBody(values)});
    if (seq !== cf.seq) return; // đã có yêu cầu mới hơn, bỏ kết quả cũ
    cf.plan = plan;
    const problem = cfRenderPlan(plan, values);
    cf.status = problem ? "error" : "ok";
    $("cf-plan-status").textContent = problem;
  } catch (err) {
    if (seq !== cf.seq) return;
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
    $("cf-name").textContent = profile.student_name;
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
    const exam = await api("/api/v1/exams/generate", {method: "POST", body, timeout: genTimeout()});
    acceptExam(exam);
    Object.assign(draftCtx, {request: body, examId: exam.exam_id});
    if (view.current === "config" && cf.studentId === studentId) location.hash = `#/students/${enc(studentId)}/exams/${enc(exam.exam_id)}`;
  } catch (err) {
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
  const actions = el("div", null, "fg-q-actions");
  actions.append(toggle);
  if (q.source_ref.kind === "template") actions.append(replace);

  card.append(head, el("p", q.content_latex, "fg-q-body"), actions, answer);
  return card;
}

function renderDraft() {
  const {exam, profile, topics} = dr;
  const plan = exam.planner_summary || null;
  $("dr-name").textContent = profile.student_name;
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
    const [exam, profile, topicsResp] = await Promise.all([
      api(`/api/v1/exams/${enc(examId)}`),
      api(`/api/v1/students/${enc(studentId)}/profile`),
      api("/api/v1/topics"),
    ]);
    if (seq !== dr.seq || view.current !== "draft") return;
    if (exam.student_id !== studentId) throw new Error("Mã đề này không thuộc học sinh đang xem.");
    acceptExam(exam);
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
    acceptExam(exam); dr.exam = exam;
    renderDraft();
    setAlert("dr", "ok", `Đã thay câu ${number}. Đề quay về trạng thái chờ giáo viên duyệt (phiên bản ${exam.revision}).`);
  } catch (err) {
    if (isAuthError(err)) { showFull("forbidden", err.message); return; }
    setAlert("dr", "error", err.message);
  } finally { drBusy(false); }
}

async function drRegenerateAll() {
  if (dr.busy) return;
  const exam = dr.exam;
  const body = draftCtx.examId === exam.exam_id
    ? draftCtx.request
    : {...planBody(exam.student_id, exam.total_questions, exam.duration_minutes), generation_mode: exam.generation_mode, selected_topic_ids: [exam.topic_id],
      difficulty_distribution: exam.quality_report?.request_snapshot?.difficulty_distribution ?? null};
  drBusy(true, "Đang tạo lại toàn bộ đề… Qwen có thể cần vài phút.");
  try {
    const fresh = await api("/api/v1/exams/generate", {method: "POST", body, timeout: genTimeout()});
    acceptExam(fresh);
    Object.assign(draftCtx, {request: body, examId: fresh.exam_id});
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
  let route;
  try { route = parseRoute(); }
  catch (error) {
    if (!(error instanceof URIError)) throw error;
    route = {name: "home"};
  }
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