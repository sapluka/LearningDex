import { Editor, rootCtx, editorViewCtx, parserCtx, serializerCtx } from "https://esm.sh/@milkdown/core@7.22.1";
import { commonmark } from "https://esm.sh/@milkdown/preset-commonmark@7.22.1";
import { gfm } from "https://esm.sh/@milkdown/preset-gfm@7.22.1";
import { nord } from "https://esm.sh/@milkdown/theme-nord@7.22.1";
import { history } from "https://esm.sh/@milkdown/plugin-history@7.22.1";
import { math } from "https://esm.sh/@milkdown/plugin-math@7";
import { samples } from "./samples.mjs";

let api = null;
let editor = null;
let currentUrl = "";
let currentTaskId = "";
const $ = (id) => document.getElementById(id);
const stateEl = $("state");
const chatLog = $("chatLog");
const chatBubbles = new Map();
let nextChatId = 0;
const hlLayer = $("hlLayer");
let currentSkills = [];
let imgDir = "";
window.__setStatus = (t) => { if (stateEl) stateEl.textContent = t; };

function setMarkdown(md) {
  md = (md || "").replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g,
    (_, alt, src) => '<img src="' + src + '" alt="' + alt + '">');
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
window._renderMermaids = renderMermaids;
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
    .use(gfm)
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
  renderSamples();
  $("startBtn").onclick = startParse;
  $("url").addEventListener("keydown", (e) => { if (e.key === "Enter") startParse(); });
  $("chatSendBtn").onclick = sendChat;
  $("chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
  $("pdfBtn").onclick = async () => {
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
  $("newParseBtn").onclick = newParse;
  $("historyBtn").onclick = openHistory;
  $("histClose").onclick = () => ($("histModal").hidden = true);
  document.querySelectorAll(".toolbar .tb").forEach((b) => {
    b.onclick = () => wrapSelection(b.dataset.wrap);
  });
  $("editor").addEventListener("mouseup", onDocMouseUp);
  $("editor").addEventListener("dblclick", onDocDblClick);
  $("editor").addEventListener("scroll", scheduleHighlights);
  $("editor").addEventListener("scroll", scheduleMermaid);
  $("editor").addEventListener("input", scheduleHighlights);
  window.addEventListener("resize", scheduleHighlights);
  window.addEventListener("resize", scheduleMermaid);
  document.addEventListener("mousedown", closePops);
}

function bind() {}

async function newParse() {
  await api.reset_context();
  currentUrl = "";
  currentTaskId = "";
  chatBubbles.clear();
  imgDir = "";
  $("workspace").hidden = true;
  $("welcome").hidden = false;
  $("url").value = "";
  chatLog.style.display = "flex";
  chatLog.style.alignItems = "center";
  chatLog.style.justifyContent = "center";
  chatLog.innerHTML = '<span class="chat-empty">今天想要学些什么</span>';
  hlLayer.innerHTML = "";
  mmdLayer.innerHTML = "";
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
  await api.reset_context(sample.markdown);
  currentUrl = "";
  currentTaskId = "";
  chatBubbles.clear();
  imgDir = "";
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  $("docTitle").textContent = sample.title;
  $("meta").textContent = "内置演示 · 可编辑、提问、导出";
  stateEl.textContent = "示例文档";
  stateEl.style.color = "#666";
  mmdLayer.innerHTML = "";
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
  if (!url) { stateEl.textContent = "请先粘贴视频链接"; return; }
  currentUrl = url;
  currentTaskId = "";
  chatBubbles.clear();
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
    imgDir = r.taskdir || "";
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

async function sendChat() {
  const q = $("chatInput").value.trim();
  if (!q) return;
  $("chatInput").value = "";
  const id = beginReply(q);
  try {
    if (!$("workspace").hidden) await api.update_doc(getMarkdown());
    await api.chat(q, id);
  } catch (e) {
    window.__chatChunk(id, "异常：" + e);
    window.__chatDone(id);
  }
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
  if (window.marked) {
    b.innerHTML = window.marked.parse(raw, { breaks: true, gfm: true });
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
  else renderBubble(b);
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
  if (bubble) renderBubble(bubble);
  chatBubbles.delete(id);
};

let hlScheduled = false;
function scheduleHighlights() {
  if (hlScheduled) return;
  hlScheduled = true;
  requestAnimationFrame(() => { hlScheduled = false; renderHighlights(); });
}

function fixImages() {
  if (!imgDir) return;
  const base = absBase();
  document.querySelectorAll("#editor img").forEach((im) => {
    const s = im.getAttribute("src") || "";
    if (s.startsWith("images/")) im.setAttribute("src", base + "/" + s);
  });
}

function absBase() {
  return imgDir ? "file:///" + imgDir.replace(/\\/g, "/").replace(/^\/+/, "") : "";
}

function mdForDisplay(md) {
  const b = absBase();
  return b ? (md || "").replace(/\]\(images\//g, "](" + b + "/images/") : (md || "");
}

let mermaidLib = null;
const mmdLayer = $("mmdLayer");
const mmdCache = {};
async function ensureMermaid() {
  if (!mermaidLib) {
    const m = await import("https://esm.sh/mermaid@10");
    mermaidLib = m.default || m;
    mermaidLib.initialize({ startOnLoad: false, securityLevel: "loose" });
  }
  return mermaidLib;
}

async function renderMermaids() {
  mmdLayer.innerHTML = "";
  const editorEl = $("editor");
  if (!editorEl || editorEl.closest("[hidden]")) return;
  const pres = [];
  editorEl.querySelectorAll("pre").forEach((p) => {
    if (p.getAttribute("data-language") === "mermaid") pres.push(p);
  });
  if (!pres.length) return;
  let lib;
  try { lib = await ensureMermaid(); } catch (e) { return; }
  const base = document.querySelector(".center").getBoundingClientRect();
  for (let i = 0; i < pres.length; i++) {
    const code = pres[i].querySelector("code").textContent;
    let svg = mmdCache[code];
    if (!svg) {
      try { svg = (await lib.render("mmd_" + Date.now() + "_" + i, code)).svg; mmdCache[code] = svg; }
      catch (e) { continue; }
    }
    const r = pres[i].getBoundingClientRect();
    const d = document.createElement("div");
    d.className = "mmd-item";
    d.style.left = (r.left - base.left) + "px";
    d.style.top = (r.top - base.top) + "px";
    d.style.width = r.width + "px";
    d.style.minHeight = r.height + "px";
    d.innerHTML = svg;
    mmdLayer.appendChild(d);
  }
}

let mmdScheduled = false;
function scheduleMermaid() {
  if (mmdScheduled) return;
  mmdScheduled = true;
  requestAnimationFrame(() => { mmdScheduled = false; renderMermaids(); });
}

const MMD_BLOCK_RE = /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g;

function decodeEntities(s) {
  return s.replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
}

async function buildPrintDoc() {
  const root = $("printRoot");
  let md = mdForDisplay(getMarkdown());
  md = md.replace(/\\==/g, "==");
  md = md.replace(/==([^=\n]+)==/g, "<mark>$1</mark>");
  let html = window.marked ? window.marked.parse(md, { breaks: true, gfm: true }) : md;
  const blocks = [...html.matchAll(MMD_BLOCK_RE)];
  if (blocks.length) {
    let lib = null;
    try { lib = await ensureMermaid(); } catch (e) { lib = null; }
    for (let i = 0; i < blocks.length; i++) {
      let svg = "";
      if (lib) {
        try { svg = (await lib.render("pmmd_" + Date.now() + "_" + i, decodeEntities(blocks[i][1]))).svg; }
        catch (e) { svg = ""; }
      }
      html = html.replace(blocks[i][0], () => (svg ? '<div class="print-mmd">' + svg + "</div>" : blocks[i][0]));
    }
  }
  root.innerHTML = html;
  if (window.renderMathInElement) {
    try {
      window.renderMathInElement(root, { delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
      ] });
    } catch (e) { /* ignore */ }
  }
}

window._buildPrintDoc = buildPrintDoc;

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

function renderHighlights() {  hlLayer.innerHTML = "";
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

async function askSelection(selection, question) {
  const id = beginReply("引用：" + selection.slice(0, 60) + (selection.length > 60 ? "…" : ""));
  try {
    await api.update_doc(getMarkdown());
    await api.ask_selection(selection, question, id);
  } catch (e) {
    window.__chatChunk(id, "异常：" + e);
    window.__chatDone(id);
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
  currentUrl = r.url || "";
  currentTaskId = id;
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  $("docTitle").textContent = id;
  $("meta").textContent = "已载入历史任务";
  imgDir = r.taskdir || "";
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
  currentUrl = r.url || "";
  currentTaskId = tid;
  if (r.doc) {
    $("welcome").hidden = true;
    $("workspace").hidden = false;
    $("docTitle").textContent = tid;
    $("meta").textContent = "已载入历史任务";
    imgDir = r.taskdir || "";
    setMarkdown(mdForDisplay(r.doc));
    scheduleHighlights();
    setTimeout(fixImages, 400);
    refreshStar();
    setTimeout(renderMermaids, 700);
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

window.addEventListener("pywebviewready", init);
