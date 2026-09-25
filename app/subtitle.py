import hashlib
import html
import http.cookiejar
import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request

import yt_dlp

LANGS = ("zh-Hans", "zh-CN", "zh", "en")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

MIXIN_KEY = "560c52ccd288fed045859ed18bffd973"
MIXIN_ENC_TAB = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]

_cfg = {}
_jar = None
_cookie_path = None


def configure(cfg):
    global _cfg, _jar, _cookie_path
    _cfg = cfg or {}
    _jar = None
    _cookie_path = None


def _sess_cookie(value):
    return http.cookiejar.Cookie(
        version=0, name="SESSDATA", value=value,
        port=None, port_specified=False,
        domain=".bilibili.com", domain_specified=True, domain_initial_dot=True,
        path="/", path_specified=True, secure=True,
        expires=time.time() + 30 * 86400, discard=False,
        comment=None, comment_url=None, rest={}, rfc2109=False,
    )


def _write_netscape():
    global _cookie_path
    _cookie_path = os.path.join(tempfile.gettempdir(), "learndex_bili_cookies.txt")
    with open(_cookie_path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in _jar:
            d = "." + c.domain.lstrip(".")
            line = "\t".join([d, "TRUE", "/", "FALSE", str(int(c.expires or 0)), c.name, c.value])
            f.write(line + "\n")


def _external_cookies():
    f = (_cfg.get("cookies_file") or "").strip()
    if f and os.path.exists(f):
        normalized = _normalize_cookies(f)
        if normalized:
            return normalized
    text = (_cfg.get("cookies_text") or "").strip()
    if text:
        p = os.path.join(tempfile.gettempdir(), "learndex_bili_cookies_custom.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return _normalize_cookies(p)
    return None


def _normalize_cookies(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = fh.read()
    except (OSError, UnicodeDecodeError):
        return None
    norm = data.replace("#HttpOnly_.", ".")
    p = os.path.join(tempfile.gettempdir(), "learndex_bili_cookies_norm.txt")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(norm)
    return p


def _load_cookies_into(jar, path):
    try:
        mj = http.cookiejar.MozillaCookieJar(path)
        mj.load(ignore_discard=True, ignore_expires=True)
        for c in mj:
            jar.set_cookie(c)
    except Exception:
        pass


def _jar_ensure():
    global _jar
    if _jar is not None:
        return _jar
    jar = http.cookiejar.CookieJar()
    ext = _external_cookies()
    if ext:
        _load_cookies_into(jar, ext)
    else:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        opener.addheaders = [("User-Agent", UA), ("Referer", "https://www.bilibili.com/")]
        try:
            opener.open("https://www.bilibili.com/", timeout=15)
        except OSError:
            pass
    sess = (_cfg.get("bili_sessdata") or "").strip()
    if sess and not ext:
        jar.set_cookie(_sess_cookie(sess))
    _jar = jar
    _write_netscape()
    return _jar


def _refresh():
    global _jar, _cookie_path
    _jar = None
    _cookie_path = None


def _buivid_boost():
    try:
        obj = _download_json("https://api.bilibili.com/x/frontend/finger/spi")
        d = obj.get("data") or {}
        now = time.time() + 30 * 86400
        for name, val in (("buvid3", d.get("b_3")), ("buvid4", d.get("b_4"))):
            if not val:
                continue
            _jar.set_cookie(http.cookiejar.Cookie(
                version=0, name=name, value=val, port=None, port_specified=False,
                domain=".bilibili.com", domain_specified=True, domain_initial_dot=True,
                path="/", path_specified=True, secure=False,
                expires=now, discard=False, comment=None, comment_url=None,
                rest={}, rfc2109=False))
        _write_netscape()
    except Exception:
        pass


def _cookie_source():
    ext = _external_cookies()
    if ext:
        _jar_ensure()
        return ext
    _jar_ensure()
    _buivid_boost()
    return _cookie_path


def _pick(subs):
    if not subs:
        return None
    languages = [lang for prefix in LANGS for lang in subs if lang == prefix or lang.startswith(prefix + "-")]
    languages += [lang for lang in subs if lang not in languages]
    for lang in languages:
        for ext in ("json", "json3", "vtt", "srt"):
            for item in subs[lang]:
                if item.get("ext") == ext and (item.get("url") or item.get("data")):
                    return item
    return None


def _norm_lan(l):
    return (l or "").split("-")[0].lower()


def _pick_bili_sub(subs):
    for s in subs:
        if _norm_lan(s.get("lan")) == "zh":
            return s
    for s in subs:
        if _norm_lan(s.get("lan")) == "en":
            return s
    return subs[0]


def _parse_time(value):
    parts = value.replace(",", ".").split(":")
    try:
        return sum(float(part) * 60 ** power for power, part in enumerate(reversed(parts)))
    except ValueError:
        return None


def _parse_cues(data):
    segments = []
    for block in re.split(r"\r?\n\s*\r?\n", data):
        lines = block.strip().splitlines()
        index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if index is None:
            continue
        start, end = lines[index].split("-->", 1)
        fr = _parse_time(start.strip())
        to = _parse_time(end.strip().split()[0])
        text = html.unescape(re.sub(r"<[^>]+>", "", " ".join(lines[index + 1:]))).strip()
        if fr is not None and text and (not segments or segments[-1]["text"] != text):
            segments.append({"from": fr, "to": to, "text": text})
    return segments


def _parse_json3(data):
    segments = []
    for event in json.loads(data).get("events", []):
        text = "".join(seg.get("utf8", "") for seg in event.get("segs", [])).strip()
        if text:
            fr = float(event.get("tStartMs", 0)) / 1000
            to = fr + float(event.get("dDurationMs", 0)) / 1000
            segments.append({"from": fr, "to": to, "text": text})
    return segments


def _download_subtitle(item):
    data = item.get("data")
    if data is None:
        req = urllib.request.Request(item["url"], headers=item.get("http_headers") or {"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
    if isinstance(data, bytes):
        data = data.decode("utf-8-sig", "ignore")
    ext = item.get("ext")
    if ext in ("vtt", "srt"):
        return _parse_cues(data)
    if ext == "json3":
        return _parse_json3(data)
    if ext == "json":
        obj = json.loads(data)
        return _segments_from_json(obj)
    return []


def _download_json(url):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar_ensure()))
    opener.addheaders = [("User-Agent", UA), ("Referer", "https://www.bilibili.com/")]
    with opener.open(url, timeout=30) as r:
        data = r.read().decode("utf-8", "ignore").strip()
    i = data.find("(")
    if i >= 0 and data.rstrip().endswith(")"):
        data = data[i + 1:data.rfind(")")]
    return json.loads(data)


def _wbi_keys():
    obj = _download_json("https://api.bilibili.com/x/web-interface/nav")
    img = ((obj.get("data") or {}).get("wbi_img") or {}).get("img_url") or ""
    sub = ((obj.get("data") or {}).get("wbi_img") or {}).get("sub_url") or ""
    return img.rsplit("/", 1)[-1].split(".")[0], sub.rsplit("/", 1)[-1].split(".")[0]


def _mixin(orig):
    return "".join(orig[i] for i in MIXIN_ENC_TAB)[:32]


def _wbi_sign(params, img_key, sub_key):
    params["wts"] = int(time.time())
    query = urllib.parse.urlencode(dict(sorted(params.items())))
    params["w_rid"] = hashlib.md5((query + _mixin(img_key + sub_key)).encode()).hexdigest()
    return params


def _bili_segments(bvid):
    if not bvid:
        return []
    try:
        obj = _download_json("https://api.bilibili.com/x/web-interface/view?bvid=" + bvid)
        cid = (obj.get("data") or {}).get("cid")
        if not cid:
            return []
        img_key, sub_key = _wbi_keys()
        params = _wbi_sign({"bvid": bvid, "cid": int(cid)}, img_key, sub_key)
        pobj = _download_json("https://api.bilibili.com/x/player/wbi/v2?" + urllib.parse.urlencode(params))
        subs = ((pobj.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        if not subs:
            return []
        s = _pick_bili_sub(subs)
        u = s.get("subtitle_url") or ""
        if u and not u.startswith("http"):
            u = "https:" + u
        return _subtitle_segments(u) if u else []
    except Exception:
        return []


def _subtitle_segments(url):
    return _segments_from_json(_download_json(url))


def _segments_from_json(obj):
    body = obj.get("body") or (obj.get("data") or {}).get("body") or []
    segs = []
    for s in body:
        c = (s.get("content") or "").strip()
        if not c:
            continue
        try:
            fr = float(s.get("from")) if s.get("from") is not None else None
        except (TypeError, ValueError):
            fr = None
        try:
            to = float(s.get("to")) if s.get("to") is not None else None
        except (TypeError, ValueError):
            to = None
        segs.append({"from": fr, "to": to, "text": c})
    return segs


def _extract(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    sub = _pick(info.get("subtitles")) or _pick(info.get("automatic_captions"))
    segs = []
    err = ""
    if sub:
        try:
            segs = _download_subtitle(sub)
        except Exception as e:
            err = str(e)
    if not segs and "bilibili" in urllib.parse.urlparse(url).netloc.lower():
        m = re.search(r"BV[0-9A-Za-z]+", url)
        segs = _bili_segments(m.group(0) if m else None)
    text = "\n".join(s["text"] for s in segs)
    return {
        "title": info.get("title", ""),
        "uploader": info.get("uploader", ""),
        "duration": info.get("duration"),
        "subtitle": text,
        "segments": segs,
        "error": err,
    }


def extract(url, cfg=None):
    if cfg is not None:
        configure(cfg)
    for i in range(3):
        opts = {"skip_download": True, "quiet": True, "noplaylist": True}
        host = urllib.parse.urlparse(url).netloc.lower()
        if "bilibili" in host:
            opts["cookiefile"] = _cookie_source()
        try:
            return _extract(url, opts)
        except Exception as e:
            if "412" in str(e) and i < 2:
                _refresh()
                time.sleep(2 * (i + 1))
                continue
            raise
