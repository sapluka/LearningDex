import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import main, transcribe


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

    def test_transcription_reports_model_and_recognition_stages(self):
        stages = []
        segment = mock.Mock(text="测试", start=0, end=62)
        model = mock.Mock()
        model.transcribe.return_value = ([segment], mock.Mock(duration=120))
        with mock.patch.object(transcribe, "ensure_model", return_value="model"), \
             mock.patch.object(transcribe, "WhisperModel", return_value=model):
            transcribe.transcribe("audio.m4a", progress=stages.append)
        self.assertTrue(any("加载 base CPU" in stage for stage in stages))
        self.assertTrue(any("已处理 1 分钟" in stage for stage in stages))

    def test_generate_doc_passes_status_callback_to_transcription(self):
        api = main.Api()
        api.cfg = {"whisper_model": "base", "screenshots": False, "proofread": False}
        with mock.patch.object(main.subtitle, "extract", return_value={"subtitle": "", "segments": []}), \
             mock.patch.object(main.transcribe, "transcribe_video", return_value={
                 "subtitle": "测试", "segments": [], "used": "base(cpu)", "download_s": 1, "asr_s": 2}) as run, \
             mock.patch.object(main.agents, "summarize", return_value="# 文档"), \
             mock.patch.object(main.agents, "suggest_title", return_value="文档"), \
             mock.patch.object(main, "_save_output", return_value={"doc": "D:/learndex/output/test/doc.md"}), \
             mock.patch.object(api, "_save_history"), mock.patch.object(api, "_emit") as emit:
            result = api.generate_doc("https://example.org/video")
        self.assertTrue(result["ok"])
        self.assertEqual(run.call_args.kwargs["progress"], emit)


if __name__ == "__main__":
    unittest.main()
