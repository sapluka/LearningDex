import { Editor, rootCtx, editorViewCtx, parserCtx, serializerCtx } from "@milkdown/core";
import { commonmark } from "@milkdown/preset-commonmark";
import { gfm } from "@milkdown/preset-gfm";
import { nord } from "@milkdown/theme-nord";
import { history } from "@milkdown/plugin-history";
import { samples } from "./samples.mjs";
import { highlightMarkdown, prepareEditorImages, restoreEditorImages, restoreMath } from "./render_utils.mjs";
import { createDocumentView } from "./document_view.mjs";
import { initPanelDivider } from "./panel_divider.mjs";

let api = null;
let editor = null;
let currentUrl = "";
let currentTaskId = "";
const $ = (id) => document.getElementById(id);
const stateEl = $("state");
const processingEl = $("processingMessage");
const chatLog = $("chatLog");
const documentView = createDocumentView(getMarkdown, chatLog);
const { scheduleHighlights, scheduleMermaid, renderHighlights, renderMermaids,
  renderMessageMermaid, buildPrintDoc, fixImages, mdForDisplay } = documentView;
const chatBubbles = new Map();
let nextChatId = 0;
let pendingQuote = "";
let draftTimer = null;
let draftWrite = Promise.resolve();
let draftError = "";
let currentSkills = [];
window.__setStatus = (t) => {
  stateEl.textContent = t;
  if (!processingEl.hidden) processingEl.textContent = t;
};

function setMarkdown(md) {
  md = prepareEditorImages(md);
  editor.action((ctx) => {
    const view = ctx.get(editorViewCtx);
    const parser = ctx.get(parserCtx);
    const doc = parser(md || "");
    view.dispatch(view.state.tr.replaceWith(0, view.state.doc.content.size, doc.content));
  });
}

function getMarkdown() {
  let md = "";
  editor.action((ctx) => {
    const serializer = ctx.get(serializerCtx);
    const view = ctx.get(editorViewCtx);
    md = serializer(view.state.doc);
  });
  return restoreMath(restoreEditorImages(documentView.mdForStorage(md)));
}

function formatSelection(marker) {
  editor.action((ctx) => {
    const view = ctx.get(editorViewCtx);
    const { from, to } = view.state.selection;
    if (from === to) return;
    if (marker === "==") {
      const text = view.state.doc.textBetween(from, to, "");
      view.dispatch(view.state.tr.insertText("==" + text + "==", from, to));
      return;
    }
    const name = { "**": "strong", "*": "emphasis", "~~": "strike_through" }[marker];
    const mark = view.state.schema.marks[name];
    if (!mark) return;
    const tr = view.state.doc.rangeHasMark(from, to, mark)
      ? view.state.tr.removeMark(from, to, mark)
      : view.state.tr.addMark(from, to, mark.create());
    view.dispatch(tr);
  });
  scheduleHighlights();
}

window._selectAll = () => {
  editor.action((ctx) => {
    const view = ctx.get(editorViewCtx);
    const state = view.state;
    const TS = state.selection.constructor;
    const sel = TS.create(state.doc, 1, Math.max(1, state.doc.content.size - 1));
    view.dispatch(state.tr.setSelection(sel));
  });
};

window._setMarkdown = setMarkdown;
window._getMarkdown = getMarkdown;
window._renderHighlights = renderHighlights;
window._renderMermaids = renderMermaids;
window._buildPrintDoc = buildPrintDoc;
window.__err = "";
window.addEventListener("error", (e) => { window.__err = "ERR:" + (e.message || e.error); });
window.addEventListener("unhandledrejection", (e) => { window.__err = "REJ:" + (e.reason && String(e.reason)); });

function readQuick() {
  return { whisper_model: $("whisperModel").value, proofread: $("proofread").checked };
}

function readSettings() {
  return {
    protocol: $("protocol").value,
    api_key: $("apiKey").value,
    base_url: $("baseUrl").value,
    model: $("model").value,
    bili_sessdata: $("sessdata").value,
    cookies_file: $("cookiesFile").value,
    output_dir: $("outputDir").value,
    ...readQuick(),
  };
}

