export function escapeAttribute(value) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;")
    .replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export const SAFE_PRINT_URI = /^(?:(?:https?|mailto|file):|\/|\.\.?\/|[^:/?#][^:]*$)/i;
