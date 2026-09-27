import ctypes
import json
import sys
from ctypes import wintypes
from functools import lru_cache

WS_CAPTION = 0x00C00000
GWL_STYLE = -16
SWP_FRAMECHANGED = 0x20


@lru_cache(maxsize=1)
def _win32():
    api = ctypes.WinDLL("user32", use_last_error=True)
    pointer_size = ctypes.sizeof(ctypes.c_void_p)
    api.get_style = api.GetWindowLongPtrW if pointer_size == 8 else api.GetWindowLongW
    api.set_style = api.SetWindowLongPtrW if pointer_size == 8 else api.SetWindowLongW
    api.get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    api.get_style.restype = ctypes.c_ssize_t
    api.set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    api.set_style.restype = ctypes.c_ssize_t
    api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    api.SetWindowPos.restype = wintypes.BOOL
    api.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    api.GetCursorPos.restype = wintypes.BOOL
    api.GetAsyncKeyState.argtypes = [ctypes.c_int]
    api.GetAsyncKeyState.restype = ctypes.c_short
    api.ReleaseCapture.argtypes = []
    api.ReleaseCapture.restype = wintypes.BOOL
    api.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    api.SendMessageW.restype = ctypes.c_ssize_t
    return api


def prepare(window):
    native = window.native
    if hasattr(native, "ShowIcon"):
        native.ShowIcon = False
    if sys.platform != "win32" or not hasattr(native, "Handle"):
        return
    api = _win32()
    handle = native.Handle.ToInt64()
    style = api.get_style(handle, GWL_STYLE)
    ctypes.set_last_error(0)
    previous = api.set_style(handle, GWL_STYLE, style & ~WS_CAPTION)
    if not previous and ctypes.get_last_error():
        raise ctypes.WinError()
    # 保留系统缩放边框及窗口状态，只替换标题栏。
    if not api.SetWindowPos(handle, None, 0, 0, 0, 0, SWP_FRAMECHANGED | 0x17):
        api.set_style(handle, GWL_STYLE, style)
        raise ctypes.WinError()
    window._centered_titlebar = True


def state(window):
    return {"custom_titlebar": bool(getattr(window, "_centered_titlebar", False)),
            "maximized": str(getattr(window.native, "WindowState", "")) == "Maximized"}


def notify_state(window):
    if state(window)["custom_titlebar"]:
        window.evaluate_js("window.__setWindowState && window.__setWindowState(%s)" %
                           json.dumps(state(window)))


def control(window, action):
    if action == "minimize":
        window.minimize()
    elif action == "toggle_maximize":
        if state(window)["maximized"]:
            window.restore()
        else:
            window.maximize()
    elif action == "close":
        window.destroy()
    elif action == "drag":
        api = _win32()
        if api.GetAsyncKeyState(0x01) & 0x8000:
            point = wintypes.POINT()
            if not api.GetCursorPos(ctypes.byref(point)):
                raise ctypes.WinError()
            position = ctypes.c_int32((point.x & 0xFFFF) | ((point.y & 0xFFFF) << 16)).value
            api.ReleaseCapture()
            api.SendMessageW(window.native.Handle.ToInt64(), 0xA1, 2, position)
    else:
        raise ValueError("未知窗口操作")
    return state(window)
