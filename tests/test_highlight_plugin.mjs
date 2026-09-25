import assert from 'node:assert/strict';
import test from 'node:test';
import { splitHighlights } from '../app/web/highlight_plugin.mjs';

test('highlight syntax becomes a mark without changing surrounding text', () => {
  const tree = { type: 'root', children: [
    { type: 'paragraph', children: [{ type: 'text', value: '前面==重点==后面' }] },
  ] };
  splitHighlights(tree);
  assert.deepEqual(tree.children[0].children, [
    { type: 'text', value: '前面' },
    { type: 'highlight', children: [{ type: 'text', value: '重点' }] },
    { type: 'text', value: '后面' },
  ]);
});

test('code and unmatched equals remain literal', () => {
  const tree = { type: 'root', children: [
    { type: 'code', value: '==code==' },
    { type: 'paragraph', children: [{ type: 'text', value: 'a == b' }] },
  ] };
  splitHighlights(tree);
  assert.equal(tree.children[0].value, '==code==');
  assert.equal(tree.children[1].children[0].value, 'a == b');
});
