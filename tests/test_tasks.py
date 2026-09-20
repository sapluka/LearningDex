import os
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
            api = main.Api()
            api.cfg = {"output_dir": d}
            r = api.list_tasks()
            self.assertTrue(r["ok"])
            self.assertEqual([t["id"] for t in r["tasks"]], ["BV1AAA"])
            self.assertTrue(r["tasks"][0]["has_doc"])
            lr = api.load_task("BV1AAA")
            self.assertTrue(lr["ok"])
            self.assertEqual(lr["doc"], "# hi")

    def test_load_task_invalid(self):
        api = main.Api()
        api.cfg = {}
        self.assertFalse(api.load_task("../x")["ok"])
        self.assertFalse(api.load_task("nope")["ok"])


if __name__ == "__main__":
    unittest.main()