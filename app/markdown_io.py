"""Markdown export helpers shared by the desktop API."""

import html.parser
import os
import re
import shutil
from urllib.parse import quote, unquote, urlsplit
from urllib.request import url2pathname


IMAGE_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\((<?[^)]+>?)\)")


class _ImageAttributes(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            self.attrs = dict(attrs)


def _local_path(src, source_dir):
    if os.path.isabs(src):
        return src
    parsed = urlsplit(src)
    if parsed.scheme == "file":
        return url2pathname(unquote(parsed.path))
    if parsed.scheme or src.startswith("//"):
        return None
    return os.path.join(source_dir, unquote(src)) if source_dir else None


def export_markdown(content, destination, source_dir=""):
    """Save Markdown and copy local images beside it using relative links."""
    destination = os.path.abspath(destination)
    asset_name = os.path.splitext(os.path.basename(destination))[0] + "_images"
    asset_dir = os.path.join(os.path.dirname(destination), asset_name)
    copied = {}

    def image_url(src):
        path = _local_path(src, source_dir)
        if path is None:
            return src
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"图片不存在：{path}")
        if path not in copied:
            os.makedirs(asset_dir, exist_ok=True)
            name = f"{len(copied) + 1}_{os.path.basename(path)}"
            shutil.copy2(path, os.path.join(asset_dir, name))
            copied[path] = name
        return quote(asset_name + "/" + copied[path], safe="/-._~")

    def markdown_image(alt, src):
        alt = alt.replace("[", "\\[").replace("]", "\\]")
        return f"![{alt}]({image_url(src)})"

    def replace_tag(match):
        tag = _ImageAttributes()
        tag.feed(match.group(0))
        src = tag.attrs.get("src", "")
        return markdown_image(tag.attrs.get("alt", "") or "", src) if src else match.group(0)

    def replace_md(match):
        src = match.group(2).strip("<>")
        return markdown_image(match.group(1), src)

    md = MARKDOWN_IMAGE.sub(replace_md, (content or "").replace("\\==", "=="))
    md = IMAGE_TAG.sub(replace_tag, md)
    with open(destination, "w", encoding="utf-8") as f:
        f.write(md)
    return destination
