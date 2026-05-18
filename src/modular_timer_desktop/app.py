from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QProgressBar, QSpinBox, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget, QDialog
)

from . import __app_name__, __version__
from .settings import load_settings, save_settings

BASE_DIR = Path(__file__).resolve().parents[2]
ICON_PATH = BASE_DIR / "assets" / "app.ico"

MODES = {"single": "单模块", "parallel": "多模块同时", "manual": "手动独立", "sequential": "依次计时"}
ALARMS = {"global": "跟随全局", "mute": "静音", "end_once": "结束响一次", "last_10": "最后10秒提示"}


def fmt(sec: int) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


@dataclass
class TimerUnit:
    name: str = "计时模块"
    duration: int = 180
    color: str = "#2563EB"
    alarm_mode: str = "global"
    sound_path: str = ""
    remaining: int = 180
    running: bool = False

    def reset(self) -> None:
        self.remaining = self.duration
        self.running = False


@dataclass
class Stage:
    name: str = "新阶段"
    mode: str = "single"
    timers: list[TimerUnit] = field(default_factory=lambda: [TimerUnit()])


@dataclass
class Flow:
    schema: str = "modular-timer-flow-v2"
    name: str = "ModularTimer 自由流程"
    stages: list[Stage] = field(default_factory=list)


def default_flow() -> Flow:
    return Flow(stages=[
        Stage("单人汇报", "single", [TimerUnit("汇报人", 480, "#2563EB")]),
        Stage("自由辩论", "parallel", [TimerUnit("正方", 240, "#16A34A"), TimerUnit("反方", 240, "#DC2626")]),
        Stage("答辩问答", "sequential", [TimerUnit("提问", 120, "#D97706"), TimerUnit("回答", 180, "#7C3AED")]),
    ])


def flow_from_dict(data: dict[str, Any]) -> Flow:
    stages: list[Stage] = []
    for s in data.get("stages", []):
        timers = []
        for t in s.get("timers", []):
            u = TimerUnit(
                str(t.get("name", "计时模块")), int(t.get("duration", 180)),
                str(t.get("color", "#2563EB")), str(t.get("alarm_mode", "global")),
                str(t.get("sound_path", ""))
            )
            u.reset(); timers.append(u)
        stages.append(Stage(str(s.get("name", "新阶段")), str(s.get("mode", "single")), timers or [TimerUnit()]))
    return Flow(str(data.get("schema", "modular-timer-flow-v2")), str(data.get("name", "ModularTimer 自由流程")), stages or default_flow().stages)


class UnitDialog(QDialog):
    def __init__(self, parent: QWidget, unit: TimerUnit | None = None):
        super().__init__(parent)
        self.setWindowTitle("计时模块")
        self.unit = unit or TimerUnit()
        self.name = QLineEdit(self.unit.name)
        self.min = QSpinBox(); self.min.setRange(0, 999); self.min.setValue(self.unit.duration // 60)
        self.sec = QSpinBox(); self.sec.setRange(0, 59); self.sec.setValue(self.unit.duration % 60)
        self.color = QPushButton(self.unit.color); self.color.clicked.connect(self.pick_color)
        self.alarm = QComboBox(); self.alarm.addItems(list(ALARMS.values()))
        keys = list(ALARMS); self.alarm.setCurrentIndex(keys.index(self.unit.alarm_mode if self.unit.alarm_mode in keys else "global"))
        form = QFormLayout(self)
        form.addRow("名称", self.name)
        row = QHBoxLayout(); row.addWidget(self.min); row.addWidget(QLabel("分")); row.addWidget(self.sec); row.addWidget(QLabel("秒"))
        form.addRow("时长", row); form.addRow("颜色", self.color); form.addRow("铃声模式", self.alarm)
        ok = QPushButton("保存"); ok.clicked.connect(self.accept)
        cancel = QPushButton("取消"); cancel.clicked.connect(self.reject)
        br = QHBoxLayout(); br.addWidget(ok); br.addWidget(cancel); form.addRow(br)

    def pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self.color.text()), self)
        if c.isValid(): self.color.setText(c.name())

    def result_unit(self) -> TimerUnit:
        sec = max(1, self.min.value() * 60 + self.sec.value())
        keys = list(ALARMS)
        u = TimerUnit(self.name.text().strip() or "计时模块", sec, self.color.text(), keys[self.alarm.currentIndex()])
        u.reset(); return u