function fillSettings(cfg) {
  $("protocol").value = cfg.protocol || "openai";
  $("apiKey").value = cfg.api_key || "";
  $("baseUrl").value = cfg.base_url || "";
  $("model").value = cfg.model || "";
  $("sessdata").value = cfg.bili_sessdata || "";
  $("cookiesFile").value = cfg.cookies_file || "";
  $("outputDir").value = cfg.output_dir || "";
  $("whisperModel").value = cfg.whisper_model || "base";
  $("proofread").checked = cfg.proofread !== false;
}

async function init() {
  api = window.pywebview.api;
  fillSettings(await api.load_config());
  initPanelDivider(() => { scheduleHighlights(); scheduleMermaid(); });
  editor = await Editor.make()
    .config((ctx) => ctx.set(rootCtx, $("editor")))
    .use(nord)
    .use(commonmark)
    .use(gfm)
    .use(history)
    .create();
  window.editor = editor;
  editor._setMarkdown = setMarkdown;
  editor._getMarkdown = getMarkdown;
  document.querySelectorAll("#editor [contenteditable], #editor .ProseMirror").forEach((e) => {
    e.setAttribute("spellcheck", "false");
    e.setAttribute("autocorrect", "off");
    e.setAttribute("autocapitalize", "off");
  });
  renderSamples();
  $("startBtn").onclick = startParse;
  $("url").addEventListener("keydown", (e) => { if (e.key === "Enter") startParse(); });
  $("chatSendBtn").onclick = sendChat;
  $("clearQuote").onclick = clearQuote;
  $("chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
  $("pdfBtn").onclick = async () => {
    await flushDraft();
    const saved = await api.save_final(getMarkdown());
    if (!saved.ok) {
      stateEl.textContent = "保存最终笔记失败：" + saved.error;
      stateEl.style.color = "red";
      return;
    }
    await buildPrintDoc();
    window.print();
  };
  $("exportMdBtn").onclick = exportMarkdown;
  $("githubBtn").onclick = () => openLink("https://github.com/sapluka/LearningDex");
  $("settingsBtn").onclick = () => ($("settings").hidden = false);
  $("closeSettings").onclick = () => ($("settings").hidden = true);
  $("saveBtn").onclick = saveSettings;
  $("testBtn").onclick = testConnection;
  $("skillBtn").onclick = openSkills;
  $("skillClose").onclick = () => ($("skillsModal").hidden = true);
  $("skillNew").onclick = () => { $("skillSelect").value = ""; $("skillName").value = ""; $("skillContent").value = ""; };
  $("skillSave").onclick = saveSkill;
  $("skillDelete").onclick = deleteSkill;
  $("skillSelect").onchange = () => {
    const s = currentSkills.find((x) => x.name === $("skillSelect").value);
    if (s) { $("skillName").value = s.name; $("skillContent").value = s.content; }
  };
  $("taskBtn").onclick = openTasks;
  $("tasksClose").onclick = () => ($("tasksModal").hidden = true);
  $("favBtn").onclick = openFavorites;
  $("favsClose").onclick = () => ($("favsModal").hidden = true);
  $("favDocBtn").onclick = toggleCurrentFav;
  $("newParseBtn").onclick = newParse;
  $("historyBtn").onclick = openHistory;
  $("histClose").onclick = () => ($("histModal").hidden = true);
  document.querySelectorAll(".toolbar .tb").forEach((b) => {
    b.onclick = () => formatSelection(b.dataset.wrap);
  });
  $("editor").addEventListener("mouseup", onDocMouseUp);
  $("editor").addEventListener("dblclick", onDocDblClick);
  $("editor").addEventListener("scroll", scheduleHighlights);
  $("editor").addEventListener("scroll", scheduleMermaid);
  $("editor").addEventListener("input", scheduleHighlights);
  $("editor").addEventListener("input", scheduleDraft);
  window.addEventListener("resize", scheduleHighlights);
  window.addEventListener("resize", scheduleMermaid);
  document.addEventListener("mousedown", closePops);
}

async function newParse() {
  if (!await flushDraft()) return;
  await api.reset_context();
  currentUrl = "";
  currentTaskId = "";
  chatBubbles.clear();
  clearQuote();
  documentView.setImageDir("");
  $("workspace").hidden = true;
  processingEl.hidden = true;
  $("welcome").hidden = false;
  $("url").value = "";
  $("welcomeError").hidden = true;
  chatLog.style.display = "flex";
  chatLog.style.alignItems = "center";
  chatLog.style.justifyContent = "center";
  chatLog.innerHTML = '<span class="chat-empty">今天想要学些什么</span>';
  documentView.clearLayers();
  setMarkdown("");
  $("favDocBtn").textContent = "☆";
}

function renderSamples() {
  const container = $("sampleCards");
  for (const sample of samples) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "sample-card";
    const category = document.createElement("small");
    category.textContent = sample.category;
    const title = document.createElement("strong");
    title.textContent = sample.title;
    const preview = document.createElement("span");
    preview.textContent = sample.preview;
    card.append(category, title, preview);
    card.onclick = () => openSample(sample);
    container.appendChild(card);
  }
}

