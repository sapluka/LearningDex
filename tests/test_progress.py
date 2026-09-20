import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import main


class TestProgress(unittest.TestCase):
    def test_emit_calls_js_with_status(self):
        api = main.Api()
        win = mock.Mock()
        with mock.patch.object(main.webview, "windows", [win]):
            api._emit("正在生成笔记")
        win.evaluate_js.assert_called_once()
        arg = win.evaluate_js.call_args[0][0]
        self.assertIn("__setStatus", arg)
        self.assertIn("正在生成笔记", arg)

    def test_emit_no_window_safe(self):
        api = main.Api()
        with mock.patch.object(main.webview, "windows", []):
            api._emit("x")  # 不应抛异常


if __name__ == "__main__":
    unittest.main()