"""학습용 화면녹화·캡쳐 (Windows 11) — ERP 자동화 AI 학습 데이터 수집용 프로토타입."""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox, filedialog, simpledialog
import tkinter.font as tkfont

import winutil

winutil.set_dpi_aware()  # Tk 생성 전에 호출해야 좌표가 정확함

from config import (APP_NAME, APP_VERSION, QUALITY_PRESETS, RESOLUTIONS, HOTKEY_LABELS,
                    load_settings, save_settings, default_hotkeys)
from input_hub import InputHub, format_hotkey
from overlay import OverlayState
from recorder import Recorder
from capture import CaptureManager, grab_under_cursor, wrap_preview

MARKER_SIZES = {"작게": 0.8, "보통": 1.0, "크게": 1.3}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.s = load_settings()
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("560x760")
        self.minsize(520, 640)
        self._setup_fonts()

        self.ui_q: queue.Queue = queue.Queue()
        self.cap_q: queue.Queue = queue.Queue()
        self.overlay = OverlayState(self.s.click_hold_sec, self.s.key_overlay)
        self.recorder: Recorder | None = None
        self.captures = CaptureManager(self.s)
        self.note_popup: NotePopup | None = None
        self.minibar: MiniBar | None = None
        self.monitors = self._list_monitors()

        self.hub = InputHub()
        self.hub.set_hotkeys(self.s.hotkeys)
        self.hub.on_hotkey = lambda name: self.ui_q.put(("hotkey", name))
        self.hub.on_mouse.append(self._on_mouse_hook)
        self.hub.on_key.append(self._on_key_hook)
        try:
            self.hub.start()
        except Exception as ex:  # noqa: BLE001
            messagebox.showwarning(APP_NAME, f"전역 단축키/마우스 감지를 시작하지 못했습니다.\n{ex}")

        threading.Thread(target=self._capture_worker, daemon=True).start()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(30, self._poll)
        self.after(500, self._tick)
        self.after(300, self._apply_exclude)

    # ================================================================ 기본 설정
    def _setup_fonts(self):
        fam = "Malgun Gothic" if winutil.IS_WIN else "NanumGothic"
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(family=fam, size=10)
            except Exception:
                pass
        style = ttk.Style(self)
        try:
            style.theme_use("vista" if winutil.IS_WIN else "clam")
        except Exception:
            pass
        style.configure("Big.TButton", font=(fam, 12, "bold"), padding=8)
        style.configure("Title.TLabel", font=(fam, 14, "bold"))
        style.configure("Status.TLabel", font=(fam, 11, "bold"))
        style.configure("Hint.TLabel", foreground="#666")

    def _apply_exclude(self):
        for w in [self] + [x for x in (self.note_popup, self.minibar) if x]:
            winutil.exclude_from_capture(w, self.s.exclude_self)

    def _list_monitors(self):
        try:
            with winutil.new_mss() as sct:
                return [dict(m) for m in sct.monitors]
        except Exception:
            return [{"left": 0, "top": 0, "width": 1920, "height": 1080}] * 2

    def _save(self):
        save_settings(self.s)

    def _bind(self, var: tk.Variable, attr: str, conv=lambda v: v, after=None):
        def cb(*_):
            try:
                setattr(self.s, attr, conv(var.get()))
            except Exception:
                return
            self._save()
            if after:
                after()
        var.trace_add("write", cb)
        return var

    # ================================================================ UI
    def _build_ui(self):
        top = ttk.Frame(self, padding=(12, 10, 12, 0))
        top.pack(fill="x")
        ttk.Label(top, text="학습용 화면녹화 · 캡쳐", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="📁 저장 폴더 열기", command=lambda: winutil.open_folder(self.s.root_dir())).pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=8)
        self._build_record_tab(nb)
        self._build_capture_tab(nb)
        self._build_settings_tab(nb)

        self.status = tk.StringVar(value="대기 중")
        bar = ttk.Frame(self, padding=(12, 0, 12, 8))
        bar.pack(fill="x")
        ttk.Label(bar, textvariable=self.status, style="Hint.TLabel").pack(side="left")

    # ---------------------------------------------------------------- 녹화 탭
    def _build_record_tab(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="  🎬 녹화  ")
        s = self.s

        g = ttk.LabelFrame(f, text="녹화 대상", padding=8)
        g.pack(fill="x")
        mons = [f"모니터 {i}  ({m['width']}x{m['height']})" for i, m in enumerate(self.monitors) if i > 0]
        self.mon_var = tk.StringVar(value=mons[min(max(s.monitor_index, 1), len(mons)) - 1] if mons else "")
        cb = ttk.Combobox(g, textvariable=self.mon_var, values=mons, state="readonly", width=28)
        cb.grid(row=0, column=0, sticky="w")
        self.mon_var.trace_add("write", lambda *_: self._set_monitor(mons.index(self.mon_var.get()) + 1))
        ttk.Button(g, text="영역 지정…", command=self._select_region).grid(row=0, column=1, padx=6)
        ttk.Button(g, text="전체 화면", command=self._clear_region).grid(row=0, column=2)
        self.region_lbl = ttk.Label(g, text="", style="Hint.TLabel")
        self.region_lbl.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self._update_region_label()

        g = ttk.LabelFrame(f, text="화질 / 용량", padding=8)
        g.pack(fill="x", pady=8)
        self.res_var = self._bind(tk.StringVar(value=s.resolution), "resolution")
        ttk.Label(g, text="해상도").grid(row=0, column=0, sticky="w")
        for i, name in enumerate(RESOLUTIONS):
            ttk.Radiobutton(g, text=name, value=name, variable=self.res_var).grid(row=0, column=1 + i, sticky="w", padx=4)
        self.fps_var = self._bind(tk.IntVar(value=s.fps), "fps", int)
        ttk.Label(g, text="프레임").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Radiobutton(g, text="30 fps", value=30, variable=self.fps_var).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Radiobutton(g, text="15 fps (용량↓)", value=15, variable=self.fps_var).grid(row=1, column=2, sticky="w", padx=4)
        self.q_var = self._bind(tk.StringVar(value=s.quality), "quality")
        ttk.Label(g, text="압축").grid(row=2, column=0, sticky="w")
        for i, name in enumerate(QUALITY_PRESETS):
            ttk.Radiobutton(g, text=name, value=name, variable=self.q_var).grid(row=2, column=1 + i, sticky="w", padx=4)
        ttk.Label(g, text="* 글자가 읽히는 범위에서 최소 용량: '표준' 권장 (1분당 약 1~5MB)",
                  style="Hint.TLabel").grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))

        g = ttk.LabelFrame(f, text="AI 인식용 표시", padding=8)
        g.pack(fill="x")
        self.halo_var = self._bind(tk.BooleanVar(value=s.show_cursor_halo), "show_cursor_halo", bool)
        ttk.Checkbutton(g, text="마우스 포인터 항상 표시 + 노란 하이라이트", variable=self.halo_var).grid(row=0, column=0, columnspan=3, sticky="w")
        self.clk_var = self._bind(tk.BooleanVar(value=s.show_clicks), "show_clicks", bool)
        ttk.Checkbutton(g, text="클릭 표시 (왼쪽=빨강, 오른쪽=파랑, 더블/드래그/휠 구분)", variable=self.clk_var).grid(row=1, column=0, columnspan=3, sticky="w")
        ttk.Label(g, text="키 입력 표시").grid(row=2, column=0, sticky="w", pady=4)
        self.key_var = self._bind(tk.StringVar(value=s.key_overlay), "key_overlay",
                                  after=lambda: setattr(self.overlay, "key_mode", self.s.key_overlay))
        ttk.Combobox(g, textvariable=self.key_var, values=["끄기", "특수키만", "전체"], state="readonly", width=10).grid(row=2, column=1, sticky="w")
        ttk.Label(g, text="(비밀번호 입력 시 '전체'는 주의)", style="Hint.TLabel").grid(row=2, column=2, sticky="w", padx=4)
        self.log_var = self._bind(tk.BooleanVar(value=s.save_event_log), "save_event_log", bool)
        ttk.Checkbutton(g, text="클릭 좌표·프레임 번호 로그 저장 (.events.json) — AI 학습용", variable=self.log_var).grid(row=3, column=0, columnspan=3, sticky="w")
        self.cd_var = self._bind(tk.BooleanVar(value=s.countdown), "countdown", bool)
        ttk.Checkbutton(g, text="시작 전 3초 카운트다운", variable=self.cd_var).grid(row=4, column=0, columnspan=3, sticky="w")
        self.opt_var = self._bind(tk.BooleanVar(value=s.optimize_after), "optimize_after", bool)
        ttk.Checkbutton(g, text="녹화 종료 후 한 번 더 압축 (시간 걸림, 용량 약 20~30%↓)", variable=self.opt_var).grid(row=5, column=0, columnspan=3, sticky="w")

        btns = ttk.Frame(f, padding=(0, 12, 0, 0))
        btns.pack(fill="x")
        self.rec_btn = ttk.Button(btns, text="● 녹화 시작", style="Big.TButton", command=self.toggle_record)
        self.rec_btn.pack(side="left", expand=True, fill="x")
        self.pause_btn = ttk.Button(btns, text="❚❚ 일시정지", style="Big.TButton", command=self.toggle_pause, state="disabled")
        self.pause_btn.pack(side="left", expand=True, fill="x", padx=(8, 0))
        self.rec_status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.rec_status, style="Status.TLabel").pack(anchor="w", pady=(8, 0))
        self.rec_hint = ttk.Label(f, text="", style="Hint.TLabel")
        self.rec_hint.pack(anchor="w")
        self._refresh_hotkey_hints()

    # ---------------------------------------------------------------- 캡쳐 탭
    def _build_capture_tab(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="  📸 캡쳐  ")
        s = self.s

        g = ttk.LabelFrame(f, text="캡쳐 세트 (연결된 캡쳐)", padding=8)
        g.pack(fill="x")
        ttk.Label(g, text="작업 이름").grid(row=0, column=0, sticky="w")
        self.set_var = self._bind(tk.StringVar(value=s.set_name), "set_name")
        ttk.Entry(g, textvariable=self.set_var, width=30).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Label(g, text="예) 구매발주 등록", style="Hint.TLabel").grid(row=0, column=2, sticky="w")
        self.next_lbl = ttk.Label(g, text="", style="Status.TLabel")
        self.next_lbl.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        b = ttk.Frame(f, padding=(0, 8))
        b.pack(fill="x")
        self.cap_btn = ttk.Button(b, text="📸 지금 캡쳐", style="Big.TButton",
                                  command=lambda: self.request_capture(delay=0.4))
        self.cap_btn.pack(side="left", expand=True, fill="x")
        self.end_btn = ttk.Button(b, text="⏹ 세트 종료 · 번호 초기화", style="Big.TButton", command=self.end_set)
        self.end_btn.pack(side="left", expand=True, fill="x", padx=(8, 0))

        g = ttk.LabelFrame(f, text="옵션", padding=8)
        g.pack(fill="x")
        self.np_var = self._bind(tk.BooleanVar(value=s.note_popup), "note_popup", bool)
        ttk.Checkbutton(g, text="캡쳐 직후 각주 입력창 띄우기 (체크 표시 아래에 각주가 찍힘)", variable=self.np_var).pack(anchor="w")
        self.ac_var = self._bind(tk.BooleanVar(value=s.auto_click_capture), "auto_click_capture", bool)
        ttk.Checkbutton(g, text="클릭할 때마다 자동 캡쳐 (매뉴얼 자동 생성 모드)", variable=self.ac_var).pack(anchor="w")
        self.raw_var = self._bind(tk.BooleanVar(value=s.save_raw), "save_raw", bool)
        ttk.Checkbutton(g, text="표시 없는 원본도 함께 저장 (원본 폴더, AI 학습용 쌍 데이터)", variable=self.raw_var).pack(anchor="w")
        row = ttk.Frame(g)
        row.pack(anchor="w", pady=(4, 0))
        ttk.Label(row, text="이미지 형식").pack(side="left")
        self.fmt_var = self._bind(tk.StringVar(value=s.image_format), "image_format")
        ttk.Radiobutton(row, text="PNG (선명)", value="PNG", variable=self.fmt_var).pack(side="left", padx=6)
        ttk.Radiobutton(row, text="JPG (용량↓)", value="JPG", variable=self.fmt_var).pack(side="left")

        lf = ttk.LabelFrame(f, text="현재 세트의 캡쳐 (더블클릭 = 각주 수정)", padding=6)
        lf.pack(fill="both", expand=True, pady=(8, 0))
        cols = ("n", "note", "win", "xy")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings", height=7)
        for c, t, w in zip(cols, ("번호", "각주", "창 제목", "좌표"), (44, 200, 150, 80)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center" if c in ("n", "xy") else "w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit_note())
        b = ttk.Frame(lf)
        b.pack(fill="x", pady=(6, 0))
        ttk.Button(b, text="각주 수정", command=self.edit_note).pack(side="left")
        ttk.Button(b, text="마지막 캡쳐 취소", command=self.undo_capture).pack(side="left", padx=6)
        ttk.Button(b, text="가이드 보기", command=self.open_guide).pack(side="right")
        ttk.Button(b, text="세트 폴더", command=lambda: self.captures.folder and winutil.open_folder(self.captures.folder)).pack(side="right", padx=6)
        self._refresh_captures()

    # ---------------------------------------------------------------- 설정 탭
    def _build_settings_tab(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="  ⚙ 설정  ")
        s = self.s

        g = ttk.LabelFrame(f, text="단축키 (변경 클릭 → 원하는 키 조합 누르기, Esc 취소)", padding=8)
        g.pack(fill="x")
        self.hk_labels = {}
        for i, (name, label) in enumerate(HOTKEY_LABELS.items()):
            ttk.Label(g, text=label).grid(row=i, column=0, sticky="w", pady=3)
            lbl = ttk.Label(g, text=format_hotkey(s.hotkeys.get(name, "")), width=20, relief="groove", anchor="center")
            lbl.grid(row=i, column=1, padx=8)
            self.hk_labels[name] = lbl
            ttk.Button(g, text="변경", width=6, command=lambda n=name: self._change_hotkey(n)).grid(row=i, column=2)
        ttk.Button(g, text="기본값으로", command=self._reset_hotkeys).grid(row=len(HOTKEY_LABELS), column=2, pady=(6, 0))
        ttk.Label(g, text="* ERP가 '관리자 권한'으로 실행 중이면 이 프로그램도 관리자 권한으로 실행해야 단축키가 동작합니다.",
                  style="Hint.TLabel", wraplength=480).grid(row=len(HOTKEY_LABELS) + 1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        g = ttk.LabelFrame(f, text="저장 위치", padding=8)
        g.pack(fill="x", pady=8)
        self.root_lbl = ttk.Label(g, text=str(s.root_dir()), wraplength=380)
        self.root_lbl.pack(side="left", fill="x", expand=True)
        ttk.Button(g, text="기본(바탕화면)", command=lambda: self._set_root("")).pack(side="right")
        ttk.Button(g, text="변경…", command=self._choose_root).pack(side="right", padx=4)

        g = ttk.LabelFrame(f, text="표시", padding=8)
        g.pack(fill="x")
        ttk.Label(g, text="표시 크기").grid(row=0, column=0, sticky="w")
        cur = next((k for k, v in MARKER_SIZES.items() if abs(v - s.marker_scale) < 0.01), "보통")
        self.ms_var = tk.StringVar(value=cur)
        self.ms_var.trace_add("write", lambda *_: (setattr(self.s, "marker_scale", MARKER_SIZES[self.ms_var.get()]), self._save()))
        ttk.Combobox(g, textvariable=self.ms_var, values=list(MARKER_SIZES), state="readonly", width=8).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(g, text="클릭 표시 유지시간(초)").grid(row=1, column=0, sticky="w", pady=4)
        self.hold_var = tk.DoubleVar(value=s.click_hold_sec)

        def set_hold(*_):
            try:
                v = max(0.2, min(3.0, float(self.hold_var.get())))
            except Exception:
                return
            self.s.click_hold_sec = v
            self.overlay.hold_sec = v
            self._save()
        self.hold_var.trace_add("write", set_hold)
        ttk.Spinbox(g, from_=0.2, to=3.0, increment=0.1, textvariable=self.hold_var, width=6).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(g, text="15fps 에서도 놓치지 않도록 0.6초 이상 권장", style="Hint.TLabel").grid(row=1, column=2, sticky="w")
        self.ex_var = self._bind(tk.BooleanVar(value=s.exclude_self), "exclude_self", bool, after=self._apply_exclude)
        ttk.Checkbutton(g, text="이 프로그램 창은 녹화/캡쳐 화면에 찍히지 않게 (Windows 10 2004+)",
                        variable=self.ex_var).grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

        ttk.Label(f, text=f"{APP_NAME} v{APP_VERSION} — 저장 폴더: 바탕화면\\학습용캡쳐\\(녹화 | 캡쳐_날짜_작업이름)",
                  style="Hint.TLabel", wraplength=500).pack(anchor="w", pady=(12, 0))

    # ================================================================ 단축키 설정
    def _change_hotkey(self, name):
        lbl = self.hk_labels[name]
        lbl.configure(text="키 조합을 누르세요…")

        def done(combo):
            self.ui_q.put(("hotkey_set", (name, combo)))
        self.hub.record_next_hotkey(done)

    def _apply_hotkey(self, name, combo):
        if combo:
            for other, val in self.s.hotkeys.items():
                if other != name and val == combo:
                    messagebox.showwarning(APP_NAME, f"이미 '{HOTKEY_LABELS[other]}'에 사용 중인 단축키입니다.")
                    combo = None
                    break
        if combo:
            self.s.hotkeys[name] = combo
            self.hub.set_hotkeys(self.s.hotkeys)
            self._save()
        self.hk_labels[name].configure(text=format_hotkey(self.s.hotkeys.get(name, "")))
        self._refresh_hotkey_hints()

    def _reset_hotkeys(self):
        self.s.hotkeys = default_hotkeys()
        self.hub.set_hotkeys(self.s.hotkeys)
        self._save()
        for n, l in self.hk_labels.items():
            l.configure(text=format_hotkey(self.s.hotkeys[n]))
        self._refresh_hotkey_hints()

    def _refresh_hotkey_hints(self):
        hk = self.s.hotkeys
        if hasattr(self, "rec_hint"):
            self.rec_hint.configure(text=f"단축키: 녹화 {format_hotkey(hk['record'])}  ·  일시정지 {format_hotkey(hk['pause'])}")
        if hasattr(self, "next_lbl"):
            self._refresh_captures()

    # ================================================================ 저장 위치
    def _choose_root(self):
        d = filedialog.askdirectory(title="저장 폴더 선택")
        if d:
            self._set_root(d)

    def _set_root(self, path):
        self.s.save_root = path
        self._save()
        self.root_lbl.configure(text=str(self.s.root_dir()))

    # ================================================================ 녹화
    def _set_monitor(self, idx):
        self.s.monitor_index = idx
        self._save()

    def _update_region_label(self):
        r = self.s.region
        self.region_lbl.configure(text=(f"지정 영역: ({r[0]}, {r[1]}) 크기 {r[2]}x{r[3]}" if r else "선택한 모니터 전체를 녹화합니다."))

    def _clear_region(self):
        self.s.region = None
        self._save()
        self._update_region_label()

    def _select_region(self):
        RegionSelector(self, self.monitors[0], self._region_selected)

    def _region_selected(self, rect):
        if rect:
            self.s.region = list(rect)
            self._save()
        self._update_region_label()

    def _record_rect(self) -> dict:
        if self.s.region:
            l, t, w, h = self.s.region
            return {"left": l, "top": t, "width": w, "height": h}
        idx = min(max(self.s.monitor_index, 1), len(self.monitors) - 1)
        m = self.monitors[idx]
        return {k: m[k] for k in ("left", "top", "width", "height")}

    def toggle_record(self):
        if self.recorder:
            self.stop_record()
        elif not getattr(self, "_counting", False):
            if self.s.countdown:
                self._counting = True
                Countdown(self, 3, self.start_record)
            else:
                self.start_record()

    def start_record(self):
        self._counting = False
        out_dir = self.s.root_dir() / "녹화"
        out_dir.mkdir(parents=True, exist_ok=True)
        res = "1080p" if "1080" in self.s.resolution else "720p"
        name = f"녹화_{datetime.now():%Y%m%d_%H%M%S}_{res}_{self.s.fps}fps.mp4"
        self.overlay.hold_sec = self.s.click_hold_sec
        self.overlay.key_mode = self.s.key_overlay
        self.recorder = Recorder(out_dir / name, self._record_rect(), RESOLUTIONS[self.s.resolution],
                                 self.s.fps, QUALITY_PRESETS[self.s.quality], self.overlay, self.s)
        self.recorder.start()
        self.rec_btn.configure(text="■ 녹화 정지")
        self.pause_btn.configure(state="normal", text="❚❚ 일시정지")
        self.status.set(f"녹화 중 → {name}")
        self.minibar = MiniBar(self)
        winutil.exclude_from_capture(self.minibar, self.s.exclude_self)

    def stop_record(self):
        rec, self.recorder = self.recorder, None
        if not rec:
            return
        rec.stop()
        self.rec_btn.configure(text="저장 중…", state="disabled")
        self.pause_btn.configure(state="disabled")
        if self.minibar:
            self.minibar.destroy()
            self.minibar = None

        def wait():
            rec.join()
            self.ui_q.put(("rec_done", rec))
        threading.Thread(target=wait, daemon=True).start()

    def _rec_done(self, rec: Recorder):
        self.rec_btn.configure(text="● 녹화 시작", state="normal")
        self.pause_btn.configure(text="❚❚ 일시정지")
        if rec.error:
            self.rec_status.set("녹화 실패")
            messagebox.showerror(APP_NAME, f"녹화 중 오류가 발생했습니다.\n{rec.error}")
            return
        size = rec.out_path.stat().st_size / 1024 / 1024 if rec.out_path.exists() else 0
        dur = rec.frames / rec.fps
        self.rec_status.set(f"저장 완료: {rec.out_path.name}  ({dur:.0f}초, {size:.1f}MB, {rec.ow}x{rec.oh})")
        self.status.set(f"저장: {rec.out_path.parent}")

    def toggle_pause(self):
        if not self.recorder:
            return
        p = self.recorder.toggle_pause()
        self.pause_btn.configure(text="▶ 재개" if p else "❚❚ 일시정지")

    # ================================================================ 캡쳐
    def request_capture(self, delay=0.0, button="left", source="hotkey", cursor=None):
        self.cap_q.put((delay, button, source, cursor))

    def _capture_worker(self):
        sct = winutil.new_mss()
        while True:
            delay, button, source, cursor = self.cap_q.get()
            if delay:
                time.sleep(delay)
            try:
                cur = cursor or winutil.get_cursor_pos()
                if cur is None:
                    try:
                        from pynput.mouse import Controller
                        cur = tuple(int(v) for v in Controller().position)
                    except Exception:
                        cur = None
                g = grab_under_cursor(sct, cur, button, source)
                self.ui_q.put(("grabbed", g))
            except Exception as ex:  # noqa: BLE001
                self.ui_q.put(("error", f"캡쳐 실패: {ex}"))

    def _on_grabbed(self, g):
        if self.note_popup:  # 이전 각주창이 열려 있으면 입력한 내용으로 저장하고 닫기
            self.note_popup.commit()
        try:
            st = self.captures.add(g, "")
        except Exception as ex:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"캡쳐 저장 실패\n{ex}")
            return
        self._refresh_captures()
        self.status.set(f"{st.step}번 캡쳐 저장 → {self.captures.folder.name}\\{st.file}")
        if self.s.note_popup and g.source == "hotkey":
            self.note_popup = NotePopup(self, st.step, g)

    def _note_done(self, step: int, note: str | None, prev_hwnd: int):
        self.note_popup = None
        if note:
            self.captures.update_note(step, note)
            self._refresh_captures()
        if prev_hwnd:
            winutil.set_foreground(prev_hwnd)

    def end_set(self):
        if self.note_popup:
            self.note_popup.commit()
        n = len(self.captures.steps)
        folder = self.captures.end_set()
        self._refresh_captures()
        self.status.set(f"세트 종료 ({n}장) → 다음 캡쳐는 1번부터" + (f" · {folder.name}" if folder else ""))

    def edit_note(self):
        sel = self.tree.selection()
        if not sel:
            return
        n = int(self.tree.item(sel[0], "values")[0])
        st = next(s for s in self.captures.steps if s.step == n)
        note = simpledialog.askstring(APP_NAME, f"{n}번 캡쳐 각주", initialvalue=st.note, parent=self)
        if note is not None:
            if not self.captures.update_note(n, note):
                messagebox.showwarning(APP_NAME, "원본 이미지가 없어 각주를 다시 그릴 수 없습니다.")
            self._refresh_captures()

    def undo_capture(self):
        st = self.captures.undo_last()
        if st:
            self.status.set(f"{st.step}번 캡쳐를 삭제했습니다.")
        self._refresh_captures()

    def open_guide(self):
        if self.captures.folder:
            winutil.open_folder(self.captures.folder / "가이드.html")

    def _refresh_captures(self):
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        for st in self.captures.steps:
            self.tree.insert("", "end", values=(st.step, wrap_preview(st.note or "-", 34),
                                                wrap_preview(st.window or "-", 24), f"{st.x},{st.y}"))
        hk = self.s.hotkeys
        state = f"진행 중: {self.captures.folder.name}" if self.captures.active else "새 세트 대기"
        self.next_lbl.configure(text=f"다음 캡쳐 번호: {self.captures.next_number}번   ({state})\n"
                                     f"단축키: 캡쳐 {format_hotkey(hk['capture'])}  ·  세트 종료 {format_hotkey(hk['end_set'])}")

    # ================================================================ 후킹 콜백 (리스너 스레드)
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

    # ================================================================ 루프
    def _poll(self):
        try:
            while True:
                kind, arg = self.ui_q.get_nowait()
                if kind == "hotkey":
                    self._handle_hotkey(arg)
                elif kind == "hotkey_set":
                    self._apply_hotkey(*arg)
                elif kind == "grabbed":
                    self._on_grabbed(arg)
                elif kind == "rec_done":
                    self._rec_done(arg)
                elif kind == "error":
                    self.status.set(arg)
        except queue.Empty:
            pass
        self.after(30, self._poll)

    def _handle_hotkey(self, name):
        if name == "capture":
            self.request_capture()
        elif name == "end_set":
            self.end_set()
        elif name == "record":
            self.toggle_record()
        elif name == "pause":
            self.toggle_pause()

    def _tick(self):
        rec = self.recorder
        if rec and rec.start_t:
            t = rec.video_time()
            size = rec.out_path.stat().st_size / 1024 / 1024 if rec.out_path.exists() else 0
            txt = f"{'⏸ 일시정지' if rec.paused else '● REC'}  {int(t // 60):02d}:{int(t % 60):02d}   " \
                  f"{rec.ow}x{rec.oh} {rec.fps}fps   {size:.1f}MB   클릭 {sum(1 for e in rec.events if e['type'] == 'mouse_down')}회"
            self.rec_status.set(txt)
            if self.minibar:
                self.minibar.set(txt.split("   ")[0])
            if rec.error or not rec.is_alive():
                self.stop_record()
        self.after(500, self._tick)

    def _on_close(self):
        if self.recorder:
            if not messagebox.askyesno(APP_NAME, "녹화 중입니다. 정지하고 종료할까요?"):
                return
            rec = self.recorder
            rec.stop()
            rec.join(timeout=30)
        if self.captures.active:
            self.captures.end_set()
        self.hub.stop()
        self.destroy()


