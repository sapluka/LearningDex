import { NodeSelection, Plugin } from "@milkdown/prose/state";
import { closeHistory } from "@milkdown/prose/history";
import { dropCursor } from "@milkdown/prose/dropcursor";
import { $prose } from "@milkdown/utils";

export function selectedImage(state) {
  const selection = state.selection;
  return selection instanceof NodeSelection && selection.node.type.name === "image" ? selection : null;
}

export function removeSelectedImage(view) {
  if (!selectedImage(view.state)) return false;
  view.dispatch(closeHistory(view.state.tr).deleteSelection().scrollIntoView());
  return true;
}

export function createImagePlugins(onChange) {
  return [
    $prose(() => new Plugin({
      view: () => ({update(view, previous) { if (view.state.doc !== previous.doc) onChange(); }}),
      props: {
        handleClickOn(view, _pos, node, nodePos, event, direct) {
          if (!direct || event.button !== 0 || node.type.name !== "image") return false;
          view.dispatch(view.state.tr.setSelection(NodeSelection.create(view.state.doc, nodePos)));
          view.focus();
          return true;
        },
        handleDOMEvents: {
          mousedown(view, event) {
            const selection = selectedImage(view.state);
            if (event.button === 2 && selection && view.nodeDOM(selection.from) === event.target.closest?.("img")) {
              event.preventDefault();
              return true;
            }
            return false;
          },
          dragstart(view, event) {
            if (event.target.closest?.("img") && selectedImage(view.state)) {
              view.dispatch(closeHistory(view.state.tr));
            }
            return false;
          },
        },
      },
    })),
    $prose(() => dropCursor({color: "#171717", width: 2})),
  ];
}

async function copyImage(view, selection) {
  const {dom, text} = view.serializeForClipboard(selection.content());
  dom.querySelector("img")?.setAttribute("data-learndex-image", "1");
  if (navigator.clipboard?.write && window.ClipboardItem) {
    try {
      await navigator.clipboard.write([new ClipboardItem({
        "text/html": new Blob([dom.innerHTML], {type: "text/html"}),
        "text/plain": new Blob([text || selection.node.attrs.alt || "图片"], {type: "text/plain"}),
      })]);
      return true;
    } catch { /* Clipboard API 不可用时交给编辑器原生复制。 */ }
  }
  if (selectedImage(view.state)?.node !== selection.node) return false;
  return document.execCommand("copy");
}

export function initImageActions({root, menu, getView, onError, closeTextMenu}) {
  let target = null;
  const hide = () => { menu.hidden = true; target = null; };
  root.addEventListener("paste", event => {
    const html = event.clipboardData?.getData("text/html") || "";
    if (!html.includes("data-learndex-image")) return;
    const source = new DOMParser().parseFromString(html, "text/html").querySelector('img[data-learndex-image="1"]');
    if (!source) return;
    const src = source.getAttribute("src") || "";
    if (!/^(https?:|data:image\/(?:png|jpeg|gif|webp);base64,|images\/|\/task-images\/)/i.test(src)) return;
    event.preventDefault();
    event.stopPropagation();
    const view = getView();
    const image = view.state.schema.nodes.image.create({
      src,
      alt: source.getAttribute("alt") || "",
      title: source.getAttribute("title") || null,
    });
    view.dispatch(view.state.tr.replaceSelectionWith(image).scrollIntoView());
  }, true);
  root.addEventListener("contextmenu", event => {
    const view = getView();
    const selection = selectedImage(view.state);
    const image = event.target.closest?.("img");
    if (!image || !selection || view.nodeDOM(selection.from) !== image) return;
    event.preventDefault();
    closeTextMenu();
    target = {doc: view.state.doc, from: selection.from};
    menu.hidden = false;
    menu.style.left = Math.max(8, Math.min(event.clientX, window.innerWidth - menu.offsetWidth - 8)) + "px";
    menu.style.top = Math.max(8, Math.min(event.clientY, window.innerHeight - menu.offsetHeight - 8)) + "px";
  });
  menu.addEventListener("mousedown", event => event.preventDefault());
  menu.addEventListener("click", async event => {
    const action = event.target.closest("button")?.dataset.imageAction;
    if (!action) return;
    const view = getView();
    const selection = selectedImage(view.state);
    if (!target || view.state.doc !== target.doc || selection?.from !== target.from) { hide(); return; }
    const originalDoc = view.state.doc;
    hide();
    view.focus();
    try {
      if (action !== "delete" && !await copyImage(view, selection)) {
        throw new Error("图片复制失败，请重试或使用 Ctrl+C");
      }
      if (action === "cut" || action === "delete") {
        if (view.state.doc !== originalDoc || selectedImage(view.state)?.from !== selection.from) {
          throw new Error("文档或选区已改变，请重新选择图片");
        }
        removeSelectedImage(view);
      }
    } catch (error) { onError(error.message); }
  });
  root.addEventListener("drop", hide);
  root.addEventListener("input", hide);
  root.addEventListener("scroll", hide);
  document.addEventListener("mousedown", event => { if (!menu.contains(event.target)) hide(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape") hide(); });
  window.addEventListener("resize", hide);
  window.addEventListener("blur", hide);
  return {hide};
}
