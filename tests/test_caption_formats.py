import json
import unittest
from unittest import mock

from app import subtitle


class TestCaptionFormats(unittest.TestCase):
    def test_vtt_cues_keep_timestamps_and_deduplicate(self):
        data = """WEBVTT

00:00:01.000 --> 00:00:02.500 align:start
<c>你好</c>

00:00:02.500 --> 00:00:03.000
<c>你好</c>

00:00:03.000 --> 00:00:04.000
第二句
"""
        self.assertEqual(subtitle._parse_cues(data), [
            {"from": 1.0, "to": 2.5, "text": "你好"},
            {"from": 3.0, "to": 4.0, "text": "第二句"},
        ])

    def test_srt_and_json3(self):
        srt = "1\n00:00:01,000 --> 00:00:02,000\nFirst line\n"
        self.assertEqual(subtitle._parse_cues(srt)[0]["text"], "First line")
        data = json.dumps({"events": [{"tStartMs": 1500, "dDurationMs": 800,
                                       "segs": [{"utf8": "Hello"}, {"utf8": " world"}]}]})
        self.assertEqual(subtitle._parse_json3(data),
                         [{"from": 1.5, "to": 2.3, "text": "Hello world"}])

    def test_supported_chinese_format_preferred(self):
        subs = {
            "en": [{"ext": "vtt", "url": "en.vtt"}],
            "zh-CN": [{"ext": "ttml", "url": "zh.xml"}, {"ext": "vtt", "url": "zh.vtt"}],
        }
        self.assertEqual(subtitle._pick(subs)["url"], "zh.vtt")

    def test_extract_uses_auto_captions_when_manual_format_unsupported(self):
        info = {"title": "Test", "subtitles": {"zh": [{"ext": "ttml", "url": "x"}]},
                "automatic_captions": {"en": [{"ext": "vtt", "data": "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi\n"}]}}
        ydl = mock.MagicMock()
        ydl.extract_info.return_value = info
        context = mock.MagicMock()
        context.__enter__.return_value = ydl
        with mock.patch.object(subtitle.yt_dlp, "YoutubeDL", return_value=context):
            result = subtitle._extract("https://example.com/v", {})
        self.assertEqual(result["subtitle"], "Hi")
        self.assertEqual(result["segments"][0]["from"], 1.0)


if __name__ == "__main__":
    unittest.main()