# ==================================================================== 보조 창
class NotePopup(tk.Toplevel):
    """캡쳐 직후 마우스 근처에 뜨는 각주 입력창. Enter=저장, Shift+Enter=줄바꿈, Esc=건너뛰기."""

    def __init__(self, app: App, step: int, g):
        super().__init__(app)
        self.app, self.step, self.prev = app, step, g.prev_hwnd
        self._done = False
        self.title(f"{step}번 각주")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"✔ {step}번 캡쳐 저장됨 — 체크 아래에 넣을 각주 (선택)", style="Status.TLabel").pack(anchor="w")
        self.txt = tk.Text(frm, width=40, height=3, wrap="word", font=("Malgun Gothic" if winutil.IS_WIN else "NanumGothic", 11))
        self.txt.pack(fill="x", pady=6)
        b = ttk.Frame(frm)
        b.pack(fill="x")
        ttk.Label(b, text="Enter 저장 · Shift+Enter 줄바꿈 · Esc 건너뛰기", style="Hint.TLabel").pack(side="left")
        ttk.Button(b, text="건너뛰기", command=self.skip).pack(side="right")
        ttk.Button(b, text="저장", command=self.commit).pack(side="right", padx=4)
        self.txt.bind("<Return>", lambda e: (self.commit(), "break")[1])
        self.txt.bind("<Shift-Return>", lambda e: None)
        self.bind("<Escape>", lambda e: self.skip())
        self.protocol("WM_DELETE_WINDOW", self.skip)
        self.update_idletasks()
        sx, sy = g.screen_x + 40, g.screen_y + 40
        mon = g.monitor
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        sx = min(sx, mon["left"] + mon["width"] - w - 10)
        sy = min(sy, mon["top"] + mon["height"] - h - 60)
        self.geometry(f"+{sx}+{sy}")
        winutil.exclude_from_capture(self, app.s.exclude_self)
        self.after(30, self._focus)

    def _focus(self):
        self.lift()
        try:
            hwnd = winutil.user32.GetParent(self.winfo_id()) if winutil.IS_WIN else 0
            winutil.set_foreground(hwnd)
        except Exception:
            pass
        self.txt.focus_force()

    def commit(self):
        if self._done:
            return
        self._done = True
        note = self.txt.get("1.0", "end").strip()
        self.destroy()
        self.app._note_done(self.step, note, self.prev)

    def skip(self):
        if self._done:
            return
        self._done = True
        self.destroy()
        self.app._note_done(self.step, None, self.prev)


