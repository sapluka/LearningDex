import { Editor, rootCtx, editorViewCtx, parserCtx, serializerCtx } from "https://esm.sh/@milkdown/core@7.22.1";
import { commonmark } from "https://esm.sh/@milkdown/preset-commonmark@7.22.1";
import { nord } from "https://esm.sh/@milkdown/theme-nord@7.22.1";
import { history } from "https://esm.sh/@milkdown/plugin-history@7.22.1";
import { math } from "https://esm.sh/@milkdown/plugin-math@7";

let api = null;
let editor = null;
let currentUrl = "";
const $ = (id) => document.getElementById(id);
const stateEl = $("state");
const chatLog = $("chatLog");
const termLayer = $("termLayer");
const hlLayer = $("hlLayer");
let docTerms = [];
let annotations = [];
let currentSkills = [];
window.__setStatus = (t) => { if (stateEl) stateEl.textContent = t; };

function setMarkdown(md) {
  editor.action((ctx) => {
    const view = ctx.get(editorViewCtx);
    const parser = ctx.get(parserCtx);
    const doc = parser(md);
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
  return md;
}

function wrapSelection(marker) {
  editor.action((ctx) => {
    const view = ctx.get(editorViewCtx);
    const { from, to } = view.state.selection;
    const text = view.state.doc.textBetween(from, to, "");
    if (!text) return;
    view.dispatch(view.state.tr.insertText(marker + text + marker, from, to));
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
  editor = await Editor.make()
    .config((ctx) => ctx.set(rootCtx, $("editor")))
    .use(nord)
    .use(commonmark)
    .use(history)
    .use(math)
    .create();
  window.editor = editor;
  editor._setMarkdown = setMarkdown;
  editor._getMarkdown = getMarkdown;
  document.querySelectorAll("#editor [contenteditable], #editor .ProseMirror").forEach((e) => {
    e.setAttribute("spellcheck", "false");
    e.setAttribute("autocorrect", "off");
    e.setAttribute("autocapitalize", "off");
  });
  bind();
  $("startBtn").onclick = startParse;
  $("url").addEventListener("keydown", (e) => { if (e.key === "Enter") startParse(); });
  $("chatSendBtn").onclick = sendChat;
  $("chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
  $("endStudyBtn").onclick = endStudy;
  $("githubBtn").onclick = () => openLink("https://github.com");
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
  $("historyBtn").onclick = openHistory;
  $("histClose").onclick = () => ($("histModal").hidden = true);
  document.querySelectorAll(".toolbar .tb").forEach((b) => {
    b.onclick = () => wrapSelection(b.dataset.wrap);
  });
  $("editor").addEventListener("mouseup", onDocMouseUp);
  $("editor").addEventListener("dblclick", onDocDblClick);
  $("editor").addEventListener("scroll", hideTermBoxes);
  $("editor").addEventListener("scroll", scheduleHighlights);
  $("editor").addEventListener("input", scheduleHighlights);
  window.addEventListener("resize", scheduleHighlights);
  document.addEventListener("keydown", (e) => { if (e.key === "Control") showTermBoxes(); });
  document.addEventListener("keyup", (e) => { if (e.key === "Control") hideTermBoxes(); });
  document.addEventListener("mousedown", closePops);
}

function bind() {}

function openLink(url) {
  if (window.open) window.open(url, "_blank");
}

async function startParse() {
  const url = $("url").value.trim();
  if (!url) { stateEl.textContent = "请先粘贴视频链接"; return; }
  currentUrl = url;
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  stateEl.textContent = "处理中：字幕提取 → 转写 → 核验 → 生成文档…";
  stateEl.style.color = "#666";
  try {
    const r = await api.generate_doc(url);
    if (!r.ok) {
      stateEl.textContent = r.error;
      stateEl.style.color = "red";
      return;
    }
    const info = r.info || {};
    $("docTitle").textContent = info.title || "学习文档";
    $("meta").textContent =
      `${info.uploader || ""} ${info.duration ? Math.round(info.duration / 60) + "分钟" : ""}` +
      `${info.transcribe_note ? "（" + info.transcribe_note + "）" : ""}`;
    setMarkdown(r.doc);
    docTerms = r.terms || [];
    annotations = [];
    renderNotes();
    hideTermBoxes();
    scheduleHighlights();
    stateEl.textContent = "完成，可编辑文档";
    stateEl.style.color = "green";
    showChatHint();
  } catch (e) {
    stateEl.textContent = "异常：" + e;
    stateEl.style.color = "red";
  }
}

function showChatHint() {
  chatLog.style.display = "flex";
  chatLog.innerHTML = "";
  const h = el("div", "chat-empty");
  h.textContent = "学习文档已生成，可以开始提问了。";
  chatLog.appendChild(h);
}

async function sendChat() {
  const q = $("chatInput").value.trim();
  if (!q) return;
  $("chatInput").value = "";
  docChatPush("user", q);
  docChatPush("ai", "");
  try {
    await api.chat(q);
  } catch (e) {
    docChatPush("ai", "异常：" + e);
  }
}

function ensureChatLog() {
  const hint = chatLog.querySelector(".chat-empty");
  if (hint) hint.remove();
  chatLog.style.display = "flex";
  chatLog.style.flexDirection = "column";
  chatLog.style.alignItems = "stretch";
  chatLog.style.justifyContent = "flex-start";
}

function docChatPush(kind, text) {
  ensureChatLog();
  const b = el("div", "bub " + (kind === "user" ? "user" : "ai"));
  b.textContent = text;
  chatLog.appendChild(b);
  chatLog.scrollTop = chatLog.scrollHeight;
  return b;
}

window.__chatChunk = (t) => {
  ensureChatLog();
  let last = chatLog.lastElementChild;
  if (!last || !last.classList.contains("ai")) last = docChatPush("ai", "");
  last.textContent += t;
  chatLog.scrollTop = chatLog.scrollHeight;
};
window.__chatDone = () => {};

function hideTermBoxes() {
  termLayer.innerHTML = "";
}

let hlScheduled = false;
function scheduleHighlights() {
  if (hlScheduled) return;
  hlScheduled = true;
  requestAnimationFrame(() => { hlScheduled = false; renderHighlights(); });
}

function drawRect(node, from, to, base, cls) {
  const r = document.createRange();
  try {
    r.setStart(node, from);
    r.setEnd(node, to);
  } catch (e) {
    return;
  }
  for (const rc of r.getClientRects()) {
    const b = document.createElement("div");
    b.className = cls;
    b.style.left = (rc.left - base.left) + "px";
    b.style.top = (rc.top - base.top) + "px";
    b.style.width = rc.width + "px";
    b.style.height = rc.height + "px";
    hlLayer.appendChild(b);
  }
}

function renderHighlights() {
  hlLayer.innerHTML = "";
  const editorEl = $("editor");
  if (!editorEl || editorEl.closest("[hidden]")) return;
  const base = document.querySelector(".center").getBoundingClientRect();
  const walker = document.createTreeWalker(editorEl, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const re = /==([^=]+)==/g;
  for (const node of nodes) {
    const data = node.data || "";
    let m;
    re.lastIndex = 0;
    while ((m = re.exec(data)) !== null) {
      const s = m.index;
      const inner = m[1].length;
      drawRect(node, s, s + 2, base, "hl-mask");
      drawRect(node, s + 2, s + 2 + inner, base, "hl-box");
      drawRect(node, s + 2 + inner, s + 4 + inner, base, "hl-mask");
    }
  }
}

function showTermBoxes() {
  hideTermBoxes();
  if (!docTerms.length) return;
  const editorEl = $("editor");
  const base = document.querySelector(".center").getBoundingClientRect();
  const walker = document.createTreeWalker(editorEl, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const term of docTerms) {
    for (const node of nodes) {
      const data = node.data || "";
      let idx = 0;
      while ((idx = data.indexOf(term, idx)) !== -1) {
        const r = document.createRange();
        r.setStart(node, idx);
        r.setEnd(node, idx + term.length);
        for (const rc of r.getClientRects()) {
          const box = document.createElement("div");
          box.className = "term-box";
          box.style.left = (rc.left - base.left) + "px";
          box.style.top = (rc.top - base.top) + "px";
          box.style.width = rc.width + "px";
          box.style.height = rc.height + "px";
          box.onclick = (ev) => { ev.stopPropagation(); addTerm(term); hideTermBoxes(); };
          termLayer.appendChild(box);
        }
        idx += term.length;
      }
    }
  }
}

function addTerm(term) {
  const pending = $("pending");
  pending.hidden = false;
  const list = $("pendingList");
  if ([...list.children].some((c) => c.dataset.term === term)) return;
  const chip = document.createElement("div");
  chip.className = "chip";
  chip.textContent = term;
  chip.dataset.term = term;
  chip.onclick = async () => {
    chip.classList.add("done");
    const r = await api.explain(term);
    docChatPush("ai", "【" + term + "】" + (r.ok ? r.answer : "错误：" + r.error));
  };
  list.appendChild(chip);
}

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
  b1.onclick = () => { closePop("selectPop"); askSelection(text, ""); };
  const b2 = el("button", ""); b2.textContent = "网页搜索所选内容";
  b2.onclick = () => { closePop("selectPop"); lookupTerm(text); };
  const b3 = el("button", ""); b3.textContent = "添加批注";
  b3.onclick = () => {
    pop.innerHTML = "";
    const inp = document.createElement("input");
    inp.placeholder = "输入批注…";
    inp.style.width = "150px";
    const ok = el("button", ""); ok.textContent = "保存";
    ok.onclick = () => {
      const note = inp.value.trim();
      if (note) { annotations.push({ quote: text, note }); renderNotes(); }
      closePop("selectPop");
    };
    pop.appendChild(inp); pop.appendChild(ok); inp.focus();
  };
  pop.appendChild(b1);
  pop.appendChild(b2);
  pop.appendChild(b3);
  pop.style.left = Math.min(rect.left, innerWidth - 180) + "px";
  pop.style.top = rect.bottom + 8 + "px";
}

function onDocDblClick(e) {
  const text = getSelectionText();
  if (!text) return;
  lookupTerm(text);
}

async function askSelection(selection, question) {
  docChatPush("user", "引用：" + selection.slice(0, 60) + (selection.length > 60 ? "…" : ""));
  try {
    const r = await api.ask_selection(selection, question);
    docChatPush("ai", r.ok ? r.reply : "错误：" + r.error);
  } catch (e) {
    docChatPush("ai", "异常：" + e);
  }
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

function closePops() {
  if (!event.target.closest(".select-pop")) closePop("selectPop");
  if (!event.target.closest(".term-pop")) closePop("termPop");
}

function closePop(id) { $(id).hidden = true; }

function renderNotes() {
  const panel = $("notes");
  const list = $("notesList");
  list.innerHTML = "";
  if (!annotations.length) { panel.hidden = true; return; }
  panel.hidden = false;
  for (const a of annotations) {
    const d = el("div", "note-item");
    const q = el("span", "q");
    q.textContent = "「" + a.quote.slice(0, 20) + (a.quote.length > 20 ? "…" : "") + "」 ";
    d.appendChild(q);
    d.appendChild(document.createTextNode(a.note));
    list.appendChild(d);
  }
}

function buildExportMd() {
  let md = getMarkdown();
  const defs = [];
  annotations.forEach((a, i) => {
    const n = i + 1;
    const idx = md.indexOf(a.quote);
    if (idx >= 0) {
      const at = idx + a.quote.length;
      md = md.slice(0, at) + "[^" + n + "]" + md.slice(at);
    }
    defs.push("[^" + n + "]: " + a.note);
  });
  if (defs.length) md = md.replace(/\s+$/, "") + "\n\n" + defs.join("\n") + "\n";
  return md;
}

window._addNote = (q, n) => { annotations.push({ quote: q, note: n }); renderNotes(); };
window._exportMd = buildExportMd;

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
    const id = el("div", "t-id"); id.textContent = t.id;
    const sub = el("div", "t-sub");
    sub.textContent = (t.has_doc ? "有文档" : "无文档") + " · " + new Date(t.mtime * 1000).toLocaleString();
    d.appendChild(id); d.appendChild(sub);
    if (t.has_doc) d.onclick = () => loadTask(t.id);
    list.appendChild(d);
  }
  $("tasksModal").hidden = false;
}

async function loadTask(id) {
  const r = await api.load_task(id);
  if (!r.ok) return;
  currentUrl = "https://www.bilibili.com/video/" + id;
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  $("docTitle").textContent = id;
  $("meta").textContent = "已载入历史任务";
  setMarkdown(r.doc);
  docTerms = [];
  annotations = [];
  renderNotes();
  hideTermBoxes();
  scheduleHighlights();
  $("tasksModal").hidden = true;
}

function bvidOf(url) {
  const m = /BV[0-9A-Za-z]+/.exec(url || "");
  return m ? m[0] : "";
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

async function toggleCurrentFav() {
  const id = bvidOf(currentUrl);
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
    const id = el("div", "t-id"); id.textContent = h.id;
    const sub = el("div", "t-sub");
    sub.textContent = (h.count || 0) + " 条 · " + new Date(h.mtime * 1000).toLocaleString();
    d.appendChild(id); d.appendChild(sub);
    d.onclick = () => loadHistory(h.id);
    list.appendChild(d);
  }
  $("histModal").hidden = false;
}

async function loadHistory(tid) {
  const r = await api.load_history(tid);
  if (!r.ok) return;
  currentUrl = "https://www.bilibili.com/video/" + tid;
  if (r.doc) {
    $("welcome").hidden = true;
    $("workspace").hidden = false;
    $("docTitle").textContent = tid;
    $("meta").textContent = "已载入历史任务";
    setMarkdown(r.doc);
    scheduleHighlights();
  }
  const hist = r.history || [];
  chatLog.style.display = "flex";
  chatLog.innerHTML = "";
  if (hist.length) {
    ensureChatLog();
    for (const m of hist) docChatPush(m.role === "user" ? "user" : "ai", m.content);
  } else {
    chatLog.style.alignItems = "center";
    chatLog.style.justifyContent = "center";
    chatLog.innerHTML = '<span class="chat-empty">今天想要学些什么</span>';
  }
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

async function endStudy() {
  const md = buildExportMd();
  const r = await api.end_study(currentUrl, md);
  const btn = $("endStudyBtn");
  btn.textContent = "已保存：" + (r.ok ? "final.md" : r.error);
  btn.disabled = true;
  setTimeout(() => { btn.textContent = "结束学习"; btn.disabled = false; }, 2500);
}

window.addEventListener("pywebviewready", init);