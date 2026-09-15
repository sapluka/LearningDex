import litellm


def full_model(cfg):
    m = (cfg.get("model") or "").strip()
    if "/" in m:
        return m
    prefix = {"anthropic": "anthropic", "deepseek": "deepseek"}.get(cfg.get("protocol"), "openai")
    return f"{prefix}/{m}" if m else ""


def complete(cfg, messages, **kw):
    kw.setdefault("api_key", cfg.get("api_key") or None)
    if cfg.get("base_url"):
        kw.setdefault("api_base", cfg["base_url"])
    return litellm.completion(model=full_model(cfg), messages=messages, **kw)


def text(cfg, messages, **kw):
    r = complete(cfg, messages, **kw)
    return r.choices[0].message.content


def test_connection(cfg):
    return text(cfg, [{"role": "user", "content": "ping"}], max_tokens=5)