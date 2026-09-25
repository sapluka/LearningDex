import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "skills")
_NAME_RE = re.compile(r"^[\w\u4e00-\u9fa5\-]{1,40}$")


def _path(name):
    if not name or not _NAME_RE.match(name):
        return None
    return os.path.join(SKILLS_DIR, name + ".md")


def _existing_path(name):
    md = _path(name)
    if not md:
        return None
    if os.path.isfile(md):
        return md
    txt = os.path.splitext(md)[0] + ".txt"
    return txt if os.path.isfile(txt) else None


def list_skills():
    out = []
    if not os.path.isdir(SKILLS_DIR):
        return out
    seen = set()
    for fn in sorted(os.listdir(SKILLS_DIR), key=lambda value: (os.path.splitext(value)[0], value.lower().endswith(".txt"))):
        if fn.lower().endswith((".md", ".txt")) and fn.lower() != "readme.md":
            name = os.path.splitext(fn)[0]
            if name in seen:
                continue
            p = os.path.join(SKILLS_DIR, fn)
            try:
                with open(p, encoding="utf-8") as f:
                    out.append({"name": name, "content": f.read()})
                    seen.add(name)
            except OSError:
                pass
    return out


def get(name):
    p = _existing_path(name)
    if p and os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return None
    return None


def save(name, content):
    p = _existing_path(name) or _path(name)
    if not p:
        return False
    os.makedirs(SKILLS_DIR, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content or "")
    return True


def delete(name):
    md = _path(name)
    if not md:
        return False
    removed = False
    for path in (md, os.path.splitext(md)[0] + ".txt"):
        if os.path.exists(path):
            os.remove(path)
            removed = True
    return removed
