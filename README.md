# LearningDex

视频学习辅助 Agent（编辑器 + Agent 一体化）：输入视频链接，自动提取字幕或本地转写，由 Agent 生成可编辑的 Markdown 学习文档，支持对话提问、联网查词、导出笔记。

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
  agents.py     Agent 能力（讲解/核验/对话/选区提问）
  search.py     联网查词
  web/          前端界面（HTML/JS/CSS）
tests/          单元测试
skills/         可插拔 skill
```

## 个人信息

API Key、B站 SESSDATA、cookies 等**不入库**，通过 `personal.py`（个人信息文档）或环境变量注入。模板见 `personal.example.py`。
