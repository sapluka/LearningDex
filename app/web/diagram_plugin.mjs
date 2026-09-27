import { Plugin, PluginKey, TextSelection } from "@milkdown/prose/state";
import { Decoration, DecorationSet } from "@milkdown/prose/view";
import { $prose } from "@milkdown/utils";

export const diagramKey = new PluginKey("diagram-preview");
export const diagramPlugin = $prose(() => new Plugin({
  key: diagramKey,
  state: {
    init: () => DecorationSet.empty,
    apply(transaction, previous) {
      const next = transaction.getMeta(diagramKey);
      if (next) return next;
      const mapped = previous.map(transaction.mapping, transaction.doc);
      if (!transaction.docChanged) return mapped;
      return DecorationSet.create(transaction.doc, mapped.find().filter(decoration => {
        const node = transaction.doc.nodeAt(decoration.from);
        return node?.type.name === "code_block" && node.textContent === decoration.spec.source;
      }));
    },
  },
  props: {
    decorations: state => diagramKey.getState(state),
    handleDOMEvents: {
      mousedown(view, event) {
        if (event.button !== 0) return false;
        const pre = event.target.closest?.("pre[data-mermaid-preview]");
        if (!pre || !view.dom.contains(pre)) return false;
        const position = view.posAtDOM(pre.querySelector("code"), 0);
        view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, position)));
        view.focus();
        event.preventDefault();
        return true;
      },
    },
  },
}));

export function setDiagramDecorations(view, entries) {
  const decorations = entries.flatMap(({pre, code, height, error}) => {
    if (!view.dom.contains(pre)) return [];
    const position = view.state.doc.resolve(view.posAtDOM(pre.querySelector("code"), 0));
    if (position.parent.type.name !== "code_block" || position.parent.textContent !== code) return [];
    const from = position.before();
    const attrs = error ? {"data-mermaid-error": error} :
      {"data-mermaid-preview": "", style: `height:${height}px`};
    return [Decoration.node(from, from + position.parent.nodeSize, attrs, {source: code})];
  });
  const signature = items => JSON.stringify(items.map(item => [item.from, item.to, item.type.attrs, item.spec.source]));
  if (signature(decorations) === signature(diagramKey.getState(view.state).find())) return;
  view.dispatch(view.state.tr.setMeta(diagramKey, DecorationSet.create(view.state.doc, decorations))
    .setMeta("addToHistory", false));
}
