import tempfile
import unittest
from pathlib import Path

from app import main


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


if __name__ == "__main__":
    unittest.main()
