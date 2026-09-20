import os
import re
import subprocess
import tempfile
import time

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


def _hhmmss(sec):
    sec = max(0, int(sec))
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def _grab(url, sec, imgdir, idx, cfg):
    if not FFMPEG:
        return None
    start = max(0, sec - 1)
    end = sec + 1
    seg = os.path.join(tempfile.gettempdir(), f"learndex_shot_{idx}.mp4")
    if os.path.exists(seg):
        try:
            os.remove(seg)
        except OSError:
            pass
    subtitle.configure(cfg)
    opts = {
        "format": "bv*[height<=720]/bv*/b",
        "outtmpl": seg,
        "quiet": True,
        "noplaylist": True,
        "ffmpeg_location": FFMPEG,
        "download_sections": f"*{_hhmmss(start)}-{_hhmmss(end)}",
        "merge_output_format": "mp4",
    }
    if "bilibili" in url.lower():
        opts["cookiefile"] = subtitle._cookie_source()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        return None
    if not os.path.exists(seg):
        return None
    out = os.path.join(imgdir, f"shot_{idx}.jpg")
    try:
        subprocess.run([FFMPEG, "-y", "-ss", "1", "-i", seg, "-frames:v", "1", "-q:v", "2", out],
                       capture_output=True, timeout=60)
    except Exception:
        return None
    try:
        os.remove(seg)
    except OSError:
        pass
    return out if os.path.exists(out) else None


def capture(md, url, taskdir, cfg, validate=True):
    shots = parse_shots(md)
    if not shots:
        return md
    imgdir = os.path.join(taskdir, "images")
    os.makedirs(imgdir, exist_ok=True)
    for idx, (full, cap, t) in enumerate(shots, 1):
        sec = _to_seconds(t)
        path = _grab(url, sec, imgdir, idx, cfg)
        if not path:
            continue
        if validate:
            from . import agents
            if not agents.validate_frame(cfg, path, cap):
                try:
                    os.remove(path)
                except OSError:
                    pass
                continue
        md = md.replace(full, f"![{cap}](images/shot_{idx}.jpg)")
        time.sleep(0.2)
    md = SHOT_RE.sub("", md)
    return md