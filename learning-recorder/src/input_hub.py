"""전역 마우스/키보드 후킹 + 사용자 지정 단축키 처리.

pynput 리스너 스레드에서 들어온 이벤트를 구독자에게 전달한다.
(후킹 콜백은 Windows 제한시간 때문에 빠르게 리턴해야 하므로 무거운 일은 하지 않는다.)
"""
from __future__ import annotations

import threading
import time
from typing import Callable

MODIFIERS = ("ctrl", "shift", "alt", "win")

SPECIAL_KEYS = {
    "enter", "tab", "esc", "backspace", "delete", "insert", "home", "end",
    "page_up", "page_down", "up", "down", "left", "right", "space",
    "print_screen", "한/영", "한자",
} | {f"f{i}" for i in range(1, 25)}

KEY_DISPLAY = {
    "ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "win": "Win",
    "enter": "Enter", "tab": "Tab", "esc": "Esc", "backspace": "Backspace",
    "delete": "Del", "insert": "Ins", "home": "Home", "end": "End",
    "page_up": "PgUp", "page_down": "PgDn", "up": "Up", "down": "Down",
    "left": "Left", "right": "Right", "space": "Space", "print_screen": "PrtSc",
    "한/영": "Han/Eng", "한자": "Hanja",
}


# Shift 와 함께 눌렸을 때의 기호 → 원래 키 (Windows 는 가상키코드를 쓰므로 비-Windows 용 보정)
SHIFTED = dict(zip('!@#$%^&*()_+{}|:"<>?~', "1234567890-=[]\\;',./`"))


def display_key(name: str) -> str:
    if name in KEY_DISPLAY:
        return KEY_DISPLAY[name]
    if name.startswith("f") and name[1:].isdigit():
        return name.upper()
    return name.upper() if len(name) == 1 else name


def parse_hotkey(text: str) -> tuple[frozenset, str] | None:
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if not parts:
        return None
    mods = frozenset(p for p in parts if p in MODIFIERS)
    keys = [p for p in parts if p not in MODIFIERS]
    if len(keys) != 1:
        return None
    return mods, keys[0]


def format_hotkey(text: str) -> str:
    parsed = parse_hotkey(text)
    if not parsed:
        return "(없음)"
    mods, key = parsed
    order = [m for m in MODIFIERS if m in mods]
    return " + ".join([display_key(m) for m in order] + [display_key(key)])


def normalize_key(key) -> str | None:
    """pynput Key/KeyCode → 'ctrl', 'f9', 'a', '1' 같은 정규화된 이름."""
    from pynput.keyboard import Key, KeyCode  # 지연 import (디스플레이 없는 환경 대비)

    if isinstance(key, Key):
        n = key.name
        if n.startswith("ctrl"):
            return "ctrl"
        if n.startswith("shift"):
            return "shift"
        if n.startswith("alt"):
            return "alt"
        if n.startswith("cmd"):
            return "win"
        return n
    if isinstance(key, KeyCode):
        vk = getattr(key, "vk", None)
        import sys
        if sys.platform == "win32" and vk is not None:
            if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
                return chr(vk).lower()
            if 0x60 <= vk <= 0x69:
                return f"num{vk - 0x60}"
            if 0x70 <= vk <= 0x87:
                return f"f{vk - 0x6F}"
            if vk == 0x15:
                return "한/영"
            if vk == 0x19:
                return "한자"
        ch = getattr(key, "char", None)
        if ch and ch.isprintable():
            return SHIFTED.get(ch, ch.lower())
        if vk is not None:
            return f"vk{vk}"
    return None


