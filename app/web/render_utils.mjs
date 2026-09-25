export function escapeAttribute(value) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;")
    .replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function inlineImages(markdown) {
  return (markdown || "").replace(/!\[([^\]]*)\]\((<[^>]+>|[^)\n]+)\)/g, (_, alt, source) => {
    const src = source.startsWith("<") ? source.slice(1, -1) : source.trim();
    return '<img src="' + escapeAttribute(src) + '" alt="' + escapeAttribute(alt) + '">';
  });
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
