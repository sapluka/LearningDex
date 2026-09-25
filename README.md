# LearningDex

视频学习辅助 Agent（编辑器 + Agent 一体化）：输入视频链接，自动提取字幕或本地转写，由 Agent 生成可编辑的 Markdown 学习文档，支持对话提问、联网查词、导出笔记。

## 运行

使用 Python 3.9 及以上版本，安装 `requirements.txt` 后运行 `python -m app.main`。首次转写会下载本地模型；界面静态资源已随项目提供，打开历史任务不需要访问前端 CDN。

如需修改前端源码，在 `app/web/` 运行 `npm ci` 和 `npm run build`，再启动桌面应用。

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
  agents.py     Agent 能力（讲解/核验/对话/选区提问）
  search.py     联网查词
  web/          前端界面、示例文档、文档渲染模块
tests/          单元测试
skills/         可插拔 skill
```
