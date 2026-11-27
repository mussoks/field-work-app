"""UI 자동 점검: 모든 화면을 차례로 띄워 스크린샷을 남기고 종료한다.

    LearningRecorder.exe --ui-smoketest <출력폴더>
"""
from __future__ import annotations

import json
import tempfile
import traceback
from pathlib import Path

from PySide6.QtCore import QTimer


def run(app, w, argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else Path(tempfile.mkdtemp(prefix="lr_ui_"))
    out.mkdir(parents=True, exist_ok=True)
    result = {"ok": False, "shots": []}
    w.c.s.onboarded = True
    steps = []

    def shot(widget, name):
        p = out / f"{len(result['shots']) + 1:02d}_{name}.png"
        widget.grab().save(str(p))
        result["shots"].append(p.name)

    def page(key):
        def f():
            w.go(key)
            QTimer.singleShot(250, lambda: shot(w, key))
        return f

    def onboarding():
        from ui.main_window import Onboarding
        d = Onboarding(w)
        d.show()
        QTimer.singleShot(250, lambda: (shot(d, "onboarding"), d.close()))

    def note_popup():
        from ui.overlays import NotePopup
        el = {"name": "저장", "type": "ButtonControl", "type_ko": "버튼"}
        p = NotePopup(3, "'저장' 버튼 클릭", ["거래처 선택", "조회 버튼 클릭"], el, False)
        p.show()
        QTimer.singleShot(300, lambda: (shot(p, "note_popup"), p.skip()))

    def minibar():
        from PySide6.QtCore import QRect
        from ui.overlays import MiniBar
        m = MiniBar(QRect(0, 0, 1200, 800))
        m.set_state(83, "클릭 12", False)
        m.show()
        QTimer.singleShot(300, lambda: (shot(m, "minibar"), m.close()))

    def uia_check():
        # 이 앱의 '녹화 시작' 버튼을 UI Automation 으로 읽어본다 (Windows: 요소 이름 인식 확인)
        import threading
        import uia
        w.go("home")
        btn = w.pages["home"].rec_btn
        g = btn.mapToGlobal(btn.rect().center())
        dpr = btn.devicePixelRatioF()
        x, y = int(g.x() * dpr), int(g.y() * dpr)
        threading.Thread(target=lambda: result.__setitem__("uia_check", uia.element_at(x, y, 3.0)),
                         daemon=True).start()

    def capture_flow():
        # 실제 캡쳐 1장 (각주창 없이) → 캡쳐 화면 갱신
        w.c.s.note_popup = False
        w.c.request_capture(0.1)
        QTimer.singleShot(1800, page("capture"))

    def finish():
        result["ok"] = len(result["shots"]) >= 8
        result["capture_steps"] = [{"step": s.step, "note": s.note, "element": s.element}
                                   for s in w.c.captures.steps]
        (out / "ui_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        w.c.captures.end_set()
        w._quitting = True
        w.c.shutdown()
        app.exit(0 if result["ok"] else 1)

    steps = [page("home"), page("record"), page("capture"), page("library"), page("settings"),
             onboarding, note_popup, minibar, uia_check, capture_flow, finish]

    def run_step(i=0):
        if i >= len(steps):
            return
        try:
            steps[i]()
        except Exception:
            (out / "ui_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        QTimer.singleShot(2600 if steps[i] is capture_flow else 700, lambda: run_step(i + 1))

    QTimer.singleShot(800, run_step)
