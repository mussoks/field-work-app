"""앱 로직 (UI 와 분리). 후킹/녹화/캡쳐 스레드 → Qt 시그널로 UI 에 전달."""
from __future__ import annotations

import os
import queue
import shutil
import threading
import time
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path

from PySide6.QtCore import QObject, Signal

import winutil
from capture import CaptureManager, grab_under_cursor
from config import QUALITY_PRESETS, RESOLUTIONS, load_settings, save_settings
from input_hub import InputHub
from overlay import OverlayState
from recorder import Recorder


@dataclass
class LibraryItem:
    kind: str            # "record" | "capture"
    title: str
    path: Path           # 폴더 (또는 예전 형식의 mp4 파일)
    created: datetime
    size: int
    thumb: Path | None
    detail: str
    main_file: Path      # 열기 대상


def folder_size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    total = 0
    for root, _, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def human_size(n: int) -> str:
    if n < 1024 * 1024:
        return f"{n / 1024:.0f}KB"
    if n < 1024 ** 3:
        return f"{n / 1024 / 1024:.1f}MB"
    return f"{n / 1024 ** 3:.2f}GB"


class Controller(QObject):
    hotkey = Signal(str)
    grabbed = Signal(object)            # GrabResult
    capture_saved = Signal(object, object)  # Step, GrabResult
    captures_changed = Signal()
    rec_started = Signal(object)
    rec_finished = Signal(object)       # Recorder
    rec_pause_changed = Signal(bool)
    hotkey_recorded = Signal(str, object)
    toast = Signal(str)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.s = load_settings()
        self.overlay = OverlayState(self.s.click_hold_sec, self.s.key_overlay)
        self.recorder: Recorder | None = None
        self.captures = CaptureManager(self.s)
        self.monitors = self._list_monitors()
        self._cap_q: queue.Queue = queue.Queue()
        self.hub = InputHub()
        self.hub.set_hotkeys(self.s.hotkeys)
        self.hub.on_hotkey = self.hotkey.emit
        self.hub.on_mouse.append(self._on_mouse_hook)
        self.hub.on_key.append(self._on_key_hook)
        self.hub_error = None
        try:
            self.hub.start()
        except Exception as ex:  # noqa: BLE001
            self.hub_error = str(ex)
        threading.Thread(target=self._capture_worker, daemon=True, name="capture").start()
        self.grabbed.connect(self._on_grabbed)
        self.hotkey.connect(self._handle_hotkey)
        self.counting = False

    # ------------------------------------------------------------ 공통
    def save(self):
        save_settings(self.s)

    def set(self, attr: str, value):
        setattr(self.s, attr, value)
        if attr == "click_hold_sec":
            self.overlay.hold_sec = value
        if attr == "key_overlay":
            self.overlay.key_mode = value
        self.save()

    def _list_monitors(self):
        try:
            with winutil.new_mss() as sct:
                return [dict(m) for m in sct.monitors]
        except Exception:
            return [{"left": 0, "top": 0, "width": 1920, "height": 1080}] * 2

    def root(self) -> Path:
        return self.s.root_dir()

    # ------------------------------------------------------------ 단축키
    def set_hotkey(self, name: str, combo: str | None) -> str | None:
        """충돌 시 충돌한 기능 이름 반환."""
        if not combo:
            return None
        for other, val in self.s.hotkeys.items():
            if other != name and val == combo:
                return other
        self.s.hotkeys[name] = combo
        self.hub.set_hotkeys(self.s.hotkeys)
        self.save()
        return None

    def record_hotkey(self, name: str):
        self.hub.record_next_hotkey(lambda combo: self.hotkey_recorded.emit(name, combo))

    def _handle_hotkey(self, name: str):
        if name == "capture":
            self.request_capture()
        elif name == "end_set":
            self.end_set()
        elif name == "undo":
            st = self.captures.undo_last()
            if st:
                self.toast.emit(f"{st.step}번 캡쳐를 지웠어요")
                self.captures_changed.emit()
        elif name == "pause":
            self.toggle_pause()
        # record 는 카운트다운 UI 가 필요하므로 메인 창에서 처리

    # ------------------------------------------------------------ 녹화
    def record_rect(self) -> dict:
        if self.s.region:
            l, t, w, h = self.s.region
            return {"left": l, "top": t, "width": w, "height": h}
        idx = min(max(self.s.monitor_index, 1), len(self.monitors) - 1)
        m = self.monitors[idx]
        return {k: m[k] for k in ("left", "top", "width", "height")}

    def start_record(self):
        if self.recorder:
            return
        res = "1080p" if "1080" in self.s.resolution else "720p"
        name = f"녹화_{datetime.now():%Y%m%d_%H%M%S}_{res}_{self.s.fps}fps"
        folder = self.root() / "녹화" / name
        folder.mkdir(parents=True, exist_ok=True)
        self.overlay.hold_sec = self.s.click_hold_sec
        self.overlay.key_mode = self.s.key_overlay
        self.recorder = Recorder(folder / f"{name}.mp4", self.record_rect(), RESOLUTIONS[self.s.resolution],
                                 self.s.fps, QUALITY_PRESETS[self.s.quality], self.overlay, self.s)
        self.recorder.start()
        self.rec_started.emit(self.recorder)

    def stop_record(self):
        rec, self.recorder = self.recorder, None
        if not rec:
            return
        rec.stop()

        def wait():
            rec.join()
            self.rec_finished.emit(rec)
        threading.Thread(target=wait, daemon=True).start()

    def toggle_pause(self):
        if self.recorder:
            self.rec_pause_changed.emit(self.recorder.toggle_pause())

    # ------------------------------------------------------------ 캡쳐
    def request_capture(self, delay: float = 0.0, button: str = "left", source: str = "hotkey",
                        cursor=None, double: bool = False):
        self._cap_q.put((delay, button, source, cursor, double))

    def _capture_worker(self):
        sct = winutil.new_mss()
        while True:
            delay, button, source, cursor, double = self._cap_q.get()
            if delay:
                time.sleep(delay)
            try:
                cur = cursor or winutil.get_cursor_pos()
                if cur is None:
                    try:
                        from pynput.mouse import Controller as MC
                        cur = tuple(int(v) for v in MC().position)
                    except Exception:
                        cur = None
                masks = self.s.mask_regions if self.s.mask_enabled else None
                g = grab_under_cursor(sct, cur, button, source, masks, self.s.uia_enabled)
                g.double = double
                self.grabbed.emit(g)
            except Exception as ex:  # noqa: BLE001
                self.error.emit(f"캡쳐하지 못했어요: {ex}")

    def _on_grabbed(self, g):
        note = g.suggestion if (self.s.auto_note and (g.source != "hotkey" or not self.s.note_popup)) else ""
        try:
            st = self.captures.add(g, note)
        except Exception as ex:  # noqa: BLE001
            self.error.emit(f"캡쳐를 저장하지 못했어요: {ex}")
            return
        self.captures_changed.emit()
        self.capture_saved.emit(st, g)

    def set_note(self, step: int, note: str):
        if self.captures.update_note(step, note):
            if note:
                rec = [n for n in self.s.recent_notes if n != note]
                self.s.recent_notes = ([note] + rec)[:8]
                self.save()
            self.captures_changed.emit()

    def end_set(self):
        n = len(self.captures.steps)
        name = self.captures.set_name
        folder = self.captures.end_set()
        if name:
            rec = [x for x in self.s.recent_set_names if x != name]
            self.s.recent_set_names = ([name] + rec)[:6]
            self.save()
        self.captures_changed.emit()
        if folder:
            self.toast.emit(f"'{name or folder.name}' {n}장을 저장했어요. 다음 캡쳐는 1번부터예요")
        else:
            self.toast.emit("새 캡쳐 세트를 준비했어요")

    # ------------------------------------------------------------ 후킹 (리스너 스레드)
    def _on_mouse_hook(self, e):
        self.overlay.on_mouse(e)
        rec = self.recorder
        if rec:
            rec.log_mouse(e)
        if (e["type"] == "mouse_down" and self.s.auto_click_capture and not e.get("double")
                and e["button"] in ("left", "right") and not winutil.is_own_window_at(e["x"], e["y"])):
            self.request_capture(0.0, e["button"], "auto_click", (e["x"], e["y"]))

    def _on_key_hook(self, e):
        self.overlay.on_key(e)
        rec = self.recorder
        if rec:
            rec.log_key(e)

    # ------------------------------------------------------------ 보관함
    def library(self) -> list[LibraryItem]:
        items: list[LibraryItem] = []
        root = self.root()
        rec_dir = root / "녹화"
        if rec_dir.exists():
            for p in rec_dir.iterdir():
                try:
                    if p.is_dir():
                        mp4s = list(p.glob("*.mp4"))
                        if not mp4s:
                            continue
                        mp4 = mp4s[0]
                        shots = len(list((p / "클릭장면").glob("*_원본.png")))
                        detail = f"클릭 장면 {shots}개" if shots else "영상"
                        thumb = p / "thumb.jpg"
                        items.append(LibraryItem("record", p.name, p, datetime.fromtimestamp(mp4.stat().st_mtime),
                                                 folder_size(p), thumb if thumb.exists() else None, detail, mp4))
                    elif p.suffix.lower() == ".mp4":  # 0.1 버전 형식
                        items.append(LibraryItem("record", p.stem, p, datetime.fromtimestamp(p.stat().st_mtime),
                                                 p.stat().st_size, None, "영상", p))
                except OSError:
                    continue
        for p in root.glob("캡쳐_*"):
            if not p.is_dir():
                continue
            try:
                imgs = sorted(x for x in p.glob("[0-9][0-9].*") if x.suffix.lower() in (".png", ".jpg"))
                title = p.name.split("_", 3)[3] if p.name.count("_") >= 3 else "이름 없는 세트"
                guide = p / "가이드.html"
                items.append(LibraryItem("capture", title, p, datetime.fromtimestamp(p.stat().st_mtime),
                                         folder_size(p), imgs[0] if imgs else None, f"{len(imgs)}단계",
                                         guide if guide.exists() else p))
            except OSError:
                continue
        items.sort(key=lambda i: i.created, reverse=True)
        return items

    def stats(self) -> dict:
        items = self.library()
        today = date.today()
        rec_today = sum(1 for i in items if i.kind == "record" and i.created.date() == today)
        cap_today = 0
        clicks = 0
        for i in items:
            if i.kind == "capture" and i.created.date() == today:
                cap_today += int(i.detail.replace("단계", "") or 0)
            if i.kind == "record" and i.path.is_dir():
                ann = i.path / "클릭장면" / "annotations.jsonl"
                if ann.exists():
                    try:
                        clicks += sum(1 for _ in open(ann, encoding="utf-8"))
                    except OSError:
                        pass
            if i.kind == "capture":
                try:
                    clicks += int(i.detail.replace("단계", "") or 0)
                except ValueError:
                    pass
        return {"rec_today": rec_today, "cap_today": cap_today + len(self.captures.steps),
                "total": human_size(sum(i.size for i in items)), "clicks": clicks, "items": items}

    def delete_item(self, item: LibraryItem):
        if item.path.is_dir():
            shutil.rmtree(item.path, ignore_errors=True)
        else:
            for p in (item.path, item.path.with_suffix(".events.json")):
                try:
                    p.unlink()
                except OSError:
                    pass

    def shutdown(self):
        if self.recorder:
            rec = self.recorder
            self.recorder = None
            rec.stop()
            rec.join(timeout=30)
        if self.captures.active:
            self.captures.end_set()
        self.hub.stop()
