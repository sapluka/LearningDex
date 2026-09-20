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


def summarize(cfg, info):
    msgs = [
        {"role": "system", "content": lecture_system()},
        {"role": "user", "content": _prompt(info)},
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


def answer_selection(cfg, selection, question, doc=None):
    msgs = [
        {"role": "system", "content": CHAT_SYSTEM + _doc_block(doc)},
        {"role": "user", "content": f"文档选中内容：\n{selection}\n\n问题：{question}"},
    ]
    return llm.text(cfg, msgs)


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