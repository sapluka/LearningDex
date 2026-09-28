import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { samples } from "../app/web/samples.mjs";

const expected = new Map([
  ["BV1X7411F744", "纹理映射续讲：重心坐标插值与纹理过滤方法"],
  ["BV1QuYX6XEZ4", "【闪客】Computer Use 是什么？它真的有在看你的屏幕吗？可能和你想的不太一样..."],
  ["BV1CQt365EzW", "提示词工程 [02-Raw/26生成式软件工程/NJU]"],
]);

test("the three bundled video examples have complete notes and local images", () => {
  assert.equal(samples.length, expected.size);
  assert.deepEqual(new Set(samples.map(sample => sample.id)), new Set(expected.keys()));
  for (const sample of samples) {
    assert.equal(sample.title, expected.get(sample.id));
    assert.ok(sample.category && sample.preview);
    assert.equal(sample.markdownPath, `examples/${sample.id}/note.md`);
    const path = fileURLToPath(new URL(`../app/web/${sample.markdownPath}`, import.meta.url));
    const markdown = readFileSync(path, "utf8");
    assert.match(markdown, /^# .+/);
    assert.ok(markdown.length > 2500);
    assert.equal(markdown.includes("SHOT:"), false);
    const images = [...markdown.matchAll(/!\[[^\]]*\]\((images\/[^)]+)\)/g)].map(match => match[1]);
    assert.ok(images.length >= 5);
    assert.ok(images.every(src => existsSync(join(dirname(path), src))));
  }
});
