import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config


class TestPersonalIsolation(unittest.TestCase):
    def test_save_strips_sensitive(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch.object(config, "CONFIG_PATH", path):
                config.save({
                    "protocol": "anthropic", "base_url": "http://x", "model": "m",
                    "api_key": "sk-secret", "bili_sessdata": "sess",
                    "cookies_file": "C:/c.txt", "cookies_text": "netscape",
                    "whisper_model": "base", "proofread": True,
                })
                with open(path, encoding="utf-8") as f:
                    saved = json.load(f)
            for k in config.SENSITIVE:
                self.assertNotIn(k, saved)
            self.assertEqual(saved["protocol"], "anthropic")
            self.assertEqual(saved["model"], "m")

    def test_load_injects_from_personal(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch.object(config, "CONFIG_PATH", path), \
                 mock.patch.object(config, "_personal", return_value={"api_key": "sk-personal"}), \
                 mock.patch.dict(os.environ, {}, clear=True):
                cfg = config.load()
        self.assertEqual(cfg["api_key"], "sk-personal")

    def test_env_overrides_personal(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch.object(config, "CONFIG_PATH", path), \
                 mock.patch.object(config, "_personal", return_value={"api_key": "sk-personal"}), \
                 mock.patch.dict(os.environ, {"LLM_API_KEY": "sk-env"}):
                cfg = config.load()
        self.assertEqual(cfg["api_key"], "sk-env")

    def test_defaults_present(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch.object(config, "CONFIG_PATH", path), \
                 mock.patch.object(config, "_personal", return_value={}), \
                 mock.patch.dict(os.environ, {}, clear=True):
                cfg = config.load()
        for k in config.SENSITIVE:
            self.assertIn(k, cfg)


if __name__ == "__main__":
    unittest.main()