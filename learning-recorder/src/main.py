"""학습 레코더 — ERP 자동화 AI 학습용 화면 녹화·캡쳐 (Windows 11)."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path


def _log_dir() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home()) / "LearningRecorder"
    base.mkdir(parents=True, exist_ok=True)
    return base


def write_log(text: str):
    try:
        with open(_log_dir() / "error.log", "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}\n")
    except Exception:
        pass


def _fix_std_streams():
    # 창 모드 exe 에는 콘솔이 없다
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def run_gui(argv) -> int:
    from PySide6.QtCore import QLockFile, Qt, QDir
    from PySide6.QtWidgets import QApplication

    from config import APP_NAME
    from ui import theme

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("LearningRecorder")
    app.setApplicationDisplayName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    lock = QLockFile(QDir.tempPath() + "/learning_recorder.lock")
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, APP_NAME, "학습 레코더가 이미 실행 중이에요.\n작업 표시줄 트레이 아이콘을 확인해 주세요.")
        return 0

    theme.load_fonts()
    app.setFont(theme.font(14))
    app.setStyleSheet(theme.qss())

    from controller import Controller
    from ui.main_window import MainWindow

    def excepthook(exc, val, tb):
        import traceback
        write_log("".join(traceback.format_exception(exc, val, tb)))
    sys.excepthook = excepthook

    # Python GC 가 작업 스레드(녹화/캡쳐)에서 돌면 Qt 객체를 다른 스레드에서 지워 충돌할 수 있다.
    # → 자동 GC 를 끄고 GUI 스레드에서만 주기적으로 수거한다.
    import gc
    from PySide6.QtCore import QTimer
    gc.disable()
    gc_timer = QTimer()
    gc_timer.timeout.connect(lambda: gc.collect(0) if gc.get_count()[0] > 700 else None)
    gc_timer.start(1000)
    full_gc = QTimer()
    full_gc.timeout.connect(gc.collect)
    full_gc.start(30000)

    c = Controller()
    if "--ui-smoketest" in argv:
        c.s.onboarded = True  # 자동 점검 중에는 첫 실행 안내를 띄우지 않음
    w = MainWindow(c)
    if "--minimized" in argv and w.tray:
        w.hide()
    else:
        w.show()
    if "--ui-smoketest" in argv:
        from ui_smoketest import run as smoke
        smoke(app, w, argv)
    rc = app.exec()
    lock.unlock()
    return rc


def main():
    _fix_std_streams()
    if "--selftest" in sys.argv:
        import winutil
        winutil.set_dpi_aware()
        import selftest
        sys.exit(selftest.run(sys.argv))
    try:
        sys.exit(run_gui(sys.argv))
    except SystemExit:
        raise
    except BaseException:
        import traceback
        write_log(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
