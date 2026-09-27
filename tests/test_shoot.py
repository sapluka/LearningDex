import os
import sys
import unittest
import tempfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import agents, shoot
from app.shot_status import ShotError, validation_error, report_note


class TestShoot(unittest.TestCase):
    def test_parse_shots(self):
        md = "文本 ![图](SHOT:01:30) 还有 ![a](SHOT:1:02:03)"
        shots = shoot.parse_shots(md)
        self.assertEqual(shots[0][2], "01:30")
        self.assertEqual(shots[1][2], "1:02:03")
        self.assertEqual(shots[0][1], "图")
        self.assertEqual(shoot.parse_shots("![图](SHOT:105:12)")[0][2], "105:12")

    def test_to_seconds(self):
        self.assertEqual(shoot._to_seconds("01:30"), 90)
        self.assertEqual(shoot._to_seconds("1:02:03"), 3723)

    def test_capture_no_shots_returns_same(self):
        self.assertEqual(shoot.capture("no shots here", "u", "d", {}), "no shots here")


class TestShotPrompt(unittest.TestCase):
    def test_ts_transcript(self):
        segs = [{"from": 90, "to": 95, "text": "a"}, {"from": None, "text": "b"}]
        self.assertEqual(agents._ts_transcript(segs), "[01:30] a")

    def test_validate_frame_errors_are_not_negative_judgments(self):
        with mock.patch.object(agents.llm, "text", side_effect=Exception("no vision")):
            with self.assertRaises(ShotError):
                agents.validate_frame({}, "does_not_exist.jpg", "cap")

    def test_validation_distinguishes_invalid_image_from_unsupported_model(self):
        self.assertEqual(validation_error(Exception("You have uploaded an unsupported image")).code, "invalid_image")
        self.assertEqual(validation_error(Exception("image inputs are not supported")).code, "vision_unsupported")

    def test_deepseek_validation_disables_thinking_and_allows_answer_budget(self):
        with tempfile.TemporaryDirectory() as root:
            frame = os.path.join(root, "frame.jpg")
            with open(frame, "wb") as file:
                file.write(b"frame")
            with mock.patch.object(agents.llm, "text", return_value="是") as request:
                self.assertTrue(agents.validate_frame({"protocol": "anthropic", "base_url": "https://api.deepseek.com/anthropic"}, frame))
            self.assertEqual(request.call_args.kwargs["extra_body"], {"thinking": {"type": "disabled"}})
            self.assertGreaterEqual(request.call_args.kwargs["max_tokens"], 1024)
            with mock.patch.object(agents.llm, "text", return_value=None):
                with self.assertRaisesRegex(ShotError, "未返回有效判断"):
                    agents.validate_frame({}, frame)
            with mock.patch.object(agents.llm, "text", return_value="否"):
                self.assertFalse(agents.validate_frame({}, frame))

    def test_capture_records_download_failure(self):
        report = {}
        with tempfile.TemporaryDirectory() as root, \
                mock.patch.object(shoot, "_download_video", side_effect=ShotError("download_rejected")):
            result = shoot.capture("正文 ![截图](SHOT:01:30)", "url", root, {}, report=report)
        self.assertEqual(result, "正文 ")
        self.assertEqual(report["captured"], 0)
        self.assertIn("HTTP 412", report_note(report))

    def test_capture_stops_after_validation_service_error(self):
        def frame(video, sec, out):
            with open(out, "wb") as file:
                file.write(b"frame")
            return out
        report = {}
        with tempfile.TemporaryDirectory() as root, \
                mock.patch.object(shoot, "_download_video", return_value="video"), \
                mock.patch.object(shoot, "_frame", side_effect=frame), \
                mock.patch.object(agents, "validate_frame", side_effect=ShotError("validation_response")) as validate:
            result = shoot.capture("![一](SHOT:01:30) ![二](SHOT:02:30)", "url", root, {}, report=report)
            self.assertEqual(os.listdir(os.path.join(root, "images")), [])
        self.assertNotIn("SHOT:", result)
        validate.assert_called_once()
        self.assertEqual(report["planned"], 2)
        self.assertIn("未返回有效判断", report_note(report))

    def test_download_refreshes_cookies_for_412_and_rejects_partial_files(self):
        with tempfile.TemporaryDirectory() as root:
            attempts = []
            def download(urls):
                attempts.append(urls)
                if len(attempts) == 1:
                    raise Exception("HTTP 412")
                with open(os.path.join(root, "source.mp4"), "wb") as file:
                    file.write(b"video")
            client = mock.MagicMock()
            client.__enter__.return_value.download.side_effect = download
            with mock.patch.object(shoot.yt_dlp, "YoutubeDL", return_value=client), \
                    mock.patch.object(shoot.subtitle, "_cookie_source", return_value="cookie"), \
                    mock.patch.object(shoot.subtitle, "_refresh") as refresh, \
                    mock.patch.object(shoot.time, "sleep"):
                self.assertTrue(shoot._download_video("https://www.bilibili.com/video/example", {}, root).endswith(".mp4"))
                refresh.assert_called_once()
            os.remove(os.path.join(root, "source.mp4"))
            with open(os.path.join(root, "source.mp4.part"), "wb") as file:
                file.write(b"incomplete")
            client.__enter__.return_value.download.side_effect = None
            with mock.patch.object(shoot.yt_dlp, "YoutubeDL", return_value=client), \
                    mock.patch.object(shoot.subtitle, "_cookie_source", return_value="cookie"):
                with self.assertRaisesRegex(ShotError, "下载失败"):
                    shoot._download_video("https://www.bilibili.com/video/example", {}, root)

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
