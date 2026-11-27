"""메인 창: 왼쪽 메뉴 + 페이지, 트레이, 알림, 첫 실행 안내."""
from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QDialog, QHBoxLayout, QLabel, QMainWindow, QMenu, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

import winutil
from config import APP_NAME
from controller import Controller
from input_hub import format_hotkey
from ui import theme as T
from ui.overlays import Countdown, MiniBar, NotePopup, ScreenSelector, exclude, qscreen_for_monitor
from ui.pages import CapturePage, HomePage, LibraryPage, RecordPage, SettingsPage
from ui.widgets import Toast, button, label, shadow

NAV = [("home", "🏠", "홈"), ("record", "🎬", "녹화"), ("capture", "📸", "캡쳐"),
       ("library", "🗂️", "보관함"), ("settings", "⚙️", "설정")]


def app_icon() -> QIcon:
    p = winutil.asset_path("icon.ico")
    if p.exists():
        return QIcon(str(p))
    p = winutil.asset_path("icon.png")
    return QIcon(str(p)) if p.exists() else QIcon()


class MainWindow(QMainWindow):
    def __init__(self, controller: Controller):
        super().__init__()
        self.c = controller
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1080, 760)
        self.setMinimumSize(900, 620)
        self._quitting = False
        self.minibar: MiniBar | None = None
        self.note_popup: NotePopup | None = None
        self._selector = None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 사이드바
        side = QWidget()
        side.setObjectName("sidebar")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(16, 24, 16, 20)
        sl.setSpacing(4)
        brand = QHBoxLayout()
        logo = QLabel()
        pm = QPixmap(str(winutil.asset_path("icon.png")))
        if not pm.isNull():
            logo.setPixmap(pm.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label("학습 레코더", "appName"))
        names.addWidget(label("ERP 자동화 학습용", "appTag"))
        brand.addLayout(names)
        brand.addStretch(1)
        sl.addLayout(brand)
        sl.addSpacing(22)
        self.nav_group = QButtonGroup(self)
        self.nav_btns = {}
        for key, emoji, text in NAV:
            b = button(f"{emoji}   {text}", "nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav_group.addButton(b)
            self.nav_btns[key] = b
            sl.addWidget(b)
        sl.addStretch(1)
        self.rec_chip = QLabel("")
        self.rec_chip.setObjectName("badgeRed")
        self.rec_chip.hide()
        sl.addWidget(self.rec_chip)
        sl.addSpacing(6)
        self.side_hint = label("", "caption", wrap=True)
        sl.addWidget(self.side_hint)
        lay.addWidget(side)

        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        self.pages = {
            "home": HomePage(self), "record": RecordPage(self), "capture": CapturePage(self),
            "library": LibraryPage(self), "settings": SettingsPage(self),
        }
        for p in self.pages.values():
            self.stack.addWidget(p)

        self._toast = Toast(root)
        self._setup_tray()

        c = self.c
        c.toast.connect(self.toast)
        c.error.connect(lambda m: self.toast(f"⚠️ {m}", 4000))
        c.captures_changed.connect(self._refresh_current)
        c.capture_saved.connect(self._on_capture_saved)
        c.rec_started.connect(self._on_rec_started)
        c.rec_finished.connect(self._on_rec_finished)
        c.rec_pause_changed.connect(lambda p: (self.toast("녹화를 잠시 멈췄어요" if p else "녹화를 이어서 해요"),
                                                self._refresh_current()))
        c.hotkey.connect(self._on_hotkey)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)
        self.go("home")
        self._update_side_hint()
        if c.hub_error:
            QTimer.singleShot(800, lambda: self.toast("⚠️ 전역 단축키를 시작하지 못했어요: " + c.hub_error, 5000))
        if not c.s.onboarded:
            QTimer.singleShot(400, self.show_onboarding)

    # ------------------------------------------------------------ 공통
    def go(self, key: str):
        self.nav_btns[key].setChecked(True)
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        page.refresh()

    def _refresh_current(self):
        self.stack.currentWidget().refresh()
        self._update_side_hint()

    def toast(self, text: str, ms: int = 2200):
        if self.isVisible() and not self.isMinimized():
            self._toast.show_text(text, ms)
        elif self.c.s.notify and self.tray:
            self.tray.showMessage(APP_NAME, text, app_icon(), ms)

    def apply_exclude(self):
        exclude(self, self.c.s.exclude_self)

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(50, self.apply_exclude)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._toast.isVisible():
            self._toast.move((self.centralWidget().width() - self._toast.width()) // 2,
                             self.centralWidget().height() - self._toast.height() - 36)

    def _update_side_hint(self):
        hk = self.c.s.hotkeys
        self.side_hint.setText(f"캡쳐  {format_hotkey(hk['capture'])}\n녹화  {format_hotkey(hk['record'])}")

    # ------------------------------------------------------------ 트레이
    def _setup_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        m = QMenu()
        self.act_rec = QAction("녹화 시작", self, triggered=self.toggle_record)
        m.addAction(QAction("열기", self, triggered=self.restore))
        m.addSeparator()
        m.addAction(self.act_rec)
        m.addAction(QAction("지금 캡쳐", self, triggered=lambda: self.capture_now(0.25)))
        m.addAction(QAction("캡쳐 세트 끝내기", self, triggered=self.c.end_set))
        m.addSeparator()
        m.addAction(QAction("종료", self, triggered=self.quit))
        self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda r: self.restore() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        if not self._quitting and self.c.s.minimize_to_tray and self.tray:
            e.ignore()
            self.hide()
            self.tray.showMessage(APP_NAME, "트레이에서 계속 실행 중이에요. 단축키도 그대로 쓸 수 있어요.",
                                  app_icon(), 2500)
            return
        self.quit()

    def quit(self):
        from PySide6.QtWidgets import QApplication
        if self.c.recorder:
            from ui.widgets import confirm
            self.restore()
            if not confirm(self, "녹화 중이에요", "녹화를 끝내고 저장한 뒤 종료할까요?", "끝내고 종료"):
                return
        self._quitting = True
        self.c.shutdown()
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    # ------------------------------------------------------------ 단축키
    def _on_hotkey(self, name: str):
        if name == "record":
            self.toggle_record()

    # ------------------------------------------------------------ 녹화
    def toggle_record(self):
        c = self.c
        if c.recorder:
            c.stop_record()
            self.toast("녹화를 저장하고 있어요…")
            self._refresh_current()
            return
        if c.counting:
            return
        if c.s.countdown:
            c.counting = True
            r = c.record_rect()
            scr = qscreen_for_monitor(self._monitor_of(r), c.monitors)
            g = scr.geometry()
            cd = Countdown(QPoint(g.center().x(), g.center().y()), 3)
            cd.finished.connect(self._start_after_countdown)
            cd.show()
            self._cd = cd
        else:
            c.start_record()

    def _monitor_of(self, r):
        for m in self.c.monitors[1:]:
            if m["left"] <= r["left"] < m["left"] + m["width"] and m["top"] <= r["top"] < m["top"] + m["height"]:
                return m
        return self.c.monitors[1] if len(self.c.monitors) > 1 else self.c.monitors[0]

    def _start_after_countdown(self):
        def go():
            self.c.counting = False
            self.c.start_record()
        QTimer.singleShot(150, go)

    def _on_rec_started(self, rec):
        scr = qscreen_for_monitor(self._monitor_of(rec.rect), self.c.monitors)
        self.minibar = MiniBar(scr.availableGeometry())
        self.minibar.pause_clicked.connect(self.c.toggle_pause)
        self.minibar.stop_clicked.connect(self.toggle_record)
        self.minibar.show()
        if self.tray:
            self.act_rec.setText("녹화 끝내기")
        self.rec_chip.show()
        self._refresh_current()

    def _on_rec_finished(self, rec):
        if self.minibar:
            self.minibar.close()
            self.minibar = None
        self.rec_chip.hide()
        if self.tray:
            self.act_rec.setText("녹화 시작")
        if rec.error:
            self.toast(f"⚠️ 녹화 중 문제가 생겼어요: {rec.error}", 5000)
        else:
            size = rec.out_path.stat().st_size / 1024 / 1024 if rec.out_path.exists() else 0
            shots = sum(1 for e in rec.events if "shot" in e)
            self.toast(f"녹화를 저장했어요 · {rec.frames / rec.fps:.0f}초 · {size:.1f}MB · 클릭 장면 {shots}개", 3500)
        self._refresh_current()

    def _tick(self):
        rec = self.c.recorder
        if rec and rec.start_t:
            t = rec.video_time()
            clicks = sum(1 for e in rec.events if e["type"] == "mouse_down")
            if self.minibar:
                self.minibar.set_state(t, f"클릭 {clicks}", rec.paused)
            self.rec_chip.setText(f"● 녹화 중 {int(t // 60):02d}:{int(t % 60):02d}")
            if self.stack.currentWidget() in (self.pages["record"],):
                self.pages["record"].refresh()
            if not rec.is_alive():
                self.c.stop_record()

    # ------------------------------------------------------------ 캡쳐
    def capture_now(self, delay: float = 0.35):
        # 버튼으로 찍을 때는 이 창이 찍히지 않게 잠깐 기다린 뒤 촬영
        self.c.request_capture(delay=delay)

    def _on_capture_saved(self, st, g):
        if self.note_popup is not None:
            try:
                self.note_popup.commit()
            except RuntimeError:
                pass
        if g.source == "hotkey" and self.c.s.note_popup:
            pop = NotePopup(st.step, g.suggestion, self.c.s.recent_notes, g.element, self.c.s.exclude_self)
            pop.done.connect(lambda step, note, hwnd=g.prev_hwnd: self._note_done(step, note, hwnd))
            self.note_popup = pop
            pop.show()
        else:
            self.toast(f"✔ {st.step}번을 캡쳐했어요" + (f" · {st.note}" if st.note else ""))

    def _note_done(self, step, note, prev_hwnd):
        self.note_popup = None
        if note:
            self.c.set_note(step, note)
        elif note is None and self.c.s.auto_note:
            pass
        if prev_hwnd:
            winutil.set_foreground(prev_hwnd)
        self.toast(f"✔ {step}번을 저장했어요" + (f" · {note}" if note else ""))

    # ------------------------------------------------------------ 화면 선택
    def pick_screen(self, mode, mon, callback, existing=None):
        was_visible = self.isVisible()
        self.hide()

        def done(rects):
            self._selector = None
            if was_visible:
                self.restore()
            callback(rects)

        def open_sel():
            sel = ScreenSelector(mon, self.c.monitors, mode, existing)
            sel.selected.connect(done)
            self._selector = sel
            sel.show()
        QTimer.singleShot(250, open_sel)

    # ------------------------------------------------------------ 첫 실행 안내
    def show_onboarding(self):
        Onboarding(self).exec()
        self.c.set("onboarded", True)


