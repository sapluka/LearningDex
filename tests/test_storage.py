import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import main


class TestStateDir(unittest.TestCase):
    def test_default(self):
        self.assertEqual(main._state_dir({}), main.DEFAULT_STATE_DIR)

    def test_custom(self):
        self.assertEqual(main._state_dir({"output_dir": "D:/myout"}), "D:/myout")

    def test_save_output_uses_custom_dir(self):
        with tempfile.TemporaryDirectory() as d:
            saved = main._save_output(
                "https://www.bilibili.com/video/BV1TEST123", {"subtitle": "s"}, "doc",
                {"output_dir": d})
            self.assertTrue(saved["doc"].startswith(d))
            self.assertTrue(os.path.exists(saved["doc"]))


if __name__ == "__main__":
    unittest.main()