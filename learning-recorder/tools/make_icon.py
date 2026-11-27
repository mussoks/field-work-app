"""앱 아이콘 생성 (파란 둥근 사각형 + 흰 포인터 + 빨간 녹화 점).  python tools/make_icon.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "src" / "assets"
S = 1024


def make() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # 그라디언트 바탕
    bg = Image.new("RGBA", (S, S))
    top, bot = (66, 145, 255), (27, 100, 218)
    for y in range(S):
        t = y / (S - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        ImageDraw.Draw(bg).line([(0, y), (S, y)], fill=c)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([40, 40, S - 40, S - 40], radius=230, fill=255)
    img.paste(bg, (0, 0), mask)

    # 포인터 (그림자 + 흰 화살표)
    pts = [(0, 0), (0, 21), (5, 16), (9, 25), (13, 23), (9, 15), (16, 15)]
    sc, ox, oy = 26, 300, 230
    arrow = [(ox + x * sc, oy + y * sc) for x, y in pts]
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon([(x + 14, y + 22) for x, y in arrow], fill=(10, 40, 110, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img, sh)
    d = ImageDraw.Draw(img)
    d.polygon(arrow, fill=(255, 255, 255, 255))

    # 클릭 파동 + 녹화 점
    cx, cy = ox, oy
    for r, a in ((150, 70), (105, 120)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, a), width=18)
    rx, ry, rr = 720, 720, 96
    d.ellipse([rx - rr - 16, ry - rr - 16, rx + rr + 16, ry + rr + 16], fill=(255, 255, 255, 255))
    d.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], fill=(240, 68, 82, 255))
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    big = make()
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    big.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("saved", OUT)
