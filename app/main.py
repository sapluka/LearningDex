import json
import os
import re
import threading

import webview

from . import agents, config, llm, search, shoot, skills, subtitle, transcribe

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
DEFAULT_STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def _state_dir(cfg):
    d = (cfg or {}).get("output_dir") or ""
    return d if d else DEFAULT_STATE_DIR


def _normalize_md(md):
    return (md or "").replace("\\==", "==")


def _save_output(url, info, doc, cfg=None):
    m = re.search(r"BV[0-9A-Za-z]+", url)
    folder = os.path.join(_state_dir(cfg), m.group(0) if m else "video")
    os.makedirs(folder, exist_ok=True)
    sub_path = os.path.join(folder, "subtitle.txt")
    doc_path = os.path.join(folder, "doc.md")
    with open(sub_path, "w", encoding="utf-8") as f:
        f.write(info.get("subtitle") or "")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(doc or "")
    return {"subtitle": sub_path, "doc": doc_path}


class Api:
    def __init__(self):
        self.cfg = config.load()
        self.history = []
        self.current_doc = None
        self.current_url = ""

    def load_config(self):
        return self.cfg

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

    def chat(self, message):
        threading.Thread(target=self._chat_worker, args=(message,), daemon=True).start()
        return {"ok": True}

    def _emit_js(self, js):
        try:
            if webview.windows:
                webview.windows[0].evaluate_js(js)
        except Exception:
            pass

    def _chat_worker(self, message):
        buf = []
        try:
            for chunk in agents.chat_stream(self.cfg, self.history, message, self.current_doc):
                buf.append(chunk)
                self._emit_js("window.__chatChunk && window.__chatChunk(%s)"
                              % json.dumps(chunk, ensure_ascii=False))
        except Exception as e:
            self._emit_js("window.__chatChunk && window.__chatChunk(%s)"
                          % json.dumps("\n[错误] " + str(e), ensure_ascii=False))
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": "".join(buf)})
        m = re.search(r"BV[0-9A-Za-z]+", self.current_url or "")
        if m:
            self._save_history(m.group(0))
        self._emit_js("window.__chatDone && window.__chatDone()")

    def ask_selection(self, selection, question):
        threading.Thread(target=self._ask_worker, args=(selection, question), daemon=True).start()
        return {"ok": True}

    def _ask_worker(self, selection, question):
        try:
            for chunk in agents.answer_selection_stream(self.cfg, selection, question, self.current_doc):
                self._emit_js("window.__chatChunk && window.__chatChunk(%s)"
                              % json.dumps(chunk, ensure_ascii=False))
        except Exception as e:
            self._emit_js("window.__chatChunk && window.__chatChunk(%s)"
                          % json.dumps("\n[错误] " + str(e), ensure_ascii=False))
        self._emit_js("window.__chatDone && window.__chatDone()")

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
        return {"ok": True, "favorites": self._load_fav()}

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
                        out.append({"id": name, "count": len(self._load_history(name)),
                                    "mtime": os.path.getmtime(p)})
                    except OSError:
                        pass
        out.sort(key=lambda x: x["mtime"], reverse=True)
        return {"ok": True, "histories": out}

    def load_history(self, tid):
        if not re.match(r"^[A-Za-z0-9_\-]+$", tid or ""):
            return {"ok": False, "error": "非法任务标识"}
        self.history = self._load_history(tid)
        self.current_url = "https://www.bilibili.com/video/" + tid
        doc = ""
        dp = os.path.join(_state_dir(self.cfg), tid, "doc.md")
        if os.path.exists(dp):
            with open(dp, encoding="utf-8") as f:
                doc = f.read()
            self.current_doc = doc
        return {"ok": True, "id": tid, "history": self.history, "doc": doc,
                "taskdir": os.path.join(_state_dir(self.cfg), tid)}

    def list_tasks(self):
        d = _state_dir(self.cfg)
        out = []
        if os.path.isdir(d):
            for name in sorted(os.listdir(d), reverse=True):
                p = os.path.join(d, name)
                if os.path.isdir(p):
                    out.append({
                        "id": name,
                        "has_doc": os.path.exists(os.path.join(p, "doc.md")),
                        "mtime": os.path.getmtime(p),
                    })
        return {"ok": True, "tasks": out}

    def load_task(self, tid):
        if not re.match(r"^[A-Za-z0-9_\-]+$", tid or ""):
            return {"ok": False, "error": "非法任务标识"}
        p = os.path.join(_state_dir(self.cfg), tid, "doc.md")
        if not os.path.exists(p):
            return {"ok": False, "error": "未找到该任务的文档"}
        with open(p, encoding="utf-8") as f:
            doc = f.read()
        self.current_doc = doc
        self.current_url = "https://www.bilibili.com/video/" + tid
        return {"ok": True, "doc": doc, "id": tid,
                "taskdir": os.path.join(_state_dir(self.cfg), tid)}

    def list_skills(self):
        return {"ok": True, "skills": skills.list_skills()}

    def save_skill(self, name, content):
        if skills.save(name, content):
            return {"ok": True}
        return {"ok": False, "error": "非法技能名"}

    def delete_skill(self, name):
        return {"ok": skills.delete(name)}

    def explain(self, term):
        try:
            return {"ok": True, "answer": agents.explain_term(self.cfg, term)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def lookup_term(self, term):
        res = search.search_term(term)
        if res:
            return {"ok": True, **res}
        try:
            exp = agents.explain_term(self.cfg, term)
            return {"ok": True, "summary": exp, "source": "llm"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

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
        with open(path, "w", encoding="utf-8") as f:
            f.write(_normalize_md(content))
        return {"ok": True, "path": path}

    def end_study(self, url, final_md):
        m = re.search(r"BV[0-9A-Za-z]+", url)
        folder = os.path.join(_state_dir(self.cfg), m.group(0) if m else "video")
        os.makedirs(folder, exist_ok=True)
        p = os.path.join(folder, "final.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(_normalize_md(final_md))
        return {"ok": True, "path": p}

    def extract(self, url):
        try:
            return {"ok": True, "info": subtitle.extract(url, self.cfg)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def generate_doc(self, url):
        self.current_url = url
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
        m = re.search(r"BV[0-9A-Za-z]+", url)
        bvid = m.group(0) if m else "video"
        if screenshots and info.get("segments"):
            self._emit("正在截取视频截图")
            try:
                doc = shoot.capture(doc, url, os.path.join(_state_dir(self.cfg), bvid),
                                    self.cfg, validate=self.cfg.get("shot_validate", True))
            except Exception:
                pass
        saved = _save_output(url, info, doc, self.cfg)
        self.current_doc = doc
        self.history = []
        if m:
            self._save_history(bvid)
        self._emit("正在抽取名词")
        try:
            terms = agents.extract_terms(self.cfg, doc)
        except Exception:
            terms = []
        return {"ok": True, "doc": doc, "info": info, "note": note, "saved": saved,
                "terms": terms, "taskdir": os.path.join(_state_dir(self.cfg), bvid)}


def main():
    api = Api()
    webview.create_window(
        "视频学习助手",
        os.path.join(WEB_DIR, "index.html"),
        js_api=api,
        width=1000,
        height=750,
    )
    webview.start()


if __name__ == "__main__":
    main()