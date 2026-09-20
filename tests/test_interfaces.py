import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import agents, main, search


class TestAgentsInterfaces(unittest.TestCase):
    def test_chat_builds_messages(self):
        with mock.patch.object(agents.llm, "text", return_value="答复") as t:
            reply = agents.chat({}, [{"role": "assistant", "content": "之前"}], "新问题", doc="文档内容")
        self.assertEqual(reply, "答复")
        msgs = t.call_args[0][1]
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("文档内容", msgs[0]["content"])
        self.assertEqual(msgs[-1]["content"], "新问题")

    def test_answer_selection_includes_selection(self):
        with mock.patch.object(agents.llm, "text", return_value="解答") as t:
            agents.answer_selection({}, "选中的话", "什么意思", doc="doc")
        msgs = t.call_args[0][1]
        self.assertIn("选中的话", msgs[-1]["content"])
        self.assertIn("选中的话", msgs[-1]["content"])

    def test_explain_term(self):
        with mock.patch.object(agents.llm, "text", return_value="解释") as t:
            agents.explain_term({}, "Mipmap")
        self.assertEqual(t.call_args[0][1][-1]["content"], "Mipmap")


class TestSearch(unittest.TestCase):
    def test_wiki_summary_ok(self):
        with mock.patch.object(search, "_get_json", return_value={"extract": "摘要内容"}):
            r = search.wiki_summary("测试")
        self.assertEqual(r["summary"], "摘要内容")
        self.assertEqual(r["source"], "wikipedia")

    def test_wiki_summary_fail(self):
        with mock.patch.object(search, "_get_json", side_effect=Exception("net")):
            self.assertIsNone(search.wiki_summary("测试"))


class TestChatHistory(unittest.TestCase):
    def test_chat_appends_history(self):
        api = main.Api()
        api.cfg = {}
        with mock.patch.object(agents, "chat", return_value="好"):
            r = api.chat("问题")
        self.assertTrue(r["ok"])
        self.assertEqual(api.history, [
            {"role": "user", "content": "问题"},
            {"role": "assistant", "content": "好"},
        ])


class TestNormalizeMd(unittest.TestCase):
    def test_unescape_highlight(self):
        self.assertEqual(main._normalize_md("\\==x==\n"), "==x==\n")

    def test_keep_normal(self):
        self.assertEqual(main._normalize_md("==x=="), "==x==")

    def test_empty(self):
        self.assertEqual(main._normalize_md(None), "")


if __name__ == "__main__":
    unittest.main()