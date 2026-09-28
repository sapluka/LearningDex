# LearningDex

视频学习辅助 Agent（编辑器 + Agent 一体化）：输入视频链接，自动提取字幕或本地转写，由 Agent 生成可编辑的 Markdown 学习文档，支持对话提问和导出笔记。

## Windows 下载与体验

在 [Releases](https://github.com/sapluka/LearningDex/releases) 下载最新的 `LearningDex.exe`，放在任意文件夹，双击运行。发布包已包含 Python、界面和三份示例，不必安装 Python，也不必下载仓库源码。适用于 Windows 10/11 64 位；窗口需要系统中的 Edge WebView2 运行环境。

第一次体验可按以下顺序检查：

1. 打开软件，确认首页有「纹理映射续讲」「Computer Use」「提示词工程」三张示例卡片。
2. 逐个点击卡片，确认笔记文字与图片能显示；尝试编辑一句话，再点「导出 .md」或「生成PDF」。这一步不需要 API 密钥。
3. 想测试新视频时，先打开设置，填自己的模型协议、请求 URL、模型名和 API Key，并点击「检验连接」。再返回首页输入视频链接，按回车开始解析。B 站登录信息可先留空；需要登录才能获取的视频再按设置页提示填写。
4. 解析完成后检查文档、截图提示和右侧问答；关闭再打开软件，检查历史任务是否还在。默认任务、设置及模型缓存保存在 `%LOCALAPPDATA%\LearningDex\`，可在设置中改存储目录。

API Key 等敏感字段只在本次运行中使用，不写进配置文件；重启后需重新填写。首次本地语音转写会下载模型，视频解析与模型调用需要网络。

## 从源码运行

使用 Python 3.9 及以上版本，安装 `requirements.txt` 后运行 `python -m app.main`。首次转写会下载本地模型；界面静态资源已随项目提供，打开历史任务不需要访问前端 CDN。

Windows 发布包可在已安装依赖的 `.venv` 中另装 `requirements-build.txt`，运行 `tools/build_release.ps1` 构建；产物位于忽略提交的 `output/release/dist/`。构建脚本排除个人配置及 `personal.py`。

如需修改前端源码，在 `app/web/` 运行 `npm ci` 和 `npm run build`，再启动桌面应用。

「生成PDF」会直接保存文件，不打开打印窗口。保存位置在「设置 → PDF 输出目录」中选择；留空时使用笔记存储目录。任务归档在 `output/` 中，BV 号是视频来源编号，任务列表优先显示学习文档标题。

CDN 指通过互联网提供前端代码的服务。本项目的界面代码已随软件保存，打开界面和历史任务不依赖远程 CDN；解析视频和调用模型仍需相应网络连接。

首页只显示左侧导航（1/5）和内容区（4/5）；打开文档后显示 Agent。左栏直接列出历史任务，点击恢复文档与对应对话；任务管理和收藏在右侧内容区显示，不提供独立历史对话查询。

首页内置三份真实视频图文笔记：纹理映射续讲、Computer Use 和提示词工程。笔记与配图存放在 `app/web/examples/`，随软件分发，不读取个人 `output/`；示例导出 Markdown 时会复制配图。

窗口与侧栏名称为 LearningDex，顶部标题居中并隐藏 Python 图标；支持窗口拖动、缩放及最小化、最大化、关闭，双击顶部栏切换最大化/还原。文档阅读区缩小外围留白，打开历史任务直接展示文档。

Windows 任务栏使用本地黑底白字 LD 图标和独立应用标识。图标位于 `app/assets/`；修改图标时，可在有 Pillow 和 Segoe UI Bold 字体的环境中运行 `python tools/build_icon.py` 生成多尺寸 ICO。

转写模型、字幕核验和 Skill 管理位于设置；首页输入视频链接后按回车解析。设置底部依次为「保存」「关闭」。存储目录和 PDF 输出目录均可选择；存储目录包含字幕、截图、学习文档、草稿及任务对话，默认使用 `output/`。

设置中的 B 站登录信息可以先留空；输入框下方提供 Chrome/Edge 获取 SESSDATA 和导出 B 站 cookies.txt 的步骤。设置内容可滚动，保存与关闭始终可见。说明参考 [Chrome Cookie 面板](https://developer.chrome.com/docs/devtools/application/cookies)及 [yt-dlp Cookie 文档](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)。

界面以黑白灰为主，用户消息浅蓝、高亮亮黄、收藏橙黄，学习文档正文 15px。图标使用本地 GitHub Octicons（来源和许可见 `app/web/icons/`）。

「新解析」使用蓝至粉紫渐变。首页、任务页与收藏页约 0.5 秒向上淡入，首页说明逐字显示；设置和 Skill 弹层使用协调的淡入效果。系统启用减少动画时直接显示内容。

截图未完成时会显示具体原因，重新打开任务时保留该提示。任务目录保存 `segments.json`（字幕时间戳）、`screenshot_plan.md`（截图处理前的笔记）和 `screenshots.json`（计划数、插入数及失败原因）。图片核验使用足够的输出预算；调用 DeepSeek 官方接口时关闭这一步的思考模式，避免只有思考内容而没有判断。

B 站的 Cookie 初始化、字幕提取、音频和截图下载使用相同的浏览器标识（User-Agent）；播放接口使用 B 站首页作为来源页面（Referer），修复视频页来源标记触发的 HTTP 412。仍保留原有签名、登录及格式处理。

适配层直接继承 yt-dlp 的播放函数，仅在发送播放接口请求时调整来源，兼容新版新增的 `fatal` 参数，避免视频链接统一报 `unexpected keyword argument 'fatal'`。

图片核验对异常回复有限重试；单张失败后继续后续图片，认证错误或连续服务异常才停止。任务 `screenshots.json` 记录每张图的处理状态、候选时间和判断回复，区分失败与未尝试。

## 测试

- 后端：`python -m unittest discover -s tests -q`
- 文档渲染：`node --test tests/*.mjs`
- 界面：安装 Playwright 后运行 `node tests/test_interface.cjs`；使用 Edge 可设置环境变量 `LEARNINGDEX_BROWSER_CHANNEL=msedge`。该检查使用模拟后端，不调用模型或视频服务。
- 图表：`node tests/test_diagram_interface.cjs`（同样需要 Playwright）。检查语法错误隔离、滚动边界、源码编辑与撤销、对话及 PDF 渲染；设置 `LEARNINGDEX_DIAGRAM_DOCUMENT` 可核验本地学习文档。

## 文档

- `REQUIREMENTS.md` — 总需求
- `FRONTEND.md` — 前端界面需求
- `AGENTS.md` — 开发执行规则

## 项目结构

```
app/            后端与前端源码
  main.py       入口 + 后端接口
  config.py     配置加载（个人信息仅从注入文档/环境变量进入）
  llm.py        LLM 调用封装
  subtitle.py   字幕提取
  transcribe.py 语音转写（本地模型）
  shoot.py      视频帧抽取与多模态核验
  markdown_io.py 图片路径归一化与 Markdown 导出
  pdf_export.py  桌面 PDF 直接保存
  web_server.py  本地界面与归档图片服务
  agents.py     Agent 能力（讲解/核验/对话）
  search.py     资料查询模块（当前界面未使用）
  web/          前端界面、示例文档、文档渲染模块
tests/          单元测试
skills/         可插拔 skill
```
