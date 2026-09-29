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
MODEL_VOCAB = ("vocabulary.json", "vocabulary.txt")
MODEL_MIRROR = "https://hf-mirror.com/{repo}/resolve/main/"
TURBO = "large-v3-turbo"
TURBO_REPO = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"


def _bvid(url):
    m = re.search(r"BV[0-9A-Za-z]+", url)
    return m.group(0) if m else None


def _model_dir(size):
    return os.path.join(ROOT, "cache", "models", "whisper-" + size)


def ensure_model(size="base", progress=None):
    d = _model_dir(size)
    os.makedirs(d, exist_ok=True)
    repo = TURBO_REPO if size == TURBO else f"SYSTRAN/faster-whisper-{size}"
    base = MODEL_MIRROR.format(repo=repo)
    def download(f):
        p = os.path.join(d, f)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return True
        if progress:
            progress(f"正在下载 {size} 转写模型（{f}）")
        try:
            req = urllib.request.Request(base + f, headers={"User-Agent": "python"})
            with urllib.request.urlopen(req, timeout=300) as r, open(p, "wb") as out:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                reported = -1
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
                    got += len(chunk)
                    if progress and total:
                        bucket = min(10, got * 10 // total)
                        if bucket != reported:
                            reported = bucket
                            progress(f"正在下载 {size} 转写模型（{f} {bucket * 10}%）")
                if total and got < total:
                    raise urllib.error.HTTPError(url=req.full_url, code=0, msg="incomplete", hdrs=None, fp=None)
        except (OSError, urllib.error.URLError) as e:
            if os.path.exists(p):
                os.remove(p)
            if isinstance(e, urllib.error.HTTPError) and e.code == 404:
                return False
            raise
        return True

    for f in MODEL_FILES:
        if not download(f):
            raise FileNotFoundError(f"转写模型缺少 {f}")
    if not any(os.path.getsize(os.path.join(d, f)) > 0
               for f in MODEL_VOCAB if os.path.isfile(os.path.join(d, f))):
        for f in MODEL_VOCAB:
            if download(f):
                break
        else:
            raise FileNotFoundError("转写模型缺少词表")
    return d


def download_audio(url, cfg=None, progress=None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    bvid = _bvid(url)
    name = (bvid or "video_" + hashlib.sha256(url.encode()).hexdigest()[:12]) + ".m4a"
    path = os.path.join(CACHE_DIR, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        if progress:
            progress("正在使用已下载的音频")
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
    if progress:
        progress("正在下载视频音频")
        reported = [-1]

        def on_download(status):
            if status.get("status") != "downloading":
                return
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            if not total:
                return
            bucket = min(10, (status.get("downloaded_bytes") or 0) * 10 // total)
            if bucket != reported[0]:
                reported[0] = bucket
                progress(f"正在下载视频音频（{bucket * 10}%）")

        opts["progress_hooks"] = [on_download]
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


def transcribe(path, model_size="base", language="zh", progress=None):
    if model_size not in ("base", "small", TURBO):
        raise ValueError("不支持的转写模型")

    def recognize(model, used):
        if progress:
            progress("正在识别语音")
        segments, info = model.transcribe(path, language=language, vad_filter=True)
        parts = []
        segs = []
        last_minute = -1
        for s in segments:
            parts.append(s.text)
            t = (s.text or "").strip()
            if t:
                segs.append({"from": s.start, "to": s.end, "text": t})
            minute = int(s.end // 60)
            if progress and minute > last_minute:
                last_minute = minute
                duration = getattr(info, "duration", None)
                suffix = f" / {int(duration // 60)} 分钟" if duration else ""
                progress(f"正在识别语音（已处理 {minute} 分钟{suffix}）")
        return "".join(parts).strip(), used, segs

    if model_size == TURBO:
        try:
            model_path = ensure_model(TURBO, progress=progress)
            if progress:
                progress("正在加载 turbo GPU 转写模型")
            model = WhisperModel(model_path, device="cuda", compute_type="float16")
            return recognize(model, f"{TURBO}(cuda)")
        except Exception as error:
            if progress:
                progress(f"GPU 模型不可用，改用 base CPU（{type(error).__name__}）")
            model_size = "base"

    model_path = ensure_model(model_size, progress=progress)
    if progress:
        progress(f"正在加载 {model_size} CPU 转写模型")
    model = WhisperModel(model_path, device="cpu", compute_type="int8")
    return recognize(model, f"{model_size}(cpu)")


def transcribe_video(url, cfg=None, model_size="base", progress=None):
    start = time.time()
    path, _downloaded = download_audio(url, cfg, progress=progress)
    dl = round(time.time() - start, 1)
    start = time.time()
    text, used, segs = transcribe(path, model_size=model_size, progress=progress)
    asr = round(time.time() - start, 1)
    return {"subtitle": text, "used": used, "segments": segs, "download_s": dl, "asr_s": asr, "audio": path}