class InputHub:
    def __init__(self) -> None:
        self.hotkeys: dict[str, tuple[frozenset, str]] = {}
        self.on_hotkey: Callable[[str], None] = lambda name: None
        self.on_key: list[Callable[[dict], None]] = []
        self.on_mouse: list[Callable[[dict], None]] = []
        self._pressed: set[str] = set()
        self._lock = threading.Lock()
        self._record_cb: Callable[[str | None], None] | None = None
        self._last_left = (0.0, 0, 0)
        self._kb = None
        self._ms = None
        self.enabled = True

    # ---------- 설정 ----------
    def set_hotkeys(self, mapping: dict[str, str]) -> None:
        hk = {}
        for name, text in mapping.items():
            p = parse_hotkey(text)
            if p:
                hk[name] = p
        self.hotkeys = hk

    def record_next_hotkey(self, cb: Callable[[str | None], None]) -> None:
        """다음에 누르는 키 조합을 단축키로 기록 (Esc = 취소)."""
        self._record_cb = cb

    # ---------- 시작/종료 ----------
    def start(self) -> None:
        from pynput import keyboard, mouse

        self._kb = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._ms = mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll)
        self._kb.daemon = True
        self._ms.daemon = True
        self._kb.start()
        self._ms.start()

    def stop(self) -> None:
        for l in (self._kb, self._ms):
            try:
                if l:
                    l.stop()
            except Exception:
                pass

    # ---------- 키보드 ----------
    def _mods(self) -> frozenset:
        return frozenset(m for m in MODIFIERS if m in self._pressed)

    def _on_press(self, key, injected=False):
        if injected:  # 프로그램이 스스로 보낸 키(포커스 전환용 ALT 등)는 무시
            return
        name = normalize_key(key)
        if not name:
            return
        with self._lock:
            repeat = name in self._pressed
            self._pressed.add(name)
            mods = self._mods()
        if name in MODIFIERS or repeat:
            return

        if self._record_cb is not None:
            cb, self._record_cb = self._record_cb, None
            if name == "esc" and not mods:
                cb(None)
            else:
                order = [m for m in MODIFIERS if m in mods]
                cb("+".join(order + [name]))
            return

        for hk_name, (hk_mods, hk_key) in self.hotkeys.items():
            if hk_key == name and hk_mods == mods:
                if self.enabled:
                    try:
                        self.on_hotkey(hk_name)
                    except Exception:
                        pass
                return  # 단축키는 키 입력 표시/로그에 넣지 않음

        evt = {
            "type": "key",
            "t": time.perf_counter(),
            "key": name,
            "mods": sorted(mods, key=MODIFIERS.index),
            "special": bool(mods - {"shift"}) or name in SPECIAL_KEYS,
            "label": " + ".join([display_key(m) for m in MODIFIERS if m in mods] + [display_key(name)]),
        }
        for cb in list(self.on_key):
            try:
                cb(evt)
            except Exception:
                pass

    def _on_release(self, key, injected=False):
        if injected:
            return
        name = normalize_key(key)
        with self._lock:
            self._pressed.discard(name)
            if name in MODIFIERS:
                # Windows 에서 좌/우 키가 섞여 해제 이벤트가 누락되는 경우 대비
                pass

    # ---------- 마우스 ----------
    def _on_click(self, x, y, button, pressed, injected=False):
        if injected:
            return
        bname = getattr(button, "name", str(button))
        now = time.perf_counter()
        double = False
        if pressed and bname == "left":
            lt, lx, ly = self._last_left
            double = (now - lt) < 0.45 and abs(x - lx) < 8 and abs(y - ly) < 8
            self._last_left = (0.0 if double else now, x, y)
        evt = {"type": "mouse_down" if pressed else "mouse_up", "t": now,
               "x": int(x), "y": int(y), "button": bname, "double": double}
        for cb in list(self.on_mouse):
            try:
                cb(evt)
            except Exception:
                pass

    def _on_scroll(self, x, y, dx, dy, injected=False):
        if injected:
            return
        evt = {"type": "scroll", "t": time.perf_counter(), "x": int(x), "y": int(y),
               "dy": int(dy), "button": ""}
        for cb in list(self.on_mouse):
            try:
                cb(evt)
            except Exception:
                pass
