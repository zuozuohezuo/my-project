"""A whole-turn budget and an explicitly ordered, editable activity draft."""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QHBoxLayout, QHeaderView,
    QProgressBar, QPushButton, QSlider, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from dynasty.core import ACTIVITY_LABELS, ActionResult, Activity, GameSession, Phase
from dynasty.ui.emperor_page import panel, scroll_content, text_label


WORK_KINDS = {"court", "paperwork", "audience", "palace", "lecture"}
OFFICE_KINDS = {"paperwork", "audience", "palace"}
CATALOGUE = (
    ("court", "早朝", "听取奏报，议论多项朝务", 5),
    ("paperwork", "批阅章奏", "按所分配的时间推进待办", None),
    ("audience", "召见臣工", "安排面议与臣工奏对", None),
    ("palace", "宫廷事务", "处理宫中待办事务", None),
    ("lecture", "日讲", "听讲经史，论治问学", 1),
    ("rest", "休息", "留一段安静歇息的时间", 1),
    ("study", "个人读书", "自选书目，独处研读", 1),
    ("exercise", "习武", "亲自练习或交由自动演练", 1),
    ("garden", "宫苑游赏", "在有限的游赏机会内探索", 1),
    ("calligraphy", "书法", "铺纸临池，凝神习字", 1),
    ("private", "私生活", "闲谈与陪伴，处理身边小事", 1),
)


def activity_category(activity: Activity) -> str:
    return getattr(activity, "category", "work" if activity.kind in WORK_KINDS else "private")


