const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '../app/web');
const valid = 'graph TD\n' + Array.from({length: 12}, (_, i) => `N${i}[步骤 ${i + 1}] --> N${i + 1}[步骤 ${i + 2}]`).join('\n');
const invalid = 'graph LR\nA[写作完成<br/>"含引号的标签"] --> B[下一步]';
const fixture = '# 图表检查\n\n```mermaid\n' + invalid + '\n```\n\n```mermaid\n' + valid + '\n```\n\n图表后的文字。';
const document = process.env.LEARNINGDEX_DIAGRAM_DOCUMENT ? fs.readFileSync(process.env.LEARNINGDEX_DIAGRAM_DOCUMENT, 'utf8') : fixture;
const server = http.createServer((req, res) => {
  const file = path.resolve(root, '.' + new URL(req.url, 'http://localhost').pathname);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) { res.writeHead(404).end(); return; }
  const mime = {'.js': 'text/javascript', '.mjs': 'text/javascript', '.html': 'text/html', '.css': 'text/css', '.svg': 'image/svg+xml'};
  res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless: true, channel: process.env.LEARNINGDEX_BROWSER_CHANNEL || undefined});
    const page = await browser.newPage({viewport: {width: 1000, height: 800}});
    const origin = `http://127.0.0.1:${server.address().port}`;
    await page.route('**/*', route => route.request().url().startsWith(origin) ? route.continue() : route.abort());
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.addInitScript(({doc, valid, invalid}) => {
      window.pywebview = {api: {
        load_config: async () => ({}), list_skills: async () => ({ok: true, skills: []}),
        list_tasks: async () => ({ok: true, tasks: [{id: 'diagram', title: '图表检查', has_doc: true}]}),
        list_favorites: async () => ({ok: true, favorites: []}),
        load_task: async id => ({ok: true, id, title: '图表检查', doc, history: [
          {role: 'assistant', content: '```mermaid\n' + valid + '\n```'},
          {role: 'assistant', content: '```mermaid\n' + invalid + '\n```'},
        ]}),
        save_draft: async () => ({ok: true}), update_doc: async () => ({ok: true}),
        reset_context: async () => ({ok: true}),
      }};
    }, {doc: document, valid: 'graph LR\nA[输入] --> B[输出]', invalid});
    await page.goto(origin + '/index.html');
    await page.waitForFunction(() => !!window.editor);
    await page.locator('#sidebarTasks button').click();
    await page.evaluate(() => window._renderMermaids());
    const leaks = () => page.evaluate(() => [...document.body.children].filter(node =>
      !node.matches('.app, #windowTitlebar, .modal, #printRoot, script, .mermaidTooltip')).length);
    if (process.env.LEARNINGDEX_EXPECT_MERMAID_BUG) {
      assert.ok(await leaks() > 0);
      await page.screenshot({path: path.resolve(__dirname, '../cache/ui-test/mermaid-before.png')});
      console.log('Reproduced Mermaid DOM leak');
      return;
    }
    assert.equal(await leaks(), 0);
    await page.waitForSelector('#mmdLayer svg');
    const canonical = await page.evaluate(() => window._getMarkdown());
    const count = await page.locator('#editor pre[data-language="mermaid"]').count();
    const previewCount = await page.locator('#mmdLayer svg').count();
    const errorCount = await page.locator('#editor pre[data-mermaid-error]').count();
    assert.equal(previewCount + errorCount, count);
    assert.ok(previewCount > 0);
    if (!process.env.LEARNINGDEX_DIAGRAM_DOCUMENT) assert.equal(errorCount, 1);
    const editorBox = await page.locator('#editor').boundingBox();
    const layerBox = await page.locator('#mmdLayer').boundingBox();
    assert.ok(Math.abs(editorBox.y - layerBox.y) < 1 && Math.abs(editorBox.height - layerBox.height) < 1);
    assert.equal(await page.locator('#mmdLayer').evaluate(node => getComputedStyle(node).overflow), 'hidden');
    assert.equal(await page.locator('.app').evaluate(node => node.clientHeight), 800);
    assert.equal(await page.locator('.mermaid-scratch').count(), 0);
    if (!process.env.LEARNINGDEX_DIAGRAM_DOCUMENT) {
      const graphBox = await page.locator('#editor pre').nth(1).boundingBox();
      const afterBox = await page.getByText('图表后的文字。', {exact: true}).boundingBox();
      assert.ok(graphBox.height > editorBox.height);
      assert.ok(afterBox.y >= graphBox.y + graphBox.height);
    }
    await page.waitForSelector('#chatLog .chat-mmd svg');
    await page.waitForSelector('#chatLog pre[data-mermaid-error]');
    assert.ok((await page.locator('#chatLog .chat-mmd').textContent()).includes('输入'));
    for (let i = 0; i < 4; i++) {
      await page.locator('#editor').evaluate((node, i) => { node.scrollTop = i * 180; }, i);
      await page.evaluate(() => window._renderMermaids());
    }
    assert.equal(await leaks(), 0);
    assert.equal(await page.locator('#mmdLayer svg').count(), previewCount);
    assert.equal(await page.evaluate(() => window._getMarkdown()), canonical);
    await page.locator('#editor').evaluate(node => { node.scrollTop = 0; });
    await page.evaluate(() => window._renderMermaids());
    await page.screenshot({path: path.resolve(__dirname, '../cache/ui-test/mermaid-after.png')});
    await page.evaluate(() => window._buildPrintDoc());
    assert.equal(await page.locator('#printRoot .print-mmd').count(), previewCount);
    assert.equal(await page.locator('#printRoot .diagram-error').count(), errorCount);
    assert.equal(await leaks(), 0);
    if (!process.env.LEARNINGDEX_DIAGRAM_DOCUMENT) {
      // Keep the source edit outside the editor's 500 ms history grouping window.
      await page.waitForTimeout(550);
      const corrected = 'graph LR\nA["写作完成<br/>#quot;含引号的标签#quot;"] --> B[下一步]';
      await page.locator('#editor pre code').first().click();
      await page.evaluate(() => window._renderMermaids());
      await page.locator('#editor').evaluate(node => {
        const code = node.querySelector('pre code');
        node.querySelector('.ProseMirror').focus();
        const range = document.createRange();
        range.selectNodeContents(code);
        window.getSelection().removeAllRanges(); window.getSelection().addRange(range);
      });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
      const lines = corrected.split('\n');
      await page.keyboard.type(lines[0]);
      await page.keyboard.press('Enter');
      await page.keyboard.insertText(lines[1]);
      assert.ok((await page.evaluate(() => window._getMarkdown())).includes(corrected));
      assert.equal(await page.locator('#editor pre').first().getAttribute('data-mermaid-preview'), null);
      await page.locator('#settingsBtn').click();
      await page.waitForFunction(() => document.querySelectorAll('#mmdLayer svg').length === 2);
      await page.locator('#closeSettings').click();
      await page.locator('#editor .ProseMirror').focus();
      await page.keyboard.press('Control+z');
      assert.equal(await page.evaluate(() => window._getMarkdown()), canonical);
      await page.locator('#settingsBtn').click();
      await page.waitForSelector('#editor pre[data-mermaid-error]');
      await page.locator('#closeSettings').click();
      await page.locator('#editor pre').nth(1).click({position: {x: 20, y: 10}});
      await page.waitForFunction(() => !document.querySelectorAll('#editor pre')[1].hasAttribute('data-mermaid-preview'));
      assert.equal(await page.locator('#editor pre code').nth(1).evaluate(node => getComputedStyle(node).visibility), 'visible');
      await page.locator('#settingsBtn').click();
      await page.waitForSelector('#mmdLayer svg');
      await page.locator('#closeSettings').click();
    }

    // Exercise render failure cleanup and shared pending/cache behavior.
    const rendererChecks = await page.evaluate(async () => {
      const {createMermaidRenderer} = await import('/mermaid_renderer.mjs');
      let parses = 0, renders = 0, loads = 0;
      const renderer = createMermaidRenderer({load: async () => {
        loads++;
        return {initialize() {}, parse: async code => { parses++; return code !== 'invalid'; },
          render: async (id, code, host) => {
            renders++;
            host.innerHTML = '<svg><text>Syntax error in text</text></svg>';
            if (code === 'failure') throw new Error('layout failed');
            return {svg: '<svg viewBox="0 0 100 200" onload="alert(1)"><script>alert(1)</script><foreignObject><div xmlns="http://www.w3.org/1999/xhtml" onclick="alert(1)">正常标签<script>alert(1)</script></div></foreignObject></svg>'};
          }};
      }});
      const values = await Promise.all([renderer('failure'), renderer('failure'), renderer('invalid'), renderer('valid')]);
      await renderer('failure'); await renderer('valid');
      return {parses, renders, loads, errors: values.slice(0, 3).every(value => !value.svg),
        safe: !values[3].svg.includes('onload') && !values[3].svg.includes('onclick') && !values[3].svg.includes('<script'),
        label: values[3].svg.includes('正常标签'), hosts: document.querySelectorAll('.mermaid-scratch').length};
    });
    assert.deepEqual(rendererChecks, {parses: 3, renders: 2, loads: 1, errors: true, safe: true, label: true, hosts: 0});
    assert.equal(await leaks(), 0);
    // A result that finishes after a document/page switch must be discarded.
    await page.evaluate(async () => {
      const {createEditorDiagrams} = await import('/editor_diagrams.mjs');
      const host = document.createElement('div');
      host.innerHTML = '<div class="editor"><pre data-language="mermaid"><code>graph TD; A-->B;</code></pre></div><div class="layer"></div>';
      document.getElementById('workspace').appendChild(host);
      let release;
      const view = createEditorDiagrams(host.querySelector('.editor'), host.querySelector('.layer'),
        () => new Promise(resolve => { release = resolve; }));
      const pending = view.render();
      view.clear();
      release({svg: '<svg viewBox="0 0 100 100"></svg>', width: 100, height: 100});
      await pending;
      if (host.querySelector('.layer').children.length) throw new Error('Stale diagram returned');
      host.remove();
    });
    await page.locator('#newParseBtn').click();
    assert.equal(await page.locator('#mmdLayer').evaluate(node => node.children.length), 0);
    assert.equal(await leaks(), 0);
    assert.deepEqual(errors, []);
    console.log(`Diagram interface checks passed (${previewCount} previews, ${errorCount} local fallbacks)`);
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
