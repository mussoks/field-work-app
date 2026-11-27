"""설정 저장/불러오기 (%APPDATA%\\LearningRecorder\\settings.json)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

from winutil import desktop_dir

APP_NAME = "학습용 화면녹화·캡쳐"
APP_VERSION = "0.2.0"
SAVE_FOLDER_NAME = "학습용캡쳐"

# 화질(=용량) 프리셋: x264 CRF. 숫자가 클수록 용량이 작다.
QUALITY_PRESETS = {
    "저용량": 32,
    "표준": 28,
    "선명": 23,
}

RESOLUTIONS = {
    "FHD (1920x1080)": (1920, 1080),
    "HD (1280x720)": (1280, 720),
}


def default_hotkeys() -> dict[str, str]:
    return {
        "capture": "ctrl+shift+1",      # 캡쳐 (마우스 위치에 클릭 표시)
        "end_set": "ctrl+shift+2",      # 연결된 캡쳐 세트 종료 → 번호 1번으로 초기화
        "record": "ctrl+shift+r",       # 녹화 시작/정지
        "pause": "ctrl+shift+p",        # 녹화 일시정지/재개
        "undo": "ctrl+shift+z",         # 마지막 캡쳐 취소
    }


HOTKEY_LABELS = {
    "capture": "캡쳐",
    "end_set": "캡쳐 세트 종료 (번호 초기화)",
    "record": "녹화 시작 / 정지",
    "pause": "녹화 일시정지 / 재개",
    "undo": "마지막 캡쳐 취소",
}


@dataclass
class Settings:
    save_root: str = ""
    # 녹화
    resolution: str = "FHD (1920x1080)"
    fps: int = 30
    quality: str = "표준"
    monitor_index: int = 1            # mss 모니터 번호 (1 = 주 모니터)
    region: list | None = None        # [left, top, width, height] 영역 녹화
    show_cursor_halo: bool = True     # 포인터 주변 노란 원(항상 보이게)
    show_clicks: bool = True          # 클릭 표시 (좌: 빨강, 우: 파랑)
    click_hold_sec: float = 0.8       # 클릭 표시 유지시간 → 15fps 에서도 12프레임 이상 보임
    key_overlay: str = "특수키만"      # 끄기 / 특수키만 / 전체
    save_event_log: bool = True       # 클릭/키 입력 타임라인(JSON) 저장
    countdown: bool = True            # 녹화 시작 전 3초 카운트다운
    optimize_after: bool = False      # 녹화 후 한 번 더 압축(느리지만 용량↓)
    marker_scale: float = 1.0         # 표시 크기 배율
    save_click_frames: bool = True    # 클릭 직전 원본 프레임 + 표시 프레임 저장 (데이터셋)
    uia_enabled: bool = True          # 클릭한 UI 요소(버튼 이름 등) 기록
    mask_enabled: bool = False        # 개인정보 가리기
    mask_regions: list = field(default_factory=list)  # [[l, t, w, h], ...] 화면 좌표
    # 캡쳐
    set_name: str = ""
    note_popup: bool = True           # 캡쳐 직후 각주 입력창
    auto_click_capture: bool = False  # 클릭할 때마다 자동 캡쳐
    save_raw: bool = True             # 표시 없는 원본도 함께 저장 (AI 학습용 쌍 데이터)
    image_format: str = "PNG"
    auto_note: bool = True            # 각주를 비워두면 UI 요소로 추천 각주 자동 입력
    recent_notes: list = field(default_factory=list)
    recent_set_names: list = field(default_factory=list)
    # 공통
    exclude_self: bool = True         # 이 프로그램 창은 녹화/캡쳐에 안 찍히게
    minimize_to_tray: bool = True     # 창을 닫으면 트레이로 (단축키는 계속 동작)
    notify: bool = True               # 캡쳐/녹화 알림
    onboarded: bool = False
    hotkeys: dict = field(default_factory=default_hotkeys)

    def root_dir(self) -> Path:
        p = Path(self.save_root) if self.save_root else desktop_dir() / SAVE_FOLDER_NAME
        p.mkdir(parents=True, exist_ok=True)
        return p


def _config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / "LearningRecorder"
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"


def load_settings() -> Settings:
    s = Settings()
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
        for k, v in data.items():
            if hasattr(s, k):
                setattr(s, k, v)
        hk = default_hotkeys()
        hk.update(s.hotkeys or {})
        s.hotkeys = hk
    except Exception:
        pass
    return s


def save_settings(s: Settings) -> None:
    try:
        _config_path().write_text(json.dumps(asdict(s), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
