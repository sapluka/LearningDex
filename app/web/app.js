import { Editor, rootCtx, editorViewCtx, parserCtx, serializerCtx } from "https://esm.sh/@milkdown/core@7.22.1";
import { commonmark } from "https://esm.sh/@milkdown/preset-commonmark@7.22.1";
import { nord } from "https://esm.sh/@milkdown/theme-nord@7.22.1";
import { history } from "https://esm.sh/@milkdown/plugin-history@7.22.1";

let api = null;
let editor = null;
let currentUrl = "";
const $ = (id) => document.getElementById(id);
const stateEl = $("state");
const chatLog = $("chatLog");
const termLayer = $("termLayer");
let docTerms = [];
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

window._setMarkdown = setMarkdown;
window._getMarkdown = getMarkdown;
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
    .create();
  window.editor = editor;
  editor._setMarkdown = setMarkdown;
  editor._getMarkdown = getMarkdown;
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
  $("editor").addEventListener("mouseup", onDocMouseUp);
  $("editor").addEventListener("dblclick", onDocDblClick);
  $("editor").addEventListener("scroll", hideTermBoxes);
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
    hideTermBoxes();
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
  try {
    const r = await api.chat(q);
    docChatPush("ai", r.ok ? r.reply : "错误：" + r.error);
  } catch (e) {
    docChatPush("ai", "异常：" + e);
  }
}

function ensureChatLog() {
  if (chatLog.querySelector(".chat-empty") || chatLog.innerHTML === "") {
    chatLog.style.display = "flex";
    chatLog.innerHTML = "";
  }
}

function docChatPush(kind, text) {
  ensureChatLog();
  const b = el("div", "bub " + (kind === "user" ? "user" : "ai"));
  b.textContent = text;
  chatLog.appendChild(b);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function hideTermBoxes() {
  termLayer.innerHTML = "";
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
  const r = await api.ask_selection(selection, question);
  chatLog.style.display = "flex";
  chatLog.innerHTML = "";
  docChatPush("user", selection.slice(0, 60) + (selection.length > 60 ? "…" : ""));
  docChatPush("ai", r.ok ? r.reply : "错误：" + r.error);
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
  const md = getMarkdown();
  const r = await api.end_study(currentUrl, md);
  const btn = $("endStudyBtn");
  btn.textContent = "已保存：" + (r.ok ? "final.md" : r.error);
  btn.disabled = true;
  setTimeout(() => { btn.textContent = "结束学习"; btn.disabled = false; }, 2500);
}

window.addEventListener("pywebviewready", init);