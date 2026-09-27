"""生成 Windows 图标；需 Pillow 与 Segoe UI Bold 字体。"""
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def build():
    root = Path(__file__).resolve().parents[1]
    size = 1024
    image = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=272, fill="#171717")
    font = ImageFont.truetype(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeuib.ttf"), 420)
    draw.text((size / 2, size / 2), "LD", fill="white", font=font, anchor="mm")
    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    image.save(root / "app/assets/learndex.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])


if __name__ == "__main__":
    build()
