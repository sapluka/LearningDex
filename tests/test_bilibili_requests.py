import os
import tempfile
import unittest
from unittest import mock

from app import shoot, subtitle, transcribe


URL = "https://www.bilibili.com/video/BV1CQt365EzW"


class TestBilibiliRequests(unittest.TestCase):
    def test_cookie_bootstrap_and_downloader_use_same_user_agent(self):
        subtitle.configure({})
        opener = mock.Mock()
        with mock.patch.object(subtitle, "_external_cookies", return_value=None), \
                mock.patch.object(subtitle.urllib.request, "build_opener", return_value=opener), \
                mock.patch.object(subtitle, "_write_netscape"), \
                mock.patch.object(subtitle, "_cookie_source", return_value="cookies"):
            subtitle._jar_ensure()
            options = subtitle.bilibili_options()
        self.assertEqual(options["http_headers"]["User-Agent"], dict(opener.addheaders)["User-Agent"])
        self.assertEqual(options["cookiefile"], "cookies")

    def test_subtitle_retry_keeps_user_agent_and_refreshes_cookies(self):
        attempts = []

        def extract(url, options):
            attempts.append(options)
            if len(attempts) == 1:
                raise RuntimeError("HTTP 412")
            return {"subtitle": "ok"}

        with mock.patch.object(subtitle, "_cookie_source", side_effect=["old", "new"]), \
                mock.patch.object(subtitle, "_refresh") as refresh, \
                mock.patch.object(subtitle.time, "sleep"), \
                mock.patch.object(subtitle, "_extract", side_effect=extract):
            self.assertEqual(subtitle.extract(URL, {})["subtitle"], "ok")
        self.assert_requests(attempts)
        refresh.assert_called_once()

    def assert_requests(self, attempts):
        self.assertEqual([item["cookiefile"] for item in attempts], ["old", "new"])
        self.assertEqual([item["http_headers"]["User-Agent"] for item in attempts], [subtitle.UA] * 2)

    def download_client(self, attempts, file_path):
        def client(options):
            attempts.append({**options, "http_headers": dict(options["http_headers"])})
            result = mock.MagicMock()

            def download(urls):
                self.assertEqual(urls, [URL])
                if len(attempts) == 1:
                    raise RuntimeError("HTTP 412")
                with open(file_path(options), "wb") as output:
                    output.write(b"media")

            result.__enter__.return_value.download.side_effect = download
            return result
        return client

    def test_screenshot_download_and_retry_use_consistent_user_agent(self):
        attempts = []
        with tempfile.TemporaryDirectory() as root, \
                mock.patch.object(subtitle, "_cookie_source", side_effect=["old", "new"]), \
                mock.patch.object(subtitle, "_refresh"), \
                mock.patch.object(shoot.time, "sleep"), \
                mock.patch.object(shoot.yt_dlp, "YoutubeDL", side_effect=self.download_client(
                    attempts, lambda opts: os.path.join(root, "source.mp4"))):
            self.assertTrue(os.path.isfile(shoot._download_video(URL, {}, root)))
        self.assert_requests(attempts)

    def test_audio_download_and_retry_use_consistent_user_agent(self):
        attempts = []
        with tempfile.TemporaryDirectory() as root, \
                mock.patch.object(transcribe, "CACHE_DIR", root), \
                mock.patch.object(subtitle, "_cookie_source", side_effect=["old", "new"]), \
                mock.patch.object(subtitle, "_refresh"), \
                mock.patch.object(transcribe.time, "sleep"), \
                mock.patch.object(transcribe.yt_dlp, "YoutubeDL", side_effect=self.download_client(
                    attempts, lambda opts: opts["outtmpl"])):
            path, downloaded = transcribe.download_audio(URL, {})
            self.assertTrue(downloaded)
            self.assertTrue(os.path.isfile(path))
        self.assert_requests(attempts)


if __name__ == "__main__":
    unittest.main()
