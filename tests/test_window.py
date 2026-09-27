from types import SimpleNamespace
import unittest
from unittest.mock import patch

from webview.event import Event

from app import main, window_chrome


class WindowTests(unittest.TestCase):
    def test_window_title_and_icon_before_show(self):
        window = SimpleNamespace(native=SimpleNamespace(ShowIcon=True))
        window.events = SimpleNamespace(**{name: Event(window, True) for name in
                                           ("before_show", "loaded", "maximized", "restored")})
        with patch.object(main, "Api"), patch.object(main.web_server, "create_app"), \
                patch.object(main.webview, "create_window", return_value=window) as create, \
                patch.object(main.webview, "start", side_effect=window.events.before_show.set):
            main.main()
        self.assertEqual(create.call_args.args[0], "LearningDex")
        self.assertFalse(window.native.ShowIcon)
        self.assertNotIn("frameless", create.call_args.kwargs)

    def test_other_window_backends_need_no_icon_property(self):
        window_chrome.prepare(SimpleNamespace(native=object()))


if __name__ == "__main__":
    unittest.main()
