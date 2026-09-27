import ctypes
import os
import struct
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app import window_chrome


class WindowChromeTests(unittest.TestCase):
    def test_application_id_is_set_before_window_creation(self):
        api = Mock()
        api.SetCurrentProcessExplicitAppUserModelID.return_value = 0
        with patch.object(window_chrome.sys, "platform", "win32"), \
                patch.object(window_chrome, "_shell32", return_value=api):
            window_chrome.initialize()
            api.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(window_chrome.APP_ID)
            api.SetCurrentProcessExplicitAppUserModelID.return_value = -1
            with self.assertRaises(OSError):
                window_chrome.initialize()
        with patch.object(window_chrome.sys, "platform", "linux"), \
                patch.object(window_chrome, "_shell32") as shell:
            window_chrome.initialize()
        shell.assert_not_called()

    def test_icon_has_valid_images_for_windows_display_sizes(self):
        data = Path(window_chrome.ICON_PATH).read_bytes()
        reserved, kind, count = struct.unpack_from("<HHH", data)
        self.assertEqual((reserved, kind, count), (0, 1, 7))
        sizes = []
        for i in range(count):
            width, height, _, _, planes, depth, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
            self.assertEqual(planes, 0)
            self.assertEqual(depth, 32)
            width, height = width or 256, height or 256
            self.assertEqual(width, height)
            sizes.append(width)
            self.assertEqual(data[offset:offset + 8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack_from(">II", data, offset + 16), (width, height))
            self.assertLessEqual(offset + length, len(data))
        self.assertEqual(sizes, [16, 24, 32, 48, 64, 128, 256])

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
        self.assertTrue(window.native.ShowIcon)
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
        with patch.object(window_chrome, "_win32", return_value=api), \
                patch.object(window_chrome, "_invoke_on_ui", side_effect=lambda native, cb: cb()):
            window_chrome.control(SimpleNamespace(native=object()), "drag")
        api.ReleaseCapture.assert_not_called()
        api.SendMessageW.assert_not_called()

    def test_drag_dispatches_on_ui_thread_with_current_cursor_coordinates(self):
        api = Mock()
        api.GetAsyncKeyState.return_value = 0x8000
        def cursor(pointer):
            pointer._obj.x = -100
            pointer._obj.y = 200
            return True
        api.GetCursorPos.side_effect = cursor
        window = SimpleNamespace(native=SimpleNamespace(Handle=Mock()))
        window.native.Handle.ToInt64.return_value = 42
        with patch.object(window_chrome, "_win32", return_value=api), \
                patch.object(window_chrome, "_invoke_on_ui",
                             side_effect=lambda native, cb: cb()) as invoke:
            window_chrome.control(window, "drag")
        invoke.assert_called_once()
        self.assertIs(invoke.call_args.args[0], window.native)
        api.ReleaseCapture.assert_called_once()
        api.SendMessageW.assert_called_once_with(42, 0xA1, 2, (200 << 16) | (-100 & 0xFFFF))

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
        window_chrome.initialize()
        shell = window_chrome._shell32()
        shell.GetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        shell.GetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
        app_id = ctypes.c_void_p()
        self.assertEqual(shell.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(app_id)), 0)
        try:
            self.assertEqual(ctypes.wstring_at(app_id), window_chrome.APP_ID)
        finally:
            ole = ctypes.WinDLL("ole32")
            ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
            ole.CoTaskMemFree.restype = None
            ole.CoTaskMemFree(app_id)
        import clr
        clr.AddReference("System.Windows.Forms")
        from System.Drawing import Icon
        from System.Windows.Forms import Form, FormWindowState
        form = Form()
        icon = Icon(window_chrome.ICON_PATH)
        form.Icon = icon
        try:
            window = SimpleNamespace(native=form)
            api = window_chrome._win32()
            original = api.get_style(form.Handle.ToInt64(), window_chrome.GWL_STYLE)
            window_chrome.prepare(window)
            updated = api.get_style(form.Handle.ToInt64(), window_chrome.GWL_STYLE)
            self.assertEqual(updated & window_chrome.WS_CAPTION, 0)
            self.assertEqual(updated & 0x00040000, original & 0x00040000)
            self.assertEqual(updated & 0x000B0000, original & 0x000B0000)
            self.assertTrue(form.ShowIcon)
            self.assertNotEqual(api.SendMessageW(form.Handle.ToInt64(), 0x7F, 1, 0), 0)
            for window_state in (FormWindowState.Maximized, FormWindowState.Normal):
                form.WindowState = window_state
                self.assertEqual(api.get_style(form.Handle.ToInt64(), window_chrome.GWL_STYLE) &
                                 window_chrome.WS_CAPTION, 0)
            self.assertFalse(form.Visible)
        finally:
            form.Dispose()
            icon.Dispose()


if __name__ == "__main__":
    unittest.main()