class Onboarding(QDialog):
    STEPS = [
        ("🎬", "녹화하면 클릭이 또렷하게 남아요",
         "마우스 포인터는 항상 보이고, 클릭한 곳에는 빨간 원과 표시가 찍혀요.\n클릭할 때마다 학습용 장면과 좌표도 따로 모아요."),
        ("📸", "단축키 한 번으로 단계별 캡쳐",
         "마우스를 올려두고 단축키를 누르면 ✔ 번호와 각주가 찍혀요.\n누른 버튼 이름으로 각주를 추천해 드려요."),
        ("🔢", "세트가 끝나면 번호가 1번부터",
         "'세트 끝내기'를 누르면 지금까지의 캡쳐가 한 폴더로 정리되고\n다음 캡쳐는 다시 1번부터 시작해요."),
        ("🔒", "개인정보는 가리고, 이 앱은 안 찍혀요",
         "가릴 영역을 정해두면 모자이크 처리돼요.\n이 앱의 창과 각주 입력창은 녹화·캡쳐에 나오지 않아요."),
    ]

    def __init__(self, parent):
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
        lay.setContentsMargins(36, 34, 36, 26)
        lay.setSpacing(10)
        self.emoji = QLabel()
        self.emoji.setStyleSheet("font-size: 56px;")
        self.emoji.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.emoji)
        self.title = label("", "h1")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 22px;")
        lay.addWidget(self.title)
        self.desc = label("", "h1sub", wrap=True)
        self.desc.setAlignment(Qt.AlignCenter)
        self.desc.setMinimumHeight(52)
        lay.addWidget(self.desc)
        self.dots = QLabel()
        self.dots.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.dots)
        lay.addSpacing(8)
        row = QHBoxLayout()
        self.skip = button("건너뛰기", "gray", "lg", self.accept)
        self.next = button("다음", "primary", "lg", self._next)
        row.addWidget(self.skip)
        row.addWidget(self.next, 2)
        lay.addLayout(row)
        self.i = 0
        self.setFixedWidth(560)
        self._show()

    def _show(self):
        e, t, d = self.STEPS[self.i]
        self.emoji.setText(e)
        self.title.setText(t)
        self.desc.setText(d)
        self.dots.setText("  ".join(
            f"<span style='color:{T.BLUE if k == self.i else T.G300}; font-size:16px'>●</span>"
            for k in range(len(self.STEPS))))
        last = self.i == len(self.STEPS) - 1
        self.next.setText("시작하기" if last else "다음")
        self.skip.setVisible(not last)

    def _next(self):
        if self.i >= len(self.STEPS) - 1:
            self.accept()
            return
        self.i += 1
        self._show()

    def showEvent(self, e):
        super().showEvent(e)
        par = self.parentWidget()
        if par:
            self.adjustSize()
            self.move(par.geometry().center() - QPoint(self.width() // 2, self.height() // 2))
