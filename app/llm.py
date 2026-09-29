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


def text(cfg, messages, response_meta=None, **kw):
    r = complete(cfg, messages, **kw)
    if response_meta is not None:
        response_meta["finish_reason"] = getattr(r.choices[0], "finish_reason", None)
    return r.choices[0].message.content


def stream(cfg, messages, **kw):
    kw.setdefault("api_key", cfg.get("api_key") or None)
    if cfg.get("base_url"):
        kw.setdefault("api_base", cfg["base_url"])
    kw["stream"] = True
    for chunk in litellm.completion(model=full_model(cfg), messages=messages, **kw):
        try:
            delta = chunk.choices[0].delta.content
        except Exception:
            delta = None
        if delta:
            yield delta


def test_connection(cfg):
    reply = text(cfg, [{"role": "user", "content": "只回答 OK"}], max_tokens=128,
                 timeout=30)
    if not reply or not reply.strip():
        raise RuntimeError("模型未返回正文，连接检验未通过")
    return reply
