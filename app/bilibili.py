from urllib.parse import urlsplit

from yt_dlp.extractor.bilibili import BiliBiliIE as BaseBiliBiliIE


class BiliBiliIE(BaseBiliBiliIE):
    """播放接口使用首页来源，避免视频页来源触发 HTTP 412。"""

    def _download_json(self, url_or_request, *args, **kwargs):
        # 保留上游播放函数的完整接口，包括新版的 fatal 参数。
        if isinstance(url_or_request, str):
            url = urlsplit(url_or_request)
            if url.hostname == "api.bilibili.com" and url.path == "/x/player/wbi/playurl":
                kwargs["headers"] = {**(kwargs.get("headers") or {}),
                    "Referer": "https://www.bilibili.com/"}
        return super()._download_json(url_or_request, *args, **kwargs)


def configure(downloader):
    # 沿用原提取器标识，在此下载实例内替换，不修改全局类。
    downloader.add_info_extractor(BiliBiliIE())