async function openSample(sample) {
  if (!await flushDraft()) return;
  await api.reset_context(sample.markdown);
  currentUrl = "";
  currentTaskId = "";
  chatBubbles.clear();
  clearQuote();
  documentView.setImageDir("");
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  processingEl.hidden = true;
  $("docTitle").textContent = sample.title;
  $("meta").textContent = "内置演示 · 可编辑、提问、导出";
  stateEl.textContent = "示例文档";
  stateEl.style.color = "#666";
  documentView.clearLayers();
  setMarkdown(sample.markdown);
  scheduleHighlights();
  setTimeout(renderMermaids, 300);
  $("favDocBtn").textContent = "☆";
  showChatHint();
}

function openLink(url) {
  if (window.open) window.open(url, "_blank");
}

async function startParse() {
  const url = $("url").value.trim();
  if (!url) {
    $("welcomeError").textContent = "请先粘贴视频链接";
    $("welcomeError").hidden = false;
    return;
  }
  $("welcomeError").hidden = true;
  if (!await flushDraft()) return;
  currentUrl = url;
  currentTaskId = "";
  chatBubbles.clear();
  clearQuote();
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  processingEl.hidden = false;
  processingEl.textContent = "正在提取视频字幕";
  stateEl.textContent = processingEl.textContent;
  stateEl.style.color = "#666";
  try {
    await api.save_config(readQuick());
    const r = await api.generate_doc(url);
    processingEl.hidden = true;
    if (!r.ok) {
      stateEl.textContent = r.error;
      stateEl.style.color = "red";
      return;
    }
    const info = r.info || {};
    $("docTitle").textContent = r.title || info.title || "学习文档";
    $("meta").textContent =
      `${info.uploader || ""} ${info.duration ? Math.round(info.duration / 60) + "分钟" : ""}` +
      `${info.transcribe_note ? "（" + info.transcribe_note + "）" : ""}`;
    documentView.setImageDir(r.taskdir || "");
    currentTaskId = r.id || "";
    setMarkdown(mdForDisplay(r.doc));
    scheduleHighlights();
    setTimeout(fixImages, 400);
    refreshStar();
    setTimeout(renderMermaids, 700);
    stateEl.textContent = r.note || "完成，可编辑文档";
    stateEl.style.color = r.note ? "#a65f00" : "green";
    showChatHint();
  } catch (e) {
    processingEl.hidden = true;
    stateEl.textContent = "异常：" + e;
    stateEl.style.color = "red";
  }
}

function showChatHint() {
  chatBubbles.clear();
  chatLog.style.display = "flex";
  chatLog.innerHTML = "";
  const h = el("div", "chat-empty");
  h.textContent = "学习文档已生成，可以开始提问了。";
  chatLog.appendChild(h);
}

async function exportMarkdown() {
  const title = ($("docTitle").textContent || "学习笔记").replace(/[\\/:*?"<>|]/g, "_").trim();
  try {
    await flushDraft();
    const r = await api.export_md(getMarkdown(), (title || "学习笔记") + ".md");
    if (r.ok) {
      stateEl.textContent = "Markdown 已导出：" + r.path;
      stateEl.style.color = "green";
    } else if (r.error !== "已取消") {
      stateEl.textContent = "导出失败：" + r.error;
      stateEl.style.color = "red";
    }
  } catch (e) {
    stateEl.textContent = "导出失败：" + e;
    stateEl.style.color = "red";
  }
}

function scheduleDraft() {
  if (!currentTaskId) return;
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    draftTimer = null;
    persistDraft();
  }, 600);
}

function persistDraft() {
  if (!currentTaskId) return draftWrite;
  const content = getMarkdown();
  draftWrite = draftWrite.then(() => api.save_draft(content)).then((result) => {
    if (!result.ok) throw new Error(result.error);
    draftError = "";
  }).catch((error) => {
    draftError = String(error);
    stateEl.textContent = "草稿保存失败：" + error;
    stateEl.style.color = "red";
  });
  return draftWrite;
}

