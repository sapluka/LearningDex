import tempfile
import unittest
from unittest import mock
from pathlib import Path

from app import main
from app import agents


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


if __name__ == "__main__":
    unittest.main()
