import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import quote

from app import main


class TestBundledSamples(unittest.TestCase):
    def test_sample_export_copies_its_image(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "示例.md"
            window = SimpleNamespace(create_file_dialog=lambda *_args, **_kwargs: str(target))
            with mock.patch.object(main.webview, "windows", [window]):
                result = main.Api().export_md("![图](images/shot_1.jpg)", "示例.md", "BV1X7411F744")

            self.assertTrue(result["ok"])
            self.assertEqual(target.read_text(encoding="utf-8"),
                             "![图](" + quote("示例_images/1_shot_1.jpg", safe="/-._~") + ")")
            self.assertTrue((Path(root) / "示例_images" / "1_shot_1.jpg").is_file())

    def test_unknown_sample_cannot_select_arbitrary_files(self):
        result = main.Api().export_md("![图](images/shot_1.jpg)", sample_id="../output")
        self.assertEqual(result, {"ok": False, "error": "示例资源不存在"})


if __name__ == "__main__":
    unittest.main()
