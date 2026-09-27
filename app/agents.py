from . import llm
from .skills import get as _get_skill
from .shot_status import ShotError, validation_error
from urllib.parse import urlsplit

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
    "根据学习文档，在保证可理解性的前提下，只在合适、有需要的地方安排截图。"
    "先组织完整的讲解，再为难以仅靠文字理解的图形结构、操作步骤或视觉对比选择画面。"
    "通常连续几段完整讲解后才按需要插图，不要一句话配一张图，也不要为每个名词单独配图。"
    "同一组相关知识点尽量共用一张图；只有操作步骤或前后对比确实需要时才连续配图，并说明各图的作用。"
    "已有示意图或文字已讲清楚时不要重复截图；纯概念可以不配图，不按固定张数凑图。"
    "在对应段落插入截图占位符，格式严格为：![一句话描述](SHOT:分:秒)。"
    "时间取自下方字幕的时间戳，只描述该时间附近实际应出现的画面，不把抽象结论当成可截取的画面；"
    "后续程序会核验画面，无效截图不会插入。"
)

DIAGRAM_INSTRUCTION = (
    "遇到适合用图的场景（推导过程、流程、判定分支、知识结构关系等），"
    "请用 Mermaid 流程图（```mermaid 代码块）表达，帮助理解；图形简洁、节点用中文标注。"
    "节点 ID 使用英文字母和数字；中文标签用双引号包住，标签内的双引号写成 #quot;，"
    "括号等符号也须放在带引号的标签内。换行只使用 <br/>。"
    '例如：graph LR\nA["写作完成<br/>#quot;检查结果#quot;"] --> B["下一步"]。'
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


def suggest_title(cfg, info, doc):
    """为已完成的学习文档拟一个任务标题。"""
    msgs = [
        {"role": "system", "content": "根据学习文档拟一个准确、简短的中文任务标题，突出具体主题。不要照搬视频编号、泛称或口语化标题。只输出标题，不加引号、序号或解释。"},
        {"role": "user", "content": f"视频原标题：{info.get('title') or ''}\n\n学习文档：\n{(doc or '')[:12000]}"},
    ]
    title = (llm.text(cfg, msgs, max_tokens=80) or "").strip()
    title = title.splitlines()[0].strip().strip("#*《》“”\"' ")
    if not title or len(title) > 50:
        raise ValueError("生成的任务标题无效")
    return title


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


def validate_frame(cfg, image_path, caption=""):
    """把截图交给多模态模型判断是否有效。"""
    try:
        import base64
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        msgs = [{"role": "user", "content": [
            {"type": "text", "text": f"这是视频的一帧截图（意图：{caption}）。它是否清晰、与意图相关、能用于说明该知识点？只回答“是”或“否”。"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ]}]
        options = {"max_tokens": 1024}
        if urlsplit(cfg.get("base_url") or "").hostname == "api.deepseek.com":
            options["extra_body"] = {"thinking": {"type": "disabled"}}
        r = llm.text(cfg, msgs, **options)
    except Exception as error:
        raise validation_error(error) from error
    answer = (r or "").strip()
    if answer.startswith("是"):
        return True
    if answer.startswith("否"):
        return False
    raise ShotError("validation_response")
