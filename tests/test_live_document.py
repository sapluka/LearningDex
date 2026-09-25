import tempfile
import unittest
from pathlib import Path

from app import main
from app.markdown_io import normalize_markdown


class TestLiveDocument(unittest.TestCase):
    def test_editor_image_becomes_task_relative(self):
        with tempfile.TemporaryDirectory() as root:
            task = Path(root)
            image = task / "images" / "shot.jpg"
            image.parent.mkdir()
            image.write_bytes(b"jpeg")
            self.assertEqual(normalize_markdown(f'<img src="{image.as_uri()}" alt="截图">', root),
                             "![截图](images/shot.jpg)")

    def test_save_final_and_reload_edited_document_and_history(self):
        with tempfile.TemporaryDirectory() as root:
            task = Path(root) / "BV1TEST123"
            task.mkdir()
            (task / "doc.md").write_text("# 初稿", encoding="utf-8")
            api = main.Api()
            api.cfg = {"output_dir": root}
            self.assertTrue(api.load_task(task.name)["ok"])
            self.assertEqual(api.current_doc, "# 初稿")

            api.update_doc("# 正在编辑")
            self.assertEqual(api.current_doc, "# 正在编辑")
            draft = api.save_draft("# 未完成草稿")
            self.assertTrue(draft["ok"])
            self.assertEqual((task / "draft.md").read_text(encoding="utf-8"), "# 未完成草稿")
            api.reset_context()
            self.assertEqual(api.load_task(task.name)["doc"], "# 未完成草稿")
            result = api.save_final("# 最终笔记\n==重点==")
            self.assertTrue(result["ok"])
            self.assertEqual((task / "final.md").read_text(encoding="utf-8"), "# 最终笔记\n==重点==")
            self.assertFalse((task / "draft.md").exists())

            api.history = [{"role": "user", "content": "旧问题"}]
            api._save_history(task.name)
            api.reset_context("样例")
            self.assertEqual(api.history, [])
            self.assertEqual(api.current_taskdir, "")
            self.assertEqual(api.current_doc, "样例")

            loaded = api.load_task(task.name)
            self.assertEqual(loaded["doc"], "# 最终笔记\n==重点==")
            self.assertEqual(loaded["history"], [{"role": "user", "content": "旧问题"}])


if __name__ == "__main__":
    unittest.main()
