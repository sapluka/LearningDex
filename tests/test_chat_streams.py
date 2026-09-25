import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from app import agents, main


def wait_until(predicate):
    for _ in range(100):
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("stream did not finish")


class TestChatStreams(unittest.TestCase):
    def test_selection_reply_uses_its_id_and_is_archived(self):
        with tempfile.TemporaryDirectory() as root:
            api = main.Api()
            api.cfg = {"output_dir": root}
            api.current_taskdir = str(Path(root) / "BV1TEST")
            emitted = []
            api._emit_js = emitted.append
            with mock.patch.object(agents, "answer_selection_stream", return_value=iter(["第一", "第二"])):
                result = api.ask_selection("选中的文字", "为什么", 42)
                wait_until(lambda: any("__chatDone(42)" in call for call in emitted))
            self.assertEqual(result["id"], 42)
            self.assertIn("__chatChunk(42,", emitted[0])
            self.assertIn("__chatDone(42)", emitted[-1])
            self.assertIn("选中的文字", api.history[0]["content"])
            self.assertEqual(api.history[1]["content"], "第一第二")
            self.assertTrue((Path(api.current_taskdir) / "chat.json").exists())

    def test_old_reply_cannot_enter_new_context(self):
        api = main.Api()
        gate = threading.Event()

        def slow_stream(*args):
            gate.wait(2)
            yield "旧回复"

        with mock.patch.object(agents, "chat_stream", side_effect=slow_stream):
            api.chat("旧问题", "old")
            api.reset_context("新文档")
            gate.set()
            time.sleep(0.05)
        self.assertEqual(api.history, [])
        self.assertEqual(api.current_doc, "新文档")

    def test_general_chat_is_restored_without_creating_a_video_task(self):
        with tempfile.TemporaryDirectory() as root:
            api = main.Api()
            api.cfg = {"output_dir": root}
            with mock.patch.object(agents, "chat_stream", return_value=iter(["你好"])):
                api.chat("你好", "general-1")
                wait_until(lambda: (Path(root) / "general" / "chat.json").exists())
            self.assertEqual(api.list_tasks()["tasks"], [])
            api.reset_context()
            loaded = api.load_history("general")
            self.assertEqual(loaded["doc"], "")
            self.assertEqual(loaded["history"][-1]["content"], "你好")
            self.assertEqual(api.current_taskdir, "")


if __name__ == "__main__":
    unittest.main()
