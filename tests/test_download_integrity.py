import tempfile
import unittest
from unittest import mock

from app import search, transcribe


class TestDownloadIntegrity(unittest.TestCase):
    def test_model_download_rejects_incomplete_file_and_uses_default_tls(self):
        response = mock.MagicMock()
        response.headers = {"Content-Length": "5"}
        response.read.side_effect = [b"x", b""]
        context = mock.MagicMock()
        context.__enter__.return_value = response
        with tempfile.TemporaryDirectory() as root, \
             mock.patch.object(transcribe, "_model_dir", return_value=root), \
             mock.patch.object(transcribe, "MODEL_FILES", ["model.bin"]), \
             mock.patch.object(transcribe, "MODEL_EXTRA", []), \
             mock.patch.object(transcribe.urllib.request, "urlopen", return_value=context) as fetch:
            with self.assertRaises(transcribe.urllib.error.HTTPError):
                transcribe.ensure_model("base")
            fetch.assert_called_once()
            self.assertNotIn("context", fetch.call_args.kwargs)
            self.assertFalse(transcribe.os.path.exists(transcribe.os.path.join(root, "model.bin")))

    def test_web_lookup_uses_default_tls(self):
        response = mock.MagicMock()
        response.read.return_value = b'{"extract":"ok"}'
        context = mock.MagicMock()
        context.__enter__.return_value = response
        with mock.patch.object(search.urllib.request, "urlopen", return_value=context) as fetch:
            self.assertEqual(search._get_json("https://example.org/page"), {"extract": "ok"})
        self.assertNotIn("context", fetch.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