async function flushDraft() {
  if (draftTimer) {
    clearTimeout(draftTimer);
    draftTimer = null;
    await persistDraft();
  } else {
    await draftWrite;
  }
  return !draftError;
}

async function sendChat() {
  const q = $("chatInput").value.trim();
  if (!q) return;
  $("chatInput").value = "";
  const quote = pendingQuote;
  clearQuote();
  const display = quote ? "引用：" + quote.slice(0, 60) + (quote.length > 60 ? "…" : "") + "\n" + q : q;
  const id = beginReply(display);
  try {
    if (!$("workspace").hidden) await api.update_doc(getMarkdown());
    if (quote) await api.ask_selection(quote, q, id);
    else await api.chat(q, id);
  } catch (e) {
    window.__chatChunk(id, "异常：" + e);
    window.__chatDone(id);
  }
}

function setQuote(text) {
  pendingQuote = text;
  $("quoteText").textContent = text;
  $("quoteBar").hidden = false;
  $("chatInput").value = "请解释这段内容";
  $("chatInput").focus();
}

function clearQuote() {
  pendingQuote = "";
  $("quoteBar").hidden = true;
  $("quoteText").textContent = "";
}

function beginReply(userText) {
  const id = ++nextChatId;
  docChatPush("user", userText);
  chatBubbles.set(id, docChatPush("ai", ""));
  return id;
}

function ensureChatLog() {
  const hint = chatLog.querySelector(".chat-empty");
  if (hint) hint.remove();
  chatLog.style.display = "flex";
  chatLog.style.flexDirection = "column";
  chatLog.style.alignItems = "stretch";
  chatLog.style.justifyContent = "flex-start";
}

function renderBubble(b) {
  const raw = b.dataset.raw || "";
  if (window.marked && window.DOMPurify) {
    b.innerHTML = window.DOMPurify.sanitize(window.marked.parse(highlightMarkdown(raw), { breaks: true, gfm: true }),
      { USE_PROFILES: { html: true } });
  } else {
    b.textContent = raw;
  }
  if (window.renderMathInElement) {
    try {
      window.renderMathInElement(b, { delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
      ] });
    } catch (e) { /* ignore */ }
  }
}

function docChatPush(kind, text) {
  ensureChatLog();
  const b = el("div", "bub " + (kind === "user" ? "user" : "ai"));
  b.dataset.raw = text || "";
  if (kind === "user") b.textContent = text || "";
  else {
    renderBubble(b);
    if (text) renderMessageMermaid(b);
  }
  chatLog.appendChild(b);
  chatLog.scrollTop = chatLog.scrollHeight;
  return b;
}

