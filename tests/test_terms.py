import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import agents, main


class TestTerms(unittest.TestCase):
    def test_parse_terms_strips_markers(self):
        txt = "- Mipmap\n2. 重心坐标\n• Blinn-Phong\n"
        self.assertEqual(agents._parse_terms(txt), ["Mipmap", "重心坐标", "Blinn-Phong"])

    def test_parse_terms_dedup_and_empty(self):
        self.assertEqual(agents._parse_terms("A\nA\n\n"), ["A"])
        self.assertEqual(agents._parse_terms(""), [])

    def test_explain_api(self):
        api = main.Api()
        with mock.patch.object(agents, "explain_term", return_value="解答"):
            r = api.explain("Mipmap")
        self.assertTrue(r["ok"])
        self.assertEqual(r["answer"], "解答")

    def test_extract_terms_uses_llm(self):
        with mock.patch.object(agents.llm, "text", return_value="术语A\n术语B"):
            self.assertEqual(agents.extract_terms({}, "doc"), ["术语A", "术语B"])


if __name__ == "__main__":
    unittest.main()