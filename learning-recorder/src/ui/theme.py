"""디자인 토큰 + Qt 스타일시트.

밝은 회색 바탕 위 흰 카드, 큰 굵은 제목, 파란 주 버튼, 부드러운 모서리, 친근한 존댓말 문구.
"""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

import winutil

# 색상
BLUE = "#3182F6"
BLUE_HOVER = "#1B64DA"
BLUE_PRESSED = "#1957C2"
BLUE_LIGHT = "#E8F3FF"
BLUE_LIGHT_HOVER = "#D6E8FF"
RED = "#F04452"
RED_HOVER = "#D22030"
RED_LIGHT = "#FFEEEE"
GREEN = "#03B26C"
ORANGE = "#FE9800"
G900 = "#191F28"
G800 = "#333D4B"
G700 = "#4E5968"
G600 = "#6B7684"
G500 = "#8B95A1"
G400 = "#B0B8C1"
G300 = "#D1D6DB"
G200 = "#E5E8EB"
G100 = "#F2F4F6"
G50 = "#F9FAFB"
WHITE = "#FFFFFF"

FONT_FAMILY = "Pretendard"


def load_fonts() -> str:
    global FONT_FAMILY
    fams = []
    for w in ("Regular", "Medium", "SemiBold", "Bold"):
        p = winutil.asset_path("fonts", f"Pretendard-{w}.otf")
        if p.exists():
            fid = QFontDatabase.addApplicationFont(str(p))
            if fid >= 0:
                fams += QFontDatabase.applicationFontFamilies(fid)
    if fams:
        FONT_FAMILY = fams[0]
    else:
        FONT_FAMILY = "Malgun Gothic" if winutil.IS_WIN else "NanumGothic"
    return FONT_FAMILY


