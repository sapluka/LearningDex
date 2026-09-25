import tempfile
import unittest
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from app.web_server import create_app


def request(app, path):
    environ = {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = path
    result = {}

    def start_response(status, headers, exc_info=None):
        result["status"] = status
        result["headers"] = headers

    response = app(environ, start_response)
    try:
        body = b"".join(response)
    finally:
        if hasattr(response, "close"):
            response.close()
    return result["status"], body


class TestWebServer(unittest.TestCase):
    def test_serves_ui_and_archived_image(self):
        with tempfile.TemporaryDirectory() as root:
            web = Path(root) / "web"
            images = Path(root) / "output" / "BV123" / "images"
            web.mkdir()
            images.mkdir(parents=True)
            (web / "index.html").write_text("desktop", encoding="utf-8")
            (images / "shot.jpg").write_bytes(b"jpeg")
            app = create_app(str(web), lambda: str(Path(root) / "output"))
            self.assertEqual(request(app, "/"), ("200 OK", b"desktop"))
            self.assertEqual(request(app, "/task-images/BV123/images/shot.jpg"), ("200 OK", b"jpeg"))

    def test_image_route_rejects_missing_or_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as root:
            web = Path(root) / "web"
            images = Path(root) / "output" / "BV123" / "images"
            web.mkdir()
            images.mkdir(parents=True)
            (images.parent / "doc.md").write_text("private", encoding="utf-8")
            app = create_app(str(web), lambda: str(Path(root) / "output"))
            for path in ("/task-images/BV123/images/missing.jpg",
                         "/task-images/BV123/images/../doc.md",
                         "/task-images/..%2F/images/shot.jpg"):
                status, _ = request(app, path)
                self.assertTrue(status.startswith("404"), path)


if __name__ == "__main__":
    unittest.main()
