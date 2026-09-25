import os
import sys
import unittest
import tempfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import agents, shoot


class TestShoot(unittest.TestCase):
    def test_parse_shots(self):
        md = "文本 ![图](SHOT:01:30) 还有 ![a](SHOT:1:02:03)"
        shots = shoot.parse_shots(md)
        self.assertEqual(shots[0][2], "01:30")
        self.assertEqual(shots[1][2], "1:02:03")
        self.assertEqual(shots[0][1], "图")

    def test_to_seconds(self):
        self.assertEqual(shoot._to_seconds("01:30"), 90)
        self.assertEqual(shoot._to_seconds("1:02:03"), 3723)

    def test_capture_no_shots_returns_same(self):
        self.assertEqual(shoot.capture("no shots here", "u", "d", {}), "no shots here")


class TestShotPrompt(unittest.TestCase):
    def test_ts_transcript(self):
        segs = [{"from": 90, "to": 95, "text": "a"}, {"from": None, "text": "b"}]
        self.assertEqual(agents._ts_transcript(segs), "[01:30] a")

    def test_validate_frame_error_rejects(self):
        with mock.patch.object(agents.llm, "text", side_effect=Exception("no vision")):
            self.assertFalse(agents.validate_frame({}, "does_not_exist.jpg", "cap"))

    def test_capture_tries_nearby_frames_and_cleans_temp_video(self):
        with tempfile.TemporaryDirectory() as root:
            video_paths = []

            def download(url, cfg, tmpdir):
                video = os.path.join(tmpdir, "source.mp4")
                with open(video, "wb") as f:
                    f.write(b"video")
                video_paths.append(video)
                return video

            def frame(video, sec, out):
                with open(out, "wb") as f:
                    f.write(b"frame")
                return out

            with mock.patch.object(shoot, "_download_video", side_effect=download), \
                 mock.patch.object(shoot, "_frame", side_effect=frame) as extract, \
                 mock.patch.object(agents, "validate_frame", side_effect=[False, True]) as validate:
                result = shoot.capture("图：![截图](SHOT:01:30)", "url", root, {})
            self.assertEqual(result, "图：![截图](images/shot_1.jpg)")
            self.assertEqual([call.args[1] for call in extract.call_args_list], [90, 92])
            self.assertEqual(validate.call_count, 2)
            self.assertFalse(os.path.exists(video_paths[0]))


if __name__ == "__main__":
    unittest.main()
