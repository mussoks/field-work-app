"""화면(페이지) 구성: 홈 · 녹화 · 캡쳐 · 보관함 · 설정."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from capture import font as pil_font, render_marker
from config import APP_VERSION, HOTKEY_LABELS, QUALITY_PRESETS, RESOLUTIONS, default_hotkeys
from controller import human_size
from input_hub import format_hotkey
from ui.widgets import (Card, Row, Segmented, Sheet, StatTile, ToggleRow, button, confirm, hbox, hline, label,
                        rounded_pixmap, vbox)


def open_path(p: Path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))


def keycaps(combo: str) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    for part in format_hotkey(combo).split(" + "):
        lay.addWidget(label(part, "keycap"))
    return w


class Page(QWidget):
    def __init__(self, app, title: str, subtitle: str = ""):
        super().__init__()
        self.app = app
        self.c = app.c
        self.setObjectName("page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self.scroll, 1)
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(40, 36, 40, 40)
        hl.addStretch(1)
        col = QWidget()
        col.setMaximumWidth(760)
        col.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.body = QVBoxLayout(col)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(16)
        hl.addWidget(col, 100)
        hl.addStretch(1)
        self.scroll.setWidget(holder)
        self.h1 = label(title, "h1")
        self.body.addWidget(self.h1)
        if subtitle:
            self.sub = label(subtitle, "h1sub", wrap=True)
            self.body.addWidget(self.sub)
        self.body.addSpacing(8)
        self.outer = outer

    def finish(self):
        self.body.addStretch(1)

    def refresh(self):
        pass


def clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w:
            w.deleteLater()
        elif it.layout():
            clear_layout(it.layout())


class ItemRow(QFrame):
    """보관함/최근 기록 한 줄."""

    def __init__(self, item, on_delete=None, compact=False):
        super().__init__()
        self.setObjectName("listRow")
        self.item = item
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(14)
        th = QLabel()
        th.setObjectName("thumb")
        tw, tht = (96, 56) if compact else (144, 82)
        th.setFixedSize(tw, tht)
        th.setAlignment(Qt.AlignCenter)
        pm = QPixmap(str(item.thumb)) if item.thumb else QPixmap()
        if not pm.isNull():
            th.setPixmap(rounded_pixmap(pm, tw, tht, 10))
        else:
            th.setText("🎬" if item.kind == "record" else "📸")
            th.setStyleSheet("font-size: 26px;")
        lay.addWidget(th)
        mid = QVBoxLayout()
        mid.setSpacing(4)
        badge = label("녹화" if item.kind == "record" else "캡쳐", "badgeRed" if item.kind == "record" else "badge")
        title = label(item.title, "rowTitle")
        title.setTextInteractionFlags(Qt.NoTextInteraction)
        mid.addLayout(hbox(badge, title, None, spacing=8))
        mid.addWidget(label(f"{item.created:%m월 %d일 %H:%M} · {item.detail} · {human_size(item.size)}", "rowCaption"))
        lay.addLayout(mid, 1)
        if not compact:
            lay.addWidget(button("열기", "secondary", "sm", lambda: open_path(item.main_file)))
            lay.addWidget(button("폴더", "gray", "sm", lambda: open_path(item.path if item.path.is_dir() else item.path.parent)))
            if on_delete:
                lay.addWidget(button("삭제", "ghost", "sm", lambda: on_delete(item)))
        else:
            lay.addWidget(label("›", "h2"))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            open_path(self.item.main_file)


class EmptyState(QWidget):
    def __init__(self, emoji: str, title: str, caption: str):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 24, 0, 24)
        lay.setSpacing(6)
        for w, a in ((label(emoji, "emptyIcon"), 0), (label(title, "cardTitle"), 0), (label(caption, "caption"), 0)):
            w.setAlignment(Qt.AlignCenter)
            lay.addWidget(w)


# ===================================================================== 홈
class HomePage(Page):
    def __init__(self, app):
        super().__init__(app, "안녕하세요 👋", "오늘도 ERP 업무를 AI에게 알려줄 데이터를 모아볼까요?")
        c = self.c

        heroes = QHBoxLayout()
        heroes.setSpacing(16)
        rec = QFrame()
        rec.setObjectName("heroBlue")
        rl = vbox(spacing=6, margins=(26, 24, 26, 22))
        rec.setLayout(rl)
        rl.addWidget(label("🎬", "heroEmoji"))
        t = label("화면 녹화", "h2")
        rl.addWidget(t)
        cap = label("클릭 위치가 또렷하게 보이는 영상과\n클릭 데이터를 함께 저장해요", "caption", wrap=True)
        cap.setStyleSheet("color: rgba(255,255,255,0.85);")
        rl.addWidget(cap)
        rl.addSpacing(10)
        self.rec_btn = button("녹화 시작", "white", None, app.toggle_record)
        rl.addWidget(self.rec_btn)
        self.rec_hint = label("", "caption")
        self.rec_hint.setStyleSheet("color: rgba(255,255,255,0.75);")
        rl.addWidget(self.rec_hint)
        heroes.addWidget(rec, 1)

        capc = Card(padding=26)
        capc.lay.setSpacing(6)
        capc.add(label("📸", "heroEmoji"))
        capc.add(label("단계별 캡쳐", "h2"))
        self.cap_state = label("", "caption", wrap=True)
        capc.add(self.cap_state)
        capc.lay.addSpacing(10)
        capc.add(hbox(button("지금 캡쳐", "secondary", None, lambda: app.capture_now()),
                      button("세트 끝내기", "gray", None, c.end_set), spacing=8))
        self.cap_hint = label("", "caption")
        capc.add(self.cap_hint)
        heroes.addWidget(capc, 1)
        self.body.addLayout(heroes)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_rec = StatTile("🎞️", "오늘 녹화")
        self.t_cap = StatTile("🖼️", "오늘 캡쳐")
        self.t_click = StatTile("🎯", "모은 클릭 데이터")
        self.t_size = StatTile("💾", "사용 중인 용량")
        for t_ in (self.t_rec, self.t_cap, self.t_click, self.t_size):
            tiles.addWidget(t_)
        self.body.addLayout(tiles)

        self.recent = Card("최근 기록")
        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(2)
        self.recent.add(self.recent_list)
        self.recent.add(hbox(None, button("보관함 전체 보기", "link", None, lambda: app.go("library"))))
        self.body.addWidget(self.recent)
        self.finish()

    def refresh(self):
        c = self.c
        hk = c.s.hotkeys
        self.rec_hint.setText(f"단축키 {format_hotkey(hk['record'])}")
        self.rec_btn.setText("녹화 끝내기" if c.recorder else "녹화 시작")
        n = c.captures.next_number
        if c.captures.active:
            self.cap_state.setText(f"'{c.captures.set_name or '이름 없는 세트'}' 진행 중이에요\n다음은 {n}번이에요")
        else:
            self.cap_state.setText("마우스가 있는 곳에 클릭 표시와\n번호·각주를 찍어서 저장해요")
        self.cap_hint.setText(f"단축키 {format_hotkey(hk['capture'])}")
        st = c.stats()
        self.t_rec.set(f"{st['rec_today']}개")
        self.t_cap.set(f"{st['cap_today']}장")
        self.t_click.set(f"{st['clicks']}개")
        self.t_size.set(st["total"])
        clear_layout(self.recent_list)
        items = st["items"][:4]
        if not items:
            self.recent_list.addWidget(EmptyState("🗂️", "아직 기록이 없어요", "녹화나 캡쳐를 하면 여기에 모여요"))
        for it in items:
            self.recent_list.addWidget(ItemRow(it, compact=True))


# ===================================================================== 녹화
class RecordPage(Page):
    def __init__(self, app):
        super().__init__(app, "화면 녹화", "포인터와 클릭이 또렷하게 보이도록 녹화하고, 클릭할 때마다 학습용 장면을 따로 모아요.")
        c, s = self.c, self.c.s

        # 범위
        rng = Card("어디를 녹화할까요?")
        mons = [(i, f"모니터 {i}") for i in range(1, len(c.monitors))] + [("region", "영역 지정")]
        self.range_seg = Segmented(mons, "region" if s.region else min(max(s.monitor_index, 1), len(c.monitors) - 1))
        self.range_seg.changed.connect(self._range_changed)
        rng.add(self.range_seg)
        self.range_info = label("", "caption")
        rng.add(self.range_info)
        self.region_btn = button("영역 다시 고르기", "link", None, self._pick_region)
        rng.add(hbox(self.region_btn, None))
        self.body.addWidget(rng)

        # 화질
        q = Card("화질과 용량", "글자가 읽히는 선에서 가장 작게 저장해요")
        self.res_seg = Segmented([(k, "FHD 1080p" if "1080" in k else "HD 720p") for k in RESOLUTIONS], s.resolution)
        self.res_seg.changed.connect(lambda v: (c.set("resolution", v), self._estimate()))
        q.add(Row("해상도", None, self.res_seg))
        self.fps_seg = Segmented([(30, "30fps"), (15, "15fps")], s.fps)
        self.fps_seg.changed.connect(lambda v: (c.set("fps", v), self._estimate()))
        q.add(Row("프레임", "15fps는 용량이 더 작아요", self.fps_seg))
        self.q_seg = Segmented([(k, k) for k in QUALITY_PRESETS], s.quality)
        self.q_seg.changed.connect(lambda v: (c.set("quality", v), self._estimate()))
        q.add(Row("압축", None, self.q_seg))
        self.estimate = label("", "badge")
        q.add(hbox(self.estimate, None))
        self.body.addWidget(q)

        # AI 표시
        ai = Card("AI가 알아보기 쉽게", "녹화 영상과 함께 학습에 바로 쓸 수 있는 데이터를 만들어요")
        ai.add(ToggleRow("마우스 포인터 강조", "흰 화살표 + 노란 원으로 항상 보여요", s.show_cursor_halo,
                         lambda v: c.set("show_cursor_halo", v)))
        ai.add(ToggleRow("클릭 표시", "왼쪽 빨강 · 오른쪽 파랑 · 더블클릭 · 드래그 · 휠을 구분해요", s.show_clicks,
                         lambda v: c.set("show_clicks", v)))
        ai.add(ToggleRow("클릭 장면 모으기", "클릭 직전의 원본 화면과 표시 화면을 이미지로 저장해요 (annotations.jsonl)",
                         s.save_click_frames, lambda v: c.set("save_click_frames", v)))
        ai.add(ToggleRow("누른 곳의 이름 기록", "'저장' 버튼처럼 클릭한 UI 요소 이름을 함께 기록해요", s.uia_enabled,
                         lambda v: c.set("uia_enabled", v)))
        ai.add(ToggleRow("클릭 타임라인 저장", "클릭 좌표·프레임 번호를 events.json 으로 저장해요", s.save_event_log,
                         lambda v: c.set("save_event_log", v)))
        self.key_seg = Segmented([("끄기", "끄기"), ("특수키만", "단축키만"), ("전체", "전체")], s.key_overlay)
        self.key_seg.changed.connect(lambda v: c.set("key_overlay", v))
        ai.add(Row("키 입력 표시", "'전체'는 비밀번호도 보일 수 있어요", self.key_seg))
        self.body.addWidget(ai)

        # 개인정보
        pv = Card("개인정보 가리기", "거래처명·주민번호처럼 남기면 안 되는 곳을 모자이크해요. 녹화와 캡쳐 모두에 적용돼요")
        pv.add(ToggleRow("가리기 사용", None, s.mask_enabled, lambda v: (c.set("mask_enabled", v), self._mask_info())))
        self.mask_lbl = label("", "caption")
        pv.add(hbox(self.mask_lbl, None, button("영역 고르기", "secondary", "sm", self._pick_masks),
                    button("모두 지우기", "gray", "sm", self._clear_masks)))
        self.body.addWidget(pv)

        etc = Card("그 밖에")
        etc.add(ToggleRow("3초 카운트다운", "시작 전에 준비할 시간을 드려요", s.countdown, lambda v: c.set("countdown", v)))
        etc.add(ToggleRow("끝난 뒤 한 번 더 압축", "시간이 조금 걸리지만 용량이 20~30% 줄어요", s.optimize_after,
                          lambda v: c.set("optimize_after", v)))
        self.body.addWidget(etc)
        self.finish()

        bar = QFrame()
        bar.setObjectName("bottomBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(40, 14, 40, 14)
        self.status = label("", "rowCaption")
        bl.addWidget(self.status, 1)
        self.pause_btn = button("일시정지", "gray", "lg", c.toggle_pause, width=140)
        self.start_btn = button("녹화 시작", "primary", "lg", app.toggle_record, width=240)
        bl.addWidget(self.pause_btn)
        bl.addWidget(self.start_btn)
        self.outer.addWidget(bar)
        self._range_info()
        self._estimate()
        self._mask_info()

    def _range_changed(self, v):
        if v == "region":
            self._pick_region()
        else:
            self.c.set("region", None)
            self.c.set("monitor_index", v)
            self._range_info()

    def _pick_region(self):
        idx = self.c.s.monitor_index if self.c.s.monitor_index < len(self.c.monitors) else 1
        self.app.pick_screen("region", self.c.monitors[idx], self._region_done)

    def _region_done(self, rects):
        if rects:
            self.c.set("region", rects[0])
        elif not self.c.s.region:
            self.range_seg.set_value(min(max(self.c.s.monitor_index, 1), len(self.c.monitors) - 1))
        self._range_info()

    def _range_info(self):
        r = self.c.record_rect()
        self.region_btn.setVisible(bool(self.c.s.region))
        self.range_info.setText(f"{'지정한 영역' if self.c.s.region else '모니터 전체'} · {r['width']} × {r['height']}"
                                f"  (위치 {r['left']}, {r['top']})")
        self._estimate()

    def _estimate(self):
        s = self.c.s
        base = {"저용량": 0.6, "표준": 1.0, "선명": 2.2}[s.quality]
        res = 1.0 if "1080" in s.resolution else 0.55
        fps = 1.0 if s.fps == 30 else 0.7
        mb = base * res * fps * 1.6
        self.estimate.setText(f"1분에 약 {max(0.3, mb):.1f}MB 예상 · 화면 변화가 많으면 더 커져요")

    def _mask_info(self):
        n = len(self.c.s.mask_regions or [])
        state = "켜짐" if self.c.s.mask_enabled else "꺼짐"
        self.mask_lbl.setText(f"가릴 영역 {n}개 · {state}")

    def _pick_masks(self):
        idx = self.c.s.monitor_index if self.c.s.monitor_index < len(self.c.monitors) else 1
        self.app.pick_screen("mask", self.c.monitors[idx], self._mask_done, self.c.s.mask_regions)

    def _mask_done(self, rects):
        if rects is not None:
            mon = self.c.monitors[self.c.s.monitor_index if self.c.s.monitor_index < len(self.c.monitors) else 1]
            others = [r for r in (self.c.s.mask_regions or [])
                      if not (mon["left"] <= r[0] < mon["left"] + mon["width"]
                              and mon["top"] <= r[1] < mon["top"] + mon["height"])]
            self.c.set("mask_regions", others + rects)
            if rects and not self.c.s.mask_enabled:
                self.c.set("mask_enabled", True)
            self.app.toast(f"가릴 영역을 {len(rects)}개로 정했어요")
        self._mask_info()

    def _clear_masks(self):
        self.c.set("mask_regions", [])
        self._mask_info()

    def refresh(self):
        rec = self.c.recorder
        self.start_btn.setText("녹화 끝내기" if rec else "녹화 시작")
        self.start_btn.setProperty("kind", "danger" if rec else "primary")
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        self.pause_btn.setVisible(bool(rec))
        self.pause_btn.setText("이어서" if rec and rec.paused else "일시정지")
        if rec and rec.start_t:
            t = rec.video_time()
            clicks = sum(1 for e in rec.events if e["type"] == "mouse_down")
            size = rec.out_path.stat().st_size / 1024 / 1024 if rec.out_path.exists() else 0
            self.status.setText(f"{'⏸ 일시정지' if rec.paused else '🔴 녹화 중'}  {int(t // 60):02d}:{int(t % 60):02d}"
                                f"  ·  {rec.ow}×{rec.oh} {rec.fps}fps  ·  {size:.1f}MB  ·  클릭 {clicks}회")
        else:
            self.status.setText(f"단축키 {format_hotkey(self.c.s.hotkeys['record'])} 로도 시작·종료할 수 있어요")


# ===================================================================== 캡쳐
class CapturePage(Page):
    def __init__(self, app):
        super().__init__(app, "단계별 캡쳐", "단축키를 누르면 마우스가 있는 곳에 ✔ 번호와 각주를 찍어서 저장해요.")
        c, s = self.c, self.c.s

        hero = Card(padding=26)
        top = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(label("지금 만드는 세트", "cardCaption"))
        self.set_edit = QLineEdit(s.set_name)
        self.set_edit.setPlaceholderText("작업 이름을 적어주세요  예) 구매발주 등록")
        self.set_edit.textChanged.connect(lambda v: c.set("set_name", v))
        left.addWidget(self.set_edit)
        self.recent_names = QHBoxLayout()
        self.recent_names.setSpacing(6)
        left.addLayout(self.recent_names)
        top.addLayout(left, 1)
        top.addSpacing(20)
        right = QVBoxLayout()
        right.setSpacing(0)
        right.addWidget(label("다음 번호", "cardCaption"), 0, Qt.AlignRight)
        self.next_num = label("1", "bigBlue")
        right.addWidget(self.next_num, 0, Qt.AlignRight)
        top.addLayout(right)
        hero.add(top)
        hero.lay.addSpacing(12)
        self.cap_btn = button("지금 캡쳐", "primary", "lg", lambda: app.capture_now())
        self.end_btn = button("세트 끝내기", "gray", "lg", c.end_set)
        hero.add(hbox(self.cap_btn, self.end_btn, spacing=8))
        self.hint = label("", "caption")
        hero.add(self.hint)
        self.body.addWidget(hero)

        self.steps_card = Card("이번 세트의 캡쳐")
        self.steps_list = QVBoxLayout()
        self.steps_list.setSpacing(2)
        self.steps_card.add(self.steps_list)
        self.steps_actions = hbox(button("마지막 캡쳐 지우기", "ghost", "sm", self._undo), None,
                                  button("가이드 보기", "secondary", "sm", self._guide),
                                  button("폴더 열기", "gray", "sm", self._folder))
        self.steps_card.add(self.steps_actions)
        self.body.addWidget(self.steps_card)

        opt = Card("캡쳐 옵션")
        opt.add(ToggleRow("캡쳐 후 각주 입력창 띄우기", "누른 버튼 이름으로 각주를 추천해 드려요", s.note_popup,
                          lambda v: c.set("note_popup", v)))
        opt.add(ToggleRow("클릭할 때마다 자동 캡쳐", "매뉴얼을 자동으로 만들 때 좋아요", s.auto_click_capture,
                          lambda v: c.set("auto_click_capture", v)))
        opt.add(ToggleRow("추천 각주 자동 입력", "각주를 비워두면 '저장' 버튼 클릭처럼 자동으로 채워요", s.auto_note,
                          lambda v: c.set("auto_note", v)))
        opt.add(ToggleRow("표시 없는 원본도 저장", "원본 / 정답표시 이미지 쌍으로 학습할 수 있어요", s.save_raw,
                          lambda v: c.set("save_raw", v)))
        self.fmt = Segmented([("PNG", "PNG 선명"), ("JPG", "JPG 가벼움")], s.image_format)
        self.fmt.changed.connect(lambda v: c.set("image_format", v))
        opt.add(Row("이미지 형식", None, self.fmt))
        self.body.addWidget(opt)
        self.finish()

    def _undo(self):
        st = self.c.captures.undo_last()
        if st:
            self.app.toast(f"{st.step}번 캡쳐를 지웠어요")
        self.c.captures_changed.emit()

    def _guide(self):
        if self.c.captures.folder:
            open_path(self.c.captures.folder / "가이드.html")

    def _folder(self):
        if self.c.captures.folder:
            open_path(self.c.captures.folder)

    def _edit_note(self, st):
        ed = QLineEdit(st.note)
        ed.selectAll()
        d = Sheet(self, f"{st.step}번 각주", "체크 표시 아래에 들어갈 내용이에요", "저장", "취소", editor=ed)
        if d.exec():
            self.c.set_note(st.step, ed.text().strip())

    def refresh(self):
        c = self.c
        hk = c.s.hotkeys
        self.next_num.setText(str(c.captures.next_number))
        self.hint.setText(f"캡쳐 {format_hotkey(hk['capture'])}  ·  세트 끝내기 {format_hotkey(hk['end_set'])}"
                          f"  ·  마지막 지우기 {format_hotkey(hk['undo'])}")
        self.set_edit.setEnabled(not c.captures.active)
        if c.captures.active and self.set_edit.text() != c.captures.set_name:
            self.set_edit.setText(c.captures.set_name)
        clear_layout(self.recent_names)
        if not c.captures.active:
            for n in c.s.recent_set_names[:4]:
                b = button(n, "chip")
                b.clicked.connect(lambda _=False, v=n: self.set_edit.setText(v))
                self.recent_names.addWidget(b)
        self.recent_names.addStretch(1)

        clear_layout(self.steps_list)
        steps = c.captures.steps
        self.steps_card.title.setText(f"이번 세트의 캡쳐 {len(steps)}장" if steps else "이번 세트의 캡쳐")
        for i in range(self.steps_actions.count()):
            w = self.steps_actions.itemAt(i).widget()
            if w:
                w.setVisible(bool(steps))
        if not steps:
            self.steps_list.addWidget(EmptyState("🖱️", "아직 캡쳐가 없어요",
                                                 f"{format_hotkey(hk['capture'])} 을 누르면 1번부터 쌓여요"))
            return
        for st in reversed(steps):
            row = QFrame()
            row.setObjectName("listRow")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 8, 8, 8)
            rl.setSpacing(12)
            num = label(str(st.step), "stepNum")
            num.setFixedSize(28, 28)
            num.setAlignment(Qt.AlignCenter)
            rl.addWidget(num)
            th = QLabel()
            th.setObjectName("thumb")
            th.setFixedSize(112, 64)
            pm = QPixmap(str(c.captures.folder / st.file))
            if not pm.isNull():
                th.setPixmap(rounded_pixmap(pm, 112, 64, 8))
            rl.addWidget(th)
            mid = QVBoxLayout()
            mid.setSpacing(3)
            mid.addWidget(label(st.note or "각주 없음", "rowTitle" if st.note else "rowCaption"))
            el = st.element or {}
            meta = []
            if el.get("name") or el.get("type_ko"):
                meta.append(f"{el.get('type_ko', '')} '{el.get('name', '')}'".strip())
            if st.window:
                meta.append(st.window[:40])
            meta.append(f"({st.x}, {st.y})")
            mid.addWidget(label(" · ".join(meta), "rowCaption"))
            rl.addLayout(mid, 1)
            rl.addWidget(button("각주", "gray", "sm", lambda _=False, s_=st: self._edit_note(s_)))
            self.steps_list.addWidget(row)


# ===================================================================== 보관함
class LibraryPage(Page):
    def __init__(self, app):
        super().__init__(app, "보관함", "녹화와 캡쳐 기록을 한곳에서 보고 정리해요.")
        self.filter = Segmented([("all", "전체"), ("record", "녹화"), ("capture", "캡쳐")], "all")
        self.filter.changed.connect(lambda _: self.refresh())
        self.body.addLayout(hbox(self.filter, None,
                                 button("저장 폴더 열기", "gray", "sm", lambda: open_path(self.c.root())),
                                 button("새로고침", "secondary", "sm", self.refresh)))
        self.summary = label("", "caption")
        self.body.addWidget(self.summary)
        self.card = Card(padding=14)
        self.list = QVBoxLayout()
        self.list.setSpacing(2)
        self.card.add(self.list)
        self.body.addWidget(self.card)
        self.finish()

    def _delete(self, item):
        if confirm(self, f"'{item.title}'을(를) 지울까요?", "지운 기록은 휴지통으로 가지 않고 바로 삭제돼요.", "삭제", danger=True):
            self.c.delete_item(item)
            self.app.toast("삭제했어요")
            self.refresh()

    def refresh(self):
        clear_layout(self.list)
        items = self.c.library()
        f = self.filter.value()
        shown = [i for i in items if f == "all" or i.kind == f]
        total = sum(i.size for i in items)
        self.summary.setText(f"전체 {len(items)}개 · {human_size(total)} · 저장 위치 {self.c.root()}")
        if not shown:
            self.list.addWidget(EmptyState("🗂️", "보여드릴 기록이 없어요", "녹화나 캡쳐를 하면 여기에 쌓여요"))
            return
        for i, it in enumerate(shown[:200]):
            if i:
                self.list.addWidget(hline())
            self.list.addWidget(ItemRow(it, on_delete=self._delete))


# ===================================================================== 설정
class SettingsPage(Page):
    def __init__(self, app):
        super().__init__(app, "설정")
        c, s = self.c, self.c.s

        hk = Card("단축키", "바꾸고 싶은 단축키를 누른 뒤 원하는 키 조합을 눌러주세요. Esc 를 누르면 취소돼요")
        self.hk_btns = {}
        for name, text in HOTKEY_LABELS.items():
            b = button(format_hotkey(s.hotkeys.get(name, "")), "gray", "sm")
            b.setMinimumWidth(170)
            b.clicked.connect(lambda _=False, n=name: self._record(n))
            self.hk_btns[name] = b
            hk.add(Row(text, None, b))
        hk.add(hbox(None, button("기본값으로 되돌리기", "link", None, self._reset)))
        hk.add(label("ERP를 관리자 권한으로 실행 중이라면, 이 앱도 관리자 권한으로 실행해야 단축키가 동작해요.", "caption", wrap=True))
        self.body.addWidget(hk)

        loc = Card("저장 위치")
        self.root_lbl = label(str(c.root()), "rowTitle", wrap=True)
        loc.add(self.root_lbl)
        loc.add(hbox(button("바꾸기", "secondary", "sm", self._choose), button("바탕화면으로", "gray", "sm",
                                                                         lambda: self._set_root("")),
                     button("열기", "gray", "sm", lambda: open_path(c.root())), None))
        self.body.addWidget(loc)

        disp = Card("클릭 표시 모양", "AI와 사람이 한눈에 알아보도록 크고 또렷하게 찍어요")
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setObjectName("thumb")
        self.preview.setFixedHeight(170)
        disp.add(self.preview)
        self.size_seg = Segmented([(0.8, "작게"), (1.0, "보통"), (1.3, "크게")],
                                  min((0.8, 1.0, 1.3), key=lambda v: abs(v - s.marker_scale)))
        self.size_seg.changed.connect(lambda v: (c.set("marker_scale", v), self._render_preview()))
        disp.add(Row("크기", None, self.size_seg))
        self.hold_seg = Segmented([(0.5, "0.5초"), (0.8, "0.8초"), (1.2, "1.2초"), (2.0, "2초")],
                                  min((0.5, 0.8, 1.2, 2.0), key=lambda v: abs(v - s.click_hold_sec)))
        self.hold_seg.changed.connect(lambda v: c.set("click_hold_sec", v))
        disp.add(Row("영상 속 클릭 표시 시간", "15fps에서도 놓치지 않도록 0.8초 이상을 권해요", self.hold_seg))
        self.body.addWidget(disp)

        appc = Card("앱")
        appc.add(ToggleRow("창을 닫아도 계속 실행", "작업 표시줄 트레이에서 단축키가 계속 동작해요", s.minimize_to_tray,
                           lambda v: c.set("minimize_to_tray", v)))
        appc.add(ToggleRow("알림 보기", "캡쳐·녹화가 저장되면 알려드려요", s.notify, lambda v: c.set("notify", v)))
        appc.add(ToggleRow("이 앱 창은 녹화·캡쳐에서 숨기기", "각주 입력창과 녹화 바도 찍히지 않아요", s.exclude_self,
                           lambda v: (c.set("exclude_self", v), app.apply_exclude())))
        self.body.addWidget(appc)

        info = Card("정보")
        info.add(Row("버전", None, label(APP_VERSION, "badgeGray")))
        info.add(hbox(button("사용법 다시 보기", "secondary", "sm", app.show_onboarding),
                      button("오류 기록 열기", "gray", "sm", self._open_log), None))
        info.add(label("글꼴: Pretendard (SIL Open Font License 1.1)", "caption"))
        self.body.addWidget(info)
        self.finish()
        c.hotkey_recorded.connect(self._recorded)
        QTimer.singleShot(0, self._render_preview)

    def _render_preview(self):
        try:
            from PIL import Image, ImageDraw
            from ui.overlays import pil_to_pixmap
            w, h = 720, 260
            img = Image.new("RGB", (w, h), (246, 247, 249))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([40, 70, 230, 120], 8, fill=(255, 255, 255), outline=(209, 214, 219), width=2)
            d.rounded_rectangle([250, 70, 360, 120], 8, fill=(49, 130, 246))
            d.text((285, 84), "저장", fill="white", font=pil_font(20, True))
            d.text((54, 84), "거래처 검색", fill=(139, 149, 161), font=pil_font(18))
            out = render_marker(img, 305, 95, 3, "'저장' 버튼 클릭", "left", "", self.c.s.marker_scale * 0.9)
            pm = pil_to_pixmap(out)
            self.preview.setPixmap(pm.scaledToHeight(170, Qt.SmoothTransformation))
        except Exception:
            self.preview.setText("미리보기를 만들 수 없어요")

    def _record(self, name):
        self.hk_btns[name].setText("키를 눌러주세요…")
        self.hk_btns[name].setProperty("kind", "secondary")
        self.hk_btns[name].style().polish(self.hk_btns[name])
        self.c.record_hotkey(name)

    def _recorded(self, name, combo):
        if combo:
            clash = self.c.set_hotkey(name, combo)
            if clash:
                self.app.toast(f"이미 '{HOTKEY_LABELS[clash]}'에 쓰고 있는 단축키예요")
            else:
                self.app.toast(f"{HOTKEY_LABELS[name]} 단축키를 {format_hotkey(combo)}(으)로 바꿨어요")
        b = self.hk_btns[name]
        b.setText(format_hotkey(self.c.s.hotkeys.get(name, "")))
        b.setProperty("kind", "gray")
        b.style().polish(b)

    def _reset(self):
        self.c.s.hotkeys = default_hotkeys()
        self.c.hub.set_hotkeys(self.c.s.hotkeys)
        self.c.save()
        for n, b in self.hk_btns.items():
            b.setText(format_hotkey(self.c.s.hotkeys[n]))
        self.app.toast("단축키를 기본값으로 되돌렸어요")

    def _choose(self):
        d = QFileDialog.getExistingDirectory(self, "저장할 폴더를 골라주세요", str(self.c.root()))
        if d:
            self._set_root(d)

    def _set_root(self, path):
        self.c.set("save_root", path)
        self.root_lbl.setText(str(self.c.root()))

    def _open_log(self):
        import os
        p = Path(os.environ.get("APPDATA") or Path.home()) / "LearningRecorder" / "error.log"
        if p.exists():
            open_path(p)
        else:
            self.app.toast("기록된 오류가 없어요 👍")

    def refresh(self):
        for n, b in self.hk_btns.items():
            if b.text() != "키를 눌러주세요…":
                b.setText(format_hotkey(self.c.s.hotkeys.get(n, "")))
