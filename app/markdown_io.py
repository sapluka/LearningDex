"""Markdown export helpers shared by the desktop API."""

import html.parser
import os
import re
import shutil
from urllib.parse import quote, unquote, urlsplit
from urllib.request import url2pathname


IMAGE_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\((<?[^)]+>?)\)")
FENCED_BLOCK = re.compile(
    r"(?ms)^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[^\r\n]*\r?\n.*?^[ \t]{0,3}(?P=fence)[ \t]*(?:\r?\n|$)"
)


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


def _rewrite_images(content, image_url):
    def markdown_image(alt, src, title=""):
        alt = alt.replace("[", "\\[").replace("]", "\\]")
        suffix = f' "{title}"' if title else ""
        return f"![{alt}]({image_url(src)}{suffix})"

    def replace_tag(match):
        tag = _ImageAttributes()
        tag.feed(match.group(0))
        src = tag.attrs.get("src", "")
        return markdown_image(tag.attrs.get("alt", "") or "", src,
                              tag.attrs.get("title", "") or "") if src else match.group(0)

    def replace_md(match):
        value = match.group(2).strip()
        target = re.fullmatch(r'(<[^>]+>|\S+)(?:\s+(["\'])(.*?)\2)?', value)
        src = target.group(1).strip("<>") if target else value.strip("<>")
        title = target.group(3) if target else ""
        return markdown_image(match.group(1), src, title or "")

    def rewrite_prose(part):
        md = MARKDOWN_IMAGE.sub(replace_md, part.replace("\\==", "=="))
        return IMAGE_TAG.sub(replace_tag, md)

    content = content or ""
    pieces = []
    end = 0
    for match in FENCED_BLOCK.finditer(content):
        pieces.extend((rewrite_prose(content[end:match.start()]), match.group(0)))
        end = match.end()
    pieces.append(rewrite_prose(content[end:]))
    return "".join(pieces)


def normalize_markdown(content, source_dir=""):
    """Keep task images relative when serializing the live editor document."""
    source_dir = os.path.abspath(source_dir) if source_dir else ""

    def image_url(src):
        path = _local_path(src, source_dir)
        if path and source_dir:
            path = os.path.abspath(path)
            try:
                if os.path.commonpath((path, source_dir)) == source_dir:
                    return quote(os.path.relpath(path, source_dir).replace("\\", "/"), safe="/-._~")
            except ValueError:
                pass
        return src

    return _rewrite_images(content, image_url)


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

    md = _rewrite_images(content, image_url)
    with open(destination, "w", encoding="utf-8") as f:
        f.write(md)
    return destination
