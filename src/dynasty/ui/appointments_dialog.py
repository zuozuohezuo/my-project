"""Future appointments, explicit attendance decisions and retained history."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from dynasty.core import GameSession, Phase
from dynasty.ui.emperor_page import panel, text_label


class AppointmentsDialog(QDialog):
    result = Signal(object)

    def __init__(self, session: GameSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("未来日程 · 预约与赴约")
        self.resize(1000, 780)
        self.setMinimumSize(820, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        layout.addWidget(text_label("未来日程", "title"))
        layout.addWidget(text_label("时令、来访与准备条件形成后续安排。到期后，可赴约、改期或不去。", "subtitle"))
        self.notice = text_label("", "notice")
        layout.addWidget(self.notice)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["预约", "来源", "原定旬", "执行旬", "AP / 准备", "状态"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 68), (2, 142), (3, 142), (4, 112), (5, 70)):
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self._selected)
        layout.addWidget(self.table, 1)
        details, details_layout = panel()
        self.detail_label = text_label("请选择一条预约。")
        self.consequence_label = text_label("", "subtitle")
        self.conflict_label = text_label("", "notice")
        self.conflict_label.hide()
        details_layout.addWidget(self.detail_label)
        details_layout.addWidget(self.conflict_label)
        details_layout.addWidget(self.consequence_label)
        decisions = QHBoxLayout()
        self.execute_button = QPushButton("赴约 · 加入本旬日程")
        self.execute_button.setProperty("primary", True)
        self.execute_button.clicked.connect(self.execute_selected)
        decisions.addWidget(self.execute_button)
        decisions.addStretch()
        self.reschedule_offset = QSpinBox()
        self.reschedule_offset.setRange(1, 36)
        self.reschedule_offset.setValue(1)
        self.reschedule_offset.setSuffix(" 旬后")
        self.reschedule_offset.setAccessibleName("预约改期至多少旬后")
        decisions.addWidget(self.reschedule_offset)
        self.reschedule_button = QPushButton("改期")
        self.reschedule_button.clicked.connect(self.reschedule_selected)
        decisions.addWidget(self.reschedule_button)
        self.miss_button = QPushButton("不去")
        self.miss_button.setProperty("danger", True)
        self.miss_button.clicked.connect(self.miss_selected)
        decisions.addWidget(self.miss_button)
        details_layout.addLayout(decisions)
        self.history_label = text_label("", "subtitle")
        details_layout.addWidget(self.history_label)
        layout.addWidget(details)

        demo, demo_layout = panel()
        demo_layout.addWidget(text_label("添加演示预约", "sectionTitle"))
        creation = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("时令 · 经筵日讲（1 AP）", ("seasonal", "lecture", "演示 · 时令日讲", 1))
        self.preset_combo.addItem("事件 · 来使奏对（2 AP）", ("event", "audience", "演示 · 来使奏对", 2))
        self.preset_combo.addItem("准备 · 宫苑游赏（1 AP）", ("preparation", "garden", "演示 · 宫苑游赏", 1))
        creation.addWidget(self.preset_combo, 1)
        self.due_offset = QSpinBox()
        self.due_offset.setRange(0, 36)
        self.due_offset.setSpecialValueText("本旬")
        self.due_offset.setSuffix(" 旬后")
        self.due_offset.setValue(1)
        self.due_offset.setAccessibleName("演示预约到期旬")
        creation.addWidget(self.due_offset)
        self.preparation_combo = QComboBox()
        for label, value in (("已就绪", "ready"), ("筹备中", "preparing"), ("筹备延误", "delayed")):
            self.preparation_combo.addItem(label, value)
        creation.addWidget(self.preparation_combo)
        self.add_button = QPushButton("添加预约")
        self.add_button.clicked.connect(self.add_demo)
        creation.addWidget(self.add_button)
        demo_layout.addLayout(creation)
        demo_layout.addWidget(text_label("演示预约由此手动加入。改期与缺席会留下后果记录，具体数值尚待设计。", "subtitle"))
        layout.addWidget(demo)
        footer = QHBoxLayout()
        self.feedback = text_label("", "feedback")
        self.feedback.hide()
        footer.addWidget(self.feedback, 1)
        footer.addStretch(1)
        self.ready_button = QPushButton("演示：准备就绪")
        self.ready_button.clicked.connect(self.ready_selected)
        footer.addWidget(self.ready_button)
        close = QPushButton("返回本旬规划")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        layout.addLayout(footer)
        self.refresh()

    def selected_appointment(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            return None
        identifier = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return next((item for item in self.session.state.appointments if item.id == identifier), None)

    def _publish(self, result) -> None:
        self.feedback.setText(result.message)
        self.feedback.setProperty("error", not result.ok)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.show()
        self.refresh()
        self.result.emit(result)

    def add_demo(self) -> None:
        source, kind, label, cost = self.preset_combo.currentData()
        self._publish(self.session.create_appointment(
            source, self.session.state.turn_index + self.due_offset.value(), kind,
            label=label, cost=cost, preparation=self.preparation_combo.currentData()))
        if self.table.rowCount():
            self.table.selectRow(self.table.rowCount() - 1)

    def execute_selected(self) -> None:
        item = self.selected_appointment()
        if item:
            self._publish(self.session.execute_appointment(item.id))

    def reschedule_selected(self) -> None:
        item = self.selected_appointment()
        if item:
            self._publish(self.session.reschedule_appointment(
                item.id, self.session.state.turn_index + self.reschedule_offset.value(), "玩家调整日程"))

    def miss_selected(self) -> None:
        item = self.selected_appointment()
        if item:
            self._publish(self.session.miss_appointment(item.id, "玩家选择不去"))

    def ready_selected(self) -> None:
        item = self.selected_appointment()
        if item:
            self._publish(self.session.update_appointment_preparation(item.id, "ready"))

    def refresh(self, session: GameSession | None = None) -> None:
        if session is not None:
            self.session = session
        previous = self.selected_appointment()
        previous_id = previous.id if previous else None
        appointments = self.session.state.appointments
        due = len([item for item in self.session.appointments_due if item.status == "pending"])
        self.notice.setText(f"本旬待决定 {due} 项。赴约所需时间计入本旬预算；若日程已满，请返回规划调整后再加入。")
        self.table.blockSignals(True)
        self.table.setRowCount(len(appointments))
        for index, item in enumerate(appointments):
            values = (item.label, item.source_label,
                      self.session.appointment_date_label(item.original_turn),
                      self.session.appointment_date_label(item.due_turn),
                      f"{item.cost} / {item.preparation_label}", item.status_label)
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, item.id)
                self.table.setItem(index, column, cell)
            if item.id == previous_id:
                self.table.selectRow(index)
        self.table.blockSignals(False)
        if previous_id is None and appointments:
            self.table.selectRow(0)
        self._selected()

    def _selected(self) -> None:
        item = self.selected_appointment()
        pending = bool(item and item.status in {"pending", "scheduled"})
        planning = self.session.state.phase == Phase.PLANNING
        self.execute_button.setEnabled(bool(pending and planning and item.status == "pending"
                                            and item.due_turn <= self.session.state.turn_index))
        self.reschedule_button.setEnabled(pending and planning)
        self.miss_button.setEnabled(pending and planning)
        self.ready_button.setEnabled(bool(pending and item.preparation != "ready"))
        if item is None:
            self.detail_label.setText("未来日程暂无预约，可添加一条演示安排。")
            self.consequence_label.clear()
            self.history_label.clear()
            self.conflict_label.hide()
            return
        self.reschedule_offset.setMinimum(max(1, item.due_turn - self.session.state.turn_index + 1))
        people = "、".join(item.related_people) if item.related_people else "未指定"
        self.detail_label.setText(f"{item.label} · {item.cost} AP · {item.preparation_label}\n相关人物：{people}")
        conflict = self.session.appointment_conflict(item)
        self.conflict_label.setText(conflict)
        self.conflict_label.setVisible(bool(conflict))
        self.consequence_label.setText(
            self.session.appointment_consequence_preview(item, "rescheduled") +
            "\n" + self.session.appointment_consequence_preview(item, "missed"))
        history = []
        labels = {"created": "已创建", "scheduled": "已排入日程", "rescheduled": "已改期",
                  "completed": "已赴约", "missed": "已记录缺席"}
        for record in item.history[-3:]:
            history.append(labels.get(record.get("action"), "记录已保留") +
                           (f"（{record['reason']}）" if record.get("reason") else ""))
        self.history_label.setText("变更记录：" + "；".join(history) if history else "尚无变更记录。")
