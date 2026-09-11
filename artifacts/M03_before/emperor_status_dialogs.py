"""Atomic manual editors for the emperor's health and effect modifiers."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLineEdit, QPushButton, QSpinBox, QTableWidget,
    QVBoxLayout, QWidget,
)

from dynasty.core import GameSession
from dynasty.core.emperor import (
    ATTRIBUTE_DEFINITIONS, SKILL_DEFINITIONS, BodyCondition, EmperorModifier,
)
from dynasty.ui.emperor_page import text_label


class _RowTable(QTableWidget):
    """Keep the row containing the focused cell editor selected for removal."""

    def __init__(self, headers: list[str]) -> None:
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setDefaultSectionSize(44)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setMinimumHeight(190)

    def put(self, row: int, column: int, widget: QWidget) -> None:
        self.setCellWidget(row, column, widget)
        widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() in {QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress}:
            for row in range(self.rowCount()):
                for column in range(self.columnCount()):
                    if self.cellWidget(row, column) is watched:
                        self.setCurrentCell(row, column)
                        return False
        return super().eventFilter(watched, event)

    def remove_selected(self) -> None:
        row = self.currentRow()
        if row >= 0:
            self.removeRow(row)


def _combo(options: tuple[tuple[str, str], ...], selected: str) -> QComboBox:
    widget = QComboBox()
    for value, title in options:
        widget.addItem(title, value)
    widget.setCurrentIndex(widget.findData(selected))
    return widget


def _integer(raw: str, field: str) -> int:
    raw = raw.strip()
    digits = raw[1:] if raw.startswith(("+", "-")) else raw
    if not digits or not digits.isascii() or not digits.isdecimal():
        raise ValueError(f"{field}：请输入有效整数。")
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{field}：请输入有效整数。") from error


class _StatusEditor(QDialog):
    def __init__(self, session: GameSession, parent: QWidget | None, title: str, hint: str) -> None:
        super().__init__(parent)
        self.session = session
        self.result_message = ""
        self.setWindowTitle(title)
        self.resize(1040, 640)
        self.setMinimumSize(860, 520)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(24, 22, 24, 22)
        self.body.setSpacing(14)
        self.body.addWidget(text_label(title, "title"))
        self.body.addWidget(text_label(hint, "subtitle"))

    def finish_layout(self, hint: str) -> None:
        self.error_label = text_label(hint, "feedback")
        self.body.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.save_button = self.buttons.addButton("应用修改", QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_button.setProperty("primary", True)
        self.buttons.accepted.connect(self.apply_values)
        self.buttons.rejected.connect(self.reject)
        self.body.addWidget(self.buttons)

    def row_controls(self, table: _RowTable, add_callback, title: str) -> None:
        controls = QHBoxLayout()
        self.add_button = QPushButton(title)
        self.add_button.clicked.connect(lambda _checked=False: add_callback())
        self.remove_button = QPushButton("删除所选行")
        self.remove_button.clicked.connect(table.remove_selected)
        controls.addWidget(self.add_button)
        controls.addWidget(self.remove_button)
        controls.addStretch()
        self.body.addLayout(controls)

    def fail(self, message: str) -> None:
        self.error_label.setText(f"{message} 尚未应用任何修改。")
        self.error_label.setProperty("error", True)
        self.error_label.style().unpolish(self.error_label)
        self.error_label.style().polish(self.error_label)

    def apply_values(self) -> None:
        raise NotImplementedError


class EmperorHealthEditor(_StatusEditor):
    """Edit overall health, pressure, and abnormal body parts as one transaction."""

    def __init__(
        self, session: GameSession, parent: QWidget | None = None,
        activity_draft: list[str | None] | None = None,
    ) -> None:
        super().__init__(session, parent, "手动调整 · 健康状态",
                         "健康决定可用行动力；压力与异常部位在此记录，暂不自动产生疾病或属性变化。")
        self.activity_draft = list(activity_draft) if activity_draft is not None else None
        overview = QHBoxLayout()
        self.health_input = QSpinBox()
        self.health_input.setRange(0, 100)
        self.health_input.setValue(session.state.health)
        self.health_input.setAccessibleName("整体健康")
        self.pressure_input = QSpinBox()
        self.pressure_input.setRange(0, 100)
        self.pressure_input.setValue(session.state.emperor.pressure)
        self.pressure_input.setAccessibleName("压力")
        for title, widget in (("整体健康（0–100）", self.health_input),
                              ("压力（0–100）", self.pressure_input)):
            form = QFormLayout()
            form.addRow(title, widget)
            overview.addLayout(form, 1)
        self.body.addLayout(overview)
        self.body.addWidget(text_label("异常身体部位", "sectionTitle"))
        self.body.addWidget(text_label("只记录患病、受伤或残疾的部位；没有记录时，部位列表为空。", "subtitle"))
        self.conditions_table = _RowTable(["身体部位", "异常类型", "状态名称"])
        self.conditions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.body.addWidget(self.conditions_table, 1)
        self.row_controls(self.conditions_table, self.add_condition, "＋ 添加异常部位")
        for condition in session.state.emperor.body_conditions:
            self.add_condition(condition)
        self.finish_layout("修改将在所有内容通过校验后一起应用；取消会保留原状态。")

    def add_condition(self, condition: BodyCondition | None = None) -> None:
        table = self.conditions_table
        row = table.rowCount()
        table.insertRow(row)
        part = QLineEdit(condition.part if condition else "")
        part.setPlaceholderText("如：左腿、眼睛")
        kind = _combo((("disease", "疾病"), ("disability", "残疾"), ("injury", "伤势")),
                      condition.kind if condition else "disease")
        name = QLineEdit(condition.name if condition else "")
        name.setPlaceholderText("填写具体状态")
        for column, widget in enumerate((part, kind, name)):
            table.put(row, column, widget)
        table.setCurrentCell(row, 0)
        table.scrollToBottom()

    def apply_values(self) -> None:
        new_health = self.health_input.value()
        if self.activity_draft is not None:
            count = sum(value is not None for value in self.activity_draft)
            capacity = self.session.config.action_points(new_health)
            if count > capacity:
                self.fail(f"新健康值只提供 {capacity} 点行动力，当前活动草稿已安排 {count} 项。请先减少活动安排。")
                return
        conditions = []
        for row in range(self.conditions_table.rowCount()):
            part = self.conditions_table.cellWidget(row, 0).text().strip()
            kind = self.conditions_table.cellWidget(row, 1).currentData()
            name = self.conditions_table.cellWidget(row, 2).text().strip()
            if not part or not name:
                self.fail(f"第 {row + 1} 行：请填写身体部位和状态名称。")
                return
            conditions.append(BodyCondition(part=part, name=name, kind=kind))
        result = self.session.update_emperor_health(new_health, self.pressure_input.value(), conditions)
        if not result.ok:
            self.fail(result.message)
            return
        self.result_message = result.message
        self.accept()


class EmperorModifierEditor(_StatusEditor):
    """Edit explicit effects without changing the emperor's learned proficiency."""

    def __init__(self, session: GameSession, parent: QWidget | None = None) -> None:
        super().__init__(session, parent, "手动调整 · 长短期修正",
                         "属性修正按点数加减；技能效果按百分比点叠加，不改变已学熟练度。可填写正负整数，不以 100 封顶。")
        self.body.addWidget(text_label(
            "长期修正保留至手动移除；短期修正每完成一旬减少一旬。一个修正对应一个目标，多项效果可分行填写。", "subtitle"))
        self.modifiers_table = _RowTable(["修正名称", "来源（可空）", "期限", "目标类型", "作用目标", "修正值", "剩余旬数"])
        self.modifiers_table.horizontalHeader().setMinimumSectionSize(92)
        self.modifiers_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.modifiers_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.body.addWidget(self.modifiers_table, 1)
        self.row_controls(self.modifiers_table, self.add_modifier, "＋ 添加修正")
        for modifier in session.state.emperor.modifiers:
            self.add_modifier(modifier)
        self.finish_layout("长期修正无需剩余旬数；短期修正的剩余旬数须为正整数。")

    def add_modifier(self, modifier: EmperorModifier | None = None) -> None:
        table = self.modifiers_table
        row = table.rowCount()
        table.insertRow(row)
        name = QLineEdit(modifier.name if modifier else "")
        name.setPlaceholderText("填写修正名称")
        source = QLineEdit(modifier.source if modifier else "")
        source.setPlaceholderText("可留空")
        duration = _combo((("long_term", "长期"), ("short_term", "短期")),
                          modifier.duration if modifier else "long_term")
        target_type = _combo((("attribute", "属性点数"), ("skill_effect", "技能效果 %")),
                             modifier.target_type if modifier else "attribute")
        target = QComboBox()
        amount = QLineEdit(str(modifier.amount) if modifier else "0")
        remaining = QLineEdit(str(modifier.remaining_turns) if modifier and modifier.remaining_turns else "1")
        remaining.setProperty("shortTermTurns", remaining.text())
        self._change_target(target_type, target, amount)
        if modifier is not None:
            target.setCurrentIndex(target.findData(modifier.target))
        self._change_duration(duration, remaining)
        target_type.currentIndexChanged.connect(lambda _index: self._change_target(target_type, target, amount))
        duration.currentIndexChanged.connect(lambda _index: self._change_duration(duration, remaining))
        for column, widget in enumerate((name, source, duration, target_type, target, amount, remaining)):
            table.put(row, column, widget)
        table.setCurrentCell(row, 0)
        table.scrollToBottom()

    @staticmethod
    def _change_target(target_type: QComboBox, target: QComboBox, amount: QLineEdit) -> None:
        previous = target.currentData()
        attribute = target_type.currentData() == "attribute"
        definitions = ATTRIBUTE_DEFINITIONS if attribute else SKILL_DEFINITIONS
        target.clear()
        for definition in definitions:
            target.addItem(definition.label, definition.id)
        index = target.findData(previous)
        target.setCurrentIndex(index if index >= 0 else 0)
        amount.setPlaceholderText("± 点数" if attribute else "± 百分比点")
        amount.setToolTip("属性点数加减，如 -10、+20" if attribute else "技能效果百分比点，如 -20 为 -20%，+50 为 +50%")

    @staticmethod
    def _change_duration(duration: QComboBox, remaining: QLineEdit) -> None:
        short_term = duration.currentData() == "short_term"
        if short_term:
            remaining.setText(remaining.property("shortTermTurns") or "1")
        else:
            if remaining.text() != "—":
                remaining.setProperty("shortTermTurns", remaining.text())
            remaining.setText("—")
        remaining.setEnabled(short_term)

    def apply_values(self) -> None:
        modifiers = []
        table = self.modifiers_table
        for row in range(table.rowCount()):
            try:
                name = table.cellWidget(row, 0).text().strip()
                if not name:
                    raise ValueError(f"第 {row + 1} 行：请填写修正名称。")
                source = table.cellWidget(row, 1).text().strip()
                duration = table.cellWidget(row, 2).currentData()
                target_type = table.cellWidget(row, 3).currentData()
                target = table.cellWidget(row, 4).currentData()
                amount = _integer(table.cellWidget(row, 5).text(), f"第 {row + 1} 行修正值")
                remaining = None
                if duration == "short_term":
                    remaining = _integer(table.cellWidget(row, 6).text(), f"第 {row + 1} 行剩余旬数")
                    if remaining < 1:
                        raise ValueError(f"第 {row + 1} 行：短期修正的剩余旬数须为正整数。")
                modifiers.append(EmperorModifier(name=name, source=source, duration=duration,
                                                target_type=target_type, target=target,
                                                amount=amount, remaining_turns=remaining))
            except ValueError as error:
                self.fail(str(error))
                return
        result = self.session.update_emperor_modifiers(modifiers)
        if not result.ok:
            self.fail(result.message)
            return
        self.result_message = result.message
        self.accept()
