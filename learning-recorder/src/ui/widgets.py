"""공통 위젯: 토글 스위치, 세그먼트, 카드, 설정 행, 버튼, 토스트, 확인 시트."""
from __future__ import annotations

from typing import Callable, Iterable

from PySide6.QtCore import (Qt, QEasingCurve, QPropertyAnimation, QRectF, QSize, QTimer, Signal, Property,
                            QPoint)
from PySide6.QtGui import QColor, QPainter, QPixmap, QPainterPath
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QDialog, QFrame, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
                               QGraphicsOpacityEffect)

from ui import theme as T


def label(text: str = "", name: str | None = None, wrap: bool = False) -> QLabel:
    l = QLabel(text)
    if name:
        l.setObjectName(name)
    if wrap:
        l.setWordWrap(True)
    return l


def button(text: str, kind: str = "primary", size: str | None = None, on_click: Callable | None = None,
           width: int | None = None) -> QPushButton:
    b = QPushButton(text)
    b.setProperty("kind", kind)
    if size:
        b.setProperty("size", size)
    b.setCursor(Qt.PointingHandCursor)
    if on_click:
        b.clicked.connect(on_click)
    if width:
        b.setFixedWidth(width)
    return b


def restyle(w: QWidget):
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def shadow(w: QWidget, blur: int = 40, alpha: int = 40, dy: int = 8):
    e = QGraphicsDropShadowEffect(w)
    e.setBlurRadius(blur)
    e.setColor(QColor(0, 0, 0, alpha))
    e.setOffset(0, dy)
    w.setGraphicsEffect(e)


def hline() -> QFrame:
    f = QFrame()
    f.setObjectName("divider")
    return f


def hbox(*items, spacing: int = 8, margins=(0, 0, 0, 0)) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for it in items:
        if it is None:
            lay.addStretch(1)
        elif isinstance(it, int):
            lay.addSpacing(it)
        elif isinstance(it, QWidget):
            lay.addWidget(it)
        else:
            lay.addLayout(it)
    return lay


def vbox(*items, spacing: int = 8, margins=(0, 0, 0, 0)) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for it in items:
        if it is None:
            lay.addStretch(1)
        elif isinstance(it, int):
            lay.addSpacing(it)
        elif isinstance(it, QWidget):
            lay.addWidget(it)
        else:
            lay.addLayout(it)
    return lay


class Toggle(QAbstractButton):
    """iOS 스타일 토글 스위치 (애니메이션)."""

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(50, 30)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, on: bool):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def get_pos(self):
        return self._pos

    def set_pos(self, v):
        self._pos = v
        self.update()

    pos = Property(float, get_pos, set_pos)

    def sizeHint(self):
        return QSize(50, 30)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        off, on = QColor(T.G300), QColor(T.BLUE)
        if not self.isEnabled():
            on = QColor(T.BLUE_LIGHT_HOVER)
        t = self._pos
        c = QColor(int(off.red() + (on.red() - off.red()) * t), int(off.green() + (on.green() - off.green()) * t),
                   int(off.blue() + (on.blue() - off.blue()) * t))
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(0, 0, 50, 30), 15, 15)
        x = 3 + t * 20
        p.setBrush(QColor(0, 0, 0, 30))
        p.drawEllipse(QRectF(x, 4, 24, 24))
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, 3, 24, 24))


