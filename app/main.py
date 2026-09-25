import hashlib
import json
import os
import re
import shutil
import threading
import uuid

import webview

from . import agents, config, llm, markdown_io, search, shoot, skills, subtitle, transcribe, web_server

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
DEFAULT_STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


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
    for name in ("final.md", "draft.md", "doc.md"):
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


def _save_output(url, info, doc, cfg=None):
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
    return {"subtitle": sub_path, "doc": doc_path}


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
                               self.current_taskdir, not self.current_taskdir and not self.current_doc),
                         daemon=True).start()

    def _stream_worker(self, request_id, user_text, stream, token, taskdir, general):
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
                elif general:
                    self._save_history("general")
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

    def list_histories(self):
        d = _state_dir(self.cfg)
        out = []
        if os.path.isdir(d):
            for name in os.listdir(d):
                p = os.path.join(d, name, "chat.json")
                if os.path.exists(p):
                    try:
                        out.append({"id": name, "title": _task_title(os.path.join(d, name), name),
                                    "count": len(self._load_history(name)),
                                    "mtime": os.path.getmtime(p)})
                    except OSError:
                        pass
        out.sort(key=lambda x: x["mtime"], reverse=True)
        return {"ok": True, "histories": out}

    def load_history(self, tid):
        if not re.match(r"^[A-Za-z0-9_\-]+$", tid or ""):
            return {"ok": False, "error": "非法任务标识"}
        with self._chat_lock:
            self._context_token += 1
        self.history = self._load_history(tid)
        self.current_doc = None
        if tid == "general":
            self.current_taskdir = ""
            self.current_url = ""
            return {"ok": True, "id": tid, "url": "", "history": self.history,
                    "doc": "", "taskdir": ""}
        doc = ""
        self.current_taskdir = os.path.join(_state_dir(self.cfg), tid)
        self.current_url = _source_url(self.current_taskdir, tid)
        dp = next((os.path.join(self.current_taskdir, name) for name in
                   ("draft.md", "final.md", "doc.md")
                   if os.path.exists(os.path.join(self.current_taskdir, name))), "")
        if os.path.exists(dp):
            with open(dp, encoding="utf-8") as f:
                doc = f.read()
            self.current_doc = doc
        return {"ok": True, "id": tid, "title": _task_title(self.current_taskdir, tid),
                "url": self.current_url, "history": self.history, "doc": doc,
                "taskdir": self.current_taskdir}

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
                "url": self.current_url,
                "taskdir": self.current_taskdir, "history": self.history}

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

    def export_md(self, content, default_name="学习笔记.md"):
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
            markdown_io.export_markdown(content, path, self.current_taskdir)
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
        if screenshots and info.get("segments"):
            self._emit("正在截取视频截图")
            try:
                doc = shoot.capture(doc, url, os.path.join(_state_dir(self.cfg), tid),
                                    self.cfg, validate=self.cfg.get("shot_validate", True))
            except Exception as e:
                doc = shoot.SHOT_RE.sub("", doc)
                note = f"截图处理失败：{e}"
        self._emit("正在拟定任务标题")
        try:
            info["task_title"] = agents.suggest_title(self.cfg, info, doc)
        except Exception:
            info["task_title"] = (info.get("title") or "").strip()
        saved = _save_output(url, info, doc, self.cfg)
        self.current_taskdir = os.path.dirname(saved["doc"])
        self.current_doc = doc
        self.history = []
        self._save_history(tid)
        return {"ok": True, "doc": doc, "info": info, "title": _task_title(self.current_taskdir, tid), "note": note, "saved": saved,
                "taskdir": self.current_taskdir, "id": tid}


def main():
    api = Api()
    webview.create_window(
        "视频学习助手",
        web_server.create_app(WEB_DIR, lambda: _state_dir(api.cfg)),
        js_api=api,
        width=1000,
        height=750,
    )
    webview.start()


if __name__ == "__main__":
    main()
