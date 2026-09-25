import test from "node:test";
import assert from "node:assert/strict";
import { escapeAttribute, SAFE_PRINT_URI } from "../app/web/render_utils.mjs";

test("image attributes cannot inject event handlers", () => {
  const escaped = escapeAttribute('file:///a.jpg" onerror="alert(1)<x>&');
  assert.equal(escaped, 'file:///a.jpg&quot; onerror=&quot;alert(1)&lt;x&gt;&amp;');
  assert.ok(!escaped.includes('"'));
  assert.ok(!escaped.includes('<'));
});

test("print links accept local images without accepting script URLs", () => {
  for (const uri of ["file:///D:/notes/img.jpg", "images/shot.jpg", "https://example.org/a.png"])
    assert.ok(SAFE_PRINT_URI.test(uri), uri);
  for (const uri of ["javascript:alert(1)", " javascript:alert(1)", "data:text/html,bad"])
    assert.ok(!SAFE_PRINT_URI.test(uri), uri);
});
