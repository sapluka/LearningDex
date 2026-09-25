export function escapeAttribute(value) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;")
    .replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export const SAFE_PRINT_URI = /^(?:(?:https?|mailto|file):|\/|\.\.?\/|[^:/?#][^:]*$)/i;

export function restoreMath(markdown) {
  return markdown.split(/(^```[\s\S]*?^```)/gm).map((part, index) => {
    if (index % 2) return part;
    return part.replace(/\$\$[\s\S]*?\$\$|\$[^\n$]*\$/g,
      formula => formula.replace(/\\([_*{}\[\]])/g, "$1"));
  }).join("");
}
