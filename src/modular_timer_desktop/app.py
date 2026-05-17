from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from modular_timer_desktop.settings import PREFERENCES_PATH, STAGES_PATH, load_json, save_json


TEAM_LABELS = {
    "affirmative": "正方单元",
    "negative": "反方单元",
    "both": "正反方同时",
    "public": "公共/单人单元",
}


@dataclass
class Stage:
    name: str
    team: str
    duration: int = 180
    affirmative_duration: int = 180
    negative_duration: int = 180

    @classmethod
    def from_dict(cls, data: dict) -> "Stage":
        return cls(
            name=str(data.get("name", "未命名单元")),
            team=str(data.get("team", "public")),
            duration=max(1, int(data.get("duration", 180))),
            affirmative_duration=max(1, int(data.get("affirmative_duration", data.get("duration", 180)))),
            negative_duration=max(1, int(data.get("negative_duration", data.get("duration", 180)))),
        )

    def public_duration(self) -> int:
        return self.duration

    def display_duration(self) -> str:
        if self.team == "both":
            return f"正方 {format_time(self.affirmative_duration)} / 反方 {format_time(self.negative_duration)}"
        return format_time(self.duration)


def format_time(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def default_stages() -> list[Stage]:
    return [
        Stage("开篇立论 - 正方一辩", "affirmative", duration=180, affirmative_duration=180, negative_duration=180),
        Stage("开篇立论 - 反方一辩", "negative", duration=180, affirmative_duration=180, negative_duration=180),
        Stage("攻辩 - 正方二辩", "affirmative", duration=120, affirmative_duration=120, negative_duration=120),
        Stage("攻辩 - 反方二辩", "negative", duration=120, affirmative_duration=120, negative_duration=120),
        Stage("自由辩论", "both", duration=240, affirmative_duration=240, negative_duration=240),
        Stage("评委提问/准备", "public", duration=120, affirmative_duration=120, negative_duration=120),
        Stage("总结陈词 - 反方四辩", "negative", duration=180, affirmative_duration=180, negative_duration=180),
        Stage("总结陈词 - 正方四辩", "affirmative", duration=180, affirmative_duration=180, negative_duration=180),
    ]


class TimerCard(QFrame):
    def __init__(self, title: str, subtitle: str, object_name: str) -> None:
        super().__init__()
        self.setObjectName(object_name)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("cardSubtitle")
        self.time_label = QLabel("00:00")
        self.time_label.setObjectName("timeLabel")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(1000)
        self.progress.setTextVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch(1)
        layout.addWidget(self.time_label)
        layout.addWidget(self.progress)
        layout.addStretch(1)

    def set_timer(self, remaining: int, total: int, active: bool) -> None:
        self.time_label.setText(format_time(remaining))
        if total <= 0:
            self.progress.setValue(0)
        else:
            self.progress.setValue(max(0, min(1000, int(remaining / total * 1000))))
        self.setProperty("active", active)
        self.setProperty("warning", active and 0 < remaining <= 10)
        self.style().unpolish(self)
        self.style().polish(self)


class StageDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, stage: Stage | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑计时单元" if stage else "添加计时单元")
        self.setModal(True)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如：自由辩论 / 课堂展示 / 面试陈述")

        self.team_combo = QComboBox()
        self.team_combo.addItem("正方单元", "affirmative")
        self.team_combo.addItem("反方单元", "negative")
        self.team_combo.addItem("正反方同时", "both")
        self.team_combo.addItem("公共/单人单元", "public")

        self.duration_spin = self._make_duration_spinbox()
        self.aff_spin = self._make_duration_spinbox()
        self.neg_spin = self._make_duration_spinbox()

        if stage:
            self.name_input.setText(stage.name)
            index = self.team_combo.findData(stage.team)
            self.team_combo.setCurrentIndex(max(0, index))
            self.duration_spin.setValue(stage.duration)
            self.aff_spin.setValue(stage.affirmative_duration)
            self.neg_spin.setValue(stage.negative_duration)
        else:
            self.duration_spin.setValue(180)
            self.aff_spin.setValue(180)
            self.neg_spin.setValue(180)

        form = QGridLayout()
        form.addWidget(QLabel("单元名称"), 0, 0)
        form.addWidget(self.name_input, 0, 1, 1, 2)
        form.addWidget(QLabel("计时类型"), 1, 0)
        form.addWidget(self.team_combo, 1, 1, 1, 2)
        self.duration_label = QLabel("单元时长（秒）")
        self.aff_label = QLabel("正方时长（秒）")
        self.neg_label = QLabel("反方时长（秒）")
        form.addWidget(self.duration_label, 2, 0)
        form.addWidget(self.duration_spin, 2, 1, 1, 2)
        form.addWidget(self.aff_label, 3, 0)
        form.addWidget(self.aff_spin, 3, 1, 1, 2)
        form.addWidget(self.neg_label, 4, 0)
        form.addWidget(self.neg_spin, 4, 1, 1, 2)

        tip = QLabel("核心设计：每个单元都是可复用的计时模块。你可以把它组合成辩论赛、课堂汇报、考试练习、面试模拟。")
        tip.setObjectName("dialogTip")
        tip.setWordWrap(True)

        ok_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(cancel_btn)
        actions.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(tip)
        layout.addLayout(actions)
        self.team_combo.currentIndexChanged.connect(self._sync_visibility)
        self._sync_visibility()

    def _make_duration_spinbox(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 24 * 3600)
        spin.setSingleStep(10)
        spin.setSuffix(" 秒")
        return spin

    def _sync_visibility(self) -> None:
        is_both = self.team_combo.currentData() == "both"
        self.duration_label.setVisible(not is_both)
        self.duration_spin.setVisible(not is_both)
        self.aff_label.setVisible(is_both)
        self.aff_spin.setVisible(is_both)
        self.neg_label.setVisible(is_both)
        self.neg_spin.setVisible(is_both)

    def get_stage(self) -> Stage | None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少名称", "请先填写计时单元名称。")
            return None
        team = str(self.team_combo.currentData())
        if team == "both":
            duration = self.aff_spin.value()
            aff_duration = self.aff_spin.value()
            neg_duration = self.neg_spin.value()
        else:
            duration = self.duration_spin.value()
            aff_duration = duration
            neg_duration = duration
        return Stage(name=name, team=team, duration=duration, affirmative_duration=aff_duration, negative_duration=neg_duration)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Modular Timer - 多用途计时器")
        self.resize(1180, 760)
        self.setMinimumSize(980, 660)

        self.preferences = load_json(PREFERENCES_PATH, {"sound": True})
        self.sound_enabled = bool(self.preferences.get("sound", True))

        self.solo_total = 25 * 60
        self.solo_remaining = self.solo_total
        self.solo_running = False
        self.solo_timer = QTimer(self)
        self.solo_timer.setInterval(1000)
        self.solo_timer.timeout.connect(self._tick_solo)

        self.stages = self._load_stages()
        self.current_stage_index = 0
        self.aff_remaining = 0
        self.neg_remaining = 0
        self.public_remaining = 0
        self.aff_total = 0
        self.neg_total = 0
        self.public_total = 0
        self.aff_running = False
        self.neg_running = False
        self.public_running = False
        self.debate_elapsed = 0
        self.debate_clock = QTimer(self)
        self.debate_clock.setInterval(1000)
        self.debate_clock.timeout.connect(self._tick_debate)

        self._build_menu()
        self._build_ui()
        self._apply_styles()
        self._reset_debate_stage()
        self._render_stages()
        self._refresh_all()

    def _build_menu(self) -> None:
        help_menu = self.menuBar().addMenu("帮助")
        about = QAction("关于", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Modular Timer")
        title.setObjectName("appTitle")
        subtitle = QLabel("单独计时 · 辩论赛流程 · 自定义计时单元 · 本地保存")
        subtitle.setObjectName("appSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        self.sound_check = QCheckBox("提示音")
        self.sound_check.setChecked(self.sound_enabled)
        self.sound_check.stateChanged.connect(self._toggle_sound)
        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(self.sound_check)
        root_layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_solo_tab(), "单独计时")
        self.tabs.addTab(self._build_debate_tab(), "流程/辩论会计时")
        root_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

    def _build_solo_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(4, 16, 4, 4)
        layout.setSpacing(18)

        left = QFrame()
        left.setObjectName("panel")
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(16)

        self.solo_title_input = QLineEdit("专注计时")
        self.solo_title_input.setPlaceholderText("计时标题")
        duration_group = QGroupBox("自定义时长")
        duration_layout = QGridLayout(duration_group)
        self.solo_min_spin = QSpinBox()
        self.solo_min_spin.setRange(0, 999)
        self.solo_min_spin.setValue(25)
        self.solo_min_spin.setSuffix(" 分")
        self.solo_sec_spin = QSpinBox()
        self.solo_sec_spin.setRange(0, 59)
        self.solo_sec_spin.setValue(0)
        self.solo_sec_spin.setSuffix(" 秒")
        duration_layout.addWidget(QLabel("分钟"), 0, 0)
        duration_layout.addWidget(self.solo_min_spin, 0, 1)
        duration_layout.addWidget(QLabel("秒"), 1, 0)
        duration_layout.addWidget(self.solo_sec_spin, 1, 1)

        preset_group = QGroupBox("常用预设")
        preset_layout = QGridLayout(preset_group)
        presets = [("90 秒", 90), ("3 分钟", 180), ("5 分钟", 300), ("10 分钟", 600), ("25 分钟", 1500), ("45 分钟", 2700)]
        for i, (label, seconds) in enumerate(presets):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, s=seconds: self._apply_solo_preset(s))
            preset_layout.addWidget(btn, i // 2, i % 2)

        apply_btn = QPushButton("应用时长")
        apply_btn.setObjectName("primaryButton")
        apply_btn.clicked.connect(self._apply_custom_solo_duration)
        left_layout.addWidget(QLabel("计时名称"))
        left_layout.addWidget(self.solo_title_input)
        left_layout.addWidget(duration_group)
        left_layout.addWidget(preset_group)
        left_layout.addWidget(apply_btn)
        left_layout.addStretch(1)

        right = QFrame()
        right.setObjectName("heroPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(34, 34, 34, 34)
        self.solo_name_label = QLabel("专注计时")
        self.solo_name_label.setObjectName("heroTitle")
        self.solo_time_label = QLabel(format_time(self.solo_remaining))
        self.solo_time_label.setObjectName("heroTime")
        self.solo_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.solo_progress = QProgressBar()
        self.solo_progress.setRange(0, 1000)
        self.solo_progress.setTextVisible(False)
        self.solo_start_btn = QPushButton("开始")
        self.solo_start_btn.setObjectName("primaryButton")
        self.solo_start_btn.clicked.connect(self._toggle_solo)
        solo_reset_btn = QPushButton("重置")
        solo_reset_btn.clicked.connect(self._reset_solo)
        solo_actions = QHBoxLayout()
        solo_actions.addStretch(1)
        solo_actions.addWidget(self.solo_start_btn)
        solo_actions.addWidget(solo_reset_btn)
        solo_actions.addStretch(1)
        right_layout.addWidget(self.solo_name_label)
        right_layout.addStretch(1)
        right_layout.addWidget(self.solo_time_label)
        right_layout.addWidget(self.solo_progress)
        right_layout.addLayout(solo_actions)
        right_layout.addStretch(1)

        layout.addWidget(left, 3)
        layout.addWidget(right, 7)
        return tab

    def _build_debate_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(4, 16, 4, 4)
        layout.setSpacing(18)

        left = QFrame()
        left.setObjectName("panel")
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(12)
        section_title = QLabel("计时流程")
        section_title.setObjectName("sectionTitle")
        self.stage_list = QListWidget()
        self.stage_list.currentRowChanged.connect(self._jump_to_stage_from_list)
        left_layout.addWidget(section_title)
        left_layout.addWidget(self.stage_list, 1)

        edit_grid = QGridLayout()
        add_btn = QPushButton("添加")
        edit_btn = QPushButton("编辑")
        delete_btn = QPushButton("删除")
        up_btn = QPushButton("上移")
        down_btn = QPushButton("下移")
        reset_btn = QPushButton("默认")
        import_btn = QPushButton("导入")
        export_btn = QPushButton("导出")
        add_btn.clicked.connect(self._add_stage)
        edit_btn.clicked.connect(self._edit_stage)
        delete_btn.clicked.connect(self._delete_stage)
        up_btn.clicked.connect(lambda: self._move_stage(-1))
        down_btn.clicked.connect(lambda: self._move_stage(1))
        reset_btn.clicked.connect(self._restore_default_stages)
        import_btn.clicked.connect(self._import_stages)
        export_btn.clicked.connect(self._export_stages)
        for i, btn in enumerate([add_btn, edit_btn, delete_btn, up_btn, down_btn, reset_btn, import_btn, export_btn]):
            edit_grid.addWidget(btn, i // 2, i % 2)
        left_layout.addLayout(edit_grid)

        right = QFrame()
        right.setObjectName("heroPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(16)
        top_line = QHBoxLayout()
        self.stage_title_label = QLabel("当前阶段")
        self.stage_title_label.setObjectName("heroTitle")
        self.stage_count_label = QLabel("1/1")
        self.stage_count_label.setObjectName("pill")
        top_line.addWidget(self.stage_title_label)
        top_line.addStretch(1)
        top_line.addWidget(self.stage_count_label)
        right_layout.addLayout(top_line)

        cards = QHBoxLayout()
        self.aff_card = TimerCard("正方", "Affirmative", "affirmativeCard")
        self.neg_card = TimerCard("反方", "Negative", "negativeCard")
        self.public_card = TimerCard("公共", "General", "publicCard")
        cards.addWidget(self.aff_card)
        cards.addWidget(self.neg_card)
        cards.addWidget(self.public_card)
        right_layout.addLayout(cards, 1)

        stats_row = QHBoxLayout()
        self.stage_duration_label = QLabel("本阶段预设：00:00")
        self.debate_elapsed_label = QLabel("实际已用：00:00")
        self.stage_duration_label.setObjectName("mutedStat")
        self.debate_elapsed_label.setObjectName("mutedStat")
        stats_row.addWidget(self.stage_duration_label)
        stats_row.addStretch(1)
        stats_row.addWidget(self.debate_elapsed_label)
        right_layout.addLayout(stats_row)

        controls = QHBoxLayout()
        self.debate_start_btn = QPushButton("开始当前阶段")
        self.debate_start_btn.setObjectName("primaryButton")
        self.debate_pause_btn = QPushButton("暂停")
        self.debate_next_btn = QPushButton("下一阶段")
        self.debate_reset_btn = QPushButton("重置全部")
        self.debate_start_btn.clicked.connect(self._start_current_debate_stage)
        self.debate_pause_btn.clicked.connect(self._pause_debate)
        self.debate_next_btn.clicked.connect(self._next_stage)
        self.debate_reset_btn.clicked.connect(self._reset_all_debate)
        controls.addStretch(1)
        controls.addWidget(self.debate_start_btn)
        controls.addWidget(self.debate_pause_btn)
        controls.addWidget(self.debate_next_btn)
        controls.addWidget(self.debate_reset_btn)
        controls.addStretch(1)
        right_layout.addLayout(controls)

        hint = QLabel("快捷键：空格 = 开始/暂停，Enter = 下一阶段，R = 重置。流程会自动保存在本机。")
        hint.setObjectName("dialogTip")
        hint.setWordWrap(True)
        right_layout.addWidget(hint)

        layout.addWidget(left, 4)
        layout.addWidget(right, 8)
        return tab

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f7fb; }
            QWidget { font-family: 'Microsoft YaHei UI', 'Segoe UI', Arial; color: #172033; font-size: 14px; }
            QMenuBar { background: #f4f7fb; padding: 4px; }
            #appTitle { font-size: 30px; font-weight: 800; color: #111827; }
            #appSubtitle { font-size: 14px; color: #64748b; }
            QTabWidget::pane { border: 0; }
            QTabBar::tab { padding: 10px 18px; border-radius: 10px; margin-right: 8px; background: #e8edf6; color: #475569; }
            QTabBar::tab:selected { background: #1f3a5f; color: white; }
            #panel, #heroPanel { background: white; border: 1px solid #e4eaf2; border-radius: 22px; }
            #heroPanel { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ffffff, stop:1 #edf6ff); }
            #sectionTitle, #heroTitle { font-size: 20px; font-weight: 800; color: #172033; }
            #heroTime { font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 96px; font-weight: 800; color: #132238; }
            #timeLabel { font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 58px; font-weight: 800; color: #172033; }
            #cardTitle { font-size: 22px; font-weight: 800; }
            #cardSubtitle { color: #64748b; }
            #pill { background: #dbeafe; color: #1e3a8a; border-radius: 14px; padding: 6px 12px; font-weight: 700; }
            #mutedStat { color: #475569; background: rgba(255,255,255,0.75); border-radius: 12px; padding: 8px 12px; }
            #dialogTip { background: #eef6ff; border-left: 4px solid #3b82f6; padding: 10px; border-radius: 10px; color: #334155; }
            QGroupBox { border: 1px solid #e4eaf2; border-radius: 14px; margin-top: 12px; padding: 14px; font-weight: 700; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QLineEdit, QSpinBox, QComboBox { border: 1px solid #d8e1ec; border-radius: 10px; padding: 9px 10px; background: white; }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #3b82f6; }
            QPushButton { background: #eef2f7; border: 0; border-radius: 11px; padding: 10px 14px; font-weight: 700; color: #253449; }
            QPushButton:hover { background: #e1e8f2; }
            QPushButton:pressed { background: #d2dce9; }
            QPushButton#primaryButton { background: #1f3a5f; color: white; }
            QPushButton#primaryButton:hover { background: #284872; }
            QListWidget { border: 1px solid #e4eaf2; border-radius: 14px; background: #f8fafc; padding: 8px; }
            QListWidget::item { background: white; border-radius: 12px; margin: 5px; padding: 12px; }
            QListWidget::item:selected { background: #dbeafe; color: #0f172a; }
            QProgressBar { height: 10px; background: #e5eaf2; border: 0; border-radius: 5px; }
            QProgressBar::chunk { border-radius: 5px; background: #1f3a5f; }
            TimerCard { border: 1px solid #e4eaf2; border-radius: 20px; background: rgba(255,255,255,0.72); }
            TimerCard[active="true"] { border: 2px solid #3b82f6; background: #f7fbff; }
            TimerCard[warning="true"] { border: 2px solid #ef4444; background: #fff1f2; }
            #affirmativeCard QProgressBar::chunk { background: #16a34a; }
            #negativeCard QProgressBar::chunk { background: #dc2626; }
            #publicCard QProgressBar::chunk { background: #2563eb; }
            """
        )

    def _load_stages(self) -> list[Stage]:
        raw = load_json(STAGES_PATH, None)
        if not raw:
            return default_stages()
        try:
            stages = [Stage.from_dict(item) for item in raw]
            return stages or default_stages()
        except Exception:
            return default_stages()

    def _save_stages(self) -> None:
        save_json(STAGES_PATH, [asdict(stage) for stage in self.stages])

    def _toggle_sound(self) -> None:
        self.sound_enabled = self.sound_check.isChecked()
        self.preferences["sound"] = self.sound_enabled
        save_json(PREFERENCES_PATH, self.preferences)

    def _apply_solo_preset(self, seconds: int) -> None:
        self.solo_min_spin.setValue(seconds // 60)
        self.solo_sec_spin.setValue(seconds % 60)
        self._set_solo_duration(seconds)

    def _apply_custom_solo_duration(self) -> None:
        seconds = self.solo_min_spin.value() * 60 + self.solo_sec_spin.value()
        if seconds <= 0:
            QMessageBox.warning(self, "时长无效", "计时时长不能为 0。")
            return
        self._set_solo_duration(seconds)

    def _set_solo_duration(self, seconds: int) -> None:
        self.solo_timer.stop()
        self.solo_running = False
        self.solo_total = max(1, seconds)
        self.solo_remaining = self.solo_total
        self._refresh_solo()

    def _toggle_solo(self) -> None:
        if self.solo_running:
            self.solo_timer.stop()
            self.solo_running = False
        else:
            if self.solo_remaining <= 0:
                self.solo_remaining = self.solo_total
            self.solo_timer.start()
            self.solo_running = True
        self._refresh_solo()

    def _reset_solo(self) -> None:
        self.solo_timer.stop()
        self.solo_running = False
        self.solo_remaining = self.solo_total
        self._refresh_solo()

    def _tick_solo(self) -> None:
        self.solo_remaining = max(0, self.solo_remaining - 1)
        if self.sound_enabled and 0 < self.solo_remaining <= 3:
            QApplication.beep()
        if self.solo_remaining <= 0:
            self.solo_timer.stop()
            self.solo_running = False
            if self.sound_enabled:
                QApplication.beep()
        self._refresh_solo()

    def _refresh_solo(self) -> None:
        name = self.solo_title_input.text().strip() or "单独计时"
        self.solo_name_label.setText(name)
        self.solo_time_label.setText(format_time(self.solo_remaining))
        self.solo_start_btn.setText("暂停" if self.solo_running else "开始")
        self.solo_progress.setValue(max(0, min(1000, int(self.solo_remaining / self.solo_total * 1000))))

    def _render_stages(self) -> None:
        self.stage_list.blockSignals(True)
        self.stage_list.clear()
        for i, stage in enumerate(self.stages):
            item = QListWidgetItem(f"{i + 1}. {stage.name}\n{TEAM_LABELS.get(stage.team, stage.team)} · {stage.display_duration()}")
            self.stage_list.addItem(item)
        self.stage_list.setCurrentRow(self.current_stage_index)
        self.stage_list.blockSignals(False)

    def _jump_to_stage_from_list(self, row: int) -> None:
        if row < 0 or row >= len(self.stages) or row == self.current_stage_index:
            return
        self._pause_debate()
        self.current_stage_index = row
        self._reset_debate_stage()
        self._refresh_debate()

    def _current_stage(self) -> Stage:
        if not self.stages:
            self.stages = default_stages()
            self.current_stage_index = 0
        self.current_stage_index = max(0, min(self.current_stage_index, len(self.stages) - 1))
        return self.stages[self.current_stage_index]

    def _reset_debate_stage(self) -> None:
        stage = self._current_stage()
        self.aff_running = False
        self.neg_running = False
        self.public_running = False
        self.debate_clock.stop()
        self.aff_total = stage.affirmative_duration if stage.team in {"affirmative", "both"} else 0
        self.neg_total = stage.negative_duration if stage.team in {"negative", "both"} else 0
        self.public_total = stage.duration if stage.team == "public" else 0
        self.aff_remaining = self.aff_total
        self.neg_remaining = self.neg_total
        self.public_remaining = self.public_total

    def _start_current_debate_stage(self) -> None:
        stage = self._current_stage()
        if stage.team == "affirmative" and self.aff_remaining > 0:
            self.aff_running = True
        elif stage.team == "negative" and self.neg_remaining > 0:
            self.neg_running = True
        elif stage.team == "both":
            self.aff_running = self.aff_remaining > 0
            self.neg_running = self.neg_remaining > 0
        elif stage.team == "public" and self.public_remaining > 0:
            self.public_running = True
        if self.aff_running or self.neg_running or self.public_running:
            self.debate_clock.start()
        self._refresh_debate()

    def _pause_debate(self) -> None:
        self.aff_running = False
        self.neg_running = False
        self.public_running = False
        self.debate_clock.stop()
        self._refresh_debate()

    def _tick_debate(self) -> None:
        ticked = False
        if self.aff_running and self.aff_remaining > 0:
            self.aff_remaining -= 1
            ticked = True
        if self.neg_running and self.neg_remaining > 0:
            self.neg_remaining -= 1
            ticked = True
        if self.public_running and self.public_remaining > 0:
            self.public_remaining -= 1
            ticked = True
        if ticked:
            self.debate_elapsed += 1
        if self.sound_enabled and any(0 < value <= 3 for value in [self.aff_remaining if self.aff_running else 0, self.neg_remaining if self.neg_running else 0, self.public_remaining if self.public_running else 0]):
            QApplication.beep()
        if self.aff_remaining <= 0:
            self.aff_running = False
        if self.neg_remaining <= 0:
            self.neg_running = False
        if self.public_remaining <= 0:
            self.public_running = False
        if not (self.aff_running or self.neg_running or self.public_running):
            self.debate_clock.stop()
            if self.sound_enabled:
                QApplication.beep()
        self._refresh_debate()

    def _next_stage(self) -> None:
        if self.current_stage_index >= len(self.stages) - 1:
            QMessageBox.information(self, "流程结束", "已经是最后一个计时单元。")
            return
        self.current_stage_index += 1
        self._reset_debate_stage()
        self._render_stages()
        self._refresh_debate()

    def _reset_all_debate(self) -> None:
        self._pause_debate()
        self.current_stage_index = 0
        self.debate_elapsed = 0
        self._reset_debate_stage()
        self._render_stages()
        self._refresh_debate()

    def _refresh_debate(self) -> None:
        stage = self._current_stage()
        self.stage_title_label.setText(stage.name)
        self.stage_count_label.setText(f"{self.current_stage_index + 1}/{len(self.stages)}")
        self.aff_card.set_timer(self.aff_remaining, self.aff_total, self.aff_running or stage.team in {"affirmative", "both"})
        self.neg_card.set_timer(self.neg_remaining, self.neg_total, self.neg_running or stage.team in {"negative", "both"})
        self.public_card.set_timer(self.public_remaining, self.public_total, self.public_running or stage.team == "public")
        if stage.team == "both":
            total_text = f"本阶段预设：正方 {format_time(stage.affirmative_duration)} / 反方 {format_time(stage.negative_duration)}"
        else:
            total_text = f"本阶段预设：{format_time(stage.duration)}"
        self.stage_duration_label.setText(total_text)
        self.debate_elapsed_label.setText(f"实际已用：{format_time(self.debate_elapsed)}")

    def _refresh_all(self) -> None:
        self._refresh_solo()
        self._refresh_debate()

    def _add_stage(self) -> None:
        dialog = StageDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        stage = dialog.get_stage()
        if not stage:
            return
        insert_at = self.current_stage_index + 1 if self.stages else 0
        self.stages.insert(insert_at, stage)
        self.current_stage_index = insert_at
        self._save_stages()
        self._reset_debate_stage()
        self._render_stages()
        self._refresh_debate()

    def _edit_stage(self) -> None:
        if not self.stages:
            return
        stage = self._current_stage()
        dialog = StageDialog(self, stage)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_stage = dialog.get_stage()
        if not new_stage:
            return
        self.stages[self.current_stage_index] = new_stage
        self._save_stages()
        self._reset_debate_stage()
        self._render_stages()
        self._refresh_debate()

    def _delete_stage(self) -> None:
        if len(self.stages) <= 1:
            QMessageBox.warning(self, "不能删除", "至少保留一个计时单元。")
            return
        self.stages.pop(self.current_stage_index)
        self.current_stage_index = max(0, min(self.current_stage_index, len(self.stages) - 1))
        self._save_stages()
        self._reset_debate_stage()
        self._render_stages()
        self._refresh_debate()

    def _move_stage(self, direction: int) -> None:
        new_index = self.current_stage_index + direction
        if new_index < 0 or new_index >= len(self.stages):
            return
        self.stages[self.current_stage_index], self.stages[new_index] = self.stages[new_index], self.stages[self.current_stage_index]
        self.current_stage_index = new_index
        self._save_stages()
        self._render_stages()

    def _restore_default_stages(self) -> None:
        reply = QMessageBox.question(self, "恢复默认", "确定恢复默认流程？现有自定义流程会被覆盖。")
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.stages = default_stages()
        self.current_stage_index = 0
        self.debate_elapsed = 0
        self._save_stages()
        self._reset_debate_stage()
        self._render_stages()
        self._refresh_debate()

    def _export_stages(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出流程", "timer-flow.json", "JSON Files (*.json)")
        if not path:
            return
        Path(path).write_text(json.dumps([asdict(stage) for stage in self.stages], ensure_ascii=False, indent=2), encoding="utf-8")

    def _import_stages(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入流程", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            stages = [Stage.from_dict(item) for item in raw]
            if not stages:
                raise ValueError("empty stages")
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", f"无法读取该流程文件：{exc}")
            return
        self.stages = stages
        self.current_stage_index = 0
        self.debate_elapsed = 0
        self._save_stages()
        self._reset_debate_stage()
        self._render_stages()
        self._refresh_debate()

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "关于 Modular Timer",
            "Modular Timer 是一个本地运行的多用途计时器。\n\n"
            "设计重点不是堆功能，而是把每个计时任务拆成可复用的单元：单人计时、公共计时、正反方单独计时、正反方同时计时。\n\n"
            "适合辩论赛、课堂展示、面试练习、考试模拟、学习专注。",
        )

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self.tabs.currentIndex() == 0:
            if event.key() == Qt.Key.Key_Space:
                self._toggle_solo()
                return
            if event.key() == Qt.Key.Key_R:
                self._reset_solo()
                return
        else:
            if event.key() == Qt.Key.Key_Space:
                if self.debate_clock.isActive():
                    self._pause_debate()
                else:
                    self._start_current_debate_stage()
                return
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                self._next_stage()
                return
            if event.key() == Qt.Key.Key_R:
                self._reset_all_debate()
                return
        super().keyPressEvent(event)
