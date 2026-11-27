"""떠 있는 작은 창들: 각주 입력, 카운트다운, 녹화 미니바, 화면 영역 선택."""
from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QRect, QRectF, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QKeyEvent, QPainter, QPen, QPixmap, QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

import winutil
from ui import theme as T
from ui.widgets import button, label, shadow


def exclude(widget: QWidget, enable: bool):
    if not winutil.IS_WIN:
        return
    try:
        hwnd = int(widget.winId())
        winutil.user32.SetWindowDisplayAffinity(hwnd, 0x11 if enable else 0x0)
    except Exception:
        pass


def bring_to_front(widget: QWidget):
    widget.raise_()
    widget.activateWindow()
    if winutil.IS_WIN:
        try:
            winutil.set_foreground(int(widget.winId()))
        except Exception:
            pass


class _NoteEdit(QPlainTextEdit):
    submit = Signal()
    cancel = Signal()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.submit.emit()
            return
        if e.key() == Qt.Key_Escape:
            self.cancel.emit()
            return
        super().keyPressEvent(e)


class NotePopup(QWidget):
    """캡쳐 직후 마우스 근처에 뜨는 각주 입력 카드. Enter 저장 · Shift+Enter 줄바꿈 · Esc 건너뛰기."""
    done = Signal(int, object)   # step, note(None = 건너뛰기)

    def __init__(self, step: int, suggestion: str, recent: list[str], element: dict | None,
                 exclude_self: bool = True):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.step = step
        self._finished = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        card = QWidget()
        card.setObjectName("popupCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        shadow(card, 44, 55, 10)
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)

        top = QHBoxLayout()
        num = label(str(step), "stepNum")
        num.setFixedSize(28, 28)
        num.setAlignment(Qt.AlignCenter)
        top.addWidget(num)
        top.addSpacing(4)
        top.addWidget(label(f"{step}번을 캡쳐했어요", "h2"))
        top.addStretch(1)
        lay.addLayout(top)
        if element and (element.get("name") or element.get("type_ko")):
            nm = element.get("name") or element.get("label") or ""
            lay.addWidget(label(f"누른 곳: {element.get('type_ko') or '요소'} {('· ' + nm) if nm else ''}",
                                "caption"))
        else:
            lay.addWidget(label("체크 표시 아래에 들어갈 각주를 적어주세요 (선택)", "caption"))

        self.edit = _NoteEdit()
        self.edit.setPlaceholderText("예) '저장' 버튼 클릭")
        self.edit.setFixedHeight(76)
        self.edit.setPlainText(suggestion or "")
        self.edit.selectAll()
        self.edit.submit.connect(self.commit)
        self.edit.cancel.connect(self.skip)
        lay.addWidget(self.edit)

        chips = [c for c in ([suggestion] if suggestion else []) + recent if c][:4]
        seen = []
        chips = [c for c in chips if not (c in seen or seen.append(c))]
        if chips:
            row = QHBoxLayout()
            row.setSpacing(6)
            for c in chips:
                text = c if len(c) <= 16 else c[:15] + "…"
                b = button(text, "chipBlue" if c == suggestion else "chip")
                b.setToolTip(c)
                b.clicked.connect(lambda _=False, v=c: self._fill(v))
                row.addWidget(b)
            row.addStretch(1)
            lay.addLayout(row)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        hint = label("Enter 저장 · Esc 건너뛰기", "caption")
        btns.addWidget(hint)
        btns.addStretch(1)
        btns.addWidget(button("건너뛰기", "gray", "sm", self.skip))
        btns.addWidget(button("저장", "primary", "sm", self.commit, width=72))
        lay.addLayout(btns)
        self.setFixedWidth(440)
        self.adjustSize()
        self._place()
        self._exclude = exclude_self

    def _fill(self, text):
        self.edit.setPlainText(text)
        self.edit.setFocus()
        c = self.edit.textCursor()
        c.movePosition(c.MoveOperation.End)
        self.edit.setTextCursor(c)

    def _place(self):
        pos = QCursor.pos()
        scr = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        x = min(pos.x() + 28, g.right() - self.width() - 8)
        y = min(pos.y() + 28, g.bottom() - self.height() - 8)
        if pos.x() + 28 + self.width() > g.right():
            x = max(g.left() + 8, pos.x() - self.width() - 20)
        self.move(max(g.left() + 8, x), max(g.top() + 8, y))

    def showEvent(self, e):
        super().showEvent(e)
        exclude(self, self._exclude)
        QTimer.singleShot(30, lambda: (bring_to_front(self), self.edit.setFocus()))

    def commit(self):
        if self._finished:
            return
        self._finished = True
        note = self.edit.toPlainText().strip()
        self.close()
        self.done.emit(self.step, note)

    def skip(self):
        if self._finished:
            return
        self._finished = True
        self.close()
        self.done.emit(self.step, None)