def font(px: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(FONT_FAMILY)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def qss() -> str:
    F = FONT_FAMILY
    return f"""
* {{ font-family: "{F}"; color: {G900}; outline: none; }}
QWidget#root, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {G100}; }}
QWidget#sidebar {{ background: {WHITE}; border-right: 1px solid {G200}; }}
QLabel {{ background: transparent; font-size: 15px; }}

QLabel#appName {{ font-size: 17px; font-weight: 700; }}
QLabel#appTag {{ font-size: 12px; color: {G500}; }}
QLabel#h1 {{ font-size: 26px; font-weight: 700; }}
QLabel#h1sub {{ font-size: 15px; color: {G600}; }}
QLabel#h2 {{ font-size: 18px; font-weight: 700; }}
QLabel#cardTitle {{ font-size: 17px; font-weight: 700; }}
QLabel#cardCaption, QLabel#caption {{ font-size: 13px; color: {G500}; }}
QLabel#rowTitle {{ font-size: 15px; font-weight: 500; color: {G800}; }}
QLabel#rowCaption {{ font-size: 13px; color: {G500}; }}
QLabel#big {{ font-size: 34px; font-weight: 700; }}
QLabel#bigBlue {{ font-size: 40px; font-weight: 700; color: {BLUE}; }}
QLabel#statValue {{ font-size: 22px; font-weight: 700; }}
QLabel#statLabel {{ font-size: 13px; color: {G600}; }}
QLabel#badge {{ background: {BLUE_LIGHT}; color: {BLUE}; border-radius: 8px; padding: 3px 8px;
                font-size: 12px; font-weight: 600; }}
QLabel#badgeRed {{ background: {RED_LIGHT}; color: {RED}; border-radius: 8px; padding: 3px 8px;
                   font-size: 12px; font-weight: 600; }}
QLabel#badgeGray {{ background: {G100}; color: {G600}; border-radius: 8px; padding: 3px 8px;
                    font-size: 12px; font-weight: 600; }}
QLabel#keycap {{ background: {G100}; border: 1px solid {G200}; border-radius: 8px; padding: 4px 10px;
                 font-size: 13px; font-weight: 600; color: {G700}; }}
QLabel#stepNum {{ background: {RED}; color: white; border-radius: 14px; font-size: 14px; font-weight: 700; }}
QLabel#thumb {{ background: {G100}; border-radius: 10px; }}
QLabel#emptyIcon {{ font-size: 44px; }}
QLabel#heroEmoji {{ font-size: 32px; }}
QLabel#tileEmoji {{ font-size: 22px; }}

QFrame#card {{ background: {WHITE}; border-radius: 20px; }}
QFrame#heroBlue {{ background: {BLUE}; border-radius: 22px; }}
QFrame#heroBlue QLabel {{ color: white; }}
QFrame#heroDark {{ background: {G900}; border-radius: 22px; }}
QFrame#heroDark QLabel {{ color: white; }}
QFrame#tile {{ background: {WHITE}; border-radius: 18px; }}
QFrame#divider {{ background: {G100}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#listRow {{ background: transparent; border-radius: 14px; }}
QFrame#listRow:hover {{ background: {G50}; }}
QFrame#bottomBar {{ background: {WHITE}; border-top: 1px solid {G200}; }}

QPushButton {{ border: none; border-radius: 14px; font-size: 15px; font-weight: 600; padding: 0 18px; min-height: 44px; }}
QPushButton[kind="primary"] {{ background: {BLUE}; color: white; }}
QPushButton[kind="primary"]:hover {{ background: {BLUE_HOVER}; }}
QPushButton[kind="primary"]:pressed {{ background: {BLUE_PRESSED}; }}
QPushButton[kind="primary"]:disabled {{ background: {G300}; color: white; }}
QPushButton[kind="danger"] {{ background: {RED}; color: white; }}
QPushButton[kind="danger"]:hover {{ background: {RED_HOVER}; }}
QPushButton[kind="secondary"] {{ background: {BLUE_LIGHT}; color: {BLUE}; }}
QPushButton[kind="secondary"]:hover {{ background: {BLUE_LIGHT_HOVER}; }}
QPushButton[kind="secondary"]:disabled {{ background: {G100}; color: {G400}; }}
QPushButton[kind="gray"] {{ background: {G100}; color: {G700}; }}
QPushButton[kind="gray"]:hover {{ background: {G200}; }}
QPushButton[kind="gray"]:disabled {{ color: {G400}; }}
QPushButton[kind="white"] {{ background: white; color: {BLUE}; }}
QPushButton[kind="white"]:hover {{ background: {BLUE_LIGHT}; }}
QPushButton[kind="whiteGhost"] {{ background: rgba(255,255,255,0.16); color: white; }}
QPushButton[kind="whiteGhost"]:hover {{ background: rgba(255,255,255,0.26); }}
QPushButton[kind="ghost"] {{ background: transparent; color: {G600}; min-height: 36px; padding: 0 10px; font-weight: 500; }}
QPushButton[kind="ghost"]:hover {{ background: {G100}; color: {G800}; }}
QPushButton[kind="link"] {{ background: transparent; color: {BLUE}; min-height: 30px; padding: 0 4px; }}
QPushButton[kind="link"]:hover {{ text-decoration: underline; }}
QPushButton[size="lg"] {{ min-height: 56px; border-radius: 16px; font-size: 17px; font-weight: 700; }}
QPushButton[size="sm"] {{ min-height: 34px; border-radius: 10px; font-size: 13px; padding: 0 12px; }}
QPushButton[kind="chip"] {{ background: {G100}; color: {G700}; border-radius: 16px; min-height: 32px;
                             padding: 0 14px; font-size: 13px; font-weight: 500; }}
QPushButton[kind="chip"]:hover {{ background: {BLUE_LIGHT}; color: {BLUE}; }}
QPushButton[kind="chipBlue"] {{ background: {BLUE_LIGHT}; color: {BLUE}; border-radius: 16px; min-height: 32px;
                                 padding: 0 14px; font-size: 13px; font-weight: 600; }}

QPushButton[kind="nav"] {{ background: transparent; color: {G600}; text-align: left; padding-left: 14px;
                           border-radius: 12px; min-height: 46px; font-size: 15px; font-weight: 600; }}
QPushButton[kind="nav"]:hover {{ background: {G100}; color: {G800}; }}
QPushButton[kind="nav"]:checked {{ background: {BLUE_LIGHT}; color: {BLUE}; }}

QPushButton[kind="seg"] {{ background: transparent; color: {G600}; border-radius: 9px; min-height: 34px;
                           padding: 0 14px; font-size: 14px; font-weight: 600; }}
QPushButton[kind="seg"]:hover {{ color: {G800}; }}
QPushButton[kind="seg"]:checked {{ background: white; color: {G900}; }}
QFrame#segment {{ background: {G100}; border-radius: 12px; }}

QLineEdit, QPlainTextEdit {{ background: {G50}; border: 1.5px solid {G200}; border-radius: 12px;
                             padding: 10px 12px; font-size: 15px; selection-background-color: {BLUE_LIGHT_HOVER};
                             selection-color: {G900}; }}
QLineEdit:focus, QPlainTextEdit:focus {{ border: 1.5px solid {BLUE}; background: white; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: {G300}; border-radius: 3px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {G400}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{ background: {G900}; color: white; border: none; border-radius: 8px; padding: 6px 10px; font-size: 13px; }}
QMenu {{ background: white; border: 1px solid {G200}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 8px; font-size: 14px; }}
QMenu::item:selected {{ background: {G100}; }}
QMenu::separator {{ height: 1px; background: {G100}; margin: 4px 8px; }}

QDialog#sheet {{ background: white; }}
QWidget#popupCard {{ background: white; border-radius: 22px; }}
QWidget#darkPill {{ background: rgba(25,31,40,0.94); border-radius: 22px; }}
QWidget#darkPill QLabel {{ color: white; }}
QWidget#toast {{ background: rgba(25,31,40,0.92); border-radius: 18px; }}
QWidget#toast QLabel {{ color: white; font-size: 14px; font-weight: 500; }}
"""
