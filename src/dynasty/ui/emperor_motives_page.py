"""Personality tendencies and pursuits earned through completed activities."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLineEdit,
    QPlainTextEdit, QProgressBar, QPushButton, QSlider, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from dynasty.core import ACTIVITY_LABELS, GameSession
from dynasty.core.motives import PERSONALITY_DIMENSIONS
from dynasty.ui.emperor_page import panel, scroll_content, text_label


KIND_LABELS = {"desire": "近期欲望", "ambition": "长期野心"}


def _progress_bar(name: str = "pursuitProgress") -> QProgressBar:
    bar = QProgressBar()
    bar.setObjectName(name)
    bar.setRange(0, 100)
    bar.setTextVisible(False)
    bar.setFixedHeight(7)
    return bar


def _dialog_buttons(dialog, layout: QVBoxLayout, title: str) -> None:
    dialog.error_label = text_label("", "feedback")
    dialog.error_label.hide()
    layout.addWidget(dialog.error_label)
    dialog.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
    dialog.save_button = dialog.buttons.addButton(title, QDialogButtonBox.ButtonRole.AcceptRole)
    dialog.save_button.setProperty("primary", True)
    dialog.buttons.accepted.connect(dialog.apply_values)
    dialog.buttons.rejected.connect(dialog.reject)
    layout.addWidget(dialog.buttons)


class EmperorPersonalityEditor(QDialog):
    """Edit the nine independent personality axes without altering abilities."""

    def __init__(self, session: GameSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.result_message = ""
        self.setWindowTitle("手动调整 · 性格倾向")
        self.resize(780, 640)
        self.setMinimumSize(650, 530)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        layout.addWidget(text_label("性格倾向", "title"))
        layout.addWidget(text_label(
            "0 偏向左侧，100 偏向右侧，50 居中。这是可手动调整的演示量表，不代表历史评价。", "subtitle"))
        self.inputs: dict[str, QSpinBox] = {}
        self.sliders: dict[str, QSlider] = {}
        scroll, content = scroll_content()
        content.setContentsMargins(8, 8, 8, 8)
        content.setSpacing(5)
        for dimension in PERSONALITY_DIMENSIONS:
            row = QHBoxLayout()
            left = text_label(dimension.left)
            left.setFixedWidth(44)
            left.setToolTip(dimension.description)
            right = text_label(dimension.right)
            right.setFixedWidth(44)
            right.setToolTip(dimension.description)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setObjectName("personalitySlider")
            slider.setRange(0, 100)
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            slider.setTickInterval(50)
            slider.setValue(session.state.emperor.personality[dimension.id])
            value = QSpinBox()
            value.setRange(0, 100)
            value.setValue(slider.value())
            value.setAccessibleName(f"{dimension.left}与{dimension.right}倾向")
            value.setFixedWidth(74)
            slider.valueChanged.connect(value.setValue)
            value.valueChanged.connect(slider.setValue)
            self.inputs[dimension.id] = value
            self.sliders[dimension.id] = slider
            row.addWidget(left)
            row.addWidget(slider, 1)
            row.addWidget(right)
            row.addSpacing(8)
            row.addWidget(value)
            content.addLayout(row)
        content.addStretch()
        layout.addWidget(scroll, 1)
        _dialog_buttons(self, layout, "应用修改")

    def apply_values(self) -> None:
        result = self.session.update_emperor_personality({key: widget.value() for key, widget in self.inputs.items()})
        if not result.ok:
            self.error_label.setText(result.message)
            self.error_label.show()
            return
        self.result_message = result.message
        self.accept()


class EmperorObjectiveEditor(QDialog):
    """Set a player-authored pursuit; opening and saving cannot fulfill it."""

    def __init__(self, session: GameSession, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if kind not in KIND_LABELS:
            raise ValueError("目标类型须为近期欲望或长期野心。")
        self.session = session
        self.kind = kind
        self.result_message = ""
        self.setWindowTitle(f"设立{KIND_LABELS[kind]}")
        self.resize(670, 540)
        self.setMinimumSize(540, 490)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        layout.addWidget(text_label(f"设立{KIND_LABELS[kind]}", "title"))
        layout.addWidget(text_label(
            "自定义皇帝当前的追求。只有设立后实际完成的对应活动，才会推进目标。", "subtitle"))
        form = QFormLayout()
        form.setSpacing(12)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("如：静心读书（可自行命名）")
        self.description_input = QPlainTextEdit()
        self.description_input.setPlaceholderText("补充这项目标的想法，可留空")
        self.description_input.setMaximumHeight(110)
        self.activity_input = QComboBox()
        for value, label in ACTIVITY_LABELS.items():
            self.activity_input.addItem(label, value)
        self.activity_input.setCurrentIndex(self.activity_input.findData("study"))
        self.target_count_input = QLineEdit("1" if kind == "desire" else "6")
        self.target_count_input.setPlaceholderText("正整数，可自行调整")
        form.addRow("目标名称", self.title_input)
        form.addRow("说明", self.description_input)
        form.addRow("对应活动", self.activity_input)
        form.addRow("完成次数", self.target_count_input)
        layout.addLayout(form)
        layout.addWidget(text_label(
            "次数是编辑建议，可以修改。目标满足后保留记录；奖励与其他数值效果尚未设定。", "subtitle"))
        layout.addStretch()
        _dialog_buttons(self, layout, "设立目标")

    def apply_values(self) -> None:
        raw = self.target_count_input.text().strip()
        try:
            if not raw or not raw.isascii() or not raw.isdecimal() or int(raw) < 1:
                raise ValueError
            target = int(raw)
        except ValueError:
            self.error_label.setText("完成次数须为正整数。尚未设立目标。")
            self.error_label.show()
            self.target_count_input.setFocus()
            return
        result = self.session.add_emperor_objective(
            self.kind, self.title_input.text().strip(), self.description_input.toPlainText().strip(),
            self.activity_input.currentData(), target,
        )
        if not result.ok:
            self.error_label.setText(result.message)
            self.error_label.show()
            return
        self.result_message = result.message
        self.accept()


class EmperorMotivesPage(QWidget):
    updated = Signal(str)
    activity_requested = Signal(str)

    def __init__(self, session: GameSession) -> None:
        super().__init__()
        self.session = session
        self.personality_values = {}
        self.personality_bars = {}
        self.objective_cards = {}
        self.objective_progress_labels = {}
        self.objective_activity_buttons = {}
        self.objective_discard_buttons = {}
        self.objective_add_buttons = {}
        self.objective_layouts = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        columns = QHBoxLayout()
        columns.setSpacing(14)
        personality_scroll, personality = scroll_content()
        personality.setContentsMargins(16, 10, 16, 10)
        personality.setSpacing(4)
        personality_scroll.setMinimumWidth(285)
        heading = QHBoxLayout()
        heading.addWidget(text_label("性格倾向", "sectionTitle"), 1)
        self.personality_edit_button = QPushButton("手动调整…")
        self.personality_edit_button.clicked.connect(self.edit_personality)
        heading.addWidget(self.personality_edit_button)
        personality.addLayout(heading)
        personality.addWidget(text_label("演示量表 0–100，50 居中；悬停两端查看释义。", "subtitle"))
        for dimension in PERSONALITY_DIMENSIONS:
            axis = QWidget()
            axis.setToolTip(dimension.description)
            axis_layout = QVBoxLayout(axis)
            axis_layout.setContentsMargins(0, 0, 0, 0)
            axis_layout.setSpacing(2)
            endpoints = QHBoxLayout()
            endpoints.addWidget(text_label(dimension.left))
            value = text_label("", "emperorHint")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            endpoints.addWidget(value, 1)
            endpoints.addWidget(text_label(dimension.right))
            bar = _progress_bar("personalityBar")
            bar.setFixedHeight(5)
            bar.setAccessibleName(f"{dimension.left}至{dimension.right}倾向")
            self.personality_values[dimension.id] = value
            self.personality_bars[dimension.id] = bar
            axis_layout.addLayout(endpoints)
            axis_layout.addWidget(bar)
            personality.addWidget(axis)
        personality.addStretch()
        columns.addWidget(personality_scroll, 4)
        self.tabs = QTabWidget()
        for kind, title in KIND_LABELS.items():
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 10, 0, 0)
            add_row = QHBoxLayout()
            add_row.setContentsMargins(14, 0, 14, 0)
            add_row.addWidget(text_label("由玩家设立，完成活动来满足。", "subtitle"), 1)
            add_button = QPushButton(f"＋ 设立{title}")
            add_button.clicked.connect(lambda _checked=False, value=kind: self.add_objective(value))
            self.objective_add_buttons[kind] = add_button
            add_row.addWidget(add_button)
            tab_layout.addLayout(add_row)
            scroll, objectives = scroll_content()
            self.objective_layouts[kind] = objectives
            tab_layout.addWidget(scroll, 1)
            self.tabs.addTab(tab, title)
        columns.addWidget(self.tabs, 6)
        layout.addLayout(columns, 1)
        self.feedback = text_label(
            "完成目标会留下满足记录；性格对学习的影响、数值奖励与其他效果尚未设定。", "subtitle")
        layout.addWidget(self.feedback)
        self.refresh(session)

    def refresh(self, session: GameSession) -> None:
        self.session = session
        for dimension in PERSONALITY_DIMENSIONS:
            value = session.state.emperor.personality[dimension.id]
            self.personality_values[dimension.id].setText(str(value))
            self.personality_bars[dimension.id].setValue(value)
            tendency = "居中" if value == 50 else f"偏向{dimension.left if value < 50 else dimension.right}"
            self.personality_values[dimension.id].setToolTip(tendency)
        for layout in self.objective_layouts.values():
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
        self.objective_cards.clear()
        self.objective_progress_labels.clear()
        self.objective_activity_buttons.clear()
        self.objective_discard_buttons.clear()
        for kind, layout in self.objective_layouts.items():
            objectives = [item for item in session.state.emperor.objectives if item.kind == kind]
            objectives.sort(key=lambda item: item.status == "fulfilled")
            if not objectives:
                empty, empty_layout = panel()
                empty_layout.addWidget(text_label(f"暂无{KIND_LABELS[kind]}", "sectionTitle"))
                empty_layout.addWidget(text_label("设立一个目标，再到朝政页安排对应活动。", "subtitle"))
                layout.addWidget(empty)
            for objective in objectives:
                layout.addWidget(self._objective_card(objective))
            layout.addStretch()

    def _objective_card(self, objective) -> QWidget:
        card, layout = panel()
        self.objective_cards[objective.id] = card
        title_row = QHBoxLayout()
        title_row.addWidget(text_label(objective.title, "sectionTitle"), 1)
        fulfilled = objective.status == "fulfilled"
        completed_label = "已满足" if objective.kind == "desire" else "已达成"
        title_row.addWidget(text_label(completed_label if fulfilled else "进行中", "emperorHint"))
        layout.addLayout(title_row)
        if objective.description:
            layout.addWidget(text_label(objective.description, "subtitle"))
        activity_label = ACTIVITY_LABELS[objective.activity_kind]
        progress = text_label(f"完成{activity_label} · {objective.progress} / {objective.target_count} 次")
        self.objective_progress_labels[objective.id] = progress
        layout.addWidget(progress)
        bar = _progress_bar()
        bar.setValue(min(100, objective.progress * 100 // objective.target_count))
        layout.addWidget(bar)
        if fulfilled:
            completed_at = f"第 {objective.completed_turn + 1} 旬完成" if objective.completed_turn is not None else completed_label
            layout.addWidget(text_label(f"{completed_at} · 完成记录会保留。", "subtitle"))
        else:
            actions = QHBoxLayout()
            arrange = QPushButton(f"安排{activity_label} →")
            arrange.setProperty("primary", True)
            arrange.clicked.connect(lambda _checked=False, kind=objective.activity_kind: self.activity_requested.emit(kind))
            self.objective_activity_buttons[objective.id] = arrange
            discard = QPushButton("撤下目标")
            discard.clicked.connect(lambda _checked=False, key=objective.id: self.discard_objective(key))
            self.objective_discard_buttons[objective.id] = discard
            actions.addWidget(arrange)
            actions.addStretch()
            actions.addWidget(discard)
            layout.addLayout(actions)
        return card

    def edit_personality(self) -> None:
        dialog = EmperorPersonalityEditor(self.session, self)
        result = dialog.exec()
        message = dialog.result_message
        dialog.deleteLater()
        if result == QDialog.DialogCode.Accepted:
            self.refresh(self.session)
            self.updated.emit(message)

    def add_objective(self, kind: str) -> None:
        dialog = EmperorObjectiveEditor(self.session, kind, self)
        result = dialog.exec()
        message = dialog.result_message
        dialog.deleteLater()
        if result == QDialog.DialogCode.Accepted:
            self.refresh(self.session)
            self.updated.emit(message)

    def discard_objective(self, objective_id: str) -> None:
        result = self.session.discard_emperor_objective(objective_id)
        if result.ok:
            self.refresh(self.session)
            self.updated.emit(result.message)
        else:
            self.feedback.setText(result.message)
