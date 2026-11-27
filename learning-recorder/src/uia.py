"""클릭 지점의 UI 요소 정보 (Windows UI Automation).

ERP 화면에서 '어떤 버튼/입력칸을 눌렀는지'를 이름·종류·AutomationId 로 기록한다.
  예) {"name": "저장", "type": "ButtonControl", "type_ko": "버튼", "automation_id": "btnSave", ...}
→ AI 가 좌표뿐 아니라 '의미'까지 학습할 수 있고, 각주 자동 추천에도 쓴다.

자체 그리기 방식의 일부 ERP(UIA 미지원)는 정보가 비어 있을 수 있다 — 그래도 동작에는 지장 없음.
COM 은 스레드마다 초기화가 필요하므로 전용 작업 스레드 하나에서만 UIA 를 호출한다.
"""
from __future__ import annotations

import queue
import threading

import winutil

TYPE_KO = {
    "ButtonControl": "버튼", "SplitButtonControl": "버튼", "EditControl": "입력칸",
    "ComboBoxControl": "선택 상자", "CheckBoxControl": "체크박스", "RadioButtonControl": "선택 버튼",
    "MenuItemControl": "메뉴", "MenuBarControl": "메뉴", "TabItemControl": "탭", "ListItemControl": "목록 항목",
    "TreeItemControl": "트리 항목", "HyperlinkControl": "링크", "DataItemControl": "표 칸",
    "HeaderItemControl": "표 머리글", "TextControl": "글자", "DocumentControl": "문서",
    "ImageControl": "그림", "ToolBarControl": "도구 모음", "CustomControl": "항목",
    "PaneControl": "영역", "WindowControl": "창", "GroupControl": "그룹", "TableControl": "표",
    "DataGridControl": "표", "SpinnerControl": "숫자 상자", "SliderControl": "슬라이더",
}
_GENERIC = {"PaneControl", "WindowControl", "GroupControl", "CustomControl"}
_PLAIN = _GENERIC | {"TextControl", "ImageControl", "DocumentControl"}


class _Worker:
    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.ok = False
        self._t = threading.Thread(target=self._run, daemon=True, name="uia")
        self._t.start()

    def _run(self):
        try:
            import uiautomation as auto  # type: ignore
            init = auto.UIAutomationInitializerInThread()
            auto.SetGlobalSearchTimeout(0.5)
            self.ok = True
        except Exception:
            auto, init = None, None
        while True:
            x, y, box = self.q.get()
            info = None
            if auto is not None:
                try:
                    info = _describe(auto, x, y)
                except Exception:
                    info = None
            box["result"] = info
            box["event"].set()
        _ = init


def _describe(auto, x, y) -> dict | None:
    c = auto.ControlFromPoint(x, y)
    if c is None:
        return None
    r = c.BoundingRectangle
    ctype = c.ControlTypeName
    info = {
        "name": (c.Name or "").strip()[:120],
        "type": ctype,
        "type_ko": TYPE_KO.get(ctype, ""),
        "automation_id": (c.AutomationId or "")[:80],
        "class_name": (c.ClassName or "")[:80],
        "rect": [r.left, r.top, r.right - r.left, r.bottom - r.top],
    }
    # 이름 없는 칸(입력칸 등)은 주변(부모/형제 라벨) 이름을 참고로 찾는다
    parents = []
    p = c
    for _ in range(4):
        try:
            p = p.GetParentControl()
        except Exception:
            p = None
        if not p:
            break
        nm = (p.Name or "").strip()
        parents.append(f"{p.ControlTypeName}:{nm[:40]}")
        if not info["name"] and nm and p.ControlTypeName not in ("WindowControl", "PaneControl"):
            info["context_name"] = nm[:80]
    info["parents"] = parents
    if not info["name"]:
        try:
            prev = c.GetPreviousSiblingControl()
            if prev and prev.ControlTypeName == "TextControl" and prev.Name:
                info["label"] = prev.Name.strip()[:80]
        except Exception:
            pass
    return info


_worker: _Worker | None = None
_lock = threading.Lock()


def available() -> bool:
    return winutil.IS_WIN


def element_at(x: int, y: int, timeout: float = 0.6) -> dict | None:
    """(x, y) 화면 좌표의 UI 요소 정보. 실패/미지원 시 None."""
    global _worker
    if not winutil.IS_WIN:
        return None
    with _lock:
        if _worker is None:
            _worker = _Worker()
    box = {"event": threading.Event(), "result": None}
    _worker.q.put((int(x), int(y), box))
    box["event"].wait(timeout)
    return box["result"]


def element_async(x: int, y: int, target: dict, key: str = "element") -> None:
    """후킹 콜백에서 쓰는 비동기 버전: 결과가 나오면 target[key] 에 채운다."""
    if not winutil.IS_WIN:
        return

    def job():
        info = element_at(x, y)
        if info:
            target[key] = info
    threading.Thread(target=job, daemon=True).start()


def suggest_note(info: dict | None, button: str = "left", double: bool = False) -> str:
    """UI 요소 정보로 각주 문장 추천.  예) "'저장' 버튼 클릭" """
    verb = "더블클릭" if double else ("우클릭" if button == "right" else "클릭")
    if not info:
        return ""
    name = (info.get("name") or info.get("label") or info.get("context_name") or "").strip()
    name = " ".join(name.split())
    if len(name) > 30:
        name = name[:29] + "…"
    kind = info.get("type_ko", "")
    ctype = info.get("type")
    if ctype in _GENERIC and not name:
        return ""
    if not name and not kind:
        return ""
    if ctype == "EditControl":
        return f"'{name}' 입력칸 {verb} 후 입력" if name else f"입력칸 {verb} 후 입력"
    if ctype in _PLAIN:  # 글자·그림·영역 등은 종류를 붙이면 어색하다 → "'거래처명' 클릭"
        return f"'{name}' {verb}" if name else ""
    if name and kind:
        return f"'{name}' {kind} {verb}"
    return f"'{name}' {verb}" if name else f"{kind} {verb}"
