"""녹화 프레임 위에 마우스 포인터·클릭·스크롤·키 입력을 그린다 (OpenCV, BGR).

AI 가 프레임 단위로 보더라도 '어디를 눌렀는지' 확실히 알 수 있게:
  * 포인터: 항상 흰색 화살표 + 검은 테두리 + 노란 반투명 원(하이라이트)
  * 왼쪽 클릭: 빨간 원 + 십자선 + 'L-CLICK' 배지 (설정 시간 동안 유지)
  * 오른쪽 클릭: 파란 원 + 'R-CLICK',  더블클릭: 'DOUBLE'
  * 드래그: 시작점→현재점 선 + 'DRAG'
  * 휠: 화살표 + 'SCROLL'
  * 키 입력: 화면 아래 가운데 'Ctrl + S', 'Enter' 등
클릭 표시는 '유지시간' 동안 남으므로 15fps 에서도 짧은 클릭이 프레임 사이에서 사라지지 않는다.
"""
from __future__ import annotations

import threading
import time

import cv2
import numpy as np

RED = (40, 40, 235)
BLUE = (235, 120, 20)
GREEN = (60, 180, 60)
YELLOW = (0, 230, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

BUTTON_COLOR = {"left": RED, "right": BLUE, "middle": GREEN}
BUTTON_LABEL = {"left": "L-CLICK", "right": "R-CLICK", "middle": "M-CLICK"}

# 표준 화살표 커서 모양 (끝점이 (0,0))
ARROW = np.array([(0, 0), (0, 21), (5, 16), (9, 25), (13, 23), (9, 15), (16, 15)], dtype=np.float32)


def _blend_circle(img, center, radius, color, alpha):
    x, y = int(center[0]), int(center[1])
    r = int(radius) + 2
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(0, x - r), max(0, y - r), min(w, x + r + 1), min(h, y + r + 1)
    if x0 >= x1 or y0 >= y1:
        return
    roi = img[y0:y1, x0:x1]
    layer = roi.copy()
    cv2.circle(layer, (x - x0, y - y0), int(radius), color, -1, cv2.LINE_AA)
    cv2.addWeighted(layer, alpha, roi, 1 - alpha, 0, dst=roi)


def _blend_rect(img, p0, p1, color, alpha):
    h, w = img.shape[:2]
    x0, y0 = max(0, int(p0[0])), max(0, int(p0[1]))
    x1, y1 = min(w, int(p1[0])), min(h, int(p1[1]))
    if x0 >= x1 or y0 >= y1:
        return
    roi = img[y0:y1, x0:x1]
    layer = np.empty_like(roi)
    layer[:] = color
    cv2.addWeighted(layer, alpha, roi, 1 - alpha, 0, dst=roi)


def _badge(img, text, anchor, color, scale):
    """색 배경 + 흰 글씨 라벨. anchor = 왼쪽 아래 기준점."""
    fs = 0.62 * scale
    th = max(1, int(round(1.6 * scale)))
    (tw, tht), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, th)
    pad = int(4 * scale)
    h, w = img.shape[:2]
    x = int(min(max(anchor[0], 0), w - tw - 2 * pad))
    y = int(min(max(anchor[1], tht + 2 * pad), h))
    cv2.rectangle(img, (x, y - tht - 2 * pad), (x + tw + 2 * pad, y), color, -1)
    cv2.rectangle(img, (x, y - tht - 2 * pad), (x + tw + 2 * pad, y), WHITE, 1)
    cv2.putText(img, text, (x + pad, y - pad), cv2.FONT_HERSHEY_SIMPLEX, fs, WHITE, th, cv2.LINE_AA)


def draw_cursor(img, x, y, scale, halo=True):
    if halo:
        _blend_circle(img, (x, y), 20 * scale, YELLOW, 0.38)
    pts = (ARROW * (scale * 1.05) + (x, y)).astype(np.int32)
    cv2.fillPoly(img, [pts], WHITE, cv2.LINE_AA)
    cv2.polylines(img, [pts], True, BLACK, max(1, int(round(1.4 * scale))), cv2.LINE_AA)


