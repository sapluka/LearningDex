import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import uuid

import webview

from . import agents, config, llm, markdown_io, pdf_export, search, shoot, skills, subtitle, transcribe, web_server, window_chrome
from .shot_status import report_note

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
DEFAULT_STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def _sample_source_dir(sample_id):
    if not isinstance(sample_id, str) or not re.fullmatch(r"BV[0-9A-Za-z]{6,20}", sample_id):
        return ""
    directory = os.path.join(WEB_DIR, "examples", sample_id)
    return directory if os.path.isfile(os.path.join(directory, "note.md")) else ""


def _state_dir(cfg):
    d = (cfg or {}).get("output_dir") or ""
    return d if d else DEFAULT_STATE_DIR


def _normalize_md(md):
    return (md or "").replace("\\==", "==")


def _task_id(url):
    match = re.search(r"BV[0-9A-Za-z]+", url or "")
    return match.group(0) if match else "video_" + hashlib.sha256((url or "").encode()).hexdigest()[:12]


def _source_info(taskdir):
    try:
        with open(os.path.join(taskdir, "source.json"), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def _source_url(taskdir, tid):
    url = _source_info(taskdir).get("url", "")
    if isinstance(url, str) and url:
        return url
    return "https://www.bilibili.com/video/" + tid if tid.startswith("BV") else ""


def _task_title(taskdir, tid):
    source = _source_info(taskdir)
    if source.get("task_title"):
        return source["task_title"]
    if source.get("title"):
        return source["title"]
    for name in ("draft.md", "final.md", "doc.md"):
        path = os.path.join(taskdir, name)
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    match = re.match(r"^#\s+(.+?)\s*$", line)
                    if match:
                        heading = match.group(1).strip("# ")
                        wrapped = re.match(r"^《(.+?)》学习文档$", heading)
                        if wrapped:
                            return wrapped.group(1)
                        if heading and not any(x in heading for x in ("这一讲到底", "学习文档", "测试笔记")):
                            return heading
                        break
        except OSError:
            pass
    return tid


def _save_output(url, info, doc, cfg=None, screenshot_plan=None):
    folder = os.path.join(_state_dir(cfg), _task_id(url))
    os.makedirs(folder, exist_ok=True)
    sub_path = os.path.join(folder, "subtitle.txt")
    doc_path = os.path.join(folder, "doc.md")
    with open(sub_path, "w", encoding="utf-8") as f:
        f.write(info.get("subtitle") or "")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(doc or "")
    with open(os.path.join(folder, "source.json"), "w", encoding="utf-8") as f:
        json.dump({"url": url, "title": info.get("title") or "",
                   "task_title": info.get("task_title") or ""}, f, ensure_ascii=False)
    for name, data in (("segments.json", info.get("segments")),
                       ("screenshots.json", info.get("screenshot_report"))):
        if data is not None:
            with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    if screenshot_plan is not None:
        with open(os.path.join(folder, "screenshot_plan.md"), "w", encoding="utf-8") as f:
            f.write(screenshot_plan)
    return {"subtitle": sub_path, "doc": doc_path}


def _screenshot_note(taskdir):
    try:
        with open(os.path.join(taskdir, "screenshots.json"), encoding="utf-8") as file:
            return report_note(json.load(file))
    except (OSError, ValueError, TypeError, AttributeError):
        return ""


class Api:
    def __init__(self):
        self.cfg = config.load()
        self.history = []
        self.current_doc = None
        self.current_url = ""
        self.current_taskdir = ""
        self._context_token = 0
        self._chat_lock = threading.Lock()

    def load_config(self):
        return self.cfg

    def get_window_state(self):
        return window_chrome.state(webview.windows[0])

    def control_window(self, action):
        try:
            return {"ok": True, **window_chrome.control(webview.windows[0], action)}
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def reset_context(self, doc=""):
        with self._chat_lock:
            self._context_token += 1
            self.history = []
            self.current_doc = doc
            self.current_url = ""
            self.current_taskdir = ""
        return {"ok": True}

    def update_doc(self, content):
        self.current_doc = markdown_io.normalize_markdown(content, self.current_taskdir)
        return {"ok": True}

    def save_final(self, content):
        self.update_doc(content)
        if not self.current_taskdir:
            return {"ok": True, "path": ""}
        try:
            path = os.path.join(self.current_taskdir, "final.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.current_doc)
            draft = os.path.join(self.current_taskdir, "draft.md")
            if os.path.exists(draft):
                os.remove(draft)
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": path}

    def generate_pdf(self, content, title="学习笔记"):
        saved = self.save_final(content)
        if not saved.get("ok"):
            return saved
        try:
            directory = self.cfg.get("pdf_output_dir") or _state_dir(self.cfg)
            directory = os.path.abspath(os.path.expanduser(directory))
            os.makedirs(directory, exist_ok=True)
            tid = os.path.basename(self.current_taskdir) if self.current_taskdir else ""
            path = pdf_export.pdf_path(directory, title, tid)
            pdf_export.print_current_page(path, webview.windows[0])
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _choose_directory(self, directory):
        try:
            directory = os.path.abspath(os.path.expanduser(directory))
            path = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG, directory=directory if os.path.isdir(directory) else "")
            if isinstance(path, (list, tuple)):
                path = path[0] if path else ""
            return {"ok": True, "path": path or ""}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def choose_output_dir(self):
        return self._choose_directory(_state_dir(self.cfg))

    def choose_pdf_output_dir(self):
        return self._choose_directory(self.cfg.get("pdf_output_dir") or _state_dir(self.cfg))

    def save_draft(self, content):
        self.update_doc(content)
        if not self.current_taskdir:
            return {"ok": True, "path": ""}
        try:
            path = os.path.join(self.current_taskdir, "draft.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.current_doc)
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": path}

    def save_config(self, c):
        c = {**self.cfg, **c}
        config.save(c)
        self.cfg = c
        return {"ok": True}

    def test_connection(self, c):
        c = {**self.cfg, **(c or {})}
        try:
            return {"ok": True, "reply": llm.test_connection(c)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _emit(self, text):
        try:
            webview.windows[0].evaluate_js(
                "window.__setStatus && window.__setStatus(%s)" % json.dumps(text, ensure_ascii=False))
        except Exception:
            pass

    def chat(self, message, request_id=None):
        request_id = request_id or uuid.uuid4().hex
        stream = agents.chat_stream(dict(self.cfg), list(self.history), message, self.current_doc)
        self._start_stream(request_id, message, stream)
        return {"ok": True, "id": request_id}

    def _emit_js(self, js):
        try:
            if webview.windows:
                webview.windows[0].evaluate_js(js)
        except Exception:
            pass

    def _start_stream(self, request_id, user_text, stream):
        threading.Thread(target=self._stream_worker,
                         args=(request_id, user_text, stream, self._context_token,
                               self.current_taskdir),
                         daemon=True).start()

    def _stream_worker(self, request_id, user_text, stream, token, taskdir):
        buf = []
        try:
            for chunk in stream:
                if token != self._context_token:
                    break
                buf.append(chunk)
                self._emit_js("window.__chatChunk && window.__chatChunk(%s,%s)" % (
                    json.dumps(request_id), json.dumps(chunk, ensure_ascii=False)))
        except Exception as e:
            error = "\n[错误] " + str(e)
            buf.append(error)
            self._emit_js("window.__chatChunk && window.__chatChunk(%s,%s)" % (
                json.dumps(request_id), json.dumps(error, ensure_ascii=False)))
        with self._chat_lock:
            if token == self._context_token:
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": "".join(buf)})
                if taskdir:
                    self._save_history(os.path.basename(taskdir))
        self._emit_js("window.__chatDone && window.__chatDone(%s)" % json.dumps(request_id))

    def ask_selection(self, selection, question, request_id=None):
        request_id = request_id or uuid.uuid4().hex
        stream = agents.answer_selection_stream(dict(self.cfg), selection, question, self.current_doc)
        user_text = "引用：" + selection + ("\n问题：" + question if question else "\n请解释这段内容")
        self._start_stream(request_id, user_text, stream)
        return {"ok": True, "id": request_id}

    def _fav_path(self):
        return os.path.join(_state_dir(self.cfg), "favorites.json")

    def _load_fav(self):
        try:
            with open(self._fav_path(), encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def list_favorites(self):
        favorites = self._load_fav()
        for item in favorites:
            tid = item.get("id", "")
            if re.fullmatch(r"[A-Za-z0-9_\-]+", tid):
                item["title"] = _task_title(os.path.join(_state_dir(self.cfg), tid), tid)
        return {"ok": True, "favorites": favorites}

    def toggle_favorite(self, tid, title=""):
        if not re.match(r"^[A-Za-z0-9_\-]+$", tid or ""):
            return {"ok": False, "error": "非法任务标识"}
        favs = self._load_fav()
        was = any(f.get("id") == tid for f in favs)
        if was:
            favs = [f for f in favs if f.get("id") != tid]
        else:
            favs.insert(0, {"id": tid, "title": title or tid})
        os.makedirs(_state_dir(self.cfg), exist_ok=True)
        with open(self._fav_path(), "w", encoding="utf-8") as f:
            json.dump(favs, f, ensure_ascii=False, indent=2)
        return {"ok": True, "favorited": not was, "favorites": favs}

    def _chat_path(self, tid):
        return os.path.join(_state_dir(self.cfg), tid, "chat.json")

    def _save_history(self, tid):
        if not re.match(r"^[A-Za-z0-9_\-]+$", tid or ""):
            return
        folder = os.path.join(_state_dir(self.cfg), tid)
        os.makedirs(folder, exist_ok=True)
        with open(self._chat_path(tid), "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def _load_history(self, tid):
        try:
            with open(self._chat_path(tid), encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def list_tasks(self):
        d = _state_dir(self.cfg)
        out = []
        if os.path.isdir(d):
            for name in sorted(os.listdir(d), reverse=True):
                p = os.path.join(d, name)
                if os.path.isdir(p) and os.path.exists(os.path.join(p, "doc.md")):
                    out.append({
                        "id": name,
                        "title": _task_title(p, name),
                        "has_doc": os.path.exists(os.path.join(p, "doc.md")),
                        "mtime": os.path.getmtime(p),
                    })
        return {"ok": True, "tasks": out}

    def load_task(self, tid):
        if not re.match(r"^[A-Za-z0-9_\-]+$", tid or ""):
            return {"ok": False, "error": "非法任务标识"}
        taskdir = os.path.join(_state_dir(self.cfg), tid)
        p = next((os.path.join(taskdir, name) for name in
                  ("draft.md", "final.md", "doc.md")
                  if os.path.exists(os.path.join(taskdir, name))), "")
        if not p:
            return {"ok": False, "error": "未找到该任务的文档"}
        try:
            with open(p, encoding="utf-8") as f:
                doc = f.read()
        except OSError as e:
            return {"ok": False, "error": str(e)}
        with self._chat_lock:
            self._context_token += 1
            self.current_taskdir = taskdir
            self.current_doc = doc
            self.current_url = _source_url(taskdir, tid)
            self.history = self._load_history(tid)
        return {"ok": True, "doc": doc, "id": tid, "title": _task_title(self.current_taskdir, tid),
                "note": _screenshot_note(taskdir),
                "url": self.current_url,
                "taskdir": self.current_taskdir, "history": self.history}

    def rename_task(self, tid, title):
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", tid or ""):
            return {"ok": False, "error": "非法任务标识"}
        if not isinstance(title, str):
            return {"ok": False, "error": "标题不能为空"}
        title = title.strip()
        if not title or len(title) > 50 or any(ord(char) < 32 for char in title):
            return {"ok": False, "error": "标题须为 1–50 个字符且不能包含换行"}
        base = os.path.realpath(_state_dir(self.cfg))
        taskdir = os.path.join(base, tid)
        target = os.path.realpath(taskdir)
        if os.path.commonpath((base, target)) != base or os.path.islink(taskdir):
            return {"ok": False, "error": "非法任务路径"}
        if not os.path.isfile(os.path.join(target, "doc.md")):
            return {"ok": False, "error": "未找到该任务"}
        source = _source_info(target)
        source["task_title"] = title
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target,
                                             prefix=".source-", suffix=".json", delete=False) as file:
                temporary = file.name
                json.dump(source, file, ensure_ascii=False, indent=2)
            os.replace(temporary, os.path.join(target, "source.json"))
        except OSError as error:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
            return {"ok": False, "error": str(error)}
        return {"ok": True, "title": title}

    def delete_task(self, tid):
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", tid or ""):
            return {"ok": False, "error": "非法任务标识"}
        base = os.path.realpath(_state_dir(self.cfg))
        target = os.path.realpath(os.path.join(base, tid))
        if os.path.commonpath((base, target)) != base or os.path.islink(os.path.join(base, tid)):
            return {"ok": False, "error": "非法任务路径"}
        if not os.path.isfile(os.path.join(target, "doc.md")):
            return {"ok": False, "error": "未找到该任务"}
        try:
            shutil.rmtree(target)
            favorites = [item for item in self._load_fav() if item.get("id") != tid]
            if os.path.isfile(self._fav_path()):
                with open(self._fav_path(), "w", encoding="utf-8") as f:
                    json.dump(favorites, f, ensure_ascii=False, indent=2)
        except OSError as e:
            return {"ok": False, "error": str(e)}
        if self.current_taskdir and os.path.realpath(self.current_taskdir) == target:
            self.reset_context()
        return {"ok": True}

    def list_skills(self):
        return {"ok": True, "skills": skills.list_skills()}

    def save_skill(self, name, content):
        if skills.save(name, content):
            return {"ok": True}
        return {"ok": False, "error": "非法技能名"}

    def delete_skill(self, name):
        return {"ok": skills.delete(name)}

    def lookup_term(self, term):
        res = search.search_term(term)
        if res:
            return {"ok": True, **res}
        return {"ok": False, "error": "未找到结果"}

    def export_md(self, content, default_name="学习笔记.md", sample_id=""):
        source_dir = self.current_taskdir
        if sample_id and not source_dir:
            source_dir = _sample_source_dir(sample_id)
            if not source_dir:
                return {"ok": False, "error": "示例资源不存在"}
        try:
            path = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG, save_filename=default_name)
        except Exception as e:
            return {"ok": False, "error": f"无法打开保存框：{e}"}
        if not path:
            return {"ok": False, "error": "已取消"}
        if isinstance(path, (list, tuple)):
            path = path[0]
        try:
            markdown_io.export_markdown(content, path, source_dir)
        except (OSError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": path}

    def extract(self, url):
        try:
            return {"ok": True, "info": subtitle.extract(url, self.cfg)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def generate_doc(self, url):
        with self._chat_lock:
            self._context_token += 1
        self.current_url = url
        self.current_taskdir = ""
        self._emit("正在提取视频字幕")
        info = subtitle.extract(url, self.cfg)
        note = ""
        if not info["subtitle"]:
            if not self.cfg.get("auto_transcribe", True):
                return {"ok": False, "error": f"未获取到字幕：{info.get('error') or '无字幕'}", "info": info}
            self._emit("正在转写语音（本地模型，较慢请稍候）")
            try:
                tr = transcribe.transcribe_video(
                    url, self.cfg, model_size=self.cfg.get("whisper_model", "base"))
            except Exception as e:
                return {"ok": False, "error": f"语音转写失败：{e}", "info": info}
            info["subtitle"] = tr["subtitle"]
            info["segments"] = tr.get("segments") or []
            info["transcribe_note"] = f"本地语音转写[{tr.get('used', '?')}]（下载{tr['download_s']}s+识别{tr['asr_s']}s）"
            if self.cfg.get("proofread", True):
                self._emit("正在核验字幕")
                try:
                    info["subtitle"] = agents.proofread(self.cfg, info["subtitle"])
                    info["transcribe_note"] += "+字幕核验"
                except Exception as e:
                    info["transcribe_note"] += f"（核验失败跳过：{e}）"
        if not info["subtitle"]:
            return {"ok": False, "error": f"未获取到字幕：{info.get('error') or '无字幕'}", "info": info}
        self._emit("正在生成笔记")
        screenshots = self.cfg.get("screenshots", True)
        try:
            doc = agents.summarize(self.cfg, info, screenshots=screenshots)
        except Exception as e:
            return {"ok": False, "error": f"生成失败：{e}", "info": info}
        tid = _task_id(url)
        screenshot_plan = doc if screenshots else None
        if screenshots:
            report = {"planned": 0, "captured": 0, "status": "failed", "failures": [{"code": "missing_timestamps"}]}
            if any(segment.get("from") is not None for segment in info.get("segments") or []):
                self._emit("正在截取视频截图")
                try:
                    doc = shoot.capture(doc, url, os.path.join(_state_dir(self.cfg), tid),
                                        self.cfg, validate=self.cfg.get("shot_validate", True), report=report)
                except Exception:
                    doc = shoot.SHOT_RE.sub("", doc)
                    report.update(status="partial" if report["captured"] else "failed")
                    report["failures"].append({"code": "unexpected"})
            else:
                doc = shoot.SHOT_RE.sub("", doc)
            info["screenshot_report"] = report
            note = report_note(report)
        else:
            info["screenshot_report"] = {"planned": 0, "captured": 0, "status": "disabled", "failures": []}
        self._emit("正在拟定任务标题")
        try:
            info["task_title"] = agents.suggest_title(self.cfg, info, doc)
        except Exception:
            info["task_title"] = (info.get("title") or "").strip()
        saved = _save_output(url, info, doc, self.cfg, screenshot_plan=screenshot_plan)
        self.current_taskdir = os.path.dirname(saved["doc"])
        self.current_doc = doc
        self.history = []
        self._save_history(tid)
        return {"ok": True, "doc": doc, "info": info, "title": _task_title(self.current_taskdir, tid), "note": note, "saved": saved,
                "taskdir": self.current_taskdir, "id": tid}


def main():
    window_chrome.initialize()
    api = Api()
    window = webview.create_window(
        "LearningDex",
        web_server.create_app(WEB_DIR, lambda: _state_dir(api.cfg)),
        js_api=api,
        width=1000,
        height=750,
    )
    window.events.before_show += window_chrome.prepare
    window.events.loaded += window_chrome.notify_state
    window.events.maximized += window_chrome.notify_state
    window.events.restored += window_chrome.notify_state
    webview.start(icon=window_chrome.ICON_PATH)


if __name__ == "__main__":
    main()
