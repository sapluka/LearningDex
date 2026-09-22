from . import llm
from .skills import get as _get_skill

SYSTEM = (
    "你是视频学习助手。请将下方视频字幕整理成结构化的中文学习文档（markdown 格式），"
    "包含：核心要点、专有名词解释、内容脉络、关键结论。语言简洁准确。"
)

PROOF_SYSTEM = (
    "你是字幕校对员。请修复下列视频字幕中的错别字、乱码、断句与口语误识别，"
    "使其通顺合理且保持原意。只输出修正后的字幕全文，不要任何解释或额外内容。"
)


def load_skill(name):
    """从 skills 目录加载讲解 prompt（预留接口）。缺失返回 None。"""
    return _get_skill(name)


def lecture_system():
    return load_skill("讲解") or SYSTEM


def _prompt(info):
    return (
        f"视频标题：《{info.get('title')}》\n"
        f"UP主：{info.get('uploader')}\n"
        f"时长：{info.get('duration')} 秒\n\n"
        f"==== 字幕 ====\n{info.get('subtitle')}"
    )


SHOT_INSTRUCTION = (
    "在讲解过程中，凡是“配一张视频画面截图能显著帮助理解”的地方，插入一个截图占位符，"
    "格式严格为：![一句话描述](SHOT:分:秒)。时间是该内容在原视频中出现的时间点，"
    "取自下方带时间戳的字幕（用其时间戳）。只在确实需要看图处插入，不要滥用。"
)

DIAGRAM_INSTRUCTION = (
    "遇到适合用图的场景（推导过程、流程、判定分支、知识结构关系等），"
    "请用 Mermaid 流程图（```mermaid 代码块）表达，帮助理解；图形简洁、节点用中文标注。"
)


def _ts_transcript(segments):
    lines = []
    for s in segments:
        fr = s.get("from")
        if fr is None:
            continue
        lines.append(f"[{int(fr) // 60:02d}:{int(fr) % 60:02d}] {s.get('text', '')}")
    return "\n".join(lines)


def _body(info, screenshots=False):
    head = (f"视频标题：《{info.get('title')}》\n"
            f"UP主：{info.get('uploader')}\n"
            f"时长：{info.get('duration')} 秒\n\n")
    if screenshots and info.get("segments"):
        return head + "==== 带时间戳字幕 ====\n" + _ts_transcript(info["segments"])
    return head + "==== 字幕 ====\n" + (info.get("subtitle") or "")


def summarize(cfg, info, screenshots=False):
    sysmsg = lecture_system() + "\n\n" + DIAGRAM_INSTRUCTION
    if screenshots and info.get("segments"):
        sysmsg += "\n\n" + SHOT_INSTRUCTION
    msgs = [
        {"role": "system", "content": sysmsg},
        {"role": "user", "content": _body(info, screenshots)},
    ]
    return llm.text(cfg, msgs)


def proofread(cfg, text):
    msgs = [
        {"role": "system", "content": PROOF_SYSTEM},
        {"role": "user", "content": text},
    ]
    return llm.text(cfg, msgs)


CHAT_SYSTEM = "你是学习助手。请依据上下文与学习文档，用简洁准确的中文回答用户问题。"


def _doc_block(doc):
    return f"\n\n参考学习文档：\n{doc}" if doc else ""


def chat(cfg, history, question, doc=None):
    msgs = [{"role": "system", "content": CHAT_SYSTEM + _doc_block(doc)}] + history
    msgs.append({"role": "user", "content": question})
    return llm.text(cfg, msgs)


def chat_stream(cfg, history, question, doc=None):
    msgs = [{"role": "system", "content": CHAT_SYSTEM + _doc_block(doc)}] + history
    msgs.append({"role": "user", "content": question})
    yield from llm.stream(cfg, msgs)


def answer_selection(cfg, selection, question, doc=None):
    msgs = [
        {"role": "system", "content": CHAT_SYSTEM + _doc_block(doc)},
        {"role": "user", "content": f"文档选中内容：\n{selection}\n\n问题：{question}"},
    ]
    return llm.text(cfg, msgs)


def answer_selection_stream(cfg, selection, question, doc=None):
    msgs = [
        {"role": "system", "content": CHAT_SYSTEM + _doc_block(doc)},
        {"role": "user", "content": f"文档选中内容：\n{selection}\n\n问题：{question}"},
    ]
    yield from llm.stream(cfg, msgs)


def explain_term(cfg, term):
    msgs = [
        {"role": "system", "content": "你是一个词典。请用中文简明解释下列术语，并给出简短例子。"},
        {"role": "user", "content": term},
    ]
    return llm.text(cfg, msgs)


TERMS_SYSTEM = (
    "你是术语抽取器。请从下列学习文档中抽取专有名词/专业术语（排除常见词）。"
    "每行一个术语，直接输出术语本身，不要编号、不要解释、不要多余内容。"
)


def _parse_terms(text):
    out = []
    for line in (text or "").splitlines():
        s = line.strip().lstrip("-*•").strip()
        s = s.lstrip("0123456789.、) ").strip()
        if s and len(s) <= 40 and s not in out:
            out.append(s)
    return out


def extract_terms(cfg, doc):
    txt = llm.text(cfg, [
        {"role": "system", "content": TERMS_SYSTEM},
        {"role": "user", "content": doc},
    ])
    return _parse_terms(txt)


def validate_frame(cfg, image_path, caption=""):
    """把截图交给多模态模型判断是否有效；不支持视觉则默认通过。"""
    try:
        import base64
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        msgs = [{"role": "user", "content": [
            {"type": "text", "text": f"这是视频的一帧截图（意图：{caption}）。它是否清晰、与意图相关、能用于说明该知识点？只回答“是”或“否”。"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ]}]
        r = llm.text(cfg, msgs, max_tokens=5)
        return "否" not in (r or "")
    except Exception:
        return True