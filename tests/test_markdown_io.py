import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from app.markdown_io import export_markdown, normalize_markdown


class TestMarkdownExport(unittest.TestCase):
    def test_inline_local_image_is_copied_with_relative_link(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "task" / "images"
            source.mkdir(parents=True)
            image = source / "截图 1.jpg"
            image.write_bytes(b"jpeg")
            target = Path(root) / "notes" / "学习.md"
            target.parent.mkdir()
            md = f'# 笔记\n<img src="{image.as_uri()}" alt="图解">\n'

            export_markdown(md, target, str(source.parent))

            self.assertEqual(target.read_text(encoding="utf-8"),
                             "# 笔记\n![图解](" + quote("学习_images/1_截图 1.jpg", safe="/-._~") + ")\n")
            self.assertEqual((target.parent / "学习_images" / "1_截图 1.jpg").read_bytes(), b"jpeg")

    def test_relative_images_are_copied_once(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "task" / "images"
            source.mkdir(parents=True)
            (source / "a.png").write_bytes(b"png")
            target = Path(root) / "out.md"

            export_markdown("![a](images/a.png) ![b](images/a.png)", target, str(source.parent))

            self.assertEqual(target.read_text(encoding="utf-8"),
                             "![a](out_images/1_a.png) ![b](out_images/1_a.png)")
            self.assertEqual(len(list((Path(root) / "out_images").iterdir())), 1)

    def test_remote_image_and_highlight(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "note.md"
            export_markdown('\\==重点== <img src="https://example.org/a.png" alt="远程">', target)
            self.assertEqual(target.read_text(encoding="utf-8"),
                             "==重点== ![远程](https://example.org/a.png)")

    def test_missing_local_image_rejects_export(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "note.md"
            with self.assertRaises(FileNotFoundError):
                export_markdown("![missing](images/no.png)", target, root)
            self.assertFalse(target.exists())

    def test_code_fences_keep_image_examples_literal(self):
        md = "```md\n![例子](images/missing.png)\n<img src=\"images/no.png\">\n```\n\n真实 ![图](images/a.png)"
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "images"
            source.mkdir()
            (source / "a.png").write_bytes(b"png")
            target = Path(root) / "out.md"
            self.assertIn("![例子](images/missing.png)", normalize_markdown(md, root))
            export_markdown(md, target, root)
            result = target.read_text(encoding="utf-8")
            self.assertIn("![例子](images/missing.png)", result)
            self.assertIn('<img src="images/no.png">', result)
            self.assertIn("![图](out_images/1_a.png)", result)


if __name__ == "__main__":
    unittest.main()