class PlanningPage(QWidget):
    result = Signal(object)
    changed = Signal()
    start_requested = Signal()

    def __init__(self, session: GameSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.staged_mode = getattr(session.config, "turn_rules_version", 2) >= 3
        self._draft: list[Activity] = []
        self._context = None
        self._dirty = False
        self._loading = False
        self._saved_signature = None
        self.catalogue_buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self.court_checkbox = QCheckBox("安排早朝 · 固定 5 AP")
        self.court_checkbox.setToolTip("每旬默认安排，可在旬初取消。早朝始终位于最前，不占用后续办公时段。")
        self.court_checkbox.toggled.connect(self._court_toggled)
        header.addWidget(self.court_checkbox)
        self.header_hint = text_label("", "subtitle")
        header.addWidget(self.header_hint, 1)
        self.example_button = QPushButton("载入示范日程")
        self.example_button.clicked.connect(self.load_example)
        header.addWidget(self.example_button)
        layout.addLayout(header)

        self.budget_card, budget = panel()
        budget.setContentsMargins(12, 8, 12, 8)
        budget.setSpacing(3)
        allocation = QHBoxLayout()
        self.work_label = text_label("工作")
        allocation.addWidget(self.work_label)
        self.work_spin = QSpinBox()
        self.work_spin.setSuffix(" AP")
        self.work_spin.setAccessibleName("本旬工作预算")
        self.work_spin.setFixedWidth(104)
        allocation.addWidget(self.work_spin)
        self.work_slider = QSlider(Qt.Orientation.Horizontal)
        self.work_slider.setObjectName("personalitySlider")
        self.work_slider.setAccessibleName("工作与私生活比例")
        allocation.addWidget(self.work_slider, 1)
        allocation.addWidget(text_label("私生活"))
        self.private_spin = QSpinBox()
        self.private_spin.setSuffix(" AP")
        self.private_spin.setAccessibleName("本旬私生活预算")
        self.private_spin.setFixedWidth(104)
        allocation.addWidget(self.private_spin)
        self.capacity_label = text_label("", "metricLabel")
        allocation.addSpacing(12)
        allocation.addWidget(self.capacity_label)
        budget.addLayout(allocation)
        self.budget_progress = QProgressBar()
        self.budget_progress.setObjectName("pursuitProgress")
        self.budget_progress.setFixedHeight(4)
        self.budget_progress.setTextVisible(False)
        budget.addWidget(self.budget_progress)
        self.budget_status = text_label("", "subtitle")
        budget.addWidget(self.budget_status)
        layout.addWidget(self.budget_card)
        self.work_spin.valueChanged.connect(self._work_changed)
        self.work_slider.valueChanged.connect(self.work_spin.setValue)
        self.private_spin.valueChanged.connect(self._private_changed)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.catalogue_card, catalogue_layout = panel()
        catalogue_layout.setContentsMargins(12, 10, 12, 10)
        catalogue_layout.setSpacing(6)
        self.catalogue_card.setMinimumWidth(290)
        self.catalogue_card.setMaximumWidth(380)
        catalogue_layout.addWidget(text_label("活动目录", "sectionTitle"))
        office = QHBoxLayout()
        office.addWidget(text_label("办公每段投入"))
        self.office_ap = QSpinBox()
        self.office_ap.setRange(1, 30)
        self.office_ap.setValue(3)
        self.office_ap.setSuffix(" AP")
        self.office_ap.setAccessibleName("批阅召见宫务分配时间")
        office.addWidget(self.office_ap)
        catalogue_layout.addLayout(office)
        catalogue_scroll, catalogue = scroll_content()
        catalogue_scroll.widget().setObjectName("planningCatalogueContent")
        catalogue_scroll.widget().setStyleSheet("QWidget#planningCatalogueContent { background: #fffef9; }")
        catalogue.setContentsMargins(0, 0, 5, 0)
        catalogue.setSpacing(5)
        for kind, name, description, cost in CATALOGUE:
            if kind in {"court", "rest"}:
                catalogue.addWidget(text_label("工作" if kind == "court" else "私生活", "eyebrow"))
            button = QPushButton()
            button.setText(f"＋  {name}    {'分配 AP' if cost is None else str(cost) + ' AP'}")
            button.setToolTip(description)
            button.setAccessibleName(f"安排{name}")
            button.setStyleSheet("text-align: left; padding: 4px 8px;")
            button.clicked.connect(lambda checked=False, key=kind: self.arrange_activity(key))
            self.catalogue_buttons[kind] = button
            catalogue.addWidget(button)
        catalogue.addStretch()
        catalogue_layout.addWidget(catalogue_scroll, 1)
        body.addWidget(self.catalogue_card)

        self.schedule_card, schedule = panel()
        schedule.setContentsMargins(12, 10, 12, 10)
        schedule.setSpacing(6)
        schedule_heading = QHBoxLayout()
        schedule_heading.addWidget(text_label("本旬日程", "sectionTitle"), 1)
        self.count_label = text_label("", "metricLabel")
        schedule_heading.addWidget(self.count_label)
        schedule.addLayout(schedule_heading)
        self.stage_order_label = text_label("Ⅰ 早朝 → Ⅱ 工作 → Ⅲ 私生活 · 只在同一阶段内调整顺序", "subtitle")
        schedule.addWidget(self.stage_order_label)
        self.schedule_table = QTableWidget(0, 4)
        self.schedule_table.setHorizontalHeaderLabels(["顺序", "活动", "归属", "安排时间"])
        self.schedule_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.schedule_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.schedule_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.schedule_table.verticalHeader().hide()
        self.schedule_table.verticalHeader().setDefaultSectionSize(32)
        self.schedule_table.setAlternatingRowColors(True)
        self.schedule_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column, width in ((0, 54), (2, 72), (3, 93)):
            self.schedule_table.setColumnWidth(column, width)
        self.schedule_table.itemSelectionChanged.connect(self._update_selection)
        schedule.addWidget(self.schedule_table, 1)
        order = QHBoxLayout()
        self.up_button = QPushButton("↑ 上移")
        self.down_button = QPushButton("↓ 下移")
        self.remove_button = QPushButton("移除")
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        self.remove_button.clicked.connect(self.remove_selected)
        for widget in (self.up_button, self.down_button, self.remove_button):
            order.addWidget(widget)
        order.addStretch()
        self.clear_button = QPushButton("清空日程")
        self.clear_button.clicked.connect(self.clear_draft)
        order.addWidget(self.clear_button)
        self.rest_button = QPushButton("填满私生活休息")
        self.rest_button.setToolTip("只用休息补齐私生活尚未安排的时间；工作预算仍需另行安排。")
        self.rest_button.clicked.connect(self.fill_private_rest)
        order.addWidget(self.rest_button)
        for widget in (self.up_button, self.down_button, self.remove_button, self.clear_button, self.rest_button):
            widget.setStyleSheet("padding: 5px 8px;")
        schedule.addLayout(order)
        body.addWidget(self.schedule_card, 1)
        layout.addLayout(body, 1)

        bottom = QHBoxLayout()
        self.validation_label = text_label("", "feedback")
        bottom.addWidget(self.validation_label, 1)
        self.save_button = QPushButton("保留规划")
        self.save_button.clicked.connect(self._save_clicked)
        bottom.addWidget(self.save_button)
        self.start_button = QPushButton("开始依次执行 →")
        self.start_button.setProperty("primary", True)
        self.start_button.clicked.connect(self.start_execution)
        bottom.addWidget(self.start_button)
        layout.addLayout(bottom)
        self.refresh(force=True)

    def _signature(self):
        activities, budget = self._planning_source()
        return repr((activities, budget))

    def _planning_source(self):
        state = self.session.state
        activities = state.activities
        budget = getattr(state, "work_budget", 20)
        if state.phase == Phase.PLANNING and not activities:
            plan = self.session._current_plan()
            if plan is not None and plan.status != "completed":
                activities = plan.activities
                if plan.work_budget is not None:
                    budget = plan.work_budget
        return activities, budget

    def refresh(self, session: GameSession | None = None, *, force: bool = False) -> None:
        if session is not None:
            self.session = session
        state = self.session.state
        self.staged_mode = getattr(self.session.config, "turn_rules_version", 2) >= 3
        context = (id(self.session), state.turn_index, self.staged_mode)
        if force or context != self._context or (not self._dirty and self._signature() != self._saved_signature):
            self._context = context
            source, work_budget = self._planning_source()
            self._draft = [copy.deepcopy(item) if isinstance(item, Activity) else
                           Activity(**copy.deepcopy(item)) if isinstance(item, dict) else
                           Activity(kind=item, cost=5 if item == "court" else 1)
                           for item in source]
            self._loading = True
            self.court_checkbox.setChecked(any(item.kind == "court" for item in self._draft))
            capacity = self._distributable_ap()
            for widget in (self.work_spin, self.work_slider, self.private_spin):
                widget.setRange(0, capacity)
            self.office_ap.setMaximum(state.ap_capacity)
            self.work_spin.setValue(max(0, min(work_budget - self._court_ap(), capacity)))
            self.work_slider.setValue(self.work_spin.value())
            self.private_spin.setValue(capacity - self.work_spin.value())
            self._loading = False
            self._dirty = False
            self._saved_signature = self._signature()
        elif self.work_spin.maximum() != self._distributable_ap():
            self._loading = True
            for widget in (self.work_spin, self.work_slider, self.private_spin):
                widget.setMaximum(self._distributable_ap())
            self.private_spin.setValue(self._distributable_ap() - self.work_spin.value())
            self._loading = False
        enabled = state.phase == Phase.PLANNING
        for widget in (self.budget_card, self.catalogue_card, self.example_button, self.save_button,
                       self.clear_button, self.rest_button, self.court_checkbox):
            widget.setEnabled(enabled)
        self.court_checkbox.setVisible(self.staged_mode)
        self.catalogue_buttons["court"].setVisible(not self.staged_mode)
        self.stage_order_label.setVisible(self.staged_mode)
        self.header_hint.setText("先朝议，后办公，最后私生活。" if self.staged_mode else
                                 "先分配工作与私生活，再排好这一旬的全部活动。")
        self.work_label.setText("其余工作" if self.staged_mode and self._court_ap() else "工作")
        self.work_spin.setAccessibleName("早朝以外的工作预算" if self.staged_mode else "本旬工作预算")
        self.capacity_label.setText(f"早朝 {self._court_ap()} + 余 {self._distributable_ap()} AP"
                                    if self.staged_mode else f"整旬共 {state.ap_capacity} AP")
        self.clear_button.setText("清空预排" if self.staged_mode else "清空日程")
        self.schedule_table.setHorizontalHeaderLabels(["顺序", "活动", "阶段" if self.staged_mode else "归属", "安排时间"])
        self._render_draft()

    def _court_ap(self) -> int:
        return sum(item.cost for item in self._draft if item.kind == "court") if self.staged_mode else 0

    def _distributable_ap(self) -> int:
        return max(0, self.session.state.ap_capacity - self._court_ap())

    def total_work_budget(self) -> int:
        """The session budget includes early court; the staged slider excludes it."""
        return self.work_spin.value() + self._court_ap()

    def draft_work_budget(self) -> int:
        return self.total_work_budget()

    def _stage(self, activity: Activity) -> str:
        return "court" if self.staged_mode and activity.kind == "court" else activity_category(activity)

    def _sort_stages(self) -> None:
        if self.staged_mode:
            order = {"court": 0, "work": 1, "private": 2}
            self._draft.sort(key=lambda activity: order[self._stage(activity)])

    def _court_toggled(self, enabled: bool) -> None:
        if self._loading or not self.staged_mode:
            return
        total_work = self.total_work_budget()
        existing = [item for item in self._draft if item.kind == "court"]
        if not enabled and any(item.appointment_id for item in existing):
            self.court_checkbox.blockSignals(True)
            self.court_checkbox.setChecked(True)
            self.court_checkbox.blockSignals(False)
            self.result.emit(ActionResult("error", "本次早朝关联预约，请先在未来日程中改期或不去。"))
            return
        if enabled and not existing:
            self._draft.insert(0, Activity(kind="court", cost=5))
        elif not enabled:
            self._draft = [item for item in self._draft if item.kind != "court"]
        self._loading = True
        for widget in (self.work_spin, self.work_slider, self.private_spin):
            widget.setRange(0, self._distributable_ap())
        self.work_spin.setValue(max(0, total_work - self._court_ap()))
        self.work_slider.setValue(self.work_spin.value())
        self.private_spin.setValue(self._distributable_ap() - self.work_spin.value())
        self._loading = False
        self._mark_changed()
        self.refresh()

    def _work_changed(self, value: int) -> None:
        self.work_slider.blockSignals(True)
        self.private_spin.blockSignals(True)
        self.work_slider.setValue(value)
        self.private_spin.setValue(self._distributable_ap() - value)
        self.work_slider.blockSignals(False)
        self.private_spin.blockSignals(False)
        if not self._loading:
            self._mark_changed()

    def _private_changed(self, value: int) -> None:
        self.work_spin.setValue(self._distributable_ap() - value)

    def _mark_changed(self) -> None:
        self._dirty = True
        self._sort_stages()
        self._render_draft()
        self.changed.emit()

    def draft_activities(self) -> list[Activity]:
        return copy.deepcopy(self._draft)

    def arrange_activity(self, kind: str) -> None:
        if self.session.state.phase != Phase.PLANNING:
            self.result.emit(ActionResult("error", "本旬已开始，请在下一旬规划活动。"))
            return
        if kind not in ACTIVITY_LABELS:
            return
        if self.staged_mode and kind == "court":
            self.court_checkbox.setChecked(True)
            return
        cost = self.office_ap.value() if kind in OFFICE_KINDS else 5 if kind == "court" else 1
        activity = Activity(kind=kind, cost=cost)
        self._draft.append(activity)
        self._mark_changed()
        row = next(index for index, item in enumerate(self._draft) if item is activity)
        self.schedule_table.selectRow(row)
        self.schedule_table.scrollToItem(self.schedule_table.item(row, 0))

    def move_selected(self, delta: int) -> None:
        row = self.schedule_table.currentRow()
        target = row + delta
        if self.session.state.phase != Phase.PLANNING or not 0 <= target < len(self._draft) or row < 0:
            return
        if self.staged_mode and (self._draft[row].kind == "court" or
                                 self._stage(self._draft[row]) != self._stage(self._draft[target])):
            return
        self._draft[row], self._draft[target] = self._draft[target], self._draft[row]
        self._mark_changed()
        self.schedule_table.selectRow(target)

    def remove_selected(self) -> None:
        row = self.schedule_table.currentRow()
        if self.session.state.phase == Phase.PLANNING and 0 <= row < len(self._draft):
            if getattr(self._draft[row], "appointment_id", None):
                self.result.emit(ActionResult("error", "这是已承接的预约，请在预约日程中选择改期或不去。"))
                return
            if self.staged_mode and self._draft[row].kind == "court":
                self.court_checkbox.setChecked(False)
                return
            self._draft.pop(row)
            self._mark_changed()
            if self._draft:
                self.schedule_table.selectRow(min(row, len(self._draft) - 1))

    def clear_draft(self) -> None:
        if self.session.state.phase == Phase.PLANNING:
            self._draft = [item for item in self._draft if getattr(item, "appointment_id", None)
                           or (self.staged_mode and item.kind == "court")]
            self._mark_changed()

    def fill_private_rest(self) -> None:
        if self.session.state.phase != Phase.PLANNING:
            return
        used = sum(item.cost for item in self._draft if activity_category(item) == "private")
        self._draft.extend(Activity(kind="rest", cost=1)
                           for _ in range(max(0, self.private_spin.value() - used)))
        self._mark_changed()

    def load_example(self) -> None:
        if self.session.state.phase != Phase.PLANNING:
            return
        if self.staged_mode:
            self._load_staged_example()
            return
        reserved = [copy.deepcopy(item) for item in self._draft if getattr(item, "appointment_id", None)]
        has_reserved = bool(reserved)
        capacity = self.session.state.ap_capacity
        reserved_work = sum(item.cost for item in reserved if activity_category(item) == "work")
        reserved_private = sum(item.cost for item in reserved if activity_category(item) == "private")
        work = min(capacity - reserved_private, max(reserved_work, round(capacity * 2 / 3)))
        self._draft = reserved
        remaining_work = max(0, work - reserved_work)
        for kind, wanted in (("court", 5), ("lecture", 1), ("paperwork", 7), ("audience", 4), ("palace", 3)):
            cost = min(remaining_work, wanted)
            if cost and (kind != "court" or cost == 5):
                self._draft.append(Activity(kind=kind, cost=cost))
                remaining_work -= cost
        if remaining_work:
            self._draft.append(Activity(kind="paperwork", cost=remaining_work))
        private_kinds = ("garden", "exercise", "study", "private", "calligraphy", "rest")
        for index in range(max(0, capacity - work - reserved_private)):
            self._draft.append(Activity(kind=private_kinds[index % len(private_kinds)], cost=1))
        # A private interval near the start makes the alternating rhythm visible.
        if not has_reserved and len(self._draft) > 6:
            self._draft.insert(1, self._draft.pop(5))
        self.work_spin.setValue(work)
        self._mark_changed()

    def _load_staged_example(self) -> None:
        reserved = [copy.deepcopy(item) for item in self._draft if item.appointment_id]
        if not any(item.kind == "court" for item in reserved):
            reserved.insert(0, Activity(kind="court", cost=5))
        capacity = self.session.state.ap_capacity
        reserved_work = sum(item.cost for item in reserved if activity_category(item) == "work")
        reserved_private = sum(item.cost for item in reserved if activity_category(item) == "private")
        work = min(capacity - reserved_private, max(reserved_work, round(capacity * 2 / 3)))
        self._draft = reserved
        remaining_work = max(0, work - reserved_work)
        for kind, wanted in (("paperwork", 3), ("lecture", 1), ("audience", 2)):
            cost = min(remaining_work, wanted)
            if cost:
                self._draft.append(Activity(kind=kind, cost=cost))
                remaining_work -= cost
        private_left = max(0, capacity - work - reserved_private)
        for kind in ("garden", "exercise")[:private_left]:
            self._draft.append(Activity(kind=kind, cost=1))
        self._loading = True
        self.court_checkbox.setChecked(True)
        for widget in (self.work_spin, self.work_slider, self.private_spin):
            widget.setRange(0, self._distributable_ap())
        self.work_spin.setValue(max(0, work - self._court_ap()))
        self.work_slider.setValue(self.work_spin.value())
        self.private_spin.setValue(self._distributable_ap() - self.work_spin.value())
        self._loading = False
        self._mark_changed()
        self.refresh()

    def _totals(self) -> tuple[int, int]:
        def reserved(item: Activity) -> int:
            return item.reserved_ap if self.staged_mode else item.cost
        return (sum(reserved(item) for item in self._draft if activity_category(item) == "work") - self._court_ap(),
                sum(reserved(item) for item in self._draft if activity_category(item) == "private"))

    def _validation(self, *, complete: bool = True) -> str:
        work, private = self._totals()
        messages = []
        for label, used, allotted in (("工作", work, self.work_spin.value()),
                                      ("私生活", private, self.private_spin.value())):
            if used > allotted:
                messages.append(f"{label}超出 {used - allotted} AP")
            elif complete and not self.staged_mode and used < allotted:
                messages.append(f"{label}还需安排 {allotted - used} AP")
        return "；".join(messages)

    def _render_draft(self) -> None:
        selected = self.schedule_table.currentRow()
        self.schedule_table.setRowCount(len(self._draft))
        for index, activity in enumerate(self._draft):
            name = activity.label + (" · 预约" if getattr(activity, "appointment_id", None) else "")
            category = "工作" if activity_category(activity) == "work" else "私生活"
            if self.staged_mode:
                category = {"court": "Ⅰ 早朝", "work": "Ⅱ 工作", "private": "Ⅲ 私人"}[self._stage(activity)]
            cost = activity.reserved_ap if self.staged_mode else activity.cost
            for column, value in enumerate((f"{index + 1:02d}", name, category, f"{cost} AP")):
                item = QTableWidgetItem(value)
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if self.staged_mode and column == 2:
                    item.setBackground(QColor({"court": "#ede2c9", "work": "#e2ece0", "private": "#edf0e7"}[self._stage(activity)]))
                self.schedule_table.setItem(index, column, item)
        if 0 <= selected < len(self._draft):
            self.schedule_table.selectRow(selected)
        work, private = self._totals()
        total = work + private + self._court_ap()
        self.count_label.setText(f"{len(self._draft)} 项活动 · {total} AP")
        self.budget_progress.setRange(0, self.session.state.ap_capacity)
        self.budget_progress.setValue(min(total, self.session.state.ap_capacity))
        self.budget_status.setText(
            f"已预排：工作 {work} / {self.work_spin.value()} AP · 私生活 {private} / {self.private_spin.value()} AP"
            f"    ·    待临时选择 {max(0, self.session.state.ap_capacity - total)} AP"
            if self.staged_mode else
            f"已安排：工作 {work} / {self.work_spin.value()} AP    ·    "
            f"私生活 {private} / {self.private_spin.value()} AP    ·    按列表顺序执行")
        error = self._validation()
        planning = self.session.state.phase == Phase.PLANNING
        self.validation_label.setText(error if planning and error else
                                      ("可开始；未预排的时间到相应阶段再选活动。" if self.staged_mode else "日程已排满，可以开始。")
                                      if planning else "本旬已开始，前往执行阶段继续安排。" if self.staged_mode else
                                      "本旬日程已锁定，前往顺序执行。")
        self.validation_label.setProperty("error", bool(planning and error))
        self.validation_label.style().unpolish(self.validation_label)
        self.validation_label.style().polish(self.validation_label)
        self.start_button.setEnabled(planning and not error)
        self._update_selection()

    def _update_selection(self) -> None:
        row = self.schedule_table.currentRow()
        enabled = self.session.state.phase == Phase.PLANNING
        self.up_button.setEnabled(enabled and row > 0)
        self.down_button.setEnabled(enabled and 0 <= row < len(self._draft) - 1)
        if self.staged_mode and 0 <= row < len(self._draft):
            self.up_button.setEnabled(enabled and row > 0 and self._draft[row].kind != "court"
                                      and self._stage(self._draft[row]) == self._stage(self._draft[row - 1]))
            self.down_button.setEnabled(enabled and row < len(self._draft) - 1
                                        and self._draft[row].kind != "court"
                                        and self._stage(self._draft[row]) == self._stage(self._draft[row + 1]))
        self.remove_button.setEnabled(enabled and row >= 0)

    def capture_draft(self) -> ActionResult:
        if self.session.state.phase != Phase.PLANNING:
            return ActionResult("ok", "本旬已开始，执行位置已保留。")
        error = self._validation(complete=False)
        if error:
            return ActionResult("error", error + "。请调整活动或预算。")
        result = self.session.set_turn_plan(self.draft_activities(), self.total_work_budget())
        if result.ok:
            self._dirty = False
            self.refresh(force=True)
        return result

    def _save_clicked(self) -> None:
        self.result.emit(self.capture_draft())

    def start_execution(self) -> None:
        error = self._validation()
        if error:
            self.result.emit(ActionResult("error", error))
            return
        result = self.capture_draft()
        if result.ok:
            result = self.session.start_turn()
        self.refresh()
        self.result.emit(result)
        if self.session.state.phase != Phase.PLANNING:
            self.start_requested.emit()