def draw_click_marker(img, x, y, color, scale, progress=0.0, label=None, hold=False):
    """클릭 위치 표시. progress: 0(방금 클릭)→1(사라지기 직전)."""
    r = 24 * scale
    _blend_circle(img, (x, y), r, color, 0.30 if not hold else 0.42)
    cv2.circle(img, (int(x), int(y)), int(r), color, max(2, int(3 * scale)), cv2.LINE_AA)
    # 퍼지는 바깥 원 (클릭 '순간'을 강조)
    if progress < 1.0:
        rr = r + (8 + 22 * progress) * scale
        cv2.circle(img, (int(x), int(y)), int(rr), color, max(1, int(2 * scale)), cv2.LINE_AA)
    # 십자선: 정확한 클릭 지점
    L = int(r * 1.45)
    for (dx, dy) in ((1, 0), (0, 1)):
        p0 = (int(x - dx * L), int(y - dy * L))
        p1 = (int(x + dx * L), int(y + dy * L))
        cv2.line(img, p0, p1, WHITE, max(2, int(3 * scale)), cv2.LINE_AA)
        cv2.line(img, p0, p1, color, max(1, int(1.4 * scale)), cv2.LINE_AA)
    cv2.circle(img, (int(x), int(y)), max(2, int(3 * scale)), color, -1, cv2.LINE_AA)
    cv2.circle(img, (int(x), int(y)), max(2, int(3 * scale)), WHITE, 1, cv2.LINE_AA)
    if label:
        _badge(img, label, (x + r * 0.8, y - r * 0.8), color, scale)


class OverlayState:
    """InputHub 이벤트를 받아 그리기용 상태를 보관 (리스너 스레드 ↔ 녹화 스레드)."""

    def __init__(self, hold_sec=0.8, key_mode="특수키만"):
        self.hold_sec = hold_sec
        self.key_mode = key_mode
        self._lock = threading.Lock()
        self.clicks: list[dict] = []
        self.down: dict[str, dict] = {}
        self.scrolls: list[dict] = []
        self.keys: list[dict] = []

    def on_mouse(self, e: dict):
        with self._lock:
            if e["type"] == "mouse_down":
                c = dict(e, up_t=None)
                self.clicks.append(c)
                self.down[e["button"]] = c
            elif e["type"] == "mouse_up":
                c = self.down.pop(e["button"], None)
                if c is not None:
                    c["up_t"] = e["t"]
                    c["ux"], c["uy"] = e["x"], e["y"]
            elif e["type"] == "scroll":
                self.scrolls.append(e)

    def on_key(self, e: dict):
        if self.key_mode == "끄기":
            return
        if self.key_mode == "특수키만" and not e["special"]:
            return
        with self._lock:
            label = e["label"]
            # '전체' 모드에서 일반 글자는 이어붙여 'abc' 처럼 표시
            if (not e["special"] and self.keys and not self.keys[-1]["special"]
                    and e["t"] - self.keys[-1]["t"] < 1.2 and len(self.keys[-1]["label"]) < 24):
                self.keys[-1]["label"] += label
                self.keys[-1]["t"] = e["t"]
            else:
                self.keys.append({"t": e["t"], "label": label, "special": e["special"]})
            self.keys = self.keys[-4:]

    def snapshot(self, now: float):
        with self._lock:
            keep = self.hold_sec
            self.clicks = [c for c in self.clicks
                           if c["up_t"] is None or now - max(c["t"], c["up_t"]) < keep]
            self.scrolls = [s for s in self.scrolls if now - s["t"] < 0.6]
            self.keys = [k for k in self.keys if now - k["t"] < 2.0]
            return ([dict(c) for c in self.clicks], list(self.scrolls), list(self.keys))


