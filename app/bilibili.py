from yt_dlp.extractor.bilibili import BiliBiliIE as BaseBiliBiliIE


class BiliBiliIE(BaseBiliBiliIE):
    """播放接口使用首页来源，避免视频页来源触发 HTTP 412。"""

    def _download_playinfo(self, bvid, cid, headers=None, query=None):
        headers = {**(headers or {}), "Referer": "https://www.bilibili.com/"}
        return super()._download_playinfo(bvid, cid, headers=headers, query=query)


def configure(downloader):
    # 沿用原提取器标识，在此下载实例内替换，不修改全局类。
    downloader.add_info_extractor(BiliBiliIE())
