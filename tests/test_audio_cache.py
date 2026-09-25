import hashlib
import os
import tempfile
import unittest
from unittest import mock

from app import transcribe


class _Download:
    def __init__(self, opts):
        self.path = opts["outtmpl"]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def download(self, _urls):
        with open(self.path, "wb") as output:
            output.write(b"audio")


class TestAudioCache(unittest.TestCase):
    def test_non_bili_url_uses_stable_name_and_reuses_cache(self):
        url = "https://example.org/watch?v=123"
        with tempfile.TemporaryDirectory() as root, \
             mock.patch.object(transcribe, "CACHE_DIR", root), \
             mock.patch.object(transcribe.yt_dlp, "YoutubeDL", side_effect=_Download) as downloader:
            path, downloaded = transcribe.download_audio(url)
            expected = "video_" + hashlib.sha256(url.encode()).hexdigest()[:12] + ".m4a"
            self.assertEqual(os.path.basename(path), expected)
            self.assertTrue(downloaded)
            self.assertEqual(transcribe.download_audio(url), (path, False))
            downloader.assert_called_once()

    def test_failed_download_does_not_poison_cache(self):
        with tempfile.TemporaryDirectory() as root, \
             mock.patch.object(transcribe, "CACHE_DIR", root), \
             mock.patch.object(transcribe.yt_dlp, "YoutubeDL", side_effect=_Download):
            with mock.patch.object(_Download, "download", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "有效文件"):
                    transcribe.download_audio("https://example.org/empty")
            self.assertEqual(os.listdir(root), [])
            _, downloaded = transcribe.download_audio("https://example.org/empty")
            self.assertTrue(downloaded)


if __name__ == "__main__":
    unittest.main()
