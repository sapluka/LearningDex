import json
import urllib.parse
import urllib.request

UA = "Mozilla/5.0"


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def wiki_summary(term):
    """尝试中文维基（回退英文）获取术语摘要。"""
    try:
        q = urllib.parse.quote(term)
        try:
            d = _get_json(f"https://zh.wikipedia.org/api/rest_v1/page/summary/{q}")
        except Exception:
            d = _get_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{q}")
        ex = d.get("extract") or ""
        if ex:
            return {"summary": ex, "source": "wikipedia"}
    except Exception:
        pass
    return None


def search_term(term):
    """联网查找术语资料；失败返回 None。预留：可扩展更多搜索源。"""
    return wiki_summary(term)
