"""Windows 전용 유틸리티 (DPI, 커서 위치, 활성 창 제목, 캡처 제외, 바탕화면 경로 등).

Windows 가 아닌 환경에서도 import 는 되도록 모든 호출을 방어적으로 감싼다
(리눅스에서 렌더링/인코딩 로직을 테스트하기 위함).
"""
from __future__ import annotations

import os
import sys
import ctypes
from pathlib import Path

IS_WIN = sys.platform == "win32"

if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    kernel32 = ctypes.windll.kernel32


def set_dpi_aware() -> None:
    """고해상도(125%, 150% 배율) 모니터에서 좌표가 어긋나지 않도록 Per-Monitor DPI 인식."""
    if not IS_WIN:
        return
    try:
        # PER_MONITOR_AWARE_V2
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def get_cursor_pos() -> tuple[int, int] | None:
    if not IS_WIN:
        return None
    pt = wintypes.POINT()
    if user32.GetCursorPos(ctypes.byref(pt)):
        return pt.x, pt.y
    return None


def get_foreground_window() -> int:
    if not IS_WIN:
        return 0
    return int(user32.GetForegroundWindow() or 0)


def get_window_title(hwnd: int | None = None) -> str:
    if not IS_WIN:
        return ""
    try:
        hwnd = hwnd or user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def get_window_process_name(hwnd: int | None = None) -> str:
    """활성 창의 실행 파일 이름 (예: erp.exe) — AI 가 어떤 프로그램 화면인지 알 수 있게."""
    if not IS_WIN:
        return ""
    try:
        hwnd = hwnd or user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        pass
    return ""


def set_foreground(hwnd: int) -> None:
    """다른 프로그램(ERP)으로 포커스를 돌려주거나, 각주 입력창을 앞으로 가져온다."""
    if not IS_WIN or not hwnd:
        return
    try:
        VK_MENU, KEYUP = 0x12, 0x0002
        # Windows 포그라운드 잠금 우회: ALT 를 한 번 눌렀다 떼면 SetForegroundWindow 가 허용된다.
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(VK_MENU, 0, KEYUP, 0)
    except Exception:
        pass


def exclude_from_capture(tk_widget, enable: bool = True) -> bool:
    """이 프로그램의 창이 녹화/캡처 화면에 찍히지 않도록 한다 (Windows 10 2004 이상).

    WDA_EXCLUDEFROMCAPTURE = 0x11
    """
    if not IS_WIN:
        return False
    try:
        tk_widget.update_idletasks()
        hwnd = user32.GetParent(tk_widget.winfo_id()) or tk_widget.winfo_id()
        return bool(user32.SetWindowDisplayAffinity(hwnd, 0x11 if enable else 0x0))
    except Exception:
        return False


def desktop_dir() -> Path:
    """실제 바탕화면 경로 (OneDrive 로 리디렉션된 '바탕 화면' 포함)."""
    if IS_WIN:
        try:
            # FOLDERID_Desktop {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

            fid = GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                       (wintypes.BYTE * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41))
            p = ctypes.c_wchar_p()
            if shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(p)) == 0:
                path = Path(p.value)
                ole32.CoTaskMemFree(p)
                return path
        except Exception:
            pass
    home = Path.home()
    for name in ("Desktop", "바탕 화면", "바탕화면"):
        if (home / name).is_dir():
            return home / name
    return home / "Desktop"


def open_folder(path: Path) -> None:
    try:
        if IS_WIN:
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def asset_path(*parts: str) -> Path:
    """번들 리소스 경로 (PyInstaller 실행 파일 / 소스 실행 모두)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath("assets", *parts)


def font_path(bold: bool = False) -> str | None:
    """한글 표시용 폰트 경로 (번들 Pretendard → 맑은 고딕 순)."""
    bundled = asset_path("fonts", "Pretendard-Bold.otf" if bold else "Pretendard-Medium.otf")
    if bundled.exists():
        return str(bundled)
    candidates = []
    if IS_WIN:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        candidates += [os.path.join(windir, "Fonts", "malgunbd.ttf" if bold else "malgun.ttf"),
                       os.path.join(windir, "Fonts", "malgun.ttf"),
                       os.path.join(windir, "Fonts", "gulim.ttc")]
    candidates += [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf" if bold else
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def no_window_flags() -> int:
    """ffmpeg 실행 시 검은 콘솔창이 뜨지 않도록."""
    return 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW


def is_own_window_at(x: int, y: int) -> bool:
    """(x, y) 위치의 창이 이 프로그램 창인지 (자동 클릭 캡쳐에서 자기 버튼 클릭은 제외)."""
    if not IS_WIN:
        return False
    try:
        hwnd = user32.WindowFromPoint(wintypes.POINT(x, y))
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()
    except Exception:
        return False


def new_mss():
    """mss 인스턴스 생성 (버전별 API 차이 흡수)."""
    import mss
    cls = getattr(mss, "MSS", None) or mss.mss
    return cls()
