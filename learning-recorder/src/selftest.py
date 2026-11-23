"""자가 진단: 실제 화면을 3초 녹화 + 표시 캡쳐 1장 → 결과 파일 검증.

    학습용녹화캡쳐.exe --selftest [출력폴더]

GitHub Actions(Windows) 빌드 후 exe 가 정상 동작하는지 확인하는 데 사용한다.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path


def run(argv) -> int:
    """예외가 나도 (창 모드 exe 의 오류 대화상자로 멈추지 않도록) 파일에 기록하고 종료 코드로 알린다."""
    args = [a for a in argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else Path(tempfile.mkdtemp(prefix="lr_selftest_"))
    out.mkdir(parents=True, exist_ok=True)
    progress = out / "selftest_progress.txt"

    def log(msg):
        with open(progress, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

    try:
        import faulthandler
        fh = open(out / "selftest_faulthandler.txt", "w")
        faulthandler.enable(fh)
        faulthandler.dump_traceback_later(120, exit=True, file=fh)  # 멈추면 2분 뒤 스택 기록 후 종료
    except Exception:
        pass
    try:
        return _run(out, log)
    except BaseException:
        import traceback
        (out / "selftest_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 2


def _run(out: Path, log) -> int:
    import cv2

    import winutil

    from capture import CaptureManager, grab_under_cursor
    from config import Settings, RESOLUTIONS, QUALITY_PRESETS
    from overlay import OverlayState
    from recorder import Recorder

    import recorder as _rec
    log(f"start frozen={getattr(sys, 'frozen', False)} ffmpeg={_rec.get_ffmpeg()}")
    s = Settings(save_root=str(out), save_event_log=True, countdown=False, key_overlay="특수키만")
    result = {"out": str(out), "ok": False}

    with winutil.new_mss() as sct:
        mon = dict(sct.monitors[1])
    rect = {k: mon[k] for k in ("left", "top", "width", "height")}
    cx, cy = rect["left"] + rect["width"] // 3, rect["top"] + rect["height"] // 3

    for fps in (30, 15):
        ov = OverlayState(0.8, "특수키만")
        video = out / f"selftest_{fps}fps.mp4"
        rec = Recorder(video, rect, RESOLUTIONS["HD (1280x720)"], fps, QUALITY_PRESETS["표준"], ov, s,
                       cursor_fn=lambda: (cx, cy))
        rec.start()
        log(f"recording {fps}fps")
        time.sleep(1.0)
        t = time.perf_counter()
        for e in ({"type": "mouse_down", "t": t, "x": cx, "y": cy, "button": "left", "double": False},
                  {"type": "mouse_up", "t": t + 0.05, "x": cx, "y": cy, "button": "left", "double": False}):
            ov.on_mouse(e)
            rec.log_mouse(e)
        k = {"type": "key", "t": t, "key": "s", "mods": ["ctrl"], "special": True, "label": "Ctrl + S"}
        ov.on_key(k)
        rec.log_key(k)
        time.sleep(2.0)
        rec.stop()
        rec.join(60)
        log(f"recorded {fps}fps error={rec.error} alive={rec.is_alive()}")
        cap = cv2.VideoCapture(str(video))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ev = json.loads(video.with_suffix(".events.json").read_text(encoding="utf-8"))
        click = next(e for e in ev["events"] if e["type"] == "mouse_down")
        cap.set(cv2.CAP_PROP_POS_FRAMES, click["frame"] + 2)
        ok, frame = cap.read()
        if ok:
            cv2.imwrite(str(out / f"selftest_{fps}fps_clickframe.png"), frame)
        cap.release()
        result[f"video_{fps}"] = {"error": rec.error, "bytes": video.stat().st_size if video.exists() else 0,
                                  "frames": frames, "size": [w, h], "click_frame": click["frame"],
                                  "click_xy": [click["x"], click["y"]], "events": len(ev["events"])}

    log("capture")
    cm = CaptureManager(s)
    s.set_name = "자가진단"
    with winutil.new_mss() as sct:
        for i in range(2):
            g = grab_under_cursor(sct, (cx + i * 200, cy + i * 120))
            cm.add(g, "자가진단 각주: 이 버튼을 클릭" if i == 0 else "")
    cm.update_note(2, "두 번째 단계 각주\n줄바꿈 테스트")
    folder = cm.end_set()
    result["capture"] = {"folder": str(folder), "files": sorted(p.name for p in folder.rglob("*") if p.is_file())}

    log("verify")
    v30, v15 = result["video_30"], result["video_15"]
    result["ok"] = (not v30["error"] and not v15["error"] and v30["bytes"] > 0 and v15["bytes"] > 0
                    and 75 <= v30["frames"] <= 110 and 38 <= v15["frames"] <= 55
                    and "01.png" in result["capture"]["files"] and "가이드.html" in result["capture"]["files"])
    (out / "selftest_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    try:  # 콘솔 인코딩(cp1252 등)에서도 깨지지 않게 ASCII 로 출력
        print(json.dumps(result, ensure_ascii=True, indent=1))
    except Exception:
        pass
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(run(sys.argv))
