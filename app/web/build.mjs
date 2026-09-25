import { build } from "esbuild";
import { cpSync, copyFileSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { dirname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const dist = resolve(root, "dist");
if (!dist.startsWith(resolve(root) + sep)) throw new Error("Invalid build output path");
if (existsSync(dist)) rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });

await build({
  entryPoints: [join(root, "app.js")],
  outdir: dist,
  entryNames: "[name]",
  chunkNames: "chunks/[name]-[hash]",
  bundle: true,
  splitting: true,
  format: "esm",
  platform: "browser",
  target: "es2020",
  minify: true,
  logLevel: "info",
});

const assets = [
  ["marked/lib/marked.umd.js", "marked.umd.js"],
  ["dompurify/dist/purify.min.js", "purify.min.js"],
  ["katex/dist/katex.min.js", "katex.min.js"],
  ["katex/dist/contrib/auto-render.min.js", "auto-render.min.js"],
  ["katex/dist/katex.min.css", "katex.min.css"],
];
for (const [source, target] of assets) {
  copyFileSync(join(root, "node_modules", source), join(dist, target));
}
cpSync(join(root, "node_modules/katex/dist/fonts"), join(dist, "fonts"), { recursive: true });
if (!readdirSync(dist).includes("app.js")) throw new Error("Editor bundle missing");
