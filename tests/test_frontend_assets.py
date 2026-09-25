import os
import unittest
from html.parser import HTMLParser
from urllib.parse import urlsplit

from app.main import WEB_DIR


class _Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        if tag not in ("script", "link"):
            return
        attributes = dict(attrs)
        path = attributes.get("src") or attributes.get("href")
        if path:
            self.paths.append(path)


class TestDesktopAssets(unittest.TestCase):
    def test_boot_assets_are_local_and_present(self):
        with open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8") as page:
            assets = _Assets()
            assets.feed(page.read())
        self.assertTrue(assets.paths)
        for path in assets.paths:
            self.assertEqual(urlsplit(path).scheme, "", path)
            self.assertTrue(os.path.isfile(os.path.join(WEB_DIR, path)), path)


if __name__ == "__main__":
    unittest.main()
