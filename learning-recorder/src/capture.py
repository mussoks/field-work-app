"""단축키 캡쳐: 마우스 포인터 위치에 '여기를 클릭' 표시(체크 + 번호) + 각주를 찍어 저장.

번호 규칙
  * 하나의 '캡쳐 세트(연결된 캡쳐)' 안에서는 1, 2, 3 … 순서대로 번호
  * '세트 종료' 단축키를 누르면 번호가 초기화되어 다음 캡쳐는 다시 1번
  * 세트마다 폴더 1개:  바탕화면\\학습용캡쳐\\캡쳐_20261123_143012_세트이름\\01.png …
    - 원본\\01.png      : 표시 없는 원본 (선택) → AI 학습용 '원본/정답표시' 쌍
    - steps.json       : 단계별 클릭 좌표, 버튼, 활성 창 제목, 각주
    - 가이드.html       : 단계별 이미지+각주를 한 페이지로 보는 매뉴얼
"""
from __future__ import annotations

import html
import json
import re
import shutil
import tempfile
import textwrap
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import masking
import uia
import winutil

RED = (230, 30, 30)
BLUE = (20, 110, 235)
GREEN = (16, 160, 70)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

_font_cache: dict = {}


def font(size: int, bold: bool = False):
    key = (size, bold)
    if key not in _font_cache:
        path = winutil.font_path(bold)
        try:
            _font_cache[key] = ImageFont.truetype(path, size) if path else ImageFont.load_default()
        except Exception:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def safe_name(text: str, limit: int = 40) -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", text).strip(" ._")
    return text[:limit]


@dataclass
class GrabResult:
    image: Image.Image
    x: int                      # 이미지 내 클릭 좌표
    y: int
    screen_x: int
    screen_y: int
    monitor: dict
    window: str = ""
    process: str = ""
    button: str = "left"
    source: str = "hotkey"      # hotkey | auto_click
    time: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    prev_hwnd: int = 0
    element: dict | None = None
    double: bool = False

    @property
    def suggestion(self) -> str:
        return uia.suggest_note(self.element, self.button, self.double)


