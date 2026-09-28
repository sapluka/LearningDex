import hashlib
import os
import re
import site
import time
import urllib.request
import uuid

import yt_dlp
from faster_whisper import WhisperModel

from . import bilibili, subtitle
from . import runtime_paths


def _preload_cuda_dlls():
    try:
        roots = list(site.getsitepackages())
        try:
            roots.append(site.getusersitepackages())
        except Exception:
            pass
        dirs = []
        for root in roots:
            for sub in ("nvidia/cublas/bin", "nvidia/cuda_runtime/bin",
                        "nvidia/cuda_nvrtc/bin", "nvidia/cudnn/bin"):
                p = os.path.join(root, sub)
                if os.path.isdir(p) and p not in dirs:
                    dirs.append(p)
        if dirs:
            os.environ["PATH"] = ";".join(dirs) + ";" + os.environ.get("PATH", "")
            for d in dirs:
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass
    except Exception:
        pass


_preload_cuda_dlls()

ROOT = str(runtime_paths.data_root())
CACHE_DIR = os.path.join(ROOT, "cache", "audio")
MODEL_FILES = ["config.json", "model.bin", "tokenizer.json"]
MODEL_EXTRA = ["vocabulary.txt", "vocabulary.json", "preprocessor_config.json"]
MODEL_MIRROR = "https://hf-mirror.com/{repo}/resolve/main/"
TURBO = "large-v3-turbo"
TURBO_REPO = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"


def _bvid(url):
    m = re.search(r"BV[0-9A-Za-z]+", url)
    return m.group(0) if m else None


def _model_dir(size):
    return os.path.join(ROOT, "cache", "models", "whisper-" + size)


def ensure_model(size="base"):
    d = _model_dir(size)
    os.makedirs(d, exist_ok=True)
    repo = TURBO_REPO if size == TURBO else f"SYSTRAN/faster-whisper-{size}"
    base = MODEL_MIRROR.format(repo=repo)
    for f in MODEL_FILES + MODEL_EXTRA:
        p = os.path.join(d, f)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            continue
        try:
            req = urllib.request.Request(base + f, headers={"User-Agent": "python"})
            with urllib.request.urlopen(req, timeout=300) as r, open(p, "wb") as out:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
                    got += len(chunk)
                if total and got < total:
                    raise urllib.error.HTTPError(url=req.full_url, code=0, msg="incomplete", hdrs=None, fp=None)
        except (OSError, urllib.error.URLError) as e:
            if os.path.exists(p):
                os.remove(p)
            if f in MODEL_FILES or not isinstance(e, urllib.error.HTTPError) or e.code != 404:
                raise
    return d


def download_audio(url, cfg=None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    bvid = _bvid(url)
    name = (bvid or "video_" + hashlib.sha256(url.encode()).hexdigest()[:12]) + ".m4a"
    path = os.path.join(CACHE_DIR, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path, False
    temporary = path + "." + uuid.uuid4().hex + ".m4a"
    if cfg is not None:
        subtitle.configure(cfg)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": temporary,
        "quiet": True,
        "noplaylist": True,
    }
    if "bilibili" in url.lower():
        opts.update(subtitle.bilibili_options())
    try:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                bilibili.configure(ydl)
                ydl.download([url])
        except Exception as e:
            if "412" not in str(e):
                raise
            subtitle._refresh()
            time.sleep(2)
            opts.update(subtitle.bilibili_options())
            with yt_dlp.YoutubeDL(opts) as ydl:
                bilibili.configure(ydl)
                ydl.download([url])
        if not os.path.isfile(temporary) or os.path.getsize(temporary) == 0:
            raise RuntimeError("音频下载未生成有效文件")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return path, True


def transcribe(path, model_size="base", language="zh"):
    try:
        model = WhisperModel(ensure_model(TURBO), device="cuda", compute_type="float16")
        used = f"{TURBO}(cuda)"
    except Exception:
        model = WhisperModel(ensure_model(model_size), device="cpu", compute_type="int8")
        used = f"{model_size}(cpu)"
    segments, _info = model.transcribe(path, language=language, vad_filter=True)
    parts = []
    segs = []
    for s in segments:
        parts.append(s.text)
        t = (s.text or "").strip()
        if t:
            segs.append({"from": s.start, "to": s.end, "text": t})
    return "".join(parts).strip(), used, segs


def transcribe_video(url, cfg=None, model_size="base"):
    start = time.time()
    path, _downloaded = download_audio(url, cfg)
    dl = round(time.time() - start, 1)
    start = time.time()
    text, used, segs = transcribe(path, model_size=model_size)
    asr = round(time.time() - start, 1)
    return {"subtitle": text, "used": used, "segments": segs, "download_s": dl, "asr_s": asr, "audio": path}
