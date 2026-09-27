import { highlightMarkdown, SAFE_PRINT_URI } from "./render_utils.mjs";
import { renderDiagram } from "./mermaid_renderer.mjs";
import { createEditorDiagrams } from "./editor_diagrams.mjs";

export function createDocumentView(getMarkdown, chatLog, {setDiagramDecorations = () => {}} = {}) {
const $ = (id) => document.getElementById(id);
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
  const taskId = imgDir.split(/[\\/]/).filter(Boolean).pop();
  return taskId ? window.location.origin + "/task-images/" + encodeURIComponent(taskId) : "";
}

function mdForDisplay(md) {
  const b = absBase();
  return b ? (md || "").replace(/\]\(images\//g, "](" + b + "/images/") : (md || "");
}

function mdForStorage(md) {
  const b = absBase();
  return b ? (md || "").split(b + "/images/").join("images/") : (md || "");
}

const mmdLayer = $("mmdLayer");
const diagrams = createEditorDiagrams($("editor"), mmdLayer, renderDiagram, setDiagramDecorations);
const renderMermaids = diagrams.render;
const scheduleMermaid = diagrams.schedule;

async function renderMessageMermaid(bubble) {
  const blocks = [...bubble.querySelectorAll("pre code.language-mermaid")];
  if (!blocks.length) return;
  for (const block of blocks) {
    const code = block.textContent;
    const result = await renderDiagram(code);
    if (!bubble.isConnected || block.textContent !== code || !block.isConnected) continue;
    if (result.svg) {
      const diagram = document.createElement("div");
      diagram.className = "chat-mmd";
      diagram.innerHTML = result.svg;
      block.closest("pre").replaceWith(diagram);
    } else block.closest("pre").setAttribute("data-mermaid-error", result.error);
  }
  chatLog.scrollTop = chatLog.scrollHeight;
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
    throw new Error("文档渲染组件未加载，请重新打开软件后重试");
  }
  let html = window.DOMPurify.sanitize(window.marked.parse(md, { breaks: true, gfm: true }),
    { USE_PROFILES: { html: true }, ALLOWED_URI_REGEXP: SAFE_PRINT_URI });
  const blocks = [...html.matchAll(MMD_BLOCK_RE)];
  if (blocks.length) {
    for (let i = 0; i < blocks.length; i++) {
      const {svg} = await renderDiagram(decodeEntities(blocks[i][1]));
      html = html.replace(blocks[i][0], () => (svg ? '<div class="print-mmd">' + svg + "</div>" :
        blocks[i][0] + '<p class="diagram-error">图表无法显示，原文已保留。</p>'));
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

function renderHighlights() {
  renderEditorMath();
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
      diagrams.clear();
      mathLayer.innerHTML = "";
    },
    scheduleHighlights, scheduleMermaid, renderHighlights, renderMermaids,
    renderMessageMermaid, buildPrintDoc, fixImages, mdForDisplay, mdForStorage,
  };
}
