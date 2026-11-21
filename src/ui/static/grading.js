"use strict";

const $ = id => document.getElementById(id);
const state = {token: "", connected: false, busy: false, context: null, applied: "", editors: [],
  envelope: null, poll: null, epoch: 0, lastBody: "", lastKey: ""};

function node(tag, text, className) {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = String(text);
  if (className) result.className = className;
  return result;
}

function notice(message, error = false) {
  $("notice").textContent = message;
  $("notice").className = error ? "error" : "";
  $("notice").hidden = !message;
  $("notice").setAttribute("role", error ? "alert" : "status");
}

function controls() {
  $("start").disabled = !state.connected || state.busy;
  $("download").disabled = !state.envelope || state.envelope.metadata.state !== "COMPLETED";
  $("output").setAttribute("aria-busy", String(state.busy));
}

async function api(path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(path, {method: body === undefined ? "GET" : "POST",
      headers: {Authorization: `Bearer ${state.token}`, "Content-Type": "application/json"},
      body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal});
    const data = await response.json();
    if (!response.ok) {
      const detail = data.error || {};
      throw new Error(`${detail.code || response.status}: ${detail.message || "Không thể xử lý yêu cầu."}` +
        (detail.details || []).map(d => `\n${d.field}: ${d.reason}`).join(""));
    }
    return data;
  } finally { clearTimeout(timer); }
}

function applyInput() {
  const data = JSON.parse($("input-json").value);
  if (data.mode !== "experimental" || !Array.isArray(data.questions) || !Array.isArray(data.answers) ||
      data.questions.length < 1 || data.questions.length > 10) throw new Error("Cần experimental request với questions và answers (1–10 câu).");
  const ids = data.questions.map(q => q.question_id);
  const answerIds = data.answers.map(a => a.question_id);
  if (new Set(ids).size !== ids.length || new Set(answerIds).size !== answerIds.length ||
      ids.length !== answerIds.length || ids.some(id => !answerIds.includes(id))) throw new Error("Phải có đúng một bản ghi answer cho mỗi question_id; không thêm, thiếu hoặc trùng câu.");
  const editors = [];
  const container = node("div");
  data.questions.forEach(q => {
    const answer = data.answers.find(a => a.question_id === q.question_id);
    if (typeof answer.student_answer !== "string") throw new Error(`Thiếu student_answer dạng văn bản cho ${q.question_id}.`);
    const section = node("section", undefined, "answer-editor");
    section.append(node("h3", q.question_id), node("p", q.question_text));
    const label = node("label", "Bài làm nguyên văn");
    const editor = node("textarea");
    editor.id = `answer-${editors.length}`; label.htmlFor = editor.id;
    editor.value = answer.student_answer;
    section.append(label, editor); container.append(section);
    editors.push({question_id: q.question_id, editor});
  });
  state.context = data; state.applied = $("input-json").value; state.editors = editors;
  $("answer-editors").replaceChildren(container);
  notice("Đã nạp dữ liệu thử nghiệm. Có thể sửa trực tiếp bài làm nguyên văn bên dưới.");
}

function requestBody() {
  let body;
  if ($("mode").value === "experimental") {
    if (!state.context || state.applied !== $("input-json").value) throw new Error("Bấm Áp dụng JSON vào ô bài làm trước khi bắt đầu.");
    body = {...state.context, answers: state.editors.map(e => ({question_id: e.question_id, student_answer: e.editor.value}))};
  } else {
    body = {mode: "approved_snapshot", exam_id: $("exam-id").value.trim(),
      exam_revision: Number($("revision").value), student_id: $("student-id").value.trim(),
      answers: JSON.parse($("approved-answers").value)};
  }
  delete body.idempotency_key;
  const serialized = JSON.stringify(body);
  if (serialized !== state.lastBody) {
    state.lastBody = serialized; state.lastKey = crypto.randomUUID();
  }
  // A transport failure may hide successful admission. Retrying the same input
  // reuses this key; changing any input creates a new explicit experiment.
  return {...body, idempotency_key: state.lastKey};
}