def render_overlay(img, state: OverlayState, now: float, cursor, origin, scale_xy,
                   marker_scale=1.0, show_halo=True, show_clicks=True):
    """img(출력 해상도) 위에 오버레이를 그린다.

    cursor: 화면 좌표 (x, y) 또는 None,  origin: 캡처 영역 좌상단 화면 좌표,
    scale_xy: 화면 픽셀 → 출력 픽셀 배율
    """
    h, w = img.shape[:2]
    s = max(0.7, (h / 1080.0) * 1.15) * marker_scale
    ox, oy = origin

    def to_img(x, y):
        return (x - ox) * scale_xy, (y - oy) * scale_xy

    clicks, scrolls, keys = state.snapshot(now)

    if show_clicks:
        for c in clicks:
            color = BUTTON_COLOR.get(c["button"], RED)
            x, y = to_img(c["x"], c["y"])
            held = c["up_t"] is None
            end_t = now if held else c["up_t"]
            # 드래그 (누른 채 10px 이상 이동)
            if held and cursor is not None:
                ex, ey = to_img(*cursor)
            else:
                ex, ey = to_img(c.get("ux", c["x"]), c.get("uy", c["y"]))
            dragged = abs(ex - x) + abs(ey - y) > 12 * s
            progress = 0.0 if held else min(1.0, (now - end_t) / max(0.05, state.hold_sec))
            if not (-50 < x < w + 50 and -50 < y < h + 50):
                continue
            label = "DOUBLE" if c.get("double") else BUTTON_LABEL.get(c["button"], "CLICK")
            if dragged:
                cv2.line(img, (int(x), int(y)), (int(ex), int(ey)), WHITE, max(3, int(5 * s)), cv2.LINE_AA)
                cv2.line(img, (int(x), int(y)), (int(ex), int(ey)), color, max(2, int(3 * s)), cv2.LINE_AA)
                cv2.circle(img, (int(ex), int(ey)), int(10 * s), color, max(2, int(3 * s)), cv2.LINE_AA)
                label = "DRAG"
            draw_click_marker(img, x, y, color, s, progress, label, hold=held)

        for e in scrolls:
            x, y = to_img(e["x"], e["y"])
            up = e["dy"] > 0
            tip = (int(x + 34 * s), int(y + (-18 if up else 18) * s))
            tail = (int(x + 34 * s), int(y + (18 if up else -18) * s))
            cv2.arrowedLine(img, tail, tip, WHITE, max(3, int(5 * s)), cv2.LINE_AA, tipLength=0.45)
            cv2.arrowedLine(img, tail, tip, GREEN, max(2, int(3 * s)), cv2.LINE_AA, tipLength=0.45)
            _badge(img, "SCROLL " + ("UP" if up else "DOWN"), (x + 48 * s, y + 6 * s), GREEN, s * 0.9)

    if cursor is not None:
        cx, cy = to_img(*cursor)
        if -5 <= cx < w + 5 and -5 <= cy < h + 5:
            draw_cursor(img, cx, cy, s, show_halo)

    if keys:
        text = "   ".join(k["label"] for k in keys)
        fs = 0.85 * s
        th = max(1, int(2 * s))
        (tw, tht), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, th)
        pad = int(12 * s)
        x0 = (w - tw) // 2 - pad
        y1 = h - int(30 * s)
        _blend_rect(img, (x0, y1 - tht - 2 * pad), (x0 + tw + 2 * pad, y1), (30, 30, 30), 0.72)
        cv2.putText(img, text, (x0 + pad, y1 - pad), cv2.FONT_HERSHEY_SIMPLEX, fs, WHITE, th, cv2.LINE_AA)
    return img


if __name__ == "__main__":  # 간단한 미리보기 이미지 생성
    st = OverlayState()
    t = time.perf_counter()
    st.on_mouse({"type": "mouse_down", "t": t, "x": 400, "y": 300, "button": "left", "double": False})
    st.on_key({"t": t, "label": "Ctrl + S", "special": True})
    im = np.full((720, 1280, 3), 235, np.uint8)
    render_overlay(im, st, t + 0.1, (404, 304), (0, 0), 1.0)
    cv2.imwrite("overlay_preview.png", im)