class FloatWindow(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main; self.drag: QPoint | None = None; self.locked = False
        self.setWindowTitle("PPT 悬浮计时")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        box = QFrame(); box.setObjectName("floatBox")
        self.stage = QLabel("阶段"); self.stage.setObjectName("floatStage")
        self.time = QLabel("00:00"); self.time.setObjectName("floatTime")
        lock = QPushButton("锁定/解锁"); lock.clicked.connect(self.toggle_lock)
        close = QPushButton("关闭"); close.clicked.connect(self.hide)
        lay = QVBoxLayout(box); lay.addWidget(self.stage); lay.addWidget(self.time)
        row = QHBoxLayout(); row.addWidget(lock); row.addWidget(close); lay.addLayout(row)
        root = QVBoxLayout(self); root.addWidget(box); self.resize(560, 190)

    def toggle_lock(self): self.locked = not self.locked
    def mousePressEvent(self, e):
        if not self.locked and e.button() == Qt.LeftButton: self.drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if self.drag and not self.locked: self.move(e.globalPosition().toPoint() - self.drag)
    def mouseReleaseEvent(self, e): self.drag = None
    def refresh(self):
        s = self.main.stage()
        self.stage.setText(s.name if s else "暂无阶段")
        self.time.setText("  |  ".join(f"{t.name} {fmt(t.remaining)}" for t in s.timers) if s else "00:00")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__app_name__} v{__version__} - 自由流程计时器")
        if ICON_PATH.exists(): self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.settings = load_settings({"flow": asdict(default_flow()), "alarm": "last_10"})
        self.flow = flow_from_dict(self.settings.get("flow", asdict(default_flow())))
        self.index = 0; self.cards: list[QFrame] = []
        self.float = FloatWindow(self)
        self.timer = QTimer(self); self.timer.setInterval(1000); self.timer.timeout.connect(self.tick); self.timer.start()
        self.ui(); self.keys(); self.style(); self.reset_stage()

    def ui(self):
        tabs = QTabWidget(); self.setCentralWidget(tabs)
        main = QWidget(); root = QVBoxLayout(main)
        self.title = QLabel(self.flow.name); self.title.setObjectName("title")
        self.stage_label = QLabel(); root.addWidget(self.title); root.addWidget(self.stage_label)
        body = QHBoxLayout(); self.tree = QTreeWidget(); self.tree.setHeaderLabels(["阶段", "模式"]); self.tree.itemClicked.connect(self.choose_stage); body.addWidget(self.tree, 1)
        self.grid_wrap = QWidget(); self.grid = QGridLayout(self.grid_wrap); body.addWidget(self.grid_wrap, 2); root.addLayout(body)
        controls = QHBoxLayout()
        for txt, fn in [("开始/暂停", self.toggle_stage), ("下一阶段", self.next_stage), ("重置阶段", self.reset_stage), ("PPT悬浮", self.show_float)]:
            b = QPushButton(txt); b.clicked.connect(fn); controls.addWidget(b)
        root.addLayout(controls); tabs.addTab(main, "计时")
        edit = QWidget(); er = QVBoxLayout(edit)
        self.editor = QTreeWidget(); self.editor.setHeaderLabels(["流程/模块", "信息"]); er.addWidget(self.editor)
        row = QHBoxLayout()
        for txt, fn in [("添加阶段", self.add_stage), ("删除阶段", self.del_stage), ("添加模块", self.add_unit), ("编辑模块", self.edit_unit), ("删除模块", self.del_unit), ("导入JSON", self.import_flow), ("导出JSON", self.export_flow), ("保存", self.save)]:
            b = QPushButton(txt); b.clicked.connect(fn); row.addWidget(b)
        er.addLayout(row); tabs.addTab(edit, "流程编辑")
        self.resize(1150, 720)

    def keys(self):
        QShortcut(QKeySequence("Space"), self, activated=self.toggle_stage)
        QShortcut(QKeySequence("Return"), self, activated=self.next_stage)
        QShortcut(QKeySequence("R"), self, activated=self.reset_stage)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.float.toggle_lock)

    def stage(self) -> Stage | None:
        if not self.flow.stages: return None
        self.index = max(0, min(self.index, len(self.flow.stages) - 1)); return self.flow.stages[self.index]

    def refresh(self):
        s = self.stage(); self.title.setText(self.flow.name)
        self.stage_label.setText(f"{self.index + 1}/{len(self.flow.stages)} · {s.name if s else '无'}")
        self.tree.clear(); self.editor.clear()
        for i, st in enumerate(self.flow.stages):
            self.tree.addTopLevelItem(QTreeWidgetItem([f"{i+1}. {st.name}", MODES.get(st.mode, st.mode)]))
            si = QTreeWidgetItem([st.name, MODES.get(st.mode, st.mode)]); self.editor.addTopLevelItem(si)
            for t in st.timers: si.addChild(QTreeWidgetItem([t.name, f"{fmt(t.duration)} · {ALARMS.get(t.alarm_mode, t.alarm_mode)}"])); si.setExpanded(True)
        while self.grid.count():
            w = self.grid.takeAt(0).widget();
            if w: w.setParent(None)
        if s:
            for i, t in enumerate(s.timers): self.grid.addWidget(self.card(t, i), i // 2, i % 2)
        self.float.refresh()

    def card(self, t: TimerUnit, i: int) -> QFrame:
        f = QFrame(); f.setObjectName("card"); f.setStyleSheet(f"QFrame#card{{border-left:8px solid {t.color};}}")
        name = QLabel(t.name); name.setObjectName("unit")
        time = QLabel(fmt(t.remaining)); time.setObjectName("time")
        p = QProgressBar(); p.setRange(0, max(1, t.duration)); p.setValue(t.remaining); p.setTextVisible(False)
        b = QPushButton("开始/暂停"); b.clicked.connect(lambda: self.toggle_unit(i))
        r = QPushButton("重置"); r.clicked.connect(lambda: self.reset_unit(i))
        lay = QVBoxLayout(f); lay.addWidget(name); lay.addWidget(time); lay.addWidget(p)
        row = QHBoxLayout(); row.addWidget(b); row.addWidget(r); lay.addLayout(row); return f

    def choose_stage(self, item): self.index = self.tree.indexOfTopLevelItem(item); self.reset_stage()
    def toggle_unit(self, i):
        s = self.stage();
        if s and 0 <= i < len(s.timers): s.timers[i].running = not s.timers[i].running
        self.refresh()
    def reset_unit(self, i):
        s = self.stage();
        if s and 0 <= i < len(s.timers): s.timers[i].reset()
        self.refresh()
    def toggle_stage(self):
        s = self.stage();
        if not s: return
        if any(t.running for t in s.timers):
            for t in s.timers: t.running = False
        elif s.mode in ("single", "parallel", "manual"):
            for t in s.timers: t.running = t.remaining > 0
        else:
            for t in s.timers: t.running = False
            next((setattr(t, "running", True) for t in s.timers if t.remaining > 0), None)
        self.refresh()
    def next_stage(self):
        if self.index < len(self.flow.stages) - 1: self.index += 1; self.reset_stage()
    def reset_stage(self):
        s = self.stage();
        if s:
            for t in s.timers: t.reset()
        self.refresh()
    def tick(self):
        s = self.stage();
        if not s: return
        for t in s.timers:
            if t.running and t.remaining > 0:
                t.remaining -= 1
                if t.alarm_mode != "mute" and (t.remaining == 0 or (t.alarm_mode in ("global", "last_10") and 0 < t.remaining <= 10)): QApplication.beep()
                if t.remaining == 0:
                    t.running = False
                    if s.mode == "sequential":
                        for n in s.timers:
                            if n.remaining > 0: n.running = True; break
        self.refresh()
    def selected_stage_index(self):
        item = self.editor.currentItem();
        if not item: return self.index
        return self.editor.indexOfTopLevelItem(item if not item.parent() else item.parent())
    def selected_unit(self):
        item = self.editor.currentItem();
        if item and item.parent(): return self.editor.indexOfTopLevelItem(item.parent()), item.parent().indexOfChild(item)
        return None
    def add_stage(self):
        name, ok = QInputDialog.getText(self, "阶段", "阶段名称")
        if not ok: return
        mode, ok = QInputDialog.getItem(self, "模式", "选择模式", list(MODES.values()), 0, False)
        key = list(MODES)[list(MODES.values()).index(mode)] if ok else "single"
        self.flow.stages.append(Stage(name or "新阶段", key, [TimerUnit()])); self.save()
    def del_stage(self):
        if len(self.flow.stages) <= 1: return
        self.flow.stages.pop(self.selected_stage_index()); self.index = min(self.index, len(self.flow.stages)-1); self.save()
    def add_unit(self):
        dlg = UnitDialog(self)
        if dlg.exec() == QDialog.Accepted: self.flow.stages[self.selected_stage_index()].timers.append(dlg.result_unit()); self.save()
    def edit_unit(self):
        sel = self.selected_unit();
        if not sel: return
        s, u = sel; dlg = UnitDialog(self, self.flow.stages[s].timers[u])
        if dlg.exec() == QDialog.Accepted: self.flow.stages[s].timers[u] = dlg.result_unit(); self.save()
    def del_unit(self):
        sel = self.selected_unit();
        if sel and len(self.flow.stages[sel[0]].timers) > 1: self.flow.stages[sel[0]].timers.pop(sel[1]); self.save()
    def import_flow(self):
        p, _ = QFileDialog.getOpenFileName(self, "导入", "", "JSON (*.json)")
        if p: self.flow = flow_from_dict(json.loads(Path(p).read_text(encoding="utf-8"))); self.index = 0; self.save()
    def export_flow(self):
        p, _ = QFileDialog.getSaveFileName(self, "导出", f"{self.flow.name}.json", "JSON (*.json)")
        if p: Path(p).write_text(json.dumps(asdict(self.flow), ensure_ascii=False, indent=2), encoding="utf-8")
    def show_float(self): self.float.refresh(); self.float.show(); self.float.raise_()
    def save(self): save_settings({"flow": asdict(self.flow), "alarm": "last_10"}); self.refresh()
    def closeEvent(self, e): self.save(); self.float.close(); super().closeEvent(e)
    def style(self):
        self.setStyleSheet("""
        QWidget{font-family:'Microsoft YaHei','Segoe UI';font-size:14px} QMainWindow{background:#F6F7FB}
        QLabel#title{font-size:26px;font-weight:900;color:#111827} QLabel#unit{font-size:18px;font-weight:800;color:#374151}
        QLabel#time{font-size:56px;font-weight:900;font-family:Consolas;color:#111827}
        QFrame#card{background:white;border:1px solid #E5E7EB;border-radius:18px;padding:14px}
        QPushButton{background:#2563EB;color:white;border:0;border-radius:10px;padding:9px 14px;font-weight:700} QPushButton:hover{background:#1D4ED8}
        QTreeWidget,QLineEdit,QComboBox,QSpinBox{background:white;border:1px solid #D1D5DB;border-radius:8px;padding:6px}
        QProgressBar{height:10px;border-radius:5px;background:#E5E7EB} QProgressBar::chunk{border-radius:5px;background:#2563EB}
        QFrame#floatBox{background:rgba(17,24,39,225);border-radius:22px;padding:18px} QLabel#floatStage{color:#D1D5DB;font-size:20px;font-weight:800}
        QLabel#floatTime{color:white;font-size:42px;font-weight:900;font-family:Consolas}
        """)
