import test from "node:test";
import assert from "node:assert/strict";
import { samples } from "../app/web/samples.mjs";

test("homepage samples have distinct, usable Markdown documents", () => {
  assert.equal(samples.length, 3);
  assert.equal(new Set(samples.map((sample) => sample.title)).size, samples.length);
  for (const sample of samples) {
    assert.ok(sample.category && sample.preview);
    assert.ok(sample.markdown.startsWith(`# ${sample.title}\n`));
    assert.ok(sample.markdown.includes("内置演示文档"));
    assert.ok(sample.markdown.length > 250);
    assert.ok(!sample.markdown.includes("选中这句话向右侧助手提问"));
  }
  assert.ok(samples.some((sample) => sample.markdown.includes("```mermaid")));
  assert.ok(samples.some((sample) => sample.markdown.includes("$$")));
});
