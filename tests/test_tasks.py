import os
import json
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import main


class TestTasks(unittest.TestCase):
    def test_list_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "BV1AAA"))
            with open(os.path.join(d, "BV1AAA", "doc.md"), "w", encoding="utf-8") as f:
                f.write("# hi")
            with open(os.path.join(d, "BV1AAA", "source.json"), "w", encoding="utf-8") as f:
                json.dump({"url": "https://www.bilibili.com/video/BV1AAA", "title": "课程标题"}, f)
            api = main.Api()
            api.cfg = {"output_dir": d}
            r = api.list_tasks()
            self.assertTrue(r["ok"])
            self.assertEqual([t["id"] for t in r["tasks"]], ["BV1AAA"])
            self.assertTrue(r["tasks"][0]["has_doc"])
            self.assertEqual(r["tasks"][0]["title"], "课程标题")
            lr = api.load_task("BV1AAA")
            self.assertTrue(lr["ok"])
            self.assertEqual(lr["doc"], "# hi")
            self.assertEqual(lr["title"], "课程标题")

    def test_delete_task_removes_archive_and_favorite(self):
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "BV1AAA")
            os.makedirs(folder)
            with open(os.path.join(folder, "doc.md"), "w", encoding="utf-8") as f:
                f.write("# note")
            api = main.Api()
            api.cfg = {"output_dir": d}
            api.toggle_favorite("BV1AAA", "课程")
            api.load_task("BV1AAA")
            self.assertTrue(api.delete_task("BV1AAA")["ok"])
            self.assertFalse(os.path.exists(folder))
            self.assertEqual(api.list_favorites()["favorites"], [])
            self.assertEqual(api.current_taskdir, "")

    def test_load_task_invalid(self):
        api = main.Api()
        api.cfg = {}
        self.assertFalse(api.load_task("../x")["ok"])
        self.assertFalse(api.load_task("nope")["ok"])
        self.assertFalse(api.delete_task("../x")["ok"])


if __name__ == "__main__":
    unittest.main()
