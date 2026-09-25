import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import agents, config, llm, subtitle, transcribe


class TestSubtitle(unittest.TestCase):
    def test_pick_bili_zh_preferred(self):
        subs = [{"lan": "zh-CN", "subtitle_url": "/zh"}, {"lan": "en-US", "subtitle_url": "/en"}]
        self.assertEqual(subtitle._pick_bili_sub(subs)["subtitle_url"], "/zh")

    def test_pick_bili_zh(self):
        subs = [{"lan": "zh-CN", "subtitle_url": "/zh"}]
        self.assertEqual(subtitle._pick_bili_sub(subs)["subtitle_url"], "/zh")

    def test_pick_bili_fallback_first(self):
        subs = [{"lan": "ja", "subtitle_url": "/ja"}]
        self.assertEqual(subtitle._pick_bili_sub(subs)["subtitle_url"], "/ja")

    def test_pick_empty(self):
        self.assertIsNone(subtitle._pick(None))
        self.assertIsNone(subtitle._pick({}))


class TestTranscribe(unittest.TestCase):
    def test_bvid(self):
        self.assertEqual(transcribe._bvid("https://www.bilibili.com/video/BV1X7411F744?p=9"), "BV1X7411F744")
        self.assertIsNone(transcribe._bvid("https://example.com/x"))

    def test_model_dir(self):
        self.assertTrue(transcribe._model_dir("base").endswith("whisper-base"))


class TestLlm(unittest.TestCase):
    def test_full_model_anthropic(self):
        self.assertEqual(llm.full_model({"protocol": "anthropic", "model": "deepseek-v4-flash"}),
                         "anthropic/deepseek-v4-flash")

    def test_full_model_openai(self):
        self.assertEqual(llm.full_model({"protocol": "openai", "model": "gpt-4o"}), "openai/gpt-4o")

    def test_full_model_preserve_slash(self):
        self.assertEqual(llm.full_model({"protocol": "custom", "model": "ollama/llama3"}), "ollama/llama3")

    def test_full_model_empty(self):
        self.assertEqual(llm.full_model({"protocol": "openai", "model": ""}), "")


class TestAgents(unittest.TestCase):
    def test_load_skill_missing(self):
        self.assertIsNone(agents.load_skill("不存在"))

    def test_lecture_uses_skill_when_present(self):
        with mock.patch.object(agents, "_get_skill", return_value="SKILLX"):
            self.assertEqual(agents.lecture_system(), "SKILLX")

    def test_lecture_fallback_default(self):
        with mock.patch.object(agents, "_get_skill", return_value=None):
            self.assertIn("视频学习助手", agents.lecture_system())

    def test_visual_lessons_request_multiple_distinct_frames(self):
        info = {"title": "纹理", "segments": [{"from": 12, "text": "对比两种采样效果"}]}
        with mock.patch.object(agents.llm, "text", return_value="笔记") as request:
            agents.summarize({}, info, screenshots=True)
        system, user = request.call_args.args[1]
        self.assertIn("不同知识点", system["content"])
        self.assertIn("视觉对比", system["content"])
        self.assertIn("SHOT:分:秒", system["content"])
        self.assertIn("[00:12] 对比两种采样效果", user["content"])


class TestConfig(unittest.TestCase):
    def test_load_has_defaults(self):
        cfg = config.load()
        for k in ("protocol", "base_url", "api_key", "model", "bili_sessdata",
                  "cookies_file", "whisper_model", "proofread"):
            self.assertIn(k, cfg)


if __name__ == "__main__":
    unittest.main()
