import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from app import main


class DirectorySelectionTests(unittest.TestCase):
    def setUp(self):
        with patch.object(main.config, "load", return_value={}):
            self.api = main.Api()

    def test_selection_uses_each_configured_directory_without_saving(self):
        with tempfile.TemporaryDirectory() as root:
            notes = os.path.join(root, "notes")
            pdf = os.path.join(root, "pdf")
            os.makedirs(notes)
            os.makedirs(pdf)
            self.api.cfg = {"output_dir": notes, "pdf_output_dir": pdf}
            window = Mock()
            for method, directory in ((self.api.choose_output_dir, notes),
                                      (self.api.choose_pdf_output_dir, pdf)):
                with self.subTest(directory=directory), \
                        patch.object(main.webview, "windows", [window]), \
                        patch.object(main.config, "save") as save:
                    selected = os.path.join(root, "新目录")
                    window.create_file_dialog.return_value = (selected,)
                    self.assertEqual(method(), {"ok": True, "path": selected})
                    window.create_file_dialog.assert_called_with(
                        main.webview.FOLDER_DIALOG, directory=directory)
                    self.assertEqual(self.api.cfg, {"output_dir": notes, "pdf_output_dir": pdf})
                    save.assert_not_called()

    def test_pdf_directory_defaults_to_task_directory(self):
        with tempfile.TemporaryDirectory() as root, \
                patch.object(main.webview, "windows", [Mock()]) as windows:
            self.api.cfg = {"output_dir": root}
            windows[0].create_file_dialog.return_value = root
            self.assertEqual(self.api.choose_pdf_output_dir(), {"ok": True, "path": root})
            windows[0].create_file_dialog.assert_called_once_with(
                main.webview.FOLDER_DIALOG, directory=root)

    def test_cancel_returns_empty_path_for_both_choosers(self):
        with patch.object(main.webview, "windows", [Mock()]) as windows:
            for method in (self.api.choose_output_dir, self.api.choose_pdf_output_dir):
                for cancelled in (None, (), [], ""):
                    with self.subTest(method=method.__name__, cancelled=cancelled):
                        windows[0].create_file_dialog.return_value = cancelled
                        self.assertEqual(method(), {"ok": True, "path": ""})

    def test_invalid_starting_directory_does_not_block_selection(self):
        with tempfile.TemporaryDirectory() as root, \
                patch.object(main.webview, "windows", [Mock()]) as windows:
            self.api.cfg = {"output_dir": os.path.join(root, "missing")}
            windows[0].create_file_dialog.return_value = [root]
            self.assertEqual(self.api.choose_output_dir()["path"], root)
            windows[0].create_file_dialog.assert_called_once_with(
                main.webview.FOLDER_DIALOG, directory="")

    def test_dialog_failure_is_reported(self):
        window = Mock()
        window.create_file_dialog.side_effect = RuntimeError("无法打开目录选择")
        with patch.object(main.webview, "windows", [window]):
            for method in (self.api.choose_output_dir, self.api.choose_pdf_output_dir):
                self.assertEqual(method(), {"ok": False, "error": "无法打开目录选择"})


if __name__ == "__main__":
    unittest.main()
