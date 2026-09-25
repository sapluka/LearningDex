import os
import re


def pdf_path(directory, title, task_id=""):
    """生成不覆盖现有文件的 PDF 路径。"""
    directory = os.path.abspath(os.path.expanduser(directory))
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title or "学习笔记").strip(" .")
    name = (name or "学习笔记")[:80]
    if task_id:
        name += f"（{task_id}）"
    path = os.path.join(directory, name + ".pdf")
    index = 2
    while os.path.exists(path):
        path = os.path.join(directory, f"{name}（{index}）.pdf")
        index += 1
    return path


def print_current_page(path, window):
    """在 WebView2 后台导出当前页面，使用页面的 @media print 样式。"""
    from System import Action

    native = getattr(window, "native", None)
    control = getattr(native, "webview", None)
    if control is None:
        raise RuntimeError("当前窗口不支持直接生成 PDF（需要 Edge WebView2）")
    result = {}

    def start():
        core = control.CoreWebView2
        if core is None:
            raise RuntimeError("WebView2 尚未就绪")
        result["task"] = core.PrintToPdfAsync(path, None)

    control.Invoke(Action(start))
    task = result["task"]
    if not task.Wait(60000):
        raise TimeoutError("PDF 生成超时")
    if not task.Result:
        raise RuntimeError("PDF 生成失败")
    if not os.path.isfile(path) or not os.path.getsize(path):
        raise RuntimeError("PDF 文件未写入")
    return path
