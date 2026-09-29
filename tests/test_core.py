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

    def test_cpu_selection_never_loads_gpu_model(self):
        segment = mock.Mock(text="你好", start=0, end=2)
        model = mock.Mock()
        model.transcribe.return_value = ([segment], mock.Mock(duration=2))
        with mock.patch.object(transcribe, "ensure_model", return_value="model") as ensure, \
             mock.patch.object(transcribe, "WhisperModel", return_value=model) as create:
            result = transcribe.transcribe("audio.m4a", model_size="base")
        ensure.assert_called_once_with("base", progress=None)
        create.assert_called_once_with("model", device="cpu", compute_type="int8")
        self.assertEqual(result[1], "base(cpu)")

    def test_gpu_failure_falls_back_to_base_cpu(self):
        segment = mock.Mock(text="你好", start=0, end=2)
        model = mock.Mock()
        model.transcribe.return_value = ([segment], mock.Mock(duration=2))
        with mock.patch.object(transcribe, "ensure_model", return_value="model") as ensure, \
             mock.patch.object(transcribe, "WhisperModel", side_effect=[OSError("missing DLL"), model]) as create:
            result = transcribe.transcribe("audio.m4a", model_size=transcribe.TURBO)
        self.assertEqual([call.args[0] for call in ensure.call_args_list], [transcribe.TURBO, "base"])
        self.assertEqual(create.call_args_list[1].kwargs["device"], "cpu")
        self.assertEqual(result[1], "base(cpu)")

    def test_gpu_failure_during_lazy_recognition_falls_back_to_cpu(self):
        gpu = mock.Mock()
        gpu.transcribe.return_value = (iter([mock.Mock(text="", start=0, end=1),
                                               mock.Mock(text="", start=1, end=2)]), mock.Mock(duration=2))
        cpu = mock.Mock()
        cpu.transcribe.return_value = ([mock.Mock(text="完成", start=0, end=2)], mock.Mock(duration=2))
        stages = []
        with mock.patch.object(transcribe, "ensure_model", return_value="model"), \
             mock.patch.object(transcribe, "WhisperModel", side_effect=[gpu, cpu]):
            original = gpu.transcribe.return_value[0]

            def failing_segments():
                next(original)
                raise RuntimeError("CUDA DLL missing")
                yield

            gpu.transcribe.return_value = (failing_segments(), mock.Mock(duration=2))
            result = transcribe.transcribe("audio.m4a", transcribe.TURBO, progress=stages.append)
        self.assertEqual(result[0], "完成")
        self.assertEqual(result[1], "base(cpu)")
        self.assertTrue(any("改用 base CPU" in stage for stage in stages))


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

    def test_visual_lessons_request_only_needed_frames_between_complete_explanations(self):
        info = {"title": "纹理", "segments": [{"from": 12, "text": "对比两种采样效果"}]}
        with mock.patch.object(agents.llm, "text", return_value="笔记") as request:
            agents.summarize({}, info, screenshots=True)
        system, user = request.call_args.args[1]
        self.assertIn("连续几段完整讲解", system["content"])
        self.assertIn("不要一句话配一张图", system["content"])
        self.assertIn("同一组相关知识点尽量共用一张图", system["content"])
        self.assertNotIn("为每个适合借助视频画面理解的不同知识点主动安排截图", system["content"])
        self.assertIn("视觉对比", system["content"])
        self.assertIn("SHOT:分:秒", system["content"])
        self.assertIn("[00:12] 对比两种采样效果", user["content"])

    def test_screenshot_plan_requires_enabled_capture_and_timestamps(self):
        for enabled, info in ((False, {"segments": [{"from": 12, "text": "示例"}]}),
                (True, {"subtitle": "没有时间戳"})):
            with self.subTest(enabled=enabled), mock.patch.object(agents.llm, "text", return_value="笔记") as request:
                agents.summarize({}, info, screenshots=enabled)
                self.assertNotIn("SHOT:分:秒", request.call_args.args[1][0]["content"])

    def test_default_lecture_skill_has_precise_positive_examples(self):
        prompt = agents.lecture_system()
        self.assertIn("过渡句应说明具体关系、条件或后续位置", prompt)
        self.assertNotIn("这个东西现在知道它存在就够了", prompt)
        self.assertNotIn("允许废话", prompt)

    def test_custom_lecture_still_receives_safe_diagram_syntax(self):
        info = {"title": "流程", "subtitle": "先完成写作，再检查结果。"}
        with mock.patch.object(agents, "lecture_system", return_value="自定义讲解要求"), \
                mock.patch.object(agents.llm, "text", return_value="笔记") as request:
            self.assertEqual(agents.summarize({}, info), "笔记")
        system, user = request.call_args.args[1]
        self.assertIn("自定义讲解要求", system["content"])
        self.assertIn("节点 ID 使用英文字母和数字", system["content"])
        self.assertIn('A["写作完成<br/>#quot;检查结果#quot;"] --> B["下一步"]', system["content"])
        self.assertIn(info["subtitle"], user["content"])


class TestConfig(unittest.TestCase):
    def test_load_has_defaults(self):
        cfg = config.load()
        for k in ("protocol", "base_url", "api_key", "model", "bili_sessdata",
                  "cookies_file", "whisper_model", "proofread"):
            self.assertIn(k, cfg)


if __name__ == "__main__":
    unittest.main()
