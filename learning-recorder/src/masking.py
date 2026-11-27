"""개인정보 가리기: 지정한 화면 영역을 모자이크(픽셀화) 처리.

거래처명·주민번호·금액처럼 학습 데이터에 남으면 안 되는 영역을 미리 지정해 두면
녹화 영상, 클릭 장면, 캡쳐(원본 포함)에 모두 모자이크가 적용된다.
mask 영역은 '실제 화면 좌표' [left, top, width, height] 로 저장한다.
"""
from __future__ import annotations

import numpy as np


def _cells(w: int, h: int, block: int) -> tuple[int, int]:
    return max(1, w // block), max(1, h // block)


def apply_np(img: np.ndarray, regions, origin: tuple[int, int], scale: float, block: int = 14) -> None:
    """numpy BGR 이미지(제자리 수정). origin = 이미지 좌상단의 화면 좌표, scale = 화면→이미지 배율."""
    if not regions:
        return
    import cv2
    H, W = img.shape[:2]
    ox, oy = origin
    for r in regions:
        x0 = int((r[0] - ox) * scale)
        y0 = int((r[1] - oy) * scale)
        x1 = int((r[0] + r[2] - ox) * scale)
        y1 = int((r[1] + r[3] - oy) * scale)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        roi = img[y0:y1, x0:x1]
        cw, ch = _cells(x1 - x0, y1 - y0, block)
        small = cv2.resize(roi, (cw, ch), interpolation=cv2.INTER_AREA)
        img[y0:y1, x0:x1] = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)


def apply_pil(img, regions, origin: tuple[int, int], block: int = 16):
    """PIL 이미지(원본 해상도) 에 적용한 새 이미지를 돌려준다."""
    if not regions:
        return img
    from PIL import Image
    img = img.copy()
    W, H = img.size
    ox, oy = origin
    for r in regions:
        x0, y0 = max(0, r[0] - ox), max(0, r[1] - oy)
        x1, y1 = min(W, r[0] + r[2] - ox), min(H, r[1] + r[3] - oy)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        box = (int(x0), int(y0), int(x1), int(y1))
        roi = img.crop(box)
        cw, ch = _cells(box[2] - box[0], box[3] - box[1], block)
        roi = roi.resize((cw, ch), Image.BILINEAR).resize((box[2] - box[0], box[3] - box[1]), Image.NEAREST)
        img.paste(roi, box)
    return img
