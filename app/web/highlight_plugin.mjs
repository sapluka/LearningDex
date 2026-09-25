import { $markSchema, $remark } from "@milkdown/utils";
import { remarkStringifyOptionsCtx } from "@milkdown/core";

export function splitHighlights(node) {
  if (!Array.isArray(node.children)) return;
  const children = [];
  for (const child of node.children) {
    if (child.type !== "text" || !child.value?.includes("==")) {
      splitHighlights(child);
      children.push(child);
      continue;
    }
    const value = child.value;
    const pattern = /==([^=\n]+)==/g;
    let start = 0;
    let match;
    while ((match = pattern.exec(value))) {
      if (match.index > start) children.push({ type: "text", value: value.slice(start, match.index) });
      children.push({ type: "highlight", children: [{ type: "text", value: match[1] }] });
      start = pattern.lastIndex;
    }
    if (start < value.length) children.push({ type: "text", value: value.slice(start) });
  }
  node.children = children;
}

const remarkHighlight = $remark("highlight", () => () => splitHighlights);

const highlightSchema = $markSchema("highlight", () => ({
  parseDOM: [{ tag: "mark" }],
  toDOM: () => ["mark", { class: "editor-highlight" }, 0],
  parseMarkdown: {
    match: (node) => node.type === "highlight",
    runner: (state, node, type) => {
      state.openMark(type);
      state.next(node.children);
      state.closeMark(type);
    },
  },
  toMarkdown: {
    match: (mark) => mark.type.name === "highlight",
    runner: (state, mark) => { state.withMark(mark, "highlight"); },
  },
}));

function stringifyHighlight(node, _, state, info) {
  const exit = state.enter("highlight");
  const tracker = state.createTracker(info);
  let value = tracker.move("==");
  value += tracker.move(state.containerPhrasing(node, {
    before: value,
    after: "==",
    ...tracker.current(),
  }));
  value += tracker.move("==");
  exit();
  return value;
}

export function configureHighlight(ctx) {
  ctx.update(remarkStringifyOptionsCtx, (options) => ({
    ...options,
    handlers: { ...options.handlers, highlight: stringifyHighlight },
  }));
}

export const highlightPlugins = [remarkHighlight, highlightSchema];