class Countdown(QWidget):
    finished = Signal()

    def __init__(self, rect_center: QPoint, seconds: int = 3):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.n = seconds
        self.setFixedSize(220, 220)
        self.move(rect_center - QPoint(110, 110))
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(1000)

    def showEvent(self, e):
        super().showEvent(e)
        exclude(self, True)

    def _tick(self):
        self.n -= 1
        if self.n <= 0:
            self._t.stop()
            self.hide()
            self.finished.emit()   # 받는 쪽에서 창이 사라진 뒤(150ms) 녹화 시작
            self.close()
        else:
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(25, 31, 40, 225))
        p.drawEllipse(QRectF(10, 10, 200, 200))
        p.setPen(QColor("white"))
        p.setFont(T.font(96, QFont.Weight.Bold))
        p.drawText(QRect(0, -6, 220, 220), Qt.AlignCenter, str(self.n))
        p.setFont(T.font(14, QFont.Weight.Medium))
        p.setPen(QColor(255, 255, 255, 190))
        p.drawText(QRect(0, 140, 220, 40), Qt.AlignCenter, "곧 녹화를 시작해요")


class MiniBar(QWidget):
    """녹화 중 화면 위에 떠 있는 작은 알약 모양 바 (녹화에는 찍히지 않음)."""
    pause_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self, anchor: QRect):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        wrap = QHBoxLayout(self)
        wrap.setContentsMargins(10, 10, 10, 10)
        pill = QWidget()
        pill.setObjectName("darkPill")
        pill.setAttribute(Qt.WA_StyledBackground, True)
        shadow(pill, 30, 60, 6)
        wrap.addWidget(pill)
        lay = QHBoxLayout(pill)
        lay.setContentsMargins(18, 6, 8, 6)
        lay.setSpacing(8)
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color: {T.RED}; font-size: 14px;")
        lay.addWidget(self.dot)
        self.time = QLabel("00:00")
        self.time.setStyleSheet("font-size: 15px; font-weight: 700; color: white;")
        lay.addWidget(self.time)
        self.info = QLabel("")
        self.info.setStyleSheet(f"font-size: 12px; color: {T.G400};")
        lay.addWidget(self.info)
        lay.addSpacing(6)
        self.pause_btn = button("일시정지", "whiteGhost", "sm", self.pause_clicked.emit)
        lay.addWidget(self.pause_btn)
        lay.addWidget(button("끝내기", "danger", "sm", self.stop_clicked.emit))
        self.adjustSize()
        self.move(anchor.center().x() - self.width() // 2, anchor.top() + 8)
        self._drag = None
        self._blink = QTimer(self)
        self._blink.timeout.connect(lambda: self.dot.setVisible(not self.dot.isVisible()))
        self._blink.start(700)

    def showEvent(self, e):
        super().showEvent(e)
        exclude(self, True)

    def set_state(self, t: float, info: str, paused: bool):
        self.time.setText(f"{int(t // 60):02d}:{int(t % 60):02d}")
        self.info.setText(info)
        self.pause_btn.setText("이어서" if paused else "일시정지")
        if paused:
            self._blink.stop()
            self.dot.setVisible(True)
            self.dot.setStyleSheet(f"color: {T.ORANGE}; font-size: 14px;")
        elif not self._blink.isActive():
            self.dot.setStyleSheet(f"color: {T.RED}; font-size: 14px;")
            self._blink.start(700)

    def mousePressEvent(self, e):
        self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None


def qscreen_for_monitor(mon: dict, monitors: list[dict]):
    """mss 모니터(물리 좌표) ↔ Qt 화면 매칭 (같은 순서/크기로 추정)."""
    screens = sorted(QGuiApplication.screens(), key=lambda s: (s.geometry().x(), s.geometry().y()))
    mons = sorted(monitors[1:], key=lambda m: (m["left"], m["top"]))
    if len(screens) == len(mons) and mon in mons:
        return screens[mons.index(mon)]
    best, score = QGuiApplication.primaryScreen(), 1e18
    for s in screens:
        g = s.geometry()
        dpr = s.devicePixelRatio()
        sc = abs(g.width() * dpr - mon["width"]) + abs(g.height() * dpr - mon["height"])
        if sc < score:
            best, score = s, sc
    return best


class ScreenSelector(QWidget):
    """멈춘 화면 위에서 드래그해 영역을 고른다.

    mode="region": 녹화 영역 1개 / mode="mask": 가릴 영역 여러 개 (Enter 완료)
    결과 좌표는 실제 화면(물리) 좌표 [left, top, width, height].
    """
    selected = Signal(object)  # list[list[int]] 또는 None

    def __init__(self, mon: dict, monitors: list[dict], mode: str = "region", existing=None):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.mon, self.mode = mon, mode
        with winutil.new_mss() as sct:
            shot = sct.grab(mon)
            self.img = QImage(bytes(shot.bgra), shot.width, shot.height, QImage.Format_RGB32).copy()
        self.rects: list[QRect] = []   # 이미지(물리) 좌표
        for r in existing or []:
            self.rects.append(QRect(r[0] - mon["left"], r[1] - mon["top"], r[2], r[3]))
        self._start = None
        self._cur = None
        scr = qscreen_for_monitor(mon, monitors)
        self.setGeometry(scr.geometry())
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

    # 위젯 ↔ 이미지 좌표 변환
    def _sx(self):
        return self.img.width() / max(1, self.width())

    def _sy(self):
        return self.img.height() / max(1, self.height())

    def _to_img(self, r: QRect) -> QRect:
        return QRect(int(r.x() * self._sx()), int(r.y() * self._sy()), int(r.width() * self._sx()),
                     int(r.height() * self._sy()))

    def _to_widget(self, r: QRect) -> QRectF:
        return QRectF(r.x() / self._sx(), r.y() / self._sy(), r.width() / self._sx(), r.height() / self._sy())

    def showEvent(self, e):
        super().showEvent(e)
        exclude(self, True)
        self.showFullScreen()
        bring_to_front(self)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawImage(self.rect(), self.img)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))
        boxes = [self._to_widget(r) for r in self.rects]
        if self._start and self._cur:
            boxes.append(QRectF(QRect(self._start, self._cur).normalized()))
        for i, b in enumerate(boxes):
            src = QRectF(b.x() * self._sx(), b.y() * self._sy(), b.width() * self._sx(), b.height() * self._sy())
            p.drawImage(b, self.img, src)
            color = QColor(T.BLUE) if self.mode == "region" else QColor(T.RED)
            if self.mode == "mask":
                p.fillRect(b, QColor(240, 68, 82, 70))
            p.setPen(QPen(color, 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(b, 6, 6)
            ir = self._to_img(b.toRect())
            tag = f"{ir.width()} × {ir.height()}"
            p.setFont(T.font(13, QFont.Weight.Bold))
            tw = p.fontMetrics().horizontalAdvance(tag) + 16
            tr = QRectF(b.x(), max(0, b.y() - 30), tw, 24)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(tr, 8, 8)
            p.setPen(QColor("white"))
            p.drawText(tr, Qt.AlignCenter, tag)
        # 안내 카드
        msg = ("드래그해서 녹화할 영역을 골라주세요" if self.mode == "region"
               else "가릴 영역을 드래그로 추가하세요 · 클릭하면 지워져요")
        sub = "Esc 취소" if self.mode == "region" else "Enter 완료 · Esc 취소 · Backspace 마지막 지우기"
        p.setFont(T.font(20, QFont.Weight.Bold))
        w = max(p.fontMetrics().horizontalAdvance(msg), 300) + 64
        card = QRectF((self.width() - w) / 2, 40, w, 84)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 245))
        p.drawRoundedRect(card, 20, 20)
        p.setPen(QColor(T.G900))
        p.drawText(card.adjusted(0, 12, 0, -36), Qt.AlignCenter, msg)
        p.setFont(T.font(14, QFont.Weight.Medium))
        p.setPen(QColor(T.G500))
        p.drawText(card.adjusted(0, 46, 0, -8), Qt.AlignCenter, sub)

    def mousePressEvent(self, e):
        pt = e.position().toPoint()
        if self.mode == "mask":
            for r in list(self.rects):
                if self._to_widget(r).contains(pt):
                    self.rects.remove(r)
                    self.update()
                    return
        self._start = pt
        self._cur = pt

    def mouseMoveEvent(self, e):
        if self._start:
            self._cur = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if not self._start:
            return
        r = QRect(self._start, e.position().toPoint()).normalized()
        self._start = self._cur = None
        ir = self._to_img(r)
        if ir.width() < 24 or ir.height() < 24:
            self.update()
            return
        if self.mode == "region":
            ir.setWidth(ir.width() // 2 * 2)
            ir.setHeight(ir.height() // 2 * 2)
            self._finish([ir])
        else:
            self.rects.append(ir)
            self.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            self.selected.emit(None)
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.mode == "mask":
            self._finish(self.rects)
        elif e.key() == Qt.Key_Backspace and self.mode == "mask" and self.rects:
            self.rects.pop()
            self.update()

    def _finish(self, rects):
        out = [[r.x() + self.mon["left"], r.y() + self.mon["top"], r.width(), r.height()] for r in rects]
        self.close()
        self.selected.emit(out)


def pil_to_pixmap(img) -> QPixmap:
    rgb = img.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    q = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(q)
