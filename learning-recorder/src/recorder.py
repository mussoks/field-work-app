"""화면 녹화: mss 로 화면을 잡고 → 오버레이를 그리고 → ffmpeg(libx264) 로 인코딩.

* 해상도: FHD / HD 중 선택 (원본이 더 작으면 원본 크기 유지, 비율 유지)
* 프레임: 30 / 15 fps (고정 프레임레이트. 캡처가 늦으면 직전 프레임을 복제해 시간 동기 유지)
* 용량: x264 CRF + yuv420p + faststart. 화면 녹화는 정지된 부분이 많아 용량이 매우 작다.
* 이벤트 로그: 클릭/키 입력을 '영상 시간·프레임 번호·영상 내 좌표'로 JSON 저장
  → AI 학습 시 프레임과 클릭 좌표를 정확히 매칭할 수 있다.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import winutil
from overlay import OverlayState, render_overlay


def get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def output_size(src_w: int, src_h: int, target: tuple[int, int]) -> tuple[int, int, float]:
    tw, th = target
    scale = min(tw / src_w, th / src_h, 1.0)
    ow = max(2, int(src_w * scale) // 2 * 2)
    oh = max(2, int(src_h * scale) // 2 * 2)
    return ow, oh, ow / src_w


class Recorder(threading.Thread):
    def __init__(self, out_path: Path, rect: dict, target_res: tuple[int, int], fps: int, crf: int,
                 overlay: OverlayState, settings, grabber=None, cursor_fn=None):
        super().__init__(daemon=True)
        self.out_path = Path(out_path)
        self.rect = {k: int(rect[k]) for k in ("left", "top", "width", "height")}
        self.fps = int(fps)
        self.crf = int(crf)
        self.overlay = overlay
        self.settings = settings
        self.ow, self.oh, self.scale = output_size(self.rect["width"], self.rect["height"], target_res)
        self._grabber = grabber          # 테스트용: 프레임 공급 함수 주입
        self._cursor_fn = cursor_fn
        self._stop_evt = threading.Event()
        self._paused = threading.Event()
        self._pause_started = 0.0
        self.paused_total = 0.0
        self.start_t = 0.0
        self.frames = 0
        self.events: list[dict] = []
        self.error: str | None = None
        self._proc: subprocess.Popen | None = None
        self._mouse_ctrl = None

    # ---------- 제어 ----------
    def stop(self):
        self._stop_evt.set()

    def toggle_pause(self) -> bool:
        if self._paused.is_set():
            self.paused_total += time.perf_counter() - self._pause_started
            self._paused.clear()
            return False
        self._pause_started = time.perf_counter()
        self._paused.set()
        return True

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def video_time(self, t: float | None = None) -> float:
        t = time.perf_counter() if t is None else t
        extra = (t - self._pause_started) if self._paused.is_set() else 0.0
        return max(0.0, t - self.start_t - self.paused_total - extra)

    # ---------- 이벤트 로그 ----------
    def log_mouse(self, e: dict):
        if not self.start_t or self._paused.is_set() or not self.settings.save_event_log:
            return
        vt = self.video_time(e["t"])
        r = self.rect
        inside = r["left"] <= e["x"] < r["left"] + r["width"] and r["top"] <= e["y"] < r["top"] + r["height"]
        rec = {
            "t": round(vt, 3), "frame": int(vt * self.fps), "type": e["type"], "button": e.get("button", ""),
            "x": round((e["x"] - r["left"]) * self.scale), "y": round((e["y"] - r["top"]) * self.scale),
            "screen_x": e["x"], "screen_y": e["y"], "inside": inside,
        }
        if e.get("double"):
            rec["double"] = True
        if e["type"] == "scroll":
            rec["dy"] = e["dy"]
        if e["type"] == "mouse_down":
            rec["window"] = winutil.get_window_title()
            rec["process"] = winutil.get_window_process_name()
        self.events.append(rec)

    def log_key(self, e: dict):
        mode = self.settings.key_overlay
        if not self.start_t or self._paused.is_set() or mode == "끄기" or not self.settings.save_event_log:
            return
        if mode == "특수키만" and not e["special"]:
            return
        vt = self.video_time(e["t"])
        self.events.append({"t": round(vt, 3), "frame": int(vt * self.fps), "type": "key",
                            "key": e["label"]})

    # ---------- 본체 ----------
    def _cursor(self):
        if self._cursor_fn:
            return self._cursor_fn()
        pos = winutil.get_cursor_pos()
        if pos is None:
            try:
                if self._mouse_ctrl is None:
                    from pynput.mouse import Controller
                    self._mouse_ctrl = Controller()
                pos = tuple(int(v) for v in self._mouse_ctrl.position)
            except Exception:
                pos = None
        return pos

    def _open_ffmpeg(self):
        cmd = [
            get_ffmpeg(), "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{self.ow}x{self.oh}",
            "-framerate", str(self.fps), "-i", "-",
            "-c:v", "libx264", "-preset", "faster", "-crf", str(self.crf),
            "-pix_fmt", "yuv420p", "-g", str(self.fps * 4),
            "-movflags", "+faststart",
            "-metadata", "comment=learning-recorder: click markers drawn on frames",
            str(self.out_path),
        ]
        self._errlog = open(self.out_path.with_suffix(".ffmpeg.log"), "wb")
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                      stderr=self._errlog, creationflags=winutil.no_window_flags())

    def run(self):
        try:
            self._run()
        except Exception as ex:  # noqa: BLE001
            self.error = f"{type(ex).__name__}: {ex}"
        finally:
            self._finish()

    def _run(self):
        self._open_ffmpeg()
        sct = None
        if self._grabber is None:
            sct = winutil.new_mss()
        r = self.rect
        origin = (r["left"], r["top"])
        self.start_t = time.perf_counter()
        s = self.settings
        while not self._stop_evt.is_set():
            if self._paused.is_set():
                time.sleep(0.02)
                continue
            vt = self.video_time()
            target = int(vt * self.fps) + 1
            if self.frames >= target:
                time.sleep(max(0.001, (self.frames / self.fps) - vt))
                continue
            if self._grabber is not None:
                img = self._grabber()
            else:
                shot = sct.grab(r)
                img = np.asarray(shot)[:, :, :3]
            if self.scale < 0.999:
                img = cv2.resize(img, (self.ow, self.oh), interpolation=cv2.INTER_AREA)
            else:
                img = np.ascontiguousarray(img[: self.oh, : self.ow])
            render_overlay(img, self.overlay, time.perf_counter(), self._cursor(), origin, self.scale,
                           s.marker_scale, s.show_cursor_halo, s.show_clicks)
            data = img.tobytes()
            # 캡처가 늦어 밀린 만큼 같은 프레임을 반복 기록 → 영상 시간 = 실제 시간 (로그 프레임 번호와 일치)
            for _ in range(target - self.frames):
                self._proc.stdin.write(data)
            self.frames = target

    def _finish(self):
        try:
            if self._proc and self._proc.stdin:
                self._proc.stdin.close()
            if self._proc:
                self._proc.wait(timeout=60)
        except Exception as ex:  # noqa: BLE001
            self.error = self.error or str(ex)
        try:
            self._errlog.close()
            log = self.out_path.with_suffix(".ffmpeg.log")
            if log.exists() and log.stat().st_size == 0:
                log.unlink()
        except Exception:
            pass
        if self._proc and self._proc.returncode not in (0, None) and not self.error:
            self.error = f"ffmpeg 종료 코드 {self._proc.returncode}"
        if self.settings.optimize_after and not self.error and self.out_path.exists():
            self._optimize()
        if self.settings.save_event_log:
            self._write_events()

    def _optimize(self):
        tmp = self.out_path.with_name(self.out_path.stem + "_opt.mp4")
        cmd = [get_ffmpeg(), "-y", "-loglevel", "error", "-i", str(self.out_path),
               "-c:v", "libx264", "-preset", "slow", "-crf", str(self.crf),
               "-pix_fmt", "yuv420p", "-g", str(self.fps * 4), "-movflags", "+faststart", str(tmp)]
        try:
            subprocess.run(cmd, check=True, creationflags=winutil.no_window_flags())
            if tmp.stat().st_size < self.out_path.stat().st_size:
                os.replace(tmp, self.out_path)
            else:
                tmp.unlink()
        except Exception:
            if tmp.exists():
                tmp.unlink()

    def _write_events(self):
        info = {
            "video": self.out_path.name,
            "created": datetime.now().isoformat(timespec="seconds"),
            "fps": self.fps,
            "width": self.ow, "height": self.oh,
            "source_rect": self.rect,
            "scale": round(self.scale, 6),
            "duration_sec": round(self.frames / self.fps, 3),
            "frames": self.frames,
            "coords": "x,y = 영상 프레임 내 픽셀 좌표 / screen_x,screen_y = 실제 화면 좌표",
            "events": sorted(self.events, key=lambda e: e["t"]),
        }
        p = self.out_path.with_suffix(".events.json")
        p.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