class Countdown(tk.Toplevel):
    def __init__(self, app: App, n: int, then):
        super().__init__(app)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.85)
        except Exception:
            pass
        self.configure(bg="#c00")
        self.lbl = tk.Label(self, text="", fg="white", bg="#c00", font=("Arial", 64, "bold"), width=3)
        self.lbl.pack(padx=20, pady=10)
        self.update_idletasks()
        m = app._record_rect()
        x = m["left"] + m["width"] // 2 - self.winfo_reqwidth() // 2
        y = m["top"] + m["height"] // 2 - self.winfo_reqheight() // 2
        self.geometry(f"+{x}+{y}")
        winutil.exclude_from_capture(self, True)
        self.n, self.then = n, then
        self._step()

    def _step(self):
        if self.n <= 0:
            app = self.master
            self.destroy()
            app.after(150, self.then)  # 카운트다운 창이 완전히 사라진 뒤 녹화 시작
            return
        self.lbl.configure(text=str(self.n))
        self.n -= 1
        self.after(1000, self._step)


class MiniBar(tk.Toplevel):
    """녹화 중 화면 위쪽에 뜨는 작은 상태바 (녹화 영상에는 찍히지 않음)."""

    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#222")
        self.var = tk.StringVar(value="● REC")
        tk.Label(self, textvariable=self.var, fg="#ff4040", bg="#222", font=("Arial", 10, "bold")).pack(side="left", padx=8)
        for txt, cmd in (("❚❚", app.toggle_pause), ("■", app.stop_record)):
            tk.Button(self, text=txt, command=cmd, bg="#333", fg="white", relief="flat", bd=0, padx=8,
                      activebackground="#555").pack(side="left", padx=2, pady=2)
        self.update_idletasks()
        m = app.monitors[min(max(app.s.monitor_index, 1), len(app.monitors) - 1)]
        self.geometry(f"+{m['left'] + m['width'] // 2 - 90}+{m['top'] + 4}")
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<B1-Motion>", self._move)

    def set(self, text):
        self.var.set(text)

    def _start_move(self, e):
        self._dx, self._dy = e.x, e.y

    def _move(self, e):
        self.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")


