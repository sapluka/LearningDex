import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

# 敏感字段：只能由个人信息文档(personal.py)/环境变量注入，绝不写入 config.json
SENSITIVE = ("api_key", "bili_sessdata", "cookies_file", "cookies_text")

DEFAULT = {
    "protocol": "openai",
    "base_url": "",
    "api_key": "",
    "model": "",
    "whisper_model": "base",
    "proofread": True,
    "screenshots": True,
    "shot_validate": True,
    "output_dir": "",
    "pdf_output_dir": "",
    "bili_sessdata": "",
    "cookies_file": "",
    "cookies_text": "",
}

_ENV_MAP = {
    "LLM_API_KEY": "api_key",
    "BILI_SESSDATA": "bili_sessdata",
    "BILI_COOKIES_FILE": "cookies_file",
    "BILI_COOKIES_TEXT": "cookies_text",
}

def _personal():
    try:
        from personal import INFO
    except Exception:
        return {}
    return {k: v for k, v in INFO.items() if v not in ("", None)}


def _env():
    out = {}
    for env, key in _ENV_MAP.items():
        val = os.environ.get(env)
        if val:
            out[key] = val
    return out


def load():
    cfg = dict(DEFAULT)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = {**cfg, **json.load(f)}
    except (OSError, json.JSONDecodeError):
        pass
    cfg = {**cfg, **_personal()}
    cfg = {**cfg, **_env()}
    return cfg


def save(cfg):
    safe = {k: v for k, v in cfg.items() if k not in SENSITIVE}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(safe, f, ensure_ascii=False, indent=2)