class Segmented(QFrame):
    """세그먼트 컨트롤. options = [(value, label), ...]"""
    changed = Signal(object)

    def __init__(self, options: Iterable[tuple[object, str]], value=None, parent=None):
        super().__init__(parent)
        self.setObjectName("segment")
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._values = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        for i, (val, text) in enumerate(options):
            b = QPushButton(text)
            b.setProperty("kind", "seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self._group.addButton(b, i)
            self._values.append(val)
            lay.addWidget(b)
        self.set_value(value if value is not None else self._values[0])
        self._group.idClicked.connect(lambda i: self.changed.emit(self._values[i]))
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def set_value(self, value):
        if value in self._values:
            self._group.button(self._values.index(value)).setChecked(True)

    def value(self):
        i = self._group.checkedId()
        return self._values[i] if i >= 0 else None

    def set_options_enabled(self, enabled: bool):
        for b in self._group.buttons():
            b.setEnabled(enabled)


class Card(QFrame):
    def __init__(self, title: str | None = None, caption: str | None = None, parent=None, padding: int = 24):
        super().__init__(parent)
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(padding, padding - 2, padding, padding - 4)
        self.lay.setSpacing(4)
        if title:
            self.title = label(title, "cardTitle")
            self.lay.addWidget(self.title)
        if caption:
            c = label(caption, "cardCaption", wrap=True)
            self.lay.addWidget(c)
        if title or caption:
            self.lay.addSpacing(8)

    def add(self, w):
        if isinstance(w, QWidget):
            self.lay.addWidget(w)
        else:
            self.lay.addLayout(w)
        return w


class Row(QWidget):
    """설정 행: 왼쪽 제목/설명, 오른쪽 컨트롤."""

    def __init__(self, title: str, caption: str | None = None, control: QWidget | None = None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 10)
        lay.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(2)
        self.title = label(title, "rowTitle")
        left.addWidget(self.title)
        self.caption = None
        if caption:
            self.caption = label(caption, "rowCaption", wrap=True)
            left.addWidget(self.caption)
        lay.addLayout(left, 1)
        if control is not None:
            lay.addWidget(control, 0, Qt.AlignVCenter | Qt.AlignRight)
        self.control = control


class ToggleRow(Row):
    def __init__(self, title: str, caption: str | None, checked: bool, on_change: Callable[[bool], None]):
        self.toggle = Toggle(checked)
        super().__init__(title, caption, self.toggle)
        self.toggle.toggled.connect(on_change)


class StatTile(QFrame):
    def __init__(self, emoji: str, label_text: str, value: str = "-"):
        super().__init__()
        self.setObjectName("tile")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(4)
        lay.addWidget(label(emoji, "tileEmoji"))
        self.value = label(value, "statValue")
        lay.addWidget(self.value)
        lay.addWidget(label(label_text, "statLabel"))

    def set(self, v: str):
        self.value.setText(v)


def rounded_pixmap(pm: QPixmap, w: int, h: int, radius: int = 10) -> QPixmap:
    if pm.isNull():
        return pm
    pm = pm.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (pm.width() - w) // 2
    y = (pm.height() - h) // 2
    pm = pm.copy(x, y, w, h)
    out = QPixmap(w, h)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, pm)
    p.end()
    return out


class Toast(QWidget):
    """창 아래쪽 가운데에 잠깐 떴다 사라지는 알림."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 12, 20, 12)
        self.lbl = QLabel("")
        lay.addWidget(self.lbl)
        self._op = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._op)
        self._anim = QPropertyAnimation(self._op, b"opacity", self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.hide()

    def show_text(self, text: str, ms: int = 2200):
        self.lbl.setText(text)
        self.adjustSize()
        par = self.parentWidget()
        self.move((par.width() - self.width()) // 2, par.height() - self.height() - 36)
        self.raise_()
        self.show()
        self._anim.stop()
        self._anim.setDuration(160)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(ms)

    def _fade_out(self):
        self._anim.stop()
        self._anim.setDuration(300)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._hide_once)
        self._anim.start()

    def _hide_once(self):
        try:
            self._anim.finished.disconnect(self._hide_once)
        except Exception:
            pass
        if self._op.opacity() < 0.05:
            self.hide()


class Sheet(QDialog):
    """확인/입력용 둥근 시트 대화상자."""

    def __init__(self, parent, title: str, body: str = "", ok: str = "확인", cancel: str | None = "취소",
                 danger: bool = False, editor: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        card = QWidget()
        card.setObjectName("popupCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        shadow(card, 48, 50, 10)
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 26, 28, 22)
        lay.setSpacing(10)
        lay.addWidget(label(title, "h2", wrap=True))
        if body:
            lay.addWidget(label(body, "h1sub", wrap=True))
        self.editor = editor
        if editor is not None:
            lay.addSpacing(4)
            lay.addWidget(editor)
        lay.addSpacing(10)
        btns = QHBoxLayout()
        btns.setSpacing(8)
        if cancel:
            btns.addWidget(button(cancel, "gray", on_click=self.reject))
        okb = button(ok, "danger" if danger else "primary", on_click=self.accept)
        okb.setDefault(True)
        btns.addWidget(okb)
        lay.addLayout(btns)
        self.setMinimumWidth(420)

    def showEvent(self, e):
        super().showEvent(e)
        par = self.parentWidget()
        if par:
            g = par.window().geometry()
            self.adjustSize()
            self.move(g.center() - QPoint(self.width() // 2, self.height() // 2))
        if self.editor is not None:
            self.editor.setFocus()


def confirm(parent, title: str, body: str = "", ok: str = "확인", danger: bool = False) -> bool:
    return Sheet(parent, title, body, ok, "취소", danger).exec() == QDialog.Accepted
