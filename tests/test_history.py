import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import main


class TestHistory(unittest.TestCase):
    def test_save_load_list(self):
        with tempfile.TemporaryDirectory() as d:
            api = main.Api()
            api.cfg = {"output_dir": d}
            api.history = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
            api._save_history("BV1AAA")
            self.assertTrue(os.path.exists(os.path.join(d, "BV1AAA", "chat.json")))
            lr = api.load_history("BV1AAA")
            self.assertTrue(lr["ok"])
            self.assertEqual(lr["history"], api.history)
            self.assertEqual([h["id"] for h in api.list_histories()["histories"]], ["BV1AAA"])

    def test_invalid(self):
        api = main.Api()
        api.cfg = {}
        self.assertFalse(api.load_history("../x")["ok"])

    def test_load_history_resets_history(self):
        with tempfile.TemporaryDirectory() as d:
            api = main.Api()
            api.cfg = {"output_dir": d}
            api.history = [{"role": "user", "content": "old"}]
            api._save_history("BV1BBB")
            api.history = [{"role": "user", "content": "other"}]
            api.load_history("BV1BBB")
            self.assertEqual(api.history, [{"role": "user", "content": "old"}])


if __name__ == "__main__":
    unittest.main()