function render(envelope) {
  state.envelope = envelope;
  const m = envelope.metadata;
  $("job-id").value = m.job_id;
  $("job-label").textContent = `${m.experimental ? "THỬ NGHIỆM" : `ĐỀ ĐÃ DUYỆT · revision ${m.exam_revision}`} · ${m.job_id}`;
  $("progress").max = m.total_questions; $("progress").value = m.completed_questions;
  const processing = {QUEUED: "Đang chờ xử lý", RUNNING: "Đang xử lý", COMPLETED: "Đã xử lý hết các câu",
    FAILED: "Xử lý bị lỗi kỹ thuật", INTERRUPTED: "Xử lý bị gián đoạn; kết quả đã lưu được giữ lại"};
  $("status").textContent = `${processing[m.state] || m.state} · ${m.completed_questions}/${m.total_questions} câu. ` +
    `${m.definite_questions} câu đã có kết luận, ${m.uncertain_questions} câu chưa kết luận.` +
    (m.state === "COMPLETED" && m.uncertain_questions === 0 ? " Tất cả câu đã có kết luận xác định." : "") +
    (m.provider_failures ? ` ${m.provider_failures} câu gặp lỗi dịch vụ AI.` : "") + (m.error_code ? ` ${m.error_code}` : "");
  $("time").textContent = `Thời gian xử lý đã lưu: ${Number(m.elapsed_seconds).toFixed(1)} giây.`;
  const results = node("div");
  const issues = {provider_timeout: "Dịch vụ AI hết thời gian chờ. Chưa kết luận về bài làm.",
    provider_failure: "Dịch vụ AI không sẵn sàng hoặc trả kết quả lỗi. Chưa kết luận về bài làm.",
    invalid_model_output: "Đầu ra AI không hợp lệ sau giới hạn xử lý. Chưa kết luận.",
    unresolved_judgment: "Chưa đủ cơ sở kết luận từ kết quả AI và kiểm tra bằng chứng."};
  for (const submission of envelope.result.submissions) {
    const grade = submission.grading_result;
    const section = node("article", undefined, "question-result");
    section.append(node("h3", submission.question_id), node("span",
      grade.overall_result === "UNCERTAIN" ? "UNCERTAIN · Chưa kết luận" : grade.overall_result,
      `verdict ${grade.overall_result}`));
    const progress = m.questions.find(q => q.question_id === submission.question_id);
    if (progress) {
      section.append(node("p", `${Number(progress.seconds).toFixed(1)} giây`, "hint"));
      if (progress.issue) section.append(node("p", issues[progress.issue], "issue"));
    }
    if (submission.answer.length) {
      const steps = node("ol");
      for (const step of submission.answer) steps.append(node("li", step.description));
      section.append(steps);
    } else section.append(node("p", "Không có bước được công bố là đã đánh giá."));
    for (const error of grade.errors) {
      section.append(node("p", `Lỗi đầu tiên · bước ${error.step}: ${error.reason}`));
      if (error.skill_ids.length) section.append(node("p", `Kỹ năng có lỗi: ${error.skill_ids.join(", ")}`));
    }
    results.append(section);
  }
  $("results").replaceChildren(results);
  $("feedback").hidden = !envelope.result.feedback;
  $("feedback").textContent = envelope.result.feedback || "";
  state.busy = ["QUEUED", "RUNNING"].includes(m.state); controls();
}

function stopPolling() {
  state.epoch += 1;
  clearTimeout(state.poll); state.poll = null;
}

function poll(jobId, epoch) {
  state.poll = setTimeout(async () => {
    try {
      const envelope = await api(`/api/v1/grading/jobs/${encodeURIComponent(jobId)}`);
      if (epoch !== state.epoch) return;
      render(envelope);
      if (state.busy) poll(jobId, epoch);
    } catch (error) {
      if (epoch !== state.epoch) return;
      notice(`${error.message}\nJob vẫn được backend lưu; mở lại bằng mã job để tiếp tục xem.`, true);
      state.busy = false; controls();
    }
  }, 1000);
}

$("connect-form").addEventListener("submit", async event => {
  event.preventDefault(); state.token = $("token").value;
  try {
    await api("/ui/config"); state.connected = true; $("token").value = "";
    $("connection").textContent = "Đã kết nối"; notice("");
  } catch (error) { state.connected = false; $("connection").textContent = "Chưa kết nối"; notice(error.message, true); }
  controls();
});
$("mode").addEventListener("change", () => {
  const experimental = $("mode").value === "experimental";
  $("experimental-fields").hidden = !experimental; $("answer-editors").hidden = !experimental;
  $("approved-fields").hidden = experimental;
});
$("example").addEventListener("click", async () => {
  try {
    const response = await fetch("/ui/assets/grading-example.json");
    if (!response.ok) throw new Error("Không tải được ví dụ tổng hợp.");
    $("input-json").value = JSON.stringify(await response.json(), null, 2); applyInput();
  } catch (error) { notice(error.message, true); }
});
$("import").addEventListener("change", async () => {
  try {
    const file = $("import").files[0]; if (!file) return;
    if (file.size > 512000) throw new Error("JSON vượt giới hạn nhập 500 KB.");
    $("input-json").value = await file.text(); applyInput();
  } catch (error) { notice(error.message, true); }
});
$("apply-input").addEventListener("click", () => { try { applyInput(); } catch (error) { notice(error.message, true); } });
$("start").addEventListener("click", async () => {
  try {
    const body = requestBody(); stopPolling(); const epoch = state.epoch;
    state.busy = true; controls(); notice("");
    $("retry-hint").textContent = "Gửi lại cùng nội dung sẽ mở cùng job để tránh chấm trùng.";
    const envelope = await api("/api/v1/grading/jobs", body);
    if (epoch !== state.epoch) return;
    render(envelope);
    if (state.busy) poll(envelope.metadata.job_id, state.epoch);
  } catch (error) { notice(error.message, true); state.busy = false; controls(); }
});
$("reopen-form").addEventListener("submit", async event => {
  event.preventDefault(); stopPolling(); const epoch = state.epoch;
  try {
    const envelope = await api(`/api/v1/grading/jobs/${encodeURIComponent($("job-id").value.trim())}`);
    if (epoch !== state.epoch) return;
    render(envelope); notice(""); if (state.busy) poll(envelope.metadata.job_id, epoch);
  } catch (error) { notice(error.message, true); state.busy = false; controls(); }
});
$("download").addEventListener("click", () => {
  if (!state.envelope || state.envelope.metadata.state !== "COMPLETED") return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(state.envelope.result, null, 2)], {type: "application/json"}));
  const link = node("a"); link.href = url; link.download = `${state.envelope.metadata.job_id}.json`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

const fragment = new URLSearchParams(window.location.hash.slice(1));
if (fragment.has("token")) {
  $("token").value = fragment.get("token");
  history.replaceState(null, "", window.location.pathname + window.location.search);
  $("connect-form").requestSubmit();
}
controls();
