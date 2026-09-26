// Run with Playwright installed and LEARNINGDEX_BROWSER_CHANNEL set if needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '../app/web');
const server = http.createServer((req, res) => {
  const filename = path.resolve(root, '.' + new URL(req.url, 'http://localhost').pathname);
  if (!filename.startsWith(root + path.sep) || !fs.existsSync(filename)) {
    res.writeHead(404).end(); return;
  }
  const mime = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
  res.setHeader('Content-Type', mime[path.extname(filename)] || 'application/octet-stream');
  fs.createReadStream(filename).pipe(res);
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ headless: true, channel: process.env.LEARNINGDEX_BROWSER_CHANNEL || undefined });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    const origin = `http://127.0.0.1:${server.address().port}`;
    await page.route('**/*', route => route.request().url().startsWith(origin) ? route.continue() : route.abort());
    await page.addInitScript(() => {
      window.pywebview = { api: {
        load_config: async () => ({}), reset_context: async () => ({ok: true}),
        list_favorites: async () => ({ok: true, favorites: []}),
        update_doc: async () => ({ok: true}), save_draft: async () => ({ok: true}),
        list_tasks: async () => ({ok: true, tasks: ['A', 'B'].map(id => ({id, title: '课程 ' + id, has_doc: true, mtime: 0}))}),
        load_task: async id => ({ok: true, id, title: '课程 ' + id, doc: '# 课程 ' + id + '\n\n正文', history: [{role: 'user', content: '问题 ' + id}, {role: 'assistant', content: '回答 ' + id}]}),
      }};
    });
    await page.goto(origin + '/index.html');
    await page.waitForFunction(() => !!window.editor);
    await page.waitForSelector('#sampleCards button');
    const style = async selector => page.locator(selector).evaluate(node => {
      const s = getComputedStyle(node);
      return {size: parseFloat(s.fontSize), weight: Number(s.fontWeight), color: s.color, background: s.backgroundColor};
    });
    assert.ok((await style('#taskBtn')).size >= 16);
    assert.ok((await style('#startBtn')).weight >= 600);
    assert.equal((await style('.chat-empty')).color, 'rgb(82, 82, 82)');
    await page.mouse.move(1200, 100);
    assert.equal((await style('#startBtn')).background, 'rgb(23, 23, 23)');
    assert.equal((await style('#startBtn')).color, 'rgb(255, 255, 255)');
    await page.locator('#startBtn').hover();
    assert.equal((await style('#startBtn')).background, 'rgb(229, 229, 229)');
    await page.locator('#settingsBtn').click();
    await page.locator('#saveBtn').hover();
    assert.equal((await style('#saveBtn')).background, 'rgb(229, 229, 229)');
    await page.locator('#closeSettings').click();
    await page.locator('#sampleCards button').first().click();
    assert.ok((await style('#editor .ProseMirror')).size >= 17);
    assert.equal((await style('#editor .ProseMirror')).color, 'rgb(23, 23, 23)');
    const coloredElements = await page.evaluate(() => {
      const isColored = color => {
        const values = color.match(/[\d.]+/g)?.map(Number);
        return values?.length >= 3 && (values.length < 4 || values[3] > 0) && (values[0] !== values[1] || values[1] !== values[2]);
      };
      return [...document.querySelectorAll('body *')].filter(node => node.getBoundingClientRect().width > 0 && !(node instanceof SVGElement)).filter(node => {
        const s = getComputedStyle(node);
        return [s.color, s.backgroundColor, s.borderTopColor].some(isColored);
      }).map(node => node.id || node.className);
    });
    assert.deepEqual(coloredElements, []);
    assert.deepEqual(errors, []);
    console.log('Browser interface checks passed');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
