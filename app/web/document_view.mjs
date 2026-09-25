import { highlightMarkdown, SAFE_PRINT_URI } from "./render_utils.mjs";

export function createDocumentView(getMarkdown, chatLog) {
const $ = (id) => document.getElementById(id);
const hlLayer = $("hlLayer");
const mathLayer = $("mathLayer");
let imgDir = "";

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
    const m = await import("mermaid");
    mermaidLib = m.default || m;
    mermaidLib.initialize({ startOnLoad: false, securityLevel: "strict" });
  }
  return mermaidLib;
}

async function renderMessageMermaid(bubble) {
  const blocks = [...bubble.querySelectorAll("pre code.language-mermaid")];
  if (!blocks.length) return;
  let lib;
  try { lib = await ensureMermaid(); } catch (e) { return; }
  for (const [index, block] of blocks.entries()) {
    try {
      const svg = (await lib.render("chat_mmd_" + Date.now() + "_" + index, block.textContent)).svg;
      const diagram = document.createElement("div");
      diagram.className = "chat-mmd";
      diagram.innerHTML = window.DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true, svgFilters: true } });
      block.closest("pre").replaceWith(diagram);
    } catch (e) { /* preserve source on invalid diagram */ }
  }
  chatLog.scrollTop = chatLog.scrollHeight;
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
  md = highlightMarkdown(md);
  if (!window.marked || !window.DOMPurify) {
    root.textContent = md;
    return;
  }
  let html = window.DOMPurify.sanitize(window.marked.parse(md, { breaks: true, gfm: true }),
    { USE_PROFILES: { html: true }, ALLOWED_URI_REGEXP: SAFE_PRINT_URI });
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
  renderEditorMath();
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

function renderEditorMath() {
  mathLayer.innerHTML = "";
  if (!window.katex) return;
  const editorEl = $("editor");
  if (!editorEl || editorEl.closest("[hidden]")) return;
  const base = document.querySelector(".center").getBoundingClientRect();
  const walker = document.createTreeWalker(editorEl, NodeFilter.SHOW_TEXT);
  const re = /\$\$([^$\n]+)\$\$|\$([^$\n]+)\$/g;
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement.closest("pre, code")) continue;
    re.lastIndex = 0;
    let match;
    while ((match = re.exec(node.data || ""))) {
      const range = document.createRange();
      range.setStart(node, match.index);
      range.setEnd(node, match.index + match[0].length);
      const rect = range.getBoundingClientRect();
      if (!rect.width) continue;
      const item = document.createElement("div");
      item.className = "math-item";
      item.style.left = (rect.left - base.left) + "px";
      item.style.top = (rect.top - base.top) + "px";
      item.style.minWidth = rect.width + "px";
      item.style.minHeight = rect.height + "px";
      item.innerHTML = window.katex.renderToString(match[1] || match[2],
        { displayMode: false, throwOnError: false, trust: false });
      mathLayer.appendChild(item);
    }
  }
}

  return {
    setImageDir(dir) { imgDir = dir || ""; },
    clearLayers() {
      hlLayer.innerHTML = "";
      mmdLayer.innerHTML = "";
      mathLayer.innerHTML = "";
    },
    scheduleHighlights, scheduleMermaid, renderHighlights, renderMermaids,
    renderMessageMermaid, buildPrintDoc, fixImages, mdForDisplay,
  };
}
