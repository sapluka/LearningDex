import test from "node:test";
import assert from "node:assert/strict";
import { escapeAttribute, highlightMarkdown, inlineImages, restoreMath, SAFE_PRINT_URI } from "../app/web/render_utils.mjs";

test("image attributes cannot inject event handlers", () => {
  const escaped = escapeAttribute('file:///a.jpg" onerror="alert(1)<x>&');
  assert.equal(escaped, 'file:///a.jpg&quot; onerror=&quot;alert(1)&lt;x&gt;&amp;');
  assert.ok(!escaped.includes('"'));
  assert.ok(!escaped.includes('<'));
});

test("Markdown images with spaces remain visible and safe in the editor", () => {
  assert.equal(inlineImages('![图解](<images/截图 1.jpg>)'),
    '<img src="images/截图 1.jpg" alt="图解">');
  assert.equal(inlineImages('![a](images/my shot.jpg)'),
    '<img src="images/my shot.jpg" alt="a">');
  assert.equal(inlineImages('![a](images/x.jpg" onerror="bad)'),
    '<img src="images/x.jpg&quot; onerror=&quot;bad" alt="a">');
});

test("print links accept local images without accepting script URLs", () => {
  for (const uri of ["file:///D:/notes/img.jpg", "images/shot.jpg", "https://example.org/a.png"])
    assert.ok(SAFE_PRINT_URI.test(uri), uri);
  for (const uri of ["javascript:alert(1)", " javascript:alert(1)", "data:text/html,bad"])
    assert.ok(!SAFE_PRINT_URI.test(uri), uri);
});

test("math serialization restores subscripts without changing code fences", () => {
  const md = "公式 $$A\\_n=P(1+r)^n$$\n\n```text\n$A\\_n$\n```";
  assert.equal(restoreMath(md), "公式 $$A_n=P(1+r)^n$$\n\n```text\n$A\\_n$\n```");
});

test("highlights render in prose but preserve code examples", () => {
  const md = "==重点==\n\n```text\n==not a highlight==\n```";
  assert.equal(highlightMarkdown(md), "<mark>重点</mark>\n\n```text\n==not a highlight==\n```");
});