def grab_under_cursor(sct, cursor: tuple[int, int] | None, button: str = "left",
                      source: str = "hotkey", masks=None, with_element: bool = True) -> GrabResult:
    """커서가 있는 모니터 전체를 캡쳐."""
    mons = sct.monitors[1:] or sct.monitors
    if cursor is None:
        cursor = (mons[0]["left"] + mons[0]["width"] // 2, mons[0]["top"] + mons[0]["height"] // 2)
    cx, cy = cursor
    mon = mons[0]
    for m in mons:
        if m["left"] <= cx < m["left"] + m["width"] and m["top"] <= cy < m["top"] + m["height"]:
            mon = m
            break
    shot = sct.grab(mon)
    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if masks:
        img = masking.apply_pil(img, masks, (mon["left"], mon["top"]))
    hwnd = winutil.get_foreground_window()
    element = uia.element_at(cx, cy) if with_element else None  # 화면을 먼저 잡은 뒤 조회
    return GrabResult(img, cx - mon["left"], cy - mon["top"], cx, cy, dict(mon),
                      winutil.get_window_title(hwnd), winutil.get_window_process_name(hwnd),
                      button, source, prev_hwnd=hwnd, element=element)


# ---------------------------------------------------------------- 렌더링

def _draw_arrow(d: ImageDraw.ImageDraw, x, y, s):
    pts = [(0, 0), (0, 21), (5, 16), (9, 25), (13, 23), (9, 15), (16, 15)]
    pts = [(x + px * s, y + py * s) for px, py in pts]
    d.polygon(pts, fill=WHITE, outline=BLACK, width=max(1, round(1.5 * s)))


def _draw_check(d: ImageDraw.ImageDraw, cx, cy, size, color, width):
    d.line([(cx - size * 0.5, cy), (cx - size * 0.12, cy + size * 0.38), (cx + size * 0.55, cy - size * 0.42)],
           fill=color, width=width, joint="curve")


def _wrap(text: str, fnt, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lines: list[str] = []
    for para in text.splitlines() or [""]:
        cur = ""
        for ch in para:
            if draw.textlength(cur + ch, font=fnt) > max_w and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


def render_marker(base: Image.Image, x: int, y: int, number: int, note: str = "",
                  button: str = "left", set_name: str = "", marker_scale: float = 1.0) -> Image.Image:
    """클릭 위치 표시 + 체크 번호 배지 + 각주 박스."""
    img = base.convert("RGBA")
    W, H = img.size
    s = max(1.0, H / 1080.0) * marker_scale
    color = BLUE if button == "right" else RED
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # 1) 클릭 지점: 반투명 원 + 두꺼운 테두리 + 바깥 원 + 십자선 + 중심점
    r = 30 * s
    d.ellipse([x - r, y - r, x + r, y + r], fill=color + (70,), outline=color + (255,), width=max(3, round(4 * s)))
    r2 = r + 9 * s
    d.ellipse([x - r2, y - r2, x + r2, y + r2], outline=color + (200,), width=max(2, round(2 * s)))
    L = r * 1.5
    for (dx, dy) in ((1, 0), (0, 1)):
        d.line([(x - dx * L, y - dy * L), (x + dx * L, y + dy * L)], fill=WHITE + (255,), width=max(3, round(4 * s)))
        d.line([(x - dx * L, y - dy * L), (x + dx * L, y + dy * L)], fill=color + (255,), width=max(1, round(2 * s)))
    cr = 4 * s
    d.ellipse([x - cr, y - cr, x + cr, y + cr], fill=color + (255,), outline=WHITE + (255,), width=max(1, round(s)))
    img = Image.alpha_composite(img, layer)

    d = ImageDraw.Draw(img)
    _draw_arrow(d, x, y, 1.15 * s)

    # 2) 체크 배지: [✔ 1  클릭]
    f_big = font(round(22 * s), bold=True)
    label = f"{number}"
    action = "우클릭" if button == "right" else "클릭"
    check_w = 26 * s
    num_w = d.textlength(label, font=f_big)
    act_w = d.textlength(action, font=font(round(17 * s), bold=True))
    pad = 8 * s
    bw = pad + check_w + 6 * s + num_w + 10 * s + act_w + pad
    bh = 38 * s

    # 3) 각주 박스 (배지 바로 아래)
    note = (note or "").strip()
    f_note = font(round(17 * s))
    note_lines, nw, nh = [], 0, 0
    if note:
        max_w = int(380 * s)
        note_lines = _wrap(note, f_note, max_w, d)
        line_h = round(24 * s)
        nw = max(d.textlength(l, font=f_note) for l in note_lines) + 2 * pad
        nh = line_h * len(note_lines) + 2 * pad
    block_w = max(bw, nw)
    block_h = bh + (6 * s + nh if note else 0)

    # 기본: 오른쪽 아래. 화면 밖으로 나가면 반대쪽으로.
    off = r + 12 * s
    bx = x + off * 0.7
    by = y + off * 0.7
    if bx + block_w > W - 4:
        bx = x - off * 0.7 - block_w
    if by + block_h > H - 4:
        by = y - off * 0.7 - block_h
    bx = max(4, min(bx, W - block_w - 4))
    by = max(4, min(by, H - block_h - 4))

    # 클릭점 ↔ 배지 연결선
    anchor = (bx if bx > x else bx + bw, by if by > y else by + bh)
    d.line([(x, y), anchor], fill=color, width=max(2, round(2 * s)))

    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=round(9 * s), fill=color, outline=WHITE, width=max(2, round(2 * s)))
    _draw_check(d, bx + pad + check_w / 2, by + bh / 2, check_w * 0.8, WHITE, max(3, round(4 * s)))
    tx = bx + pad + check_w + 6 * s
    d.text((tx, by + bh / 2), label, font=f_big, fill=WHITE, anchor="lm")
    d.text((tx + num_w + 10 * s, by + bh / 2), action, font=font(round(17 * s), bold=True), fill=WHITE, anchor="lm")

    if note:
        ny = by + bh + 6 * s
        d.rectangle([bx, ny, bx + nw, ny + nh], fill=(255, 255, 240), outline=color, width=max(2, round(2 * s)))
        line_h = round(24 * s)
        for i, line in enumerate(note_lines):
            d.text((bx + pad, ny + pad + i * line_h), line, font=f_note, fill=(20, 20, 20))

    # 4) 좌상단 작은 단계 표시 (워터마크)
    tag = f"STEP {number}" + (f" · {set_name}" if set_name else "")
    f_tag = font(round(14 * s), bold=True)
    tw = d.textlength(tag, font=f_tag)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([6 * s, 6 * s, 6 * s + tw + 16 * s, 6 * s + 26 * s], radius=round(6 * s), fill=(0, 0, 0, 120))
    od.text((14 * s, 6 * s + 13 * s), tag, font=f_tag, fill=(255, 255, 255, 230), anchor="lm")
    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


# ---------------------------------------------------------------- 세트/번호 관리

@dataclass
class Step:
    step: int
    file: str
    raw_file: str
    note: str
    x: int
    y: int
    screen_x: int
    screen_y: int
    button: str
    window: str
    process: str
    time: str
    source: str
    image_w: int
    image_h: int
    element: dict | None = None


class CaptureManager:
    def __init__(self, settings):
        self.settings = settings
        self.folder: Path | None = None
        self.set_name = ""
        self.steps: list[Step] = []
        self._tmp = Path(tempfile.gettempdir()) / "learning_recorder_raw"

    @property
    def next_number(self) -> int:
        return len(self.steps) + 1

    @property
    def active(self) -> bool:
        return self.folder is not None

    def _ensure_set(self):
        if self.folder is None:
            self.set_name = self.settings.set_name.strip()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"캡쳐_{stamp}" + (f"_{safe_name(self.set_name)}" if self.set_name else "")
            self.folder = self.settings.root_dir() / name
            self.folder.mkdir(parents=True, exist_ok=True)
            self.steps = []

    def _raw_path(self, n: int) -> Path:
        if self.settings.save_raw:
            p = self.folder / "원본" / f"{n:02d}.png"
        else:
            p = self._tmp / self.folder.name / f"{n:02d}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _ext(self) -> str:
        return "jpg" if self.settings.image_format.upper() == "JPG" else "png"

    def _save_image(self, img: Image.Image, path: Path):
        if path.suffix == ".jpg":
            img.save(path, "JPEG", quality=90, optimize=True)
        else:
            img.save(path, "PNG", optimize=False, compress_level=6)

    def add(self, g: GrabResult, note: str = "") -> Step:
        self._ensure_set()
        n = self.next_number
        raw = self._raw_path(n)
        g.image.save(raw, "PNG", compress_level=6)
        out = self.folder / f"{n:02d}.{self._ext()}"
        rendered = render_marker(g.image, g.x, g.y, n, note, g.button, self.set_name, self.settings.marker_scale)
        self._save_image(rendered, out)
        st = Step(n, out.name, str(raw.relative_to(self.folder)) if self.settings.save_raw else "",
                  note, g.x, g.y, g.screen_x, g.screen_y, g.button, g.window, g.process, g.time,
                  g.source, g.image.width, g.image.height, g.element)
        self.steps.append(st)
        self._write_index()
        return st

    def update_note(self, n: int, note: str) -> bool:
        st = next((s for s in self.steps if s.step == n), None)
        if not st or not self.folder:
            return False
        raw = self._raw_path(n)
        if not raw.exists():
            return False
        img = Image.open(raw).convert("RGB")
        rendered = render_marker(img, st.x, st.y, n, note, st.button, self.set_name, self.settings.marker_scale)
        self._save_image(rendered, self.folder / st.file)
        st.note = note
        self._write_index()
        return True

    def undo_last(self) -> Step | None:
        if not self.steps or not self.folder:
            return None
        st = self.steps.pop()
        for p in (self.folder / st.file, self._raw_path(st.step)):
            try:
                p.unlink()
            except Exception:
                pass
        self._write_index()
        return st

    def end_set(self) -> Path | None:
        """연결된 캡쳐 종료 → 다음 캡쳐는 새 폴더에서 1번부터."""
        folder = self.folder
        if folder is not None:
            self._write_index()
            if not self.steps:
                shutil.rmtree(folder, ignore_errors=True)
                folder = None
        tmp = self._tmp / (self.folder.name if self.folder else "")
        if self.folder and tmp.exists() and tmp != self._tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        self.folder = None
        self.steps = []
        return folder

    # ------------------------------------------------------------ 가이드 출력
    def _write_index(self):
        if not self.folder:
            return
        meta = {
            "set_name": self.set_name,
            "folder": self.folder.name,
            "coords": "x,y = 이미지 내 클릭 픽셀 좌표 (원본 해상도 기준)",
            "steps": [asdict(s) for s in self.steps],
        }
        (self.folder / "steps.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        # 학습 데이터셋 (JSON Lines): 한 줄 = 한 단계
        with open(self.folder / "dataset.jsonl", "w", encoding="utf-8") as f:
            for s in self.steps:
                f.write(json.dumps({
                    "step": s.step, "image": s.raw_file or None, "marked": s.file,
                    "action": "right_click" if s.button == "right" else "click",
                    "x": s.x, "y": s.y, "x_norm": round(s.x / s.image_w, 5), "y_norm": round(s.y / s.image_h, 5),
                    "width": s.image_w, "height": s.image_h, "instruction": s.note or uia.suggest_note(s.element, s.button),
                    "window": s.window, "process": s.process, "element": s.element, "task": self.set_name,
                }, ensure_ascii=False) + "\n")
        title = html.escape(self.set_name or self.folder.name)
        rows = []
        for s in self.steps:
            note = html.escape(s.note).replace("\n", "<br>") or '<span class="muted">(각주 없음)</span>'
            rows.append(f"""
<section>
  <h2><span class="n">{s.step}</span> {'우클릭' if s.button == 'right' else '클릭'} — {note}</h2>
  <p class="meta">창: {html.escape(s.window or '-')} · 프로그램: {html.escape(s.process or '-')} · 좌표 ({s.x}, {s.y}){(' · UI: ' + html.escape((s.element or {}).get('type_ko', '') + ' ' + repr((s.element or {}).get('name', '')))) if s.element else ''} · {s.time}</p>
  <img src="{html.escape(s.file)}" alt="단계 {s.step}">
</section>""")
        doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>
body{{font-family:'Malgun Gothic',sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;color:#222;background:#f6f7f9}}
section{{background:#fff;border-radius:10px;padding:14px 18px;margin:18px 0;box-shadow:0 1px 3px #0002}}
h1{{font-size:22px}} h2{{font-size:17px;margin:4px 0}} .n{{display:inline-block;background:#e61e1e;color:#fff;border-radius:50%;
width:28px;height:28px;text-align:center;line-height:28px;margin-right:6px}} .meta{{color:#666;font-size:12px;margin:2px 0 10px}}
img{{max-width:100%;border:1px solid #ddd;border-radius:6px}} .muted{{color:#999}}
</style></head><body><h1>{title}</h1><p class="meta">총 {len(self.steps)}단계 · steps.json 에 좌표/메타데이터가 있습니다.</p>
{''.join(rows)}
</body></html>"""
        (self.folder / "가이드.html").write_text(doc, encoding="utf-8")


def wrap_preview(text: str, width: int = 30) -> str:
    return textwrap.shorten(text, width=width, placeholder="…")
