import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import main


class TestHistory(unittest.TestCase):
    def test_task_restores_its_saved_conversation(self):
        with tempfile.TemporaryDirectory() as d:
            api = main.Api()
            api.cfg = {"output_dir": d}
            api.history = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
            api._save_history("BV1AAA")
            with open(os.path.join(d, "BV1AAA", "doc.md"), "w", encoding="utf-8") as f:
                f.write("# 课程 A")
            self.assertTrue(os.path.exists(os.path.join(d, "BV1AAA", "chat.json")))
            lr = api.load_task("BV1AAA")
            self.assertTrue(lr["ok"])
            self.assertEqual(lr["history"], api.history)
            self.assertEqual(lr["doc"], "# 课程 A")

    def test_invalid(self):
        api = main.Api()
        api.cfg = {}
        self.assertFalse(api.load_task("../x")["ok"])

    def test_task_switches_do_not_mix_conversations(self):
        with tempfile.TemporaryDirectory() as d:
            api = main.Api()
            api.cfg = {"output_dir": d}
            for tid in ("BV1AAA", "BV1BBB"):
                api.history = [{"role": "user", "content": tid}]
                api._save_history(tid)
                with open(os.path.join(d, tid, "doc.md"), "w", encoding="utf-8") as f:
                    f.write("# " + tid)
            for tid in ("BV1AAA", "BV1BBB", "BV1AAA"):
                restored = api.load_task(tid)
                self.assertEqual(restored["history"], [{"role": "user", "content": tid}])
                self.assertEqual(api.current_doc, "# " + tid)

    def test_legacy_general_archive_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            api = main.Api()
            api.cfg = {"output_dir": d}
            api.history = [{"role": "user", "content": "旧记录"}]
            api._save_history("general")
            path = os.path.join(d, "general", "chat.json")
            with open(path, "rb") as f:
                before = f.read()
            api.reset_context()
            self.assertEqual(api.list_tasks()["tasks"], [])
            with open(path, "rb") as f:
                self.assertEqual(f.read(), before)


if __name__ == "__main__":
    unittest.main()