class RegionSelector(tk.Toplevel):
    """반투명 전체화면 위에서 드래그하여 녹화 영역 지정."""

    def __init__(self, app: App, virt: dict, cb):
        super().__init__(app)
        self.cb = cb
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.3)
        except Exception:
            pass
        self.geometry(f"{virt['width']}x{virt['height']}+{virt['left']}+{virt['top']}")
        self.c = tk.Canvas(self, bg="black", highlightthickness=0, cursor="cross")
        self.c.pack(fill="both", expand=True)
        self.c.create_text(virt["width"] // 2, 60, text="드래그해서 녹화 영역을 지정하세요 (Esc 취소)",
                           fill="white", font=("Malgun Gothic", 20, "bold"))
        self.origin = (virt["left"], virt["top"])
        self.start = None
        self.rect = None
        self.c.bind("<ButtonPress-1>", self._press)
        self.c.bind("<B1-Motion>", self._drag)
        self.c.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda e: self._finish(None))
        self.focus_force()

    def _press(self, e):
        self.start = (e.x, e.y)
        self.rect = self.c.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=3, fill="white")

    def _drag(self, e):
        if self.rect:
            self.c.coords(self.rect, *self.start, e.x, e.y)

    def _release(self, e):
        if not self.start:
            return
        x0, y0 = min(self.start[0], e.x), min(self.start[1], e.y)
        w, h = abs(e.x - self.start[0]), abs(e.y - self.start[1])
        if w < 64 or h < 64:
            self._finish(None)
            return
        w, h = w // 2 * 2, h // 2 * 2
        self._finish((x0 + self.origin[0], y0 + self.origin[1], w, h))

    def _finish(self, rect):
        self.destroy()
        self.cb(rect)


def _install_error_log():
    """창 모드 exe 에서는 콘솔이 없으므로 오류를 파일로 남긴다."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    def write_log(text):
        try:
            base = Path(os.environ.get("APPDATA") or Path.home()) / "LearningRecorder"
            base.mkdir(parents=True, exist_ok=True)
            with open(base / "error.log", "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}\n")
        except Exception:
            pass
    return write_log


def main():
    write_log = _install_error_log()
    if "--selftest" in sys.argv:
        import selftest
        sys.exit(selftest.run(sys.argv))
    app = App()

    def report(exc, val, tb):
        import traceback
        text = "".join(traceback.format_exception(exc, val, tb))
        write_log(text)
        messagebox.showerror(APP_NAME, f"오류가 발생했습니다 (error.log 에 기록됨)\n{val}")
    app.report_callback_exception = report
    app.mainloop()


if __name__ == "__main__":
    main()
