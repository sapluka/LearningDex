import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import main


class TestFavorites(unittest.TestCase):
    def test_toggle(self):
        with tempfile.TemporaryDirectory() as d:
            api = main.Api()
            api.cfg = {"output_dir": d}
            r = api.toggle_favorite("BV1AAA", "标题A")
            self.assertTrue(r["favorited"])
            self.assertEqual([f["id"] for f in api.list_favorites()["favorites"]], ["BV1AAA"])
            r2 = api.toggle_favorite("BV1AAA")
            self.assertFalse(r2["favorited"])
            self.assertEqual(api.list_favorites()["favorites"], [])

    def test_invalid(self):
        api = main.Api()
        api.cfg = {}
        self.assertFalse(api.toggle_favorite("../x")["ok"])


if __name__ == "__main__":
    unittest.main()