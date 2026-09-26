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
    page.on('dialog', dialog => dialog.accept());
    const origin = `http://127.0.0.1:${server.address().port}`;
    await page.route('**/*', route => route.request().url().startsWith(origin) ? route.continue() : route.abort());
    await page.addInitScript(() => {
      window.__tasks = ['A', 'B'].map(id => ({id, title: '课程 ' + id, has_doc: true, mtime: 0}));
      window.pywebview = { api: {
        load_config: async () => ({}), reset_context: async () => ({ok: true}),
        save_config: async cfg => { window.__settings = cfg; return {ok: true}; },
        list_skills: async () => ({ok: true, skills: []}),
        list_favorites: async () => ({ok: true, favorites: []}),
        toggle_favorite: async () => ({ok: true, favorited: true}),
        update_doc: async () => ({ok: true}), save_draft: async () => ({ok: true}),
        list_tasks: async () => ({ok: true, tasks: window.__tasks}),
        rename_task: async (id, title) => { window.__tasks.find(task => task.id === id).title = title; return {ok: true, title}; },
        delete_task: async id => { window.__tasks = window.__tasks.filter(task => task.id !== id); return {ok: true}; },
        generate_doc: async url => {
          window.__generatedUrl = url;
          window.__tasks.unshift({id: 'C', title: '新课程', has_doc: true, mtime: 1});
          return {ok: true, id: 'C', title: '新课程', doc: '# 新课程\n\n正文', info: {}};
        },
        load_task: async id => ({ok: true, id, title: '课程 ' + id, doc: '# 课程 ' + id + '\n\n正文', history: [{role: 'user', content: '问题 ' + id}, {role: 'assistant', content: '回答 ' + id + '\n\n==重点=='}]}),
      }};
    });
    await page.goto(origin + '/index.html');
    await page.waitForFunction(() => !!window.editor);
    await page.waitForSelector('#sampleCards button');
    await page.waitForSelector('#sidebarTasks button');
    const assertWelcomeLayout = async () => {
      assert.equal(await page.locator('.chat').isVisible(), false);
      assert.equal(await page.locator('#panelDivider').isVisible(), false);
      const sidebar = await page.locator('.sidebar').boundingBox();
      const center = await page.locator('.center').boundingBox();
      assert.ok(Math.abs(sidebar.width / page.viewportSize().width - 0.2) < 0.001);
      assert.ok(Math.abs(center.width / page.viewportSize().width - 0.8) < 0.001);
    };
    await assertWelcomeLayout();
    await page.setViewportSize({width: 1200, height: 800});
    await assertWelcomeLayout();
    await page.setViewportSize({width: 1440, height: 900});
    assert.equal(await page.locator('.sidebar #whisperModel, .sidebar #proofread, .sidebar #skillBtn, .sidebar #startBtn').count(), 0);
    assert.equal(await page.locator('#historyBtn, #histModal').count(), 0);
    const icons = await page.locator('img.icon').evaluateAll(nodes => nodes.filter(node => !node.closest('[hidden]')).map(node => ({loaded: node.complete && node.naturalWidth > 0, source: node.getAttribute('src')})));
    assert.ok(icons.length >= 6);
    assert.ok(icons.every(icon => icon.loaded && icon.source.startsWith('icons/')));
    assert.equal(await page.locator('#githubBtn img').getAttribute('src'), 'icons/mark-github-16.svg');
    const snapshot = async name => {
      if (!process.env.LEARNINGDEX_UI_SCREENSHOTS) return;
      const folder = path.resolve(__dirname, '../cache/ui-test');
      fs.mkdirSync(folder, {recursive: true});
      await page.screenshot({path: path.join(folder, name + '.png')});
    };
    await snapshot('monochrome-home');
    const style = async selector => page.locator(selector).evaluate(node => {
      const s = getComputedStyle(node);
      return {size: parseFloat(s.fontSize), weight: Number(s.fontWeight), color: s.color, background: s.backgroundColor};
    });
    assert.equal((await style('#taskBtn')).size, 13);
    assert.ok((await style('#startBtn')).weight >= 600);
    assert.equal((await style('.chat-empty')).color, 'rgb(82, 82, 82)');
    await page.mouse.move(1200, 100);
    await page.locator('#settingsBtn').click();
    assert.equal(await page.locator('#settings #whisperModel, #settings #proofread, #settings #skillBtn, #settings #startBtn').count(), 4);
    assert.equal((await style('#startBtn')).background, 'rgb(23, 23, 23)');
    assert.equal((await style('#startBtn')).color, 'rgb(255, 255, 255)');
    await page.locator('#startBtn').hover();
    assert.equal((await style('#startBtn')).background, 'rgb(229, 229, 229)');
    await page.locator('#saveBtn').hover();
    assert.equal((await style('#saveBtn')).background, 'rgb(229, 229, 229)');
    await page.locator('#skillBtn').click();
    await page.waitForSelector('#skillsModal:not([hidden])');
    await page.locator('#skillClose').click();
    await page.locator('#whisperModel').selectOption('small');
    await page.locator('#saveBtn').click();
    assert.equal(await page.evaluate(() => window.__settings.whisper_model), 'small');
    await page.locator('#closeSettings').click();
    await page.locator('#sampleCards button').first().click();
    assert.equal(await page.locator('.chat').isVisible(), true);
    const beforeDrag = await page.locator('.center').boundingBox();
    const divider = await page.locator('#panelDivider').boundingBox();
    await page.mouse.move(divider.x + 3, divider.y + 100);
    await page.mouse.down();
    await page.mouse.move(divider.x + 83, divider.y + 100);
    await page.mouse.up();
    const afterDrag = await page.locator('.center').boundingBox();
    assert.ok(afterDrag.width > beforeDrag.width + 50);
    await page.locator('#newParseBtn').click();
    await assertWelcomeLayout();
    await page.locator('#sampleCards button').first().click();
    assert.ok(Math.abs((await page.locator('.center').boundingBox()).width - afterDrag.width) < 1);
    assert.equal((await style('#editor .ProseMirror')).size, 15);
    assert.equal((await style('#editor .ProseMirror')).color, 'rgb(23, 23, 23)');
    const coloredElements = await page.evaluate(() => {
      const isColored = color => {
        const values = color.match(/[\d.]+/g)?.map(Number);
        return values?.length >= 3 && (values.length < 4 || values[3] > 0) && (values[0] !== values[1] || values[1] !== values[2]);
      };
      return [...document.querySelectorAll('body *')].filter(node => node.getBoundingClientRect().width > 0 && !(node instanceof SVGElement) && !node.closest('mark, .bub.user, #favDocBtn, #newParseBtn')).filter(node => {
        const s = getComputedStyle(node);
        return [s.color, s.backgroundColor, s.borderTopColor].some(isColored);
      }).map(node => node.id || node.className);
    });
    assert.deepEqual(coloredElements, []);
    const original = '先了解重点内容，再查看示例。';
    await page.evaluate(text => window._setMarkdown(text), original);
    const selection = await page.evaluate(() => {
      const node = document.querySelector('#editor .ProseMirror p').firstChild;
      const range = document.createRange();
      range.setStart(node, 3); range.setEnd(node, 7);
      const selection = window.getSelection();
      selection.removeAllRanges(); selection.addRange(range);
      const rect = range.getBoundingClientRect();
      document.getElementById('editor').dispatchEvent(new MouseEvent('mouseup', {bubbles: true, button: 0}));
      return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
    });
    await page.locator('#editor').evaluate((node, point) => node.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, button: 2, clientX: point.x, clientY: point.y})), selection);
    await page.locator('#formatMenu button[data-wrap="=="]').click();
    assert.equal((await style('#editor mark')).background, 'rgb(255, 235, 59)');
    assert.equal(await page.locator('#editor mark').evaluate(node => getComputedStyle(node).textDecorationLine), 'none');
    assert.ok((await page.evaluate(() => window._getMarkdown())).includes('==重点内容=='));
    assert.equal(await page.locator('#editor .ProseMirror').innerText(), original);
    await page.evaluate(() => window.getSelection().removeAllRanges());
    await snapshot('revised-highlight');
    await page.evaluate(() => window._buildPrintDoc());
    await page.emulateMedia({media: 'print'});
    assert.equal((await style('#printRoot mark')).background, 'rgb(255, 235, 59)');
    await page.emulateMedia({media: 'screen'});
    await page.locator('#editor .ProseMirror').focus();
    await page.keyboard.press('Control+z');
    assert.equal(await page.locator('#editor mark').count(), 0);
    assert.equal(await page.locator('#editor .ProseMirror').innerText(), original);
    await page.locator('#sidebarTasks button[data-task-id="A"]').click();
    assert.equal(await page.locator('#state').innerText(), '');
    assert.ok((await page.locator('#chatLog').innerText()).includes('回答 A'));
    assert.equal((await style('#chatLog .bub.user')).background, 'rgb(230, 240, 255)');
    assert.equal((await style('#chatLog .bub.ai mark')).background, 'rgb(255, 235, 59)');
    await page.locator('#favDocBtn').click();
    assert.equal(await page.locator('#favDocBtn').getAttribute('aria-pressed'), 'true');
    assert.ok((await page.locator('#favDocBtn .icon').evaluate(node => getComputedStyle(node).maskImage)).includes('star-fill-24.svg'));
    assert.equal((await style('#favDocBtn .icon')).background, 'rgb(245, 166, 35)');
    await page.locator('#docTitle').click();
    await page.locator('#titleInput').fill('课程 A 新标题');
    await page.locator('#titleInput').press('Enter');
    await page.waitForFunction(() => document.querySelector('#sidebarTasks button[data-task-id="A"]').textContent.includes('新标题'));
    await page.locator('#taskBtn').click();
    await page.locator('#taskList .task-item').nth(1).click();
    const conversation = await page.locator('#chatLog').innerText();
    assert.ok(conversation.includes('回答 B'));
    assert.ok(!conversation.includes('回答 A'));
    assert.equal(await page.locator('#docTitle').innerText(), '课程 B');
    assert.equal(await page.locator('#sidebarTasks button[aria-current="true"]').getAttribute('data-task-id'), 'B');
    await snapshot('monochrome-task');
    await page.locator('#taskBtn').click();
    await page.locator('#taskList .task-item').nth(1).locator('.task-delete').click();
    await page.waitForFunction(() => !document.querySelector('#sidebarTasks button[data-task-id="B"]'));
    await page.locator('#tasksClose').click();
    await assertWelcomeLayout();
    await page.locator('#url').fill('https://www.bilibili.com/video/BV1TEST');
    await page.locator('#settingsBtn').click();
    await page.locator('#startBtn').click();
    await page.waitForSelector('#sidebarTasks button[data-task-id="C"]');
    assert.equal(await page.locator('#settings').isVisible(), false);
    assert.equal(await page.locator('.chat').isVisible(), true);
    assert.equal(await page.locator('#docTitle').innerText(), '新课程');
    assert.equal(await page.evaluate(() => window.__generatedUrl), 'https://www.bilibili.com/video/BV1TEST');
    assert.deepEqual(errors, []);
    console.log('Browser interface checks passed');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
