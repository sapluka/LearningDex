import glob
import os
import re
import subprocess
import tempfile

import yt_dlp

from . import subtitle

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = None

SHOT_RE = re.compile(r"!\[([^\]]*)\]\(SHOT:(\d{1,2}:\d{2}(?::\d{2})?)\)")


def parse_shots(md):
    return [(m.group(0), m.group(1), m.group(2)) for m in SHOT_RE.finditer(md or "")]


def _to_seconds(t):
    parts = [int(x) for x in t.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _download_video(url, cfg):
    """下载整段视频（纯视频流，<=720p）到临时文件；返回路径或 None。"""
    subtitle.configure(cfg)
    tmpl = os.path.join(tempfile.gettempdir(), "learndex_src.%(ext)s")
    for old in glob.glob(os.path.join(tempfile.gettempdir(), "learndex_src.*")):
        try:
            os.remove(old)
        except OSError:
            pass
    opts = {
        "format": "bv*[height<=720]/bv*/b",
        "outtmpl": tmpl,
        "quiet": True,
        "noplaylist": True,
    }
    if "bilibili" in url.lower():
        opts["cookiefile"] = subtitle._cookie_source()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        return None
    files = glob.glob(os.path.join(tempfile.gettempdir(), "learndex_src.*"))
    return files[0] if files else None


def _frame(video, sec, out):
    if not FFMPEG:
        return None
    try:
        subprocess.run([FFMPEG, "-y", "-ss", str(max(0, sec)), "-i", video,
                        "-frames:v", "1", "-q:v", "2", out],
                       capture_output=True, timeout=120)
    except Exception:
        return None
    return out if os.path.exists(out) else None


def capture(md, url, taskdir, cfg, validate=True):
    shots = parse_shots(md)
    if not shots:
        return md
    imgdir = os.path.join(taskdir, "images")
    os.makedirs(imgdir, exist_ok=True)
    video = _download_video(url, cfg)
    if not video:
        return SHOT_RE.sub("", md)
    try:
        for idx, (full, cap, t) in enumerate(shots, 1):
            out = os.path.join(imgdir, f"shot_{idx}.jpg")
            if not _frame(video, _to_seconds(t), out):
                continue
            if validate:
                from . import agents
                if not agents.validate_frame(cfg, out, cap):
                    try:
                        os.remove(out)
                    except OSError:
                        pass
                    continue
            md = md.replace(full, f"![{cap}](images/shot_{idx}.jpg)")
    finally:
        try:
            os.remove(video)
        except OSError:
            pass
    return SHOT_RE.sub("", md)