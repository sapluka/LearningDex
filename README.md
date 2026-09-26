# LearningDex

视频学习辅助 Agent（编辑器 + Agent 一体化）：输入视频链接，自动提取字幕或本地转写，由 Agent 生成可编辑的 Markdown 学习文档，支持对话提问和导出笔记。

## 运行

使用 Python 3.9 及以上版本，安装 `requirements.txt` 后运行 `python -m app.main`。首次转写会下载本地模型；界面静态资源已随项目提供，打开历史任务不需要访问前端 CDN。

如需修改前端源码，在 `app/web/` 运行 `npm ci` 和 `npm run build`，再启动桌面应用。

「生成PDF」会直接保存文件，不打开打印窗口。保存位置在「设置 → PDF 输出目录」中选择；留空时使用笔记存储目录。任务归档在 `output/` 中，BV 号是视频来源编号，任务列表优先显示学习文档标题。

CDN 指通过互联网提供前端代码的服务。本项目的界面代码已随软件保存，打开界面和历史任务不依赖远程 CDN；解析视频和调用模型仍需相应网络连接。

界面采用黑白灰配色，图标使用本地 GitHub Octicons（来源和许可见 `app/web/icons/`）。从左侧任务入口打开已有任务，会同时恢复文档和对应对话；不提供独立历史对话查询。

## 测试

- 后端：`python -m unittest discover -s tests -q`
- 文档渲染：`node --test tests/*.mjs`
- 界面：安装 Playwright 后运行 `node tests/test_interface.cjs`；使用 Edge 可设置环境变量 `LEARNINGDEX_BROWSER_CHANNEL=msedge`。该检查使用模拟后端，不调用模型或视频服务。

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
