import tempfile
import unittest
from unittest import mock
from pathlib import Path

from app import main
from app import agents
from app.shot_status import ShotError
import json


class TestVideoTasks(unittest.TestCase):
    def test_non_bilibili_videos_have_distinct_reopenable_folders(self):
        first = "https://www.youtube.com/watch?v=alpha"
        second = "https://www.youtube.com/watch?v=beta"
        with tempfile.TemporaryDirectory() as root:
            cfg = {"output_dir": root}
            saved_first = main._save_output(first, {"subtitle": "甲", "title": "第一课"}, "# 一", cfg)
            saved_second = main._save_output(second, {"subtitle": "乙", "title": "第二课"}, "# 二", cfg)
            self.assertNotEqual(Path(saved_first["doc"]).parent, Path(saved_second["doc"]).parent)
            self.assertTrue(Path(saved_first["doc"]).exists())
            self.assertTrue(Path(saved_second["doc"]).exists())

            api = main.Api()
            api.cfg = cfg
            task = api.load_task(main._task_id(first))
            self.assertEqual(task["url"], first)
            self.assertEqual(task["doc"], "# 一")
            self.assertEqual(main._task_id(first), main._task_id(first))

    def test_bilibili_folder_keeps_bv_id(self):
        self.assertEqual(main._task_id("https://www.bilibili.com/video/BV1X7411F744"), "BV1X7411F744")

    def test_agent_title_is_saved_and_used_in_task_views(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = {"output_dir": root}
            url = "https://www.bilibili.com/video/BV1TITLE"
            info = {"subtitle": "纹理映射", "title": "视频原标题", "task_title": "纹理映射与采样"}
            main._save_output(url, info, "# 章节", cfg)
            api = main.Api()
            api.cfg = cfg
            self.assertEqual(api.list_tasks()["tasks"][0]["title"], "纹理映射与采样")
            self.assertEqual(api.load_task("BV1TITLE")["title"], "纹理映射与采样")
            api.toggle_favorite("BV1TITLE", "旧收藏名")
            self.assertEqual(api.list_favorites()["favorites"][0]["title"], "纹理映射与采样")

    def test_renamed_title_persists_across_task_views(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = {"output_dir": root}
            main._save_output("https://www.bilibili.com/video/BV1TITLE",
                              {"subtitle": "纹理", "title": "视频原标题"}, "# 文档", cfg)
            api = main.Api()
            api.cfg = cfg
            api.toggle_favorite("BV1TITLE", "旧名称")
            self.assertEqual(api.rename_task("BV1TITLE", "纹理映射与采样"),
                             {"ok": True, "title": "纹理映射与采样"})
            self.assertEqual(api.load_task("BV1TITLE")["title"], "纹理映射与采样")
            self.assertEqual(api.list_tasks()["tasks"][0]["title"], "纹理映射与采样")
            self.assertEqual(api.list_favorites()["favorites"][0]["title"], "纹理映射与采样")
            api.history = [{"role": "user", "content": "你好"}]
            api._save_history("BV1TITLE")
            self.assertEqual(main._source_info(str(Path(root) / "BV1TITLE"))["title"], "视频原标题")

    def test_rename_rejects_missing_or_invalid_task_and_title(self):
        with tempfile.TemporaryDirectory() as root:
            api = main.Api()
            api.cfg = {"output_dir": root}
            main._save_output("https://www.bilibili.com/video/BV1TITLE",
                              {"subtitle": "纹理", "title": "原名"}, "# 文档", api.cfg)
            for tid, title in (("../other", "新名"), ("BV1MISSING", "新名"),
                               ("BV1TITLE", ""), ("BV1TITLE", "有\n换行"),
                               ("BV1TITLE", "字" * 51)):
                self.assertFalse(api.rename_task(tid, title)["ok"])
            self.assertEqual(api.load_task("BV1TITLE")["title"], "原名")

    def test_legacy_title_from_document(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "BV1OLD"
            folder.mkdir()
            (folder / "doc.md").write_text("# 《游戏架构》学习文档\n", encoding="utf-8")
            self.assertEqual(main._task_title(str(folder), "BV1OLD"), "游戏架构")
            (folder / "draft.md").write_text("# 编辑后的标题\n", encoding="utf-8")
            self.assertEqual(main._task_title(str(folder), "BV1OLD"), "编辑后的标题")

    def test_agent_title_cleanup(self):
        with mock.patch.object(agents.llm, "text", return_value="# 纹理映射与采样\n说明"):
            self.assertEqual(agents.suggest_title({}, {}, "# 文档"), "纹理映射与采样")

    def test_generate_doc_requests_title_after_document(self):
        with tempfile.TemporaryDirectory() as root:
            api = main.Api()
            api.cfg = {"output_dir": root, "screenshots": False}
            info = {"subtitle": "纹理", "title": "原视频", "segments": []}
            with mock.patch.object(main.subtitle, "extract", return_value=info), \
                 mock.patch.object(main.agents, "summarize", return_value="# 学习内容"), \
                 mock.patch.object(main.agents, "suggest_title", return_value="纹理映射与采样") as title:
                result = api.generate_doc("https://www.bilibili.com/video/BV1TITLE")
            self.assertTrue(result["ok"])
            self.assertEqual(result["title"], "纹理映射与采样")
            title.assert_called_once()


    def test_screenshot_failures_and_timestamps_survive_reopening(self):
        with tempfile.TemporaryDirectory() as root:
            api = main.Api()
            api.cfg = {"output_dir": root, "screenshots": True}
            info = {"subtitle": "界面演示", "title": "原视频", "segments": [{"from": 90, "text": "显示界面"}]}
            raw = "# 内容\n![界面](SHOT:01:30)"
            with mock.patch.object(main.subtitle, "extract", return_value=info), \
                    mock.patch.object(main.agents, "summarize", return_value=raw), \
                    mock.patch.object(main.agents, "suggest_title", return_value="界面演示"), \
                    mock.patch.object(main.shoot, "_download_video", side_effect=ShotError("download_rejected")):
                result = api.generate_doc("https://www.bilibili.com/video/BV1SHOTS")
            self.assertTrue(result["ok"])
            self.assertIn("HTTP 412", result["note"])
            folder = Path(root) / "BV1SHOTS"
            self.assertEqual(json.loads((folder / "segments.json").read_text(encoding="utf-8")), info["segments"])
            self.assertEqual((folder / "screenshot_plan.md").read_text(encoding="utf-8"), raw)
            self.assertNotIn("SHOT:", result["doc"])
            self.assertEqual(api.load_task("BV1SHOTS")["note"], result["note"])
            api.cfg["screenshots"] = False
            with mock.patch.object(main.subtitle, "extract", return_value=info), \
                    mock.patch.object(main.agents, "summarize", return_value="# 纯文字"), \
                    mock.patch.object(main.agents, "suggest_title", return_value="文字主题"):
                api.generate_doc("https://www.bilibili.com/video/BV1SHOTS")
            self.assertEqual(api.load_task("BV1SHOTS")["note"], "")

    def test_screenshot_missing_timestamps_are_reported(self):
        with tempfile.TemporaryDirectory() as root:
            api = main.Api()
            api.cfg = {"output_dir": root, "screenshots": True}
            with mock.patch.object(main.subtitle, "extract", return_value={"subtitle": "文字", "segments": []}), \
                    mock.patch.object(main.agents, "summarize", return_value="# 笔记"), \
                    mock.patch.object(main.agents, "suggest_title", return_value="主题"), \
                    mock.patch.object(main.shoot, "capture") as capture:
                result = api.generate_doc("https://www.bilibili.com/video/BV1NOFRAME")
            self.assertIn("缺少时间戳", result["note"])
            capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
