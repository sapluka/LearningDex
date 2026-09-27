MESSAGES = {
    "no_plan": "模型未安排截图位置",
    "missing_timestamps": "字幕缺少时间戳，无法定位截图",
    "download_rejected": "视频网站拒绝截图视频下载（HTTP 412）",
    "download_failed": "截图视频下载失败，请检查网络和视频访问权限",
    "ffmpeg_missing": "视频取帧组件不可用",
    "frame_failed": "视频取帧失败",
    "vision_unsupported": "当前模型不支持图片输入，请配置可识图模型",
    "invalid_image": "截图图片格式无效，无法核验",
    "validation_failed": "图片核验请求失败，请检查模型连接和配置",
    "validation_response": "图片核验未返回有效判断",
    "validation_auth": "图片核验认证失败，请检查 API 配置",
    "validation_unavailable": "图片核验连续失败，已停止剩余截图",
    "rejected": "候选画面未通过清晰度或内容核验",
    "unexpected": "截图处理异常",
}


class ShotError(RuntimeError):
    def __init__(self, code, details=None):
        self.code = code
        self.details = details or {}
        super().__init__(MESSAGES[code])


def validation_error(error):
    text = str(error).lower()
    unsupported = any(word in text for word in ("image input is not supported",
        "image inputs are not supported", "image content is not supported",
        "does not support image", "doesn't support image"))
    if unsupported:
        return ShotError("vision_unsupported")
    if any(word in text for word in ("unsupported image", "invalid image", "image is invalid")):
        return ShotError("invalid_image")
    if getattr(error, "status_code", None) in (401, 403) or any(word in text for word in
            ("invalid api key", "authenticationerror", "permissiondeniederror")):
        return ShotError("validation_auth")
    return ShotError("validation_failed")


def report_note(report):
    if not isinstance(report, dict) or report.get("status") in ("complete", "disabled"):
        return ""
    codes = list(dict.fromkeys(item.get("code") for item in report.get("failures", [])))
    reasons = "；".join(MESSAGES[code] for code in codes if code in MESSAGES)
    if not reasons:
        return ""
    captured = report.get("captured", 0)
    counts = ""
    if "failed" in report and "skipped" in report:
        counts = f"（计划 {report.get('planned', 0)} 张，失败 {report['failed']} 张，未尝试 {report['skipped']} 张）"
    return (f"已插入 {captured} 张截图{counts}，部分截图未完成：" if captured else f"未生成视频截图{counts}：") + reasons
