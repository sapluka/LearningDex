import http.cookiejar
import unittest
from unittest import mock

from app import subtitle


class TestCookiePriority(unittest.TestCase):
    def test_cookie_file_session_wins_over_injected_sessdata(self):
        subtitle.configure({"bili_sessdata": "injected-session"})

        def load_cookie(jar, path):
            jar.set_cookie(subtitle._sess_cookie("file-session"))

        with mock.patch.object(subtitle, "_external_cookies", return_value="cookies.txt"), \
             mock.patch.object(subtitle, "_load_cookies_into", side_effect=load_cookie), \
             mock.patch.object(subtitle, "_write_netscape"):
            jar = subtitle._jar_ensure()
        self.assertEqual(next(c.value for c in jar if c.name == "SESSDATA"), "file-session")

    def test_anonymous_bootstrap_failure_does_not_block_extraction(self):
        subtitle.configure({})
        opener = mock.Mock()
        opener.open.side_effect = OSError("offline")
        with mock.patch.object(subtitle, "_external_cookies", return_value=None), \
             mock.patch.object(subtitle.urllib.request, "build_opener", return_value=opener), \
             mock.patch.object(subtitle, "_write_netscape"):
            jar = subtitle._jar_ensure()
        self.assertIsInstance(jar, http.cookiejar.CookieJar)


if __name__ == "__main__":
    unittest.main()
