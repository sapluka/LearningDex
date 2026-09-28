"""Check a Windows release executable before uploading it."""

import hashlib
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


def verify(path):
    archive = CArchiveReader(str(path))
    files = set(archive.toc)
    modules = archive.open_embedded_archive("PYZ.pyz").toc
    required = {
        r"app\web\index.html",
        r"app\assets\learndex.ico",
        r"skills\讲解.md",
        r"app\web\examples\BV1X7411F744\note.md",
        r"app\web\examples\BV1QuYX6XEZ4\note.md",
        r"app\web\examples\BV1CQt365EzW\note.md",
    }
    missing = required - files
    if missing:
        raise ValueError("缺少资源：" + ", ".join(sorted(missing)))
    if "tiktoken_ext.openai_public" not in modules:
        raise ValueError("缺少 tiktoken 编码插件")
    if "personal" in modules:
        raise ValueError("个人配置模块被打入程序")
    if any("node_modules" in name or name.startswith("output\\") or
           name.lower() in ("config.json", "cookies.txt", "personal.py") for name in files):
        raise ValueError("程序包含开发依赖或个人运行文件")
    images = [name for name in files if "\\examples\\" in name and name.endswith(".jpg")]
    if len(images) != 29:
        raise ValueError("示例配图数量不符：" + str(len(images)))
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    print(f"EXE 校验通过：{path.stat().st_size} 字节，29 张示例图")
    print("SHA256 " + digest.hexdigest())


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
