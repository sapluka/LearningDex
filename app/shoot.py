import glob
import os
import re
import subprocess
import tempfile
import time

import yt_dlp

from . import bilibili, subtitle
from .shot_status import ShotError

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = None

SHOT_RE = re.compile(r"!\[([^\]]*)\]\(SHOT:(\d+:\d{2}(?::\d{2})?)\)")


def parse_shots(md):
    return [(m.group(0), m.group(1), m.group(2)) for m in SHOT_RE.finditer(md or "")]


def _to_seconds(t):
    parts = [int(x) for x in t.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _download_video(url, cfg, tmpdir):
    """下载整段视频（纯视频流，<=720p）到临时文件；返回路径或 None。"""
    subtitle.configure(cfg)
    tmpl = os.path.join(tmpdir, "source.%(ext)s")
    opts = {
        "format": "bv*[height<=720]/bv*/b",
        "outtmpl": tmpl,
        "quiet": True,
        "noplaylist": True,
        "socket_timeout": 30,
    }
    if "bilibili" in url.lower():
        opts.update(subtitle.bilibili_options())
    for attempt in range(2):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                bilibili.configure(ydl)
                ydl.download([url])
            break
        except Exception as error:
            if "412" in str(error) and attempt == 0 and "bilibili" in url.lower():
                subtitle._refresh()
                time.sleep(2)
                opts.update(subtitle.bilibili_options())
                continue
            raise ShotError("download_rejected" if "412" in str(error) else "download_failed") from error
    files = [file for file in glob.glob(os.path.join(tmpdir, "source.*"))
             if not file.endswith((".part", ".ytdl")) and os.path.getsize(file) > 0]
    if not files:
        raise ShotError("download_failed")
    return files[0]


def _frame(video, sec, out):
    if not FFMPEG:
        return None
    try:
        subprocess.run([FFMPEG, "-y", "-ss", str(max(0, sec)), "-i", video,
                        "-frames:v", "1", "-q:v", "2", out],
                       capture_output=True, timeout=120, check=True)
    except Exception:
        return None
    return out if os.path.exists(out) else None


def _validate_candidate(cfg, path, caption, seconds, offset, attempts):
    from . import agents
    for retry in range(2):
        detail = {"seconds": seconds, "offset": offset, "request": retry + 1}
        attempts.append(detail)
        try:
            valid = agents.validate_frame(cfg, path, caption, details=detail)
            detail["status"] = "accepted" if valid else "rejected"
            return valid
        except ShotError as error:
            detail.update(error.details, status="error", code=error.code)
            if retry == 0 and error.code in ("validation_response", "validation_failed"):
                continue
            raise


def _finish_report(report):
    for item in report["shots"]:
        if item["status"] == "pending":
            item["status"] = "not_attempted"
    report["failed"] = sum(item["status"] == "failed" for item in report["shots"])
    report["skipped"] = sum(item["status"] == "not_attempted" for item in report["shots"])
    if report["failures"]:
        report["status"] = "partial" if report["captured"] else "failed"


def capture(md, url, taskdir, cfg, validate=True, report=None):
    shots = parse_shots(md)
    report = report if report is not None else {}
    report.update(planned=len(shots), captured=0, failed=0, skipped=0, failures=[], status="complete",
        shots=[{"index": idx, "caption": cap, "time": t, "status": "pending", "attempts": []}
            for idx, (_, cap, t) in enumerate(shots, 1)])
    if not shots:
        report.update(status="failed", failures=[{"code": "no_plan"}])
        return md
    if not FFMPEG:
        report.update(status="failed", failures=[{"code": "ffmpeg_missing"}])
        _finish_report(report)
        return SHOT_RE.sub("", md)
    imgdir = os.path.join(taskdir, "images")
    os.makedirs(imgdir, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="learndex_video_") as tmpdir:
        try:
            video = _download_video(url, cfg, tmpdir)
            if not video:
                raise ShotError("download_failed")
        except ShotError as error:
            report.update(status="failed", failures=[{"code": error.code}])
            _finish_report(report)
            return SHOT_RE.sub("", md)
        consecutive_errors = 0
        for idx, (full, cap, t) in enumerate(shots, 1):
            item = report["shots"][idx - 1]
            out = os.path.join(imgdir, f"shot_{idx}.jpg")
            failure = "frame_failed"
            halted = False
            for offset in (0, 2, -2, 5):
                seconds = max(0, _to_seconds(t) + offset)
                if not _frame(video, seconds, out):
                    item["attempts"].append({"seconds": seconds, "offset": offset, "status": "frame_failed"})
                    continue
                if validate:
                    try:
                        valid = _validate_candidate(cfg, out, cap, seconds, offset, item["attempts"])
                    except ShotError as error:
                        failure = error.code
                        halted = failure in ("vision_unsupported", "validation_auth")
                        break
                    if not valid:
                        failure = "rejected"
                        try:
                            os.remove(out)
                        except OSError:
                            pass
                        continue
                md = md.replace(full, f"![{cap}](images/shot_{idx}.jpg)", 1)
                report["captured"] += 1
                item.update(status="accepted", image=f"images/shot_{idx}.jpg")
                break
            if item["status"] != "accepted":
                item.update(status="failed", code=failure)
                report["failures"].append({"time": t, "code": failure})
                if os.path.exists(out):
                    try:
                        os.remove(out)
                    except OSError:
                        pass
                consecutive_errors = consecutive_errors + 1 if failure in ("validation_response", "validation_failed") else 0
                if consecutive_errors >= 3:
                    report["failures"].append({"code": "validation_unavailable"})
                    halted = True
            else:
                consecutive_errors = 0
            if halted:
                break
    _finish_report(report)
    return SHOT_RE.sub("", md)