window.__chatChunk = (id, t) => {
  const bubble = chatBubbles.get(id);
  if (!bubble) return;
  bubble.dataset.raw = (bubble.dataset.raw || "") + t;
  renderBubble(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
};
window.__chatDone = (id) => {
  const bubble = chatBubbles.get(id);
  if (bubble) {
    renderBubble(bubble);
    renderMessageMermaid(bubble);
  }
  chatBubbles.delete(id);
};

function el(tag, cls) {
  const d = document.createElement(tag);
  d.className = cls;
  return d;
}

function getSelectionText() {
  const sel = window.getSelection();
  return sel && sel.toString().trim() ? sel.toString().trim() : "";
}

function onDocMouseUp(e) {
  const sel = window.getSelection();
  const text = sel && sel.toString().trim();
  if (!text) { closePop("selectPop"); return; }
  const rect = sel.getRangeAt(0).getBoundingClientRect();
  const pop = $("selectPop");
  pop.hidden = false;
  pop.innerHTML = "";
  const b1 = el("button", ""); b1.textContent = "「引用」并询问 LLM";
  b1.onclick = () => { closePop("selectPop"); setQuote(text); };
  const b2 = el("button", ""); b2.textContent = "网页搜索所选内容";
  b2.onclick = () => { closePop("selectPop"); lookupTerm(text); };
  pop.appendChild(b1);
  pop.appendChild(b2);
  pop.style.left = Math.min(rect.left, innerWidth - 180) + "px";
  pop.style.top = rect.bottom + 8 + "px";
}

function onDocDblClick(e) {
  const text = getSelectionText();
  if (!text) return;
  lookupTerm(text);
}

async function lookupTerm(term) {
  const pop = $("termPop");
  pop.hidden = false;
  pop.innerHTML = "";
  const t = el("div", "t-title"); t.textContent = term; pop.appendChild(t);
  const body = el("div", ""); body.textContent = "查询中…"; pop.appendChild(body);
  const pos = $("editor").getBoundingClientRect();
  pop.style.left = Math.min(pos.left + 20, innerWidth - 460) + "px";
  pop.style.top = (pos.top + 60) + "px";
  try {
    const r = await api.lookup_term(term);
    body.textContent = r.ok ? (r.summary || "(无结果)") : r.error;
    const s = el("div", "t-source"); s.textContent = "来源：" + (r.ok ? r.source : "-"); pop.appendChild(s);
  } catch (e) {
    body.textContent = "异常：" + e;
  }
  const h = (ev) => { if (!pop.contains(ev.target)) { pop.hidden = true; document.removeEventListener("mousedown", h); } };
  document.addEventListener("mousedown", h);
}

function closePops(event) {
  if (!event.target.closest(".select-pop")) closePop("selectPop");
  if (!event.target.closest(".term-pop")) closePop("termPop");
}

function closePop(id) { $(id).hidden = true; }

window._loadTask = loadTask;

async function openSkills() {
  const r = await api.list_skills();
  currentSkills = r.skills || [];
  const sel = $("skillSelect");
  sel.innerHTML = "";
  for (const s of currentSkills) {
    const o = document.createElement("option");
    o.value = s.name; o.textContent = s.name;
    sel.appendChild(o);
  }
  if (currentSkills.length) {
    sel.value = currentSkills[0].name;
    $("skillName").value = currentSkills[0].name;
    $("skillContent").value = currentSkills[0].content;
  }
  $("skillsModal").hidden = false;
}

async function saveSkill() {
  const name = $("skillName").value.trim();
  if (!name) { $("skillMsg").textContent = "请填名称"; return; }
  const r = await api.save_skill(name, $("skillContent").value);
  $("skillMsg").textContent = r.ok ? "已保存" : ("失败：" + r.error);
  if (r.ok) await openSkills();
}

async function deleteSkill() {
  const name = $("skillName").value.trim();
  if (!name) return;
  await api.delete_skill(name);
  $("skillContent").value = "";
  await openSkills();
}

async function openTasks() {
  const r = await api.list_tasks();
  const list = $("taskList");
  list.innerHTML = "";
  const tasks = r.tasks || [];
  if (!tasks.length) list.innerHTML = '<div class="msg">暂无历史任务</div>';
  for (const t of tasks) {
    const d = el("div", "task-item");
    const id = el("div", "t-id"); id.textContent = t.title || t.id;
    const sub = el("div", "t-sub");
    sub.textContent = t.id + " · " + new Date(t.mtime * 1000).toLocaleString();
    d.appendChild(id); d.appendChild(sub);
    if (t.has_doc) d.onclick = () => loadTask(t.id);
    const remove = el("button", "task-delete");
    remove.textContent = "删除";
    remove.onclick = async (event) => {
      event.stopPropagation();
      if (!window.confirm("删除任务及其笔记、截图和对话？此操作无法撤销。")) return;
      if (!await flushDraft()) return;
      const result = await api.delete_task(t.id);
      if (!result.ok) {
        stateEl.textContent = "删除失败：" + result.error;
        return;
      }
      if (currentTaskId === t.id) await newParse();
      await openTasks();
    };
    d.appendChild(remove);
    list.appendChild(d);
  }
  $("tasksModal").hidden = false;
}

async function loadTask(id) {
  if (!await flushDraft()) return;
  const r = await api.load_task(id);
  if (!r.ok) {
    stateEl.textContent = "打开任务失败：" + r.error;
    stateEl.style.color = "red";
    return;
  }
  currentUrl = r.url || "";
  currentTaskId = id;
  clearQuote();
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  processingEl.hidden = true;
  $("docTitle").textContent = r.title || id;
  $("meta").textContent = "已载入历史任务";
  documentView.setImageDir(r.taskdir || "");
  setMarkdown(mdForDisplay(r.doc));
  scheduleHighlights();
  setTimeout(fixImages, 400);
  refreshStar();
  setTimeout(renderMermaids, 700);
  showConversation(r.history || []);
  $("tasksModal").hidden = true;
}

function showConversation(hist) {
  chatBubbles.clear();
  chatLog.innerHTML = "";
  if (hist.length) {
    ensureChatLog();
    for (const m of hist) docChatPush(m.role === "user" ? "user" : "ai", m.content);
  } else {
    chatLog.style.display = "flex";
    chatLog.style.alignItems = "center";
    chatLog.style.justifyContent = "center";
    chatLog.innerHTML = '<span class="chat-empty">今天想要学些什么</span>';
  }
}

async function openFavorites() {
  const r = await api.list_favorites();
  const list = $("favList");
  list.innerHTML = "";
  const favs = r.favorites || [];
  if (!favs.length) list.innerHTML = '<div class="msg">暂无收藏</div>';
  for (const f of favs) {
    const d = el("div", "task-item");
    const id = el("div", "t-id"); id.textContent = f.title || f.id;
    const sub = el("div", "t-sub"); sub.textContent = f.id;
    d.appendChild(id); d.appendChild(sub);
    d.onclick = () => loadTask(f.id);
    list.appendChild(d);
  }
  $("favsModal").hidden = false;
}

async function refreshStar() {
  const id = currentTaskId;
  if (!id) { $("favDocBtn").textContent = "☆"; return; }
  try {
    const r = await api.list_favorites();
    const fav = (r.favorites || []).some((f) => f.id === id);
    $("favDocBtn").textContent = fav ? "★" : "☆";
  } catch (e) { /* ignore */ }
}

async function toggleCurrentFav() {
  const id = currentTaskId;
  if (!id) return;
  const r = await api.toggle_favorite(id, $("docTitle").textContent);
  if (r.ok) $("favDocBtn").textContent = r.favorited ? "★" : "☆";
}

async function openHistory() {
  const r = await api.list_histories();
  const list = $("histList");
  list.innerHTML = "";
  const items = r.histories || [];
  if (!items.length) list.innerHTML = '<div class="msg">暂无历史对话</div>';
  for (const h of items) {
    const d = el("div", "task-item");
    const id = el("div", "t-id"); id.textContent = h.title || h.id;
    const sub = el("div", "t-sub");
    sub.textContent = h.id + " · " + (h.count || 0) + " 条 · " + new Date(h.mtime * 1000).toLocaleString();
    d.appendChild(id); d.appendChild(sub);
    d.onclick = () => loadHistory(h.id);
    list.appendChild(d);
  }
  $("histModal").hidden = false;
}

async function loadHistory(tid) {
  if (!await flushDraft()) return;
  const r = await api.load_history(tid);
  if (!r.ok) return;
  currentUrl = r.url || "";
  currentTaskId = tid;
  clearQuote();
  if (r.doc) {
    $("welcome").hidden = true;
    $("workspace").hidden = false;
    processingEl.hidden = true;
    $("docTitle").textContent = r.title || tid;
    $("meta").textContent = "已载入历史任务";
    documentView.setImageDir(r.taskdir || "");
    setMarkdown(mdForDisplay(r.doc));
    scheduleHighlights();
    setTimeout(fixImages, 400);
    refreshStar();
    setTimeout(renderMermaids, 700);
  } else {
    currentTaskId = "";
    documentView.setImageDir("");
    $("workspace").hidden = true;
    $("welcome").hidden = false;
  }
  showConversation(r.history || []);
  $("histModal").hidden = true;
}

async function saveSettings() {
  await api.save_config(readSettings());
  $("setMsg").textContent = "已保存";
}

async function testConnection() {
  $("setMsg").textContent = "检验中…";
  const r = await api.test_connection(readSettings());
  $("setMsg").textContent = r.ok ? "连接成功：" + r.reply : "失败：" + r.error;
}

let initializationStarted = false;
function startWhenReady() {
  if (initializationStarted || typeof window.pywebview?.api?.load_config !== "function") return;
  initializationStarted = true;
  init().catch((error) => {
    const message = "界面初始化失败：" + (error?.message || String(error));
    $("welcomeError").textContent = message;
    $("welcomeError").hidden = false;
    stateEl.textContent = message;
    stateEl.style.color = "red";
    window.__err = message;
  });
}

window.addEventListener("pywebviewready", startWhenReady);
startWhenReady();
