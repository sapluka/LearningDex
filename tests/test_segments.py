import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import subtitle


class TestSegments(unittest.TestCase):
    def test_subtitle_segments(self):
        body = {"body": [{"from": 0, "to": 1.5, "content": "a"}, {"from": 1.5, "to": 3, "content": "b"},
                         {"from": 3, "to": 4, "content": "  "}]}
        with mock.patch.object(subtitle, "_download_json", return_value=body):
            segs = subtitle._subtitle_segments("x")
        self.assertEqual([s["text"] for s in segs], ["a", "b"])
        self.assertEqual(segs[0]["from"], 0.0)
        self.assertEqual(segs[1]["to"], 3.0)

    def test_segments_missing_time(self):
        body = {"body": [{"content": "only text"}]}
        with mock.patch.object(subtitle, "_download_json", return_value=body):
            segs = subtitle._subtitle_segments("x")
        self.assertEqual(segs, [{"from": None, "to": None, "text": "only text"}])


if __name__ == "__main__":
    unittest.main()