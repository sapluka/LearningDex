export function escapeAttribute(value) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;")
    .replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function mapProse(markdown, transform) {
  return (markdown || "").split(/(^```[\s\S]*?^```|^~~~[\s\S]*?^~~~)/gm).map((part, index) => {
    return index % 2 ? part : transform(part);
  }).join("");
}

// Milkdown 7.22.1 drops images whose parsed title is null. A blank title keeps
// the image node alive; it is removed again when serializing the document.
export function prepareEditorImages(markdown) {
  return mapProse(markdown, part => part.replace(/!\[([^\]]*)\]\((<[^>]+>|[^)\n]+)\)/g,
    (full, alt, value) => {
      if (/\s+["'][^"']+["']\s*$/.test(value)) return full;
      const target = value.trim().replace(/\s+["']["']$/, "");
      const source = /\s/.test(target) && !target.startsWith("<") ? `<${target}>` : target;
      return `![${alt}](${source} " ")`;
    }));
}

export function restoreEditorImages(markdown) {
  return mapProse(markdown, part => part.replace(/(!\[[^\]]*\]\([^\n)]*?) " "\)/g, "$1)"));
}

export const SAFE_PRINT_URI = /^(?:(?:https?|mailto|file):|\/|\.\.?\/|[^:/?#][^:]*$)/i;

export function restoreMath(markdown) {
  return markdown.split(/(^```[\s\S]*?^```)/gm).map((part, index) => {
    if (index % 2) return part;
    return part.replace(/\$\$[\s\S]*?\$\$|\$[^\n$]*\$/g,
      formula => formula.replace(/\\([_*{}\[\]])/g, "$1"));
  }).join("");
}

export function highlightMarkdown(markdown) {
  return markdown.split(/(^```[\s\S]*?^```)/gm).map((part, index) => {
    if (index % 2) return part;
    return part.replace(/==([^=\n]+)==/g, "<mark>$1</mark>");
  }).join("");
}
