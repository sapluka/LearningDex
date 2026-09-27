let sequence = 0;

export function createMermaidRenderer({
  load = () => import("mermaid"),
  document = globalThis.document,
  sanitize = (svg) => globalThis.DOMPurify.sanitize(svg, {
    USE_PROFILES: { html: true, svg: true, svgFilters: true }, ADD_TAGS: ["foreignObject"],
    HTML_INTEGRATION_POINTS: { foreignobject: true },
  }),
} = {}) {
  let library;
  const cache = new Map();

  async function compile(code) {
    let host;
    try {
      library ||= load().then((module) => {
        const mermaid = module.default || module;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral",
          fontFamily: "Segoe UI, Microsoft YaHei, sans-serif" });
        return mermaid;
      });
      const mermaid = await library;
      if (!await mermaid.parse(code, { suppressErrors: true })) throw new Error("图表语法有误");
      host = document.createElement("div");
      host.className = "mermaid-scratch";
      host.setAttribute("aria-hidden", "true");
      Object.assign(host.style, { position: "fixed", left: "-100000px", top: "0",
        width: "1000px", visibility: "hidden", pointerEvents: "none" });
      document.body.appendChild(host);
      const result = await mermaid.render("ld_mermaid_" + ++sequence, code, host);
      const svg = sanitize(result.svg);
      const template = document.createElement("template");
      template.innerHTML = svg;
      const element = template.content.querySelector("svg");
      const viewBox = element?.getAttribute("viewBox")?.trim().split(/[\s,]+/).map(Number);
      if (!element || !viewBox || !(viewBox[2] > 0 && viewBox[3] > 0)) throw new Error("图表尺寸无效");
      return { svg, width: viewBox[2], height: viewBox[3], error: "" };
    } catch (error) {
      return { svg: "", error: error?.message || String(error) };
    } finally {
      host?.remove();
    }
  }

  return (code) => {
    if (!cache.has(code)) {
      cache.set(code, compile(code));
      if (cache.size > 64) cache.delete(cache.keys().next().value);
    }
    return cache.get(code);
  };
}

export const renderDiagram = createMermaidRenderer();
