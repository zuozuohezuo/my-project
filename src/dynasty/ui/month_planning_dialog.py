"""Three independent, ordered turn drafts with deferred orders."""

from __future__ import annotations

import copy
from dataclasses import asdict

from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)

from dynasty.core import Activity, GameSession
from dynasty.ui.dialogs import CommandEditor
from dynasty.ui.planning_page import PlanningPage


class SequentialMonthPlanDialog(QDialog):
    def __init__(self, repository, session: GameSession, parent=None):
        super().__init__(parent)
        self.session = session
        self.run_now = False
        self.plans = []
        self.setWindowTitle("连续三旬 · 依次规划")
        self.resize(1200, 880)
        layout = QVBoxLayout(self)
        hint = QLabel("每旬依次经过早朝、工作与私生活。可以预排任务，也可保留预算到相应阶段临时选择。"
                      if session.config.turn_rules_version >= 3 else
                      "每旬各自分配工作与私生活。活动按顺序进行，遇到选择、急报或劝谏时暂停。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.tabs = QTabWidget()
        self.pages = []
        self.commands = [[], [], []]
        for offset in range(3):
            preview = GameSession.from_dict(session.to_dict())
            preview.state.month_plan = []
            if offset:
                preview.state.activities = ([Activity(kind="court", cost=5)]
                                            if session.config.turn_rules_version >= 3 else [])
            existing = next((p for p in session.state.month_plan
                             if p.turn_index == session.state.turn_index + offset), None)
            if existing:
                preview.state.activities = [
                    copy.deepcopy(a) if isinstance(a, Activity) else
                    Activity(**a) if isinstance(a, dict) else
                    Activity(kind=a, cost=5 if a == "court" else 1)
                    for a in existing.activities
                ]
                if existing.work_budget is not None:
                    preview.state.work_budget = existing.work_budget
                self.commands[offset] = [
                    {"command_id": c.command_id, "parameters": copy.deepcopy(c.parameters)}
                    for c in existing.commands if c.status == "pending"
                ]
            page = PlanningPage(preview)
            page.start_button.hide()
            page.save_button.hide()
            self.pages.append(page)
            self.tabs.addTab(page, ["本旬", "下一旬", "第三旬"][offset])
        orders = QWidget()
        row = QHBoxLayout(orders)
        left = QVBoxLayout()
        self.order_turn = QComboBox()
        self.order_turn.addItems(["本旬", "下一旬", "第三旬"])
        self.order_turn.currentIndexChanged.connect(self._refresh_orders)
        left.addWidget(self.order_turn)
        self.order_list = QListWidget()
        left.addWidget(self.order_list, 1)
        remove = QPushButton("移除选中的预拟政令")
        remove.clicked.connect(self._remove_order)
        left.addWidget(remove)
        row.addLayout(left, 1)
        right = QVBoxLayout()
        self.editor = CommandEditor(repository, session)
        right.addWidget(self.editor)
        add = QPushButton("加入所选旬的早朝")
        add.clicked.connect(self._add_order)
        right.addWidget(add)
        right.addWidget(QLabel("只有实际进入早朝才下达；执行时检查诏书额度和改税冷却。"))
        right.addStretch()
        row.addLayout(right, 1)
        self.tabs.addTab(orders, "预拟政令")
        layout.addWidget(self.tabs, 1)
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        buttons = QHBoxLayout()
        copy_next = QPushButton("将本旬草稿复制到后两旬")
        copy_next.clicked.connect(self._copy_first)
        buttons.addWidget(copy_next)
        buttons.addStretch()
        for text, callback in (("取消", self.reject), ("保存计划", lambda: self._submit(False)),
                               ("保存并开始", lambda: self._submit(True))):
            button = QPushButton(text)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self._refresh_orders()

    def _copy_first(self):
        source = self.pages[0]
        for page in self.pages[1:]:
            # Appointments retain their own due turn and must be resolved there.
            draft = source.draft_activities()
            for activity in draft:
                activity.id = ""
                activity.appointment_id = None
            page.session.state.activities = draft
            page.session.state.work_budget = source.draft_work_budget()
            page.refresh(force=True)
        self.feedback.setText("已复制活动顺序与投入时间；预约仍按原到期旬处理。")

    def _refresh_orders(self):
        self.order_list.clear()
        for order in self.commands[self.order_turn.currentIndex()]:
            name = self.session.command_definitions[order["command_id"]].label
            self.order_list.addItem(name)

    def _add_order(self):
        try:
            kind, parameters = self.editor.payload()
        except ValueError as error:
            self.feedback.setText(str(error))
            return
        self.commands[self.order_turn.currentIndex()].append({"command_id": kind, "parameters": parameters})
        self._refresh_orders()

    def _remove_order(self):
        index = self.order_list.currentRow()
        if index >= 0:
            self.commands[self.order_turn.currentIndex()].pop(index)
            self._refresh_orders()

    def _submit(self, run_now):
        plans = [{"activities": [asdict(a) for a in page.draft_activities()],
                  "work_budget": page.draft_work_budget(), "commands": commands}
                 for page, commands in zip(self.pages, self.commands)]
        preview = GameSession.from_dict(self.session.to_dict())
        result = preview.set_month_plan(plans)
        if not result.ok:
            self.feedback.setText(result.message)
            return
        self.plans = plans
        self.run_now = run_now
        self.accept()
