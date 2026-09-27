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
    await page.route(origin + '/layout-diagram.svg', route => route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="#eee"/><path d="M100 700 800 100 1500 700Z" fill="none" stroke="#171717" stroke-width="8"/></svg>',
    }));
    await page.addInitScript(() => {
      window.__tasks = ['A', 'B'].map(id => ({id, title: '课程 ' + id, has_doc: true, mtime: 0}));
      window.__directoryResults = {output: {ok: true, path: 'D:/测试/任务'}, pdf: {ok: true, path: 'D:/测试/PDF'}};
      window.pywebview = { api: {
        load_config: async () => ({}), reset_context: async () => ({ok: true}),
        get_window_state: async () => ({custom_titlebar: true, maximized: !!window.__maximized}),
        control_window: async action => {
          (window.__windowActions ||= []).push(action);
          if (action === 'toggle_maximize') window.__maximized = !window.__maximized;
          return {ok: true, custom_titlebar: true, maximized: !!window.__maximized};
        },
        save_config: async cfg => { window.__settings = cfg; return {ok: true}; },
        choose_output_dir: async () => {
          if (window.__directoryError) throw new Error('目录选择不可用');
          return window.__directoryResults.output;
        },
        choose_pdf_output_dir: async () => window.__directoryResults.pdf,
        list_skills: async () => ({ok: true, skills: []}),
        list_favorites: async () => ({ok: true, favorites: window.__tasks.slice(0, 1)}),
        toggle_favorite: async () => ({ok: true, favorited: true}),
        update_doc: async () => ({ok: true}), save_draft: async () => ({ok: true}),
        list_tasks: async () => {
          if (window.__holdTasks) await new Promise(resolve => { window.__releaseTasks = resolve; });
          return {ok: true, tasks: window.__tasks};
        },
        rename_task: async (id, title) => { window.__tasks.find(task => task.id === id).title = title; return {ok: true, title}; },
        delete_task: async id => { window.__tasks = window.__tasks.filter(task => task.id !== id); return {ok: true}; },
        generate_doc: async url => {
          window.__generatedUrl = url;
          window.__tasks.unshift({id: 'C', title: '新课程', has_doc: true, mtime: 1});
          return {ok: true, id: 'C', title: '新课程', doc: '# 新课程\n\n正文', info: {}};
        },
        load_task: async id => {
          if (window.__holdLoadTask === id) await new Promise(resolve => { window.__releaseTask = resolve; });
          return {ok: true, id, title: '课程 ' + id, doc: '# 课程 ' + id + '\n\n正文', history: [{role: 'user', content: '问题 ' + id}, {role: 'assistant', content: '回答 ' + id + '\n\n==重点=='}]};
        },
      }};
    });
    await page.goto(origin + '/index.html');
    await page.waitForFunction(() => !!window.editor);
    await page.waitForSelector('#sampleCards button');
    await page.waitForSelector('#sidebarTasks button');
    assert.equal(await page.title(), 'LearningDex');
    assert.equal(await page.locator('.brand-name').innerText(), 'LearningDex');
    await page.locator('#windowTitlebar button[aria-label="最小化"]').click();
    await page.locator('#windowMaximize').click();
    assert.equal(await page.locator('#windowMaximize').getAttribute('aria-label'), '还原');
    await page.locator('#windowMaximize').click();
    assert.equal(await page.locator('#windowMaximize').getAttribute('aria-label'), '最大化');
    await page.locator('#windowTitlebar').dblclick({position: {x: 100, y: 16}});
    assert.equal(await page.locator('#windowMaximize').getAttribute('aria-label'), '还原');
    await page.locator('#windowMaximize').click();
    await page.locator('#windowTitlebar button[aria-label="关闭窗口"]').click();
    assert.deepEqual(await page.evaluate(() => window.__windowActions),
      ['minimize', 'toggle_maximize', 'toggle_maximize', 'toggle_maximize', 'toggle_maximize', 'close']);
    await page.mouse.move(80, 16);
    await page.mouse.down();
    await page.mouse.move(95, 16);
    await page.mouse.up();
    await page.waitForFunction(() => window.__windowActions.includes('drag'));
    assert.equal(await page.evaluate(() => window.__windowActions.filter(action => action === 'drag').length), 1);
    const assertWelcomeLayout = async () => {
      assert.equal(await page.locator('.chat').isVisible(), false);
      assert.equal(await page.locator('#panelDivider').isVisible(), false);
      const sidebar = await page.locator('.sidebar').boundingBox();
      const center = await page.locator('.center').boundingBox();
      assert.ok(Math.abs(sidebar.width / page.viewportSize().width - 0.2) < 0.001);
      assert.ok(Math.abs(center.width / page.viewportSize().width - 0.8) < 0.001);
      const title = await page.locator('.window-title').boundingBox();
      assert.ok(Math.abs(title.x + title.width / 2 - page.viewportSize().width / 2) < 1);
      assert.equal(await page.evaluate(() => document.documentElement.scrollHeight), page.viewportSize().height);
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
      await page.waitForFunction(() => !document.querySelector('.slogan').classList.contains('typing'));
      await page.evaluate(() => Promise.all(document.getAnimations().filter(a => Number.isFinite(a.effect.getTiming().iterations)).map(a => a.finished.catch(() => {}))));
      await page.screenshot({path: path.join(folder, name + '.png')});
    };
    await snapshot('monochrome-home');
    const style = async selector => page.locator(selector).evaluate(node => {
      const s = getComputedStyle(node);
      return {size: parseFloat(s.fontSize), weight: Number(s.fontWeight), color: s.color, background: s.backgroundColor};
    });
    assert.equal((await style('#taskBtn')).size, 13);
    assert.ok((await style('#saveBtn')).weight >= 600);
    assert.equal((await style('.chat-empty')).color, 'rgb(82, 82, 82)');
    await page.mouse.move(1200, 100);
    await page.locator('#settingsBtn').click();
    await page.locator('#settings .modal-box').evaluate(node => Promise.all(node.getAnimations().map(a => a.finished.catch(() => {}))));
    assert.equal(await page.locator('#settings #whisperModel, #settings #proofread, #settings #skillBtn').count(), 3);
    assert.equal(await page.locator('#startBtn').count(), 0);
    assert.deepEqual(await page.locator('#settings .row.right button').allTextContents(), ['保存', '关闭']);
    const saveBox = await page.locator('#saveBtn').boundingBox();
    const closeBox = await page.locator('#closeSettings').boundingBox();
    assert.ok(saveBox.x < closeBox.x && Math.abs(saveBox.y - closeBox.y) < 1);
    assert.equal((await style('#saveBtn')).background, 'rgb(23, 23, 23)');
    assert.equal((await style('#saveBtn')).color, 'rgb(255, 255, 255)');
    await page.locator('#saveBtn').hover();
    assert.equal((await style('#saveBtn')).background, 'rgb(229, 229, 229)');
    await page.locator('#skillBtn').click();
    await page.waitForSelector('#skillsModal:not([hidden])');
    await page.locator('#skillClose').click();
    assert.equal(await page.locator('#outputDir').getAttribute('placeholder'), '中间文件的存储目录');
    await page.locator('#chooseOutputDir').click();
    assert.equal(await page.locator('#outputDir').inputValue(), 'D:/测试/任务');
    await page.locator('#choosePdfDir').click();
    assert.equal(await page.locator('#pdfOutputDir').inputValue(), 'D:/测试/PDF');
    assert.equal(await page.evaluate(() => window.__settings), undefined);
    await page.evaluate(() => {
      window.__directoryResults.output = {ok: true, path: ''};
      window.__directoryResults.pdf = {ok: true, path: ''};
    });
    await page.locator('#chooseOutputDir').click();
    await page.locator('#choosePdfDir').click();
    assert.equal(await page.locator('#outputDir').inputValue(), 'D:/测试/任务');
    assert.equal(await page.locator('#pdfOutputDir').inputValue(), 'D:/测试/PDF');
    await page.evaluate(() => { window.__directoryResults.output = {ok: false, error: '无法打开目录选择'}; });
    await page.locator('#chooseOutputDir').click();
    await page.waitForFunction(() => document.getElementById('setMsg').textContent.includes('无法打开目录选择'));
    assert.equal(await page.locator('#outputDir').inputValue(), 'D:/测试/任务');
    await page.evaluate(() => { window.__directoryError = true; });
    await page.locator('#chooseOutputDir').click();
    await page.waitForFunction(() => document.getElementById('setMsg').textContent.includes('目录选择不可用'));
    await page.evaluate(() => {
      window.__directoryError = false;
      window.__directoryResults.output = {ok: true, path: 'D:/测试/任务'};
    });
    await page.locator('#chooseOutputDir').click();
    assert.equal(await page.locator('#setMsg').textContent(), '');
    await snapshot('settings-directories');
    await page.locator('#whisperModel').selectOption('small');
    await page.locator('#saveBtn').click();
    assert.equal(await page.evaluate(() => window.__settings.whisper_model), 'small');
    assert.equal(await page.evaluate(() => window.__settings.output_dir), 'D:/测试/任务');
    assert.equal(await page.evaluate(() => window.__settings.pdf_output_dir), 'D:/测试/PDF');
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
    assert.equal(await page.locator('#meta').innerText(), '');
    const assertDocumentLayout = async () => {
      const center = await page.locator('.center').boundingBox();
      const header = await page.locator('.doc-head').boundingBox();
      const card = await page.locator('#editor').boundingBox();
      const content = await page.locator('#editor .ProseMirror').boundingBox();
      assert.equal(await page.locator('#state').isVisible(), false);
      assert.equal(await page.locator('#meta').isVisible(), false);
      assert.ok(card.x - center.x <= 12 && center.x + center.width - card.x - card.width <= 12);
      assert.ok(card.width >= center.width - 24);
      assert.ok(card.y - header.y - header.height <= 9);
      assert.ok(content.x - card.x <= 16 && card.x + card.width - content.x - content.width <= 16);
      assert.equal(await page.locator('#editor .ProseMirror').evaluate(node => getComputedStyle(node).borderTopWidth), '0px');
    };
    await assertDocumentLayout();
    await page.setViewportSize({width: 1000, height: 750});
    await assertDocumentLayout();
    await page.evaluate(() => {
      document.getElementById('state').textContent = '导出失败：测试提示';
    });
    assert.equal(await page.locator('#state').isVisible(), true);
    await page.evaluate(() => { document.getElementById('state').textContent = ''; });
    const layoutDoc = '# 阅读区检查\n\n用公式 $a+b$ 和图片说明内容。\n\n![示意图](' + origin + '/layout-diagram.svg)';
    await page.evaluate(md => window._setMarkdown(md), layoutDoc);
    await page.waitForFunction(() => document.querySelector('#editor img')?.naturalWidth === 1600);
    const storedDoc = await page.evaluate(() => window._getMarkdown());
    const assertContentFits = async () => {
      await page.evaluate(() => window.dispatchEvent(new Event('resize')));
      await page.waitForSelector('#mathLayer .math-item');
      const image = await page.locator('#editor img[alt="示意图"]').boundingBox();
      const content = await page.locator('#editor .ProseMirror').boundingBox();
      assert.ok(image.width <= content.width && image.width > content.width - 1);
      assert.ok(Math.abs(image.width / image.height - 1600 / 900) < 0.01);
      assert.equal(await page.locator('#editor').evaluate(node => node.scrollWidth > node.clientWidth), false);
      const formula = await page.evaluate(() => {
        const node = document.querySelector('#editor .ProseMirror p').firstChild;
        const start = node.textContent.indexOf('$a+b$');
        const range = document.createRange();
        range.setStart(node, start); range.setEnd(node, start + 5);
        const text = range.getBoundingClientRect();
        const overlay = document.querySelector('#mathLayer .math-item').getBoundingClientRect();
        return {left: Math.abs(text.left - overlay.left), top: Math.abs(text.top - overlay.top)};
      });
      assert.ok(formula.left < 1 && formula.top < 1);
      assert.equal(await page.evaluate(() => window._getMarkdown()), storedDoc);
    };
    await assertContentFits();
    await snapshot('expanded-document-narrow');
    await page.setViewportSize({width: 1440, height: 900});
    await assertContentFits();
    await page.evaluate(() => window._setMarkdown('# 课程 A\n\n正文'));
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
    assert.equal(await page.locator('.center #libraryPage').isVisible(), true);
    assert.equal(await page.locator('#tasksModal, #favsModal').count(), 0);
    assert.equal(await page.locator('.chat').isVisible(), false);
    await snapshot('task-management-page');
    await page.locator('#taskList .task-open').nth(1).click();
    const conversation = await page.locator('#chatLog').innerText();
    assert.ok(conversation.includes('回答 B'));
    assert.ok(!conversation.includes('回答 A'));
    assert.equal(await page.locator('#docTitle').innerText(), '课程 B');
    assert.equal(await page.locator('#sidebarTasks button[aria-current="true"]').getAttribute('data-task-id'), 'B');
    await snapshot('monochrome-task');
    await page.locator('#taskBtn').click();
    await page.locator('#taskList .task-item').nth(1).locator('.task-delete').click();
    await page.waitForFunction(() => !document.querySelector('#sidebarTasks button[data-task-id="B"]'));
    await page.locator('#libraryBack').click();
    await assertWelcomeLayout();
    // A slow task listing must not reopen a page after navigation elsewhere.
    await page.evaluate(() => { window.__holdTasks = true; });
    await page.locator('#taskBtn').click();
    await page.waitForFunction(() => !!window.__releaseTasks);
    await page.locator('#newParseBtn').click();
    await page.evaluate(() => { window.__holdTasks = false; window.__releaseTasks(); });
    await assertWelcomeLayout();
    assert.equal(await page.locator('#libraryPage').isVisible(), false);
    // Home transitions expose both the requested rise and progressive text.
    await page.waitForFunction(() => {
      const slogan = document.querySelector('.slogan');
      return slogan.textContent.length > 0 && slogan.textContent.length < slogan.getAttribute('aria-label').length;
    });
    await page.waitForFunction(() => !document.querySelector('.slogan').classList.contains('typing'));
    assert.equal(await page.locator('.slogan').textContent(), '快速总结并讲解视频内容');
    await page.locator('#favBtn').click();
    await page.waitForSelector('#favList .task-open');
    const motion = await page.locator('#libraryPage').evaluate(node => {
      const animation = node.getAnimations()[0];
      if (!animation) return null;
      animation.pause(); animation.currentTime = 0;
      const s = getComputedStyle(node);
      const result = {duration: animation.effect.getTiming().duration, opacity: s.opacity, transform: s.transform};
      animation.finish();
      return result;
    });
    assert.equal(motion?.duration, 500);
    assert.equal(motion.opacity, '0');
    assert.ok(motion.transform.includes('24'));
    await snapshot('favorites-page');
    await page.locator('#favList .task-open').first().click();
    assert.equal(await page.locator('#workspace').isVisible(), true);
    assert.equal(await page.locator('#libraryPage').isVisible(), false);
    await page.emulateMedia({reducedMotion: 'reduce'});
    await page.locator('#newParseBtn').click();
    assert.equal(await page.locator('.slogan').textContent(), '快速总结并讲解视频内容');
    assert.equal(await page.locator('#welcome').evaluate(node => node.getAnimations().length), 0);
    await page.emulateMedia({reducedMotion: 'no-preference'});
    await page.locator('#url').fill('https://www.bilibili.com/video/BV1TEST');
    await page.locator('#url').press('Enter');
    await page.waitForSelector('#sidebarTasks button[data-task-id="C"]');
    assert.equal(await page.locator('#settings').isVisible(), false);
    assert.equal(await page.locator('.chat').isVisible(), true);
    assert.equal(await page.locator('#docTitle').innerText(), '新课程');
    assert.equal(await page.evaluate(() => window.__generatedUrl), 'https://www.bilibili.com/video/BV1TEST');
    await page.locator('#taskBtn').click();
    await page.evaluate(() => { window.__holdLoadTask = 'C'; });
    await page.locator('#taskList .task-open').first().click();
    await page.waitForFunction(() => !!window.__releaseTask);
    await page.getByRole('button', {name: '删除 新课程', exact: true}).click();
    await page.evaluate(() => window.__releaseTask());
    await page.waitForFunction(() => !document.querySelector('#sidebarTasks button[data-task-id="C"]'));
    assert.equal(await page.locator('#libraryPage').isVisible(), true);
    assert.equal(await page.locator('#workspace').isVisible(), false);
    assert.equal(await page.locator('#docTitle').isDisabled(), true);
    await page.evaluate(() => { window.__holdTasks = true; window.__releaseTasks = null; });
    await page.locator('#taskBtn').click();
    await page.waitForFunction(() => !!window.__releaseTasks && document.querySelector('#libraryPage').getAnimations().length === 0);
    await page.evaluate(() => { window.__holdTasks = false; window.__releaseTasks(); });
    await page.waitForSelector('#taskList .task-open');
    const lateMotion = await page.locator('#taskList').evaluate(node => node.getAnimations()[0]?.effect.getKeyframes()[0]);
    assert.equal(lateMotion?.opacity, '0');
    assert.ok(lateMotion?.transform.includes('24'));
    assert.deepEqual(errors, []);
    console.log('Browser interface checks passed');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
