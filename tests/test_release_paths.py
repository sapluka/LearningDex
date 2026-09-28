import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import config, runtime_paths, skills


class TestReleasePaths(unittest.TestCase):
    def test_frozen_data_uses_local_app_data(self):
        with tempfile.TemporaryDirectory() as root, \
             mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.dict(os.environ, {"LOCALAPPDATA": root}):
            self.assertEqual(runtime_paths.data_root(), Path(root) / "LearningDex")

    def test_frozen_skill_is_copied_once_and_remains_editable(self):
        with tempfile.TemporaryDirectory() as root, \
             mock.patch.object(sys, "frozen", True, create=True):
            builtins = Path(root) / "builtins"
            user = Path(root) / "user"
            builtins.mkdir()
            (builtins / "讲解.md").write_text("原文", encoding="utf-8")
            with mock.patch.object(skills, "BUILTIN_SKILLS_DIR", str(builtins)), \
                 mock.patch.object(skills, "SKILLS_DIR", str(user)):
                self.assertEqual(skills.get("讲解"), "原文")
                self.assertTrue(skills.save("讲解", "修改"))
                self.assertEqual(skills.get("讲解"), "修改")
                self.assertTrue(skills.delete("讲解"))
                self.assertIsNone(skills.get("讲解"))

    def test_config_creates_data_directory_without_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "LearningDex" / "config.json"
            with mock.patch.object(config, "CONFIG_PATH", str(target)):
                config.save({"model": "example", "api_key": "private"})
            saved = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(saved["model"], "example")
            self.assertNotIn("api_key", saved)


if __name__ == "__main__":
    unittest.main()
