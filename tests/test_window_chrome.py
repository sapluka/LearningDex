import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app import window_chrome


class WindowChromeTests(unittest.TestCase):
    def test_custom_caption_preserves_resize_and_window_controls(self):
        style = window_chrome.WS_CAPTION | 0x00040000 | 0x00080000 | 0x00030000
        api = Mock()
        api.get_style.return_value = style
        api.set_style.return_value = style
        api.SetWindowPos.return_value = True
        window = SimpleNamespace(native=SimpleNamespace(Handle=Mock(), ShowIcon=True))
        window.native.Handle.ToInt64.return_value = 42
        with patch.object(window_chrome.sys, "platform", "win32"), \
                patch.object(window_chrome, "_win32", return_value=api):
            window_chrome.prepare(window)
        self.assertFalse(window.native.ShowIcon)
        api.set_style.assert_called_once_with(42, window_chrome.GWL_STYLE, style & ~window_chrome.WS_CAPTION)
        self.assertTrue(window._centered_titlebar)

    def test_window_controls_toggle_native_state_and_reject_unknown_actions(self):
        window = Mock(native=SimpleNamespace(WindowState="Normal"), _centered_titlebar=True)
        window.maximize.side_effect = lambda: setattr(window.native, "WindowState", "Maximized")
        window.restore.side_effect = lambda: setattr(window.native, "WindowState", "Normal")
        self.assertTrue(window_chrome.control(window, "toggle_maximize")["maximized"])
        self.assertFalse(window_chrome.control(window, "toggle_maximize")["maximized"])
        window_chrome.control(window, "minimize")
        window.minimize.assert_called_once()
        window_chrome.control(window, "close")
        window.destroy.assert_called_once()
        with self.assertRaises(ValueError):
            window_chrome.control(window, "invalid")

    def test_late_drag_request_does_not_start_drag_after_mouse_release(self):
        api = Mock()
        api.GetAsyncKeyState.return_value = 0
        with patch.object(window_chrome, "_win32", return_value=api):
            window_chrome.control(SimpleNamespace(native=object()), "drag")
        api.ReleaseCapture.assert_not_called()
        api.SendMessageW.assert_not_called()

    def test_caption_setup_failure_restores_original_style(self):
        api = Mock()
        api.get_style.return_value = window_chrome.WS_CAPTION | 0x00040000
        api.set_style.return_value = api.get_style.return_value
        api.SetWindowPos.return_value = False
        window = SimpleNamespace(native=SimpleNamespace(Handle=Mock()))
        with patch.object(window_chrome.sys, "platform", "win32"), \
                patch.object(window_chrome, "_win32", return_value=api), \
                self.assertRaises(OSError):
            window_chrome.prepare(window)
        self.assertEqual(api.set_style.call_args.args[2], api.get_style.return_value)
        self.assertFalse(window_chrome.state(window)["custom_titlebar"])

    @unittest.skipUnless(os.name == "nt" and os.environ.get("LEARNINGDEX_NATIVE_WINDOW_TESTS"),
                         "需要启用 Windows 窗口检查")
    def test_hidden_native_window_preserves_resizable_frame(self):
        import clr
        clr.AddReference("System.Windows.Forms")
        from System.Windows.Forms import Form, FormWindowState
        form = Form()
        try:
            window = SimpleNamespace(native=form)
            api = window_chrome._win32()
            original = api.get_style(form.Handle.ToInt64(), window_chrome.GWL_STYLE)
            window_chrome.prepare(window)
            updated = api.get_style(form.Handle.ToInt64(), window_chrome.GWL_STYLE)
            self.assertEqual(updated & window_chrome.WS_CAPTION, 0)
            self.assertEqual(updated & 0x00040000, original & 0x00040000)
            self.assertEqual(updated & 0x000B0000, original & 0x000B0000)
            for window_state in (FormWindowState.Maximized, FormWindowState.Normal):
                form.WindowState = window_state
                self.assertEqual(api.get_style(form.Handle.ToInt64(), window_chrome.GWL_STYLE) &
                                 window_chrome.WS_CAPTION, 0)
            self.assertFalse(form.Visible)
        finally:
            form.Dispose()


if __name__ == "__main__":
    unittest.main()
