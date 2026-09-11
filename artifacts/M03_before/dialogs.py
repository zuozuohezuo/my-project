"""Editors for orders and three-turn plans; no rule mutation inside widgets."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from dynasty.content import HistoryRepository
from dynasty.core import ACTIVITY_LABELS, GameSession


class CommandEditor(QWidget):
    def __init__(self, repository: HistoryRepository, session: GameSession, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.command = QComboBox()
        self.command.setObjectName("commandType")
        for definition in session.command_definitions.values():
            if not definition.emergency_only:
                self.command.addItem(f"{definition.label}  ·  {definition.cost} 份诏书", definition.id)
        self.target = QComboBox()
        self.target.addItem("全国 / 未指定地区", None)
        for row in repository.regions:
            self.target.addItem(row["name"], row["id"])
        self.delegated = QCheckBox("具体数量交由官员决定")
        self.delegated.setChecked(True)
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("留空为委派；税率填写 0–100")
        self.amount.setEnabled(False)
        self.delegated.toggled.connect(lambda enabled: self.amount.setEnabled(not enabled))
        self.person = QComboBox()
        self.person.addItem("人选待定 / 委派选择", None)
        for row in repository.tables["people"]:
            self.person.addItem(row["name"], row["id"])
        self.office = QComboBox()
        self.office.addItem("官职待定", None)
        for row in repository.tables["offices"]:
            self.office.addItem(row["name"], row["id"])
        self.note = QLineEdit()
        self.note.setPlaceholderText("可选：目标、预算限制或补充要求")
        form = QFormLayout(self)
        form.setVerticalSpacing(10)
        form.addRow("政务", self.command)
        form.addRow("作用地区", self.target)
        form.addRow("参数", self.delegated)
        self.amount_label = QLabel("拟定税率 %")
        form.addRow(self.amount_label, self.amount)
        self.person_label = QLabel("人选")
        self.office_label = QLabel("官职")
        form.addRow(self.person_label, self.person)
        form.addRow(self.office_label, self.office)
        form.addRow("补充要求", self.note)
        self.command.currentIndexChanged.connect(self._kind_changed)
        self._kind_changed()

    def _kind_changed(self) -> None:
        identifier = self.command.currentData()
        appointment = identifier == "appoint_official"
        for widget in [self.person, self.person_label, self.office, self.office_label]:
            widget.setVisible(appointment)
        for widget in [self.amount, self.amount_label, self.delegated]:
            widget.setVisible(not appointment)
        self.amount_label.setText("拟定税率 %" if identifier == "change_tax" else "拟定预算（两）")

    def payload(self) -> tuple[str, dict]:
        identifier = self.command.currentData()
        parameters = {"target": self.target.currentData(), "note": self.note.text().strip()}
        if identifier == "appoint_official":
            parameters.update(person_id=self.person.currentData(), office_id=self.office.currentData())
        else:
            amount = None
            if not self.delegated.isChecked():
                try:
                    amount = float(self.amount.text())
                except ValueError as error:
                    raise ValueError("请填写有效数量，或勾选交由官员决定。") from error
                if not 0 <= amount <= (100 if identifier == "change_tax" else 1_000_000_000):
                    raise ValueError("税率须在 0–100 之间，预算须为有效非负数。")
            parameters["rate" if identifier == "change_tax" else "budget"] = amount
        return identifier, parameters

    def select_target(self, identifier: str) -> None:
        index = self.target.findData(identifier)
        if index >= 0:
            self.target.setCurrentIndex(index)


class MonthPlanDialog(QDialog):
    def __init__(self, repository: HistoryRepository, session: GameSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("安排连续三旬")
        self.resize(1040, 710)
        self.run_now = False
        self.plans = []
        self.activity_selectors = []
        self.commands: list[list[dict]] = [[], [], []]
        self.command_lists = []
        layout = QVBoxLayout(self)
        title = QLabel("统筹三旬 · 每旬独立使用行动力与诏书")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        help_text = QLabel("从当前旬起连续安排三旬。急报或劝谏会暂停推进；未完成安排保留。未来参数在执行时重新检查。")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        body = QHBoxLayout()
        self.tabs = QTabWidget()
        for index in range(3):
            page = QWidget()
            column = QVBoxLayout(page)
            selectors = []
            for slot in range(session.state.ap_capacity):
                row = QHBoxLayout()
                row.addWidget(QLabel(f"安排 {slot + 1}"))
                combo = QComboBox()
                for kind, label in ACTIVITY_LABELS.items():
                    combo.addItem(label, kind)
                combo.setCurrentIndex(combo.findData("court" if slot == 0 else "rest"))
                row.addWidget(combo, 1)
                selectors.append(combo)
                column.addLayout(row)
            self.activity_selectors.append(selectors)
            column.addWidget(QLabel("本旬预拟政令"))
            commands = QListWidget()
            self.command_lists.append(commands)
            column.addWidget(commands, 1)
            remove = QPushButton("移除选中的预拟政令")
            remove.clicked.connect(lambda _=False, offset=index: self._remove_command(offset))
            column.addWidget(remove)
            self.tabs.addTab(page, ["本旬", "下一旬", "第三旬"][index])
        body.addWidget(self.tabs, 1)
        right = QVBoxLayout()
        self.editor = CommandEditor(repository, session)
        right.addWidget(self.editor)
        add = QPushButton("加入左侧所选旬的计划")
        add.clicked.connect(self._add_command)
        right.addWidget(add)
        right.addStretch()
        body.addLayout(right, 1)
        layout.addLayout(body, 1)
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName("feedback")
        layout.addWidget(self.feedback)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存计划")
        save.clicked.connect(lambda: self._submit(False))
        run = QPushButton("保存并推进三旬")
        run.setProperty("primary", True)
        run.clicked.connect(lambda: self._submit(True))
        actions.addWidget(cancel)
        actions.addWidget(save)
        actions.addWidget(run)
        layout.addLayout(actions)
        self._restore_existing()

    def _restore_existing(self) -> None:
        for offset in range(3):
            existing = next((plan for plan in self.session.state.month_plan
                             if plan.turn_index == self.session.state.turn_index + offset), None)
            if not existing:
                continue
            for combo, kind in zip(self.activity_selectors[offset], existing.activities):
                combo.setCurrentIndex(combo.findData(kind))
            for command in existing.commands:
                if command.status == "pending":
                    self.commands[offset].append({"command_id": command.command_id, "parameters": command.parameters})
            self._refresh_commands(offset)

    def _add_command(self) -> None:
        try:
            command_id, parameters = self.editor.payload()
        except ValueError as error:
            self.feedback.setText(str(error))
            return
        offset = self.tabs.currentIndex()
        self.commands[offset].append({"command_id": command_id, "parameters": parameters})
        self._refresh_commands(offset)

    def _remove_command(self, offset: int) -> None:
        row = self.command_lists[offset].currentRow()
        if row >= 0:
            self.commands[offset].pop(row)
            self._refresh_commands(offset)

    def _refresh_commands(self, offset: int) -> None:
        widget = self.command_lists[offset]
        widget.clear()
        for command in self.commands[offset]:
            definition = self.session.command_definitions[command["command_id"]]
            region_id = command["parameters"].get("target") or "全国"
            widget.addItem(f"{definition.label}  ·  {region_id}  ·  {definition.cost} 份诏书")

    def _submit(self, run_now: bool) -> None:
        self.plans = [{"activities": [combo.currentData() for combo in selectors], "commands": commands}
                      for selectors, commands in zip(self.activity_selectors, self.commands)]
        # Validate on a copy, so cancelling or a failed editor cannot mutate the live session.
        preview = GameSession.from_dict(self.session.to_dict())
        result = preview.set_month_plan(self.plans)
        if not result.ok:
            self.feedback.setText(result.message)
            return
        self.run_now = run_now
        self.accept()
