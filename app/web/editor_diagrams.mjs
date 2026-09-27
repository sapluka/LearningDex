import { renderDiagram } from "./mermaid_renderer.mjs";

export function createEditorDiagrams(editor, layer, compile = renderDiagram, setDecorations = () => {}) {
  let revision = 0;
  let scheduled = false;

  function clear() {
    revision++;
    layer.replaceChildren();
    setDecorations([]);
  }

  function isEditing(pre) {
    return editor.contains(document.activeElement) && pre.contains(window.getSelection()?.anchorNode);
  }

  async function render() {
    const current = ++revision;
    if (editor.closest("[hidden]")) { clear(); return; }
    const blocks = [...editor.querySelectorAll('pre[data-language="mermaid"]')].map(pre =>
      ({pre, code: pre.querySelector("code")?.textContent || ""}));
    const results = await Promise.all(blocks.map(async block =>
      ({...block, result: await compile(block.code)})));
    if (current !== revision || editor.closest("[hidden]")) return;
    const previews = [];
    const decorations = [];
    for (const {pre, code, result} of results) {
      if (!editor.contains(pre) || pre.querySelector("code")?.textContent !== code) continue;
      if (isEditing(pre)) continue;
      if (!result.svg) { decorations.push({pre, code, error: result.error}); continue; }
      const width = pre.getBoundingClientRect().width;
      decorations.push({pre, code, height: Math.ceil(result.height * Math.min(1, width / result.width))});
      previews.push({pre, result});
    }
    setDecorations(decorations);
    const base = layer.getBoundingClientRect();
    const fragment = document.createDocumentFragment();
    for (const {pre, result} of previews) {
      const rect = pre.getBoundingClientRect();
      const item = document.createElement("div");
      item.className = "mmd-item";
      Object.assign(item.style, {left: `${rect.left - base.left}px`, top: `${rect.top - base.top}px`,
        width: `${rect.width}px`, height: `${rect.height}px`});
      item.innerHTML = result.svg;
      fragment.appendChild(item);
    }
    layer.replaceChildren(fragment);
  }

  function schedule() {
    revision++;
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; render(); });
  }

  new MutationObserver(() => { layer.replaceChildren(); schedule(); })
    .observe(editor, {childList: true, characterData: true, subtree: true});
  document.addEventListener("selectionchange", () => { if (editor.contains(document.activeElement)) schedule(); });
  editor.addEventListener("focusout", schedule);
  return { render, schedule, clear };
}
