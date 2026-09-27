import inspect
import unittest
from unittest import mock

import yt_dlp
from yt_dlp.utils import ExtractorError

from app import bilibili


URL = "https://www.bilibili.com/video/BV1CQt365EzW"


class TestBilibiliAdapter(unittest.TestCase):
    def test_playback_referer_changes_without_losing_signing_parameters(self):
        original_headers = {"Referer": URL, "User-Agent": "browser"}
        query = {"qn": 64, "try_look": 1}
        with mock.patch.object(bilibili.BaseBiliBiliIE, "_download_json", autospec=True,
                return_value={"code": 0, "data": {"dash": {}}}) as request, \
                mock.patch.object(bilibili.BaseBiliBiliIE, "is_logged_in",
                    new_callable=mock.PropertyMock, return_value=False), \
                mock.patch.object(bilibili.BaseBiliBiliIE, "_sign_wbi",
                    side_effect=lambda params, _: {**params, "w_rid": "signature"}):
            result = bilibili.BiliBiliIE()._download_playinfo("BV1CQt365EzW", 123,
                headers=original_headers, query=query)
        self.assertEqual(result, {"dash": {}})
        request.assert_called_once()
        self.assertEqual(request.call_args.args[1:],
            ("https://api.bilibili.com/x/player/wbi/playurl", "BV1CQt365EzW"))
        options = request.call_args.kwargs
        self.assertEqual(options["headers"],
            {"Referer": "https://www.bilibili.com/", "User-Agent": "browser"})
        for key, value in {"bvid": "BV1CQt365EzW", "cid": 123, "qn": 64,
                "try_look": 1, "w_rid": "signature"}.items():
            self.assertEqual(options["query"][key], value)
        self.assertEqual(original_headers["Referer"], URL)
        self.assertEqual(query, {"qn": 64, "try_look": 1})

    def test_playback_api_uses_upstream_signature(self):
        # 新版增加 fatal；直接继承，避免适配层遗漏新参数。
        self.assertIs(bilibili.BiliBiliIE._download_playinfo,
            bilibili.BaseBiliBiliIE._download_playinfo)

    def test_request_options_and_nonfatal_result_pass_through(self):
        headers = {"Referer": URL, "User-Agent": "browser"}
        query = {"w_rid": "signature"}
        with mock.patch.object(bilibili.BaseBiliBiliIE, "_download_json", autospec=True,
                return_value=None) as request:
            extractor = bilibili.BiliBiliIE()
            result = extractor._download_json("https://api.bilibili.com/x/player/wbi/playurl",
                "video", "note", fatal=False, headers=headers, query=query,
                expected_status=(200, 400), impersonate="chrome")
        self.assertIsNone(result)
        request.assert_called_once_with(extractor,
            "https://api.bilibili.com/x/player/wbi/playurl", "video", "note",
            fatal=False, headers={"Referer": "https://www.bilibili.com/", "User-Agent": "browser"},
            query=query, expected_status=(200, 400), impersonate="chrome")
        self.assertEqual(headers["Referer"], URL)

    def test_other_requests_keep_original_headers(self):
        headers = {"Referer": URL}
        for url in ("https://api.bilibili.com/x/web-interface/nav",
                "https://api.bilibili.com/x/player/wbi/v2",
                "https://api.bilibili.com.invalid/x/player/wbi/playurl"):
            with self.subTest(url=url), mock.patch.object(bilibili.BaseBiliBiliIE,
                    "_download_json", autospec=True, return_value={}) as request:
                extractor = bilibili.BiliBiliIE()
                extractor._download_json(url, "video", headers=headers, fatal=False)
                request.assert_called_once_with(extractor, url, "video", headers=headers, fatal=False)

    def test_playback_request_without_headers_gets_homepage_referer(self):
        with mock.patch.object(bilibili.BaseBiliBiliIE, "_download_json", autospec=True,
                return_value={}) as request:
            extractor = bilibili.BiliBiliIE()
            extractor._download_json("https://api.bilibili.com/x/player/wbi/playurl", "video")
        request.assert_called_once_with(extractor,
            "https://api.bilibili.com/x/player/wbi/playurl", "video",
            headers={"Referer": "https://www.bilibili.com/"})

    def test_extractor_replaces_only_bilibili_in_current_instance(self):
        with yt_dlp.YoutubeDL({"quiet": True}) as downloader:
            original = downloader.get_info_extractor("BiliBili")
            youtube = downloader.get_info_extractor("Youtube")
            bilibili.configure(downloader)
            replacement = downloader.get_info_extractor("BiliBili")
            self.assertIsInstance(replacement, bilibili.BiliBiliIE)
            self.assertIsNot(replacement, original)
            self.assertIs(downloader.get_info_extractor("Youtube"), youtube)
        self.assertNotEqual(bilibili.BaseBiliBiliIE, bilibili.BiliBiliIE)

    @unittest.skipUnless("fatal" in inspect.signature(bilibili.BaseBiliBiliIE._download_playinfo).parameters,
        "当前 yt-dlp 没有 fatal 参数；此用例在新版环境运行")
    def test_new_playback_fatal_flag_preserves_error_handling(self):
        extractor = bilibili.BiliBiliIE()
        with mock.patch.object(bilibili.BaseBiliBiliIE, "_download_json", autospec=True,
                return_value={"code": -352, "message": "temporarily unavailable"}) as request, \
                mock.patch.object(bilibili.BaseBiliBiliIE, "is_logged_in",
                    new_callable=mock.PropertyMock, return_value=False), \
                mock.patch.object(bilibili.BaseBiliBiliIE, "_sign_wbi", side_effect=lambda params, _: params), \
                mock.patch.object(extractor, "report_warning") as warning:
            self.assertIsNone(extractor._download_playinfo("video", 123, fatal=False))
            warning.assert_called_once()
            with self.assertRaises(ExtractorError):
                extractor._download_playinfo("video", 123, fatal=True)
        self.assertEqual(request.call_count, 2)
        for call in request.call_args_list:
            self.assertEqual(call.kwargs["headers"]["Referer"], "https://www.bilibili.com/")


if __name__ == "__main__":
    unittest.main()
