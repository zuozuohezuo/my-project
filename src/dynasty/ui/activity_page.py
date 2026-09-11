"""Sequential activities with resumable choices, visible progress and summaries."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QProgressBar, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from dynasty.core import GameSession, Phase
from dynasty.ui.emperor_page import panel, scroll_content, text_label
from dynasty.ui.planning_page import CATALOGUE, OFFICE_KINDS, WORK_KINDS


STATUS_LABELS = {
    "pending": "待开始", "current": "进行中", "in_progress": "进行中",
    "completed": "已完成", "replaced": "已中止", "cancelled": "已撤下", "stopped": "提前结束",
}


class ActivityPage(QWidget):
    result = Signal(object)
    command_requested = Signal()

    def __init__(self, session: GameSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.staged_mode = getattr(session.config, "turn_rules_version", 2) >= 3
        self.choice_buttons: dict[str, QPushButton] = {}
        self._scene_key = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        heading.addWidget(text_label("依次 · 亲历本旬", "sectionTitle"), 1)
        self.progress_label = text_label("", "metricLabel")
        heading.addWidget(self.progress_label)
        layout.addLayout(heading)
        self.stage_bar = QWidget()
        stage_row = QHBoxLayout(self.stage_bar)
        stage_row.setContentsMargins(0, 0, 0, 0)
        stage_row.setSpacing(8)
        self.stage_labels = {}
        for stage in ("court", "work", "private"):
            stage_label = text_label("")
            stage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stage_labels[stage] = stage_label
            stage_row.addWidget(stage_label, 1)
        layout.addWidget(self.stage_bar)
        self.turn_progress = QProgressBar()
        self.turn_progress.setObjectName("pursuitProgress")
        self.turn_progress.setFixedHeight(8)
        self.turn_progress.setTextVisible(False)
        layout.addWidget(self.turn_progress)
        self.pause_label = text_label("", "notice")
        self.pause_label.hide()
        layout.addWidget(self.pause_label)

        body = QHBoxLayout()
        body.setSpacing(12)
        schedule_card, schedule = panel()
        schedule_card.setMinimumWidth(295)
        schedule_card.setMaximumWidth(440)
        schedule.addWidget(text_label("日程次序", "sectionTitle"))
        self.schedule_table = QTableWidget(0, 3)
        self.schedule_table.setHorizontalHeaderLabels(["活动", "AP", "状态"])
        self.schedule_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.schedule_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.schedule_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.schedule_table.verticalHeader().hide()
        self.schedule_table.verticalHeader().setDefaultSectionSize(39)
        self.schedule_table.setAlternatingRowColors(True)
        self.schedule_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.schedule_table.setColumnWidth(1, 40)
        self.schedule_table.setColumnWidth(2, 72)
        self.schedule_table.itemSelectionChanged.connect(self._show_selected_record)
        schedule.addWidget(self.schedule_table, 1)
        self.record_label = text_label("点击已完成活动，可查看本次小结。", "subtitle")
        schedule.addWidget(self.record_label)
        body.addWidget(schedule_card, 1)

        scene_card, scene_layout = panel()
        self.scene_eyebrow = text_label("", "eyebrow")
        self.scene_title = text_label("", "title")
        self.scene_meta = text_label("", "subtitle")
        scene_layout.addWidget(self.scene_eyebrow)
        scene_layout.addWidget(self.scene_title)
        scene_layout.addWidget(self.scene_meta)
        scroll, content = scroll_content()
        scroll.widget().setObjectName("activitySceneContent")
        scroll.widget().setStyleSheet("QWidget#activitySceneContent { background: #fffef9; }")
        content.setContentsMargins(0, 10, 3, 0)
        content.setSpacing(14)
        self.scene_text = text_label("")
        self.scene_text.setStyleSheet("font-size: 15px; line-height: 1.6; padding: 4px 0;")
        self.scene_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(self.scene_text)
        self.scene_detail = text_label("", "notice")
        content.addWidget(self.scene_detail)
        self.choices_widget = QWidget()
        self.choices_layout = QVBoxLayout(self.choices_widget)
        self.choices_layout.setContentsMargins(0, 0, 0, 0)
        self.choices_layout.setSpacing(9)
        content.addWidget(self.choices_widget)
        self.work_table = QTableWidget(0, 2)
        self.work_table.setHorizontalHeaderLabels(["本类待办", "进度"])
        self.work_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.work_table.setColumnWidth(1, 94)
        self.work_table.verticalHeader().hide()
        self.work_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.work_table.setMaximumHeight(190)
        content.addWidget(self.work_table)
        self.summary_label = text_label("", "feedback")
        content.addWidget(self.summary_label)
        self.stage_picker, picker_layout = panel()
        picker_layout.setContentsMargins(12, 10, 12, 10)
        self.stage_picker_title = text_label("", "sectionTitle")
        picker_layout.addWidget(self.stage_picker_title)
        self.stage_picker_hint = text_label("", "subtitle")
        picker_layout.addWidget(self.stage_picker_hint)
        picker_row = QHBoxLayout()
        self.stage_activity_combo = QComboBox()
        self.stage_activity_combo.setAccessibleName("当前阶段临时选择活动")
        self.stage_activity_combo.currentIndexChanged.connect(self._picker_kind_changed)
        picker_row.addWidget(self.stage_activity_combo, 1)
        self.stage_activity_ap = QSpinBox()
        self.stage_activity_ap.setRange(1, 30)
        self.stage_activity_ap.setSuffix(" AP")
        self.stage_activity_ap.setAccessibleName("本次临时活动分配时间")
        self.stage_activity_ap.setFixedWidth(90)
        picker_row.addWidget(self.stage_activity_ap)
        self.stage_add_button = QPushButton("选定并继续")
        self.stage_add_button.setProperty("primary", True)
        self.stage_add_button.clicked.connect(self.add_stage_activity)
        picker_row.addWidget(self.stage_add_button)
        picker_layout.addLayout(picker_row)
        content.addWidget(self.stage_picker)
        content.addStretch()
        scene_layout.addWidget(scroll, 1)
        self.transfer_notice = text_label("", "notice")
        scene_layout.addWidget(self.transfer_notice)
        self.transfer_button = QPushButton("结束工作，剩余时间转入私生活")
        self.transfer_button.clicked.connect(self.finish_work_stage)
        scene_layout.addWidget(self.transfer_button)
        actions = QHBoxLayout()
        self.command_button = QPushButton("下达诏令")
        self.command_button.clicked.connect(self.command_requested.emit)
        actions.addWidget(self.command_button)
        actions.addStretch()
        self.continue_button = QPushButton("继续活动")
        self.continue_button.setProperty("primary", True)
        self.continue_button.clicked.connect(lambda: self.continue_activity())
        actions.addWidget(self.continue_button)
        self.finish_button = QPushButton("结束活动 · 查看小结")
        self.finish_button.setProperty("primary", True)
        self.finish_button.clicked.connect(self.finish_activity)
        actions.addWidget(self.finish_button)
        self.next_button = QPushButton("开始下一项 →")
        self.next_button.setProperty("primary", True)
        self.next_button.clicked.connect(self.start_next_activity)
        actions.addWidget(self.next_button)
        self.settle_button = QPushButton("完成本旬 · 进入下一旬 →")
        self.settle_button.setProperty("primary", True)
        self.settle_button.clicked.connect(self.settle_turn)
        actions.addWidget(self.settle_button)
        scene_layout.addLayout(actions)
        body.addWidget(scene_card, 2)
        layout.addLayout(body, 1)
        self.refresh()

    def _submit(self, result) -> None:
        self.refresh()
        self.result.emit(result)

    def start_next_activity(self) -> None:
        self._submit(self.session.start_next_activity())

    def continue_activity(self, choice: str | None = None) -> None:
        self._submit(self.session.continue_activity(choice))

    def finish_activity(self) -> None:
        self._submit(self.session.finish_activity())

    def settle_turn(self) -> None:
        self._submit(self.session.advance_turn())

    def finish_work_stage(self) -> None:
        self._submit(self.session.finish_work_stage())

    def add_stage_activity(self) -> None:
        kind = self.stage_activity_combo.currentData()
        if not kind:
            return
        pending = self._stage_pending(self.session.state.turn_stage)
        result = self.session.append_stage_activity(kind, self.stage_activity_ap.value())
        if result.ok and not pending:
            result = self.session.start_next_activity()
        self._submit(result)

    def _picker_kind_changed(self) -> None:
        kind = self.stage_activity_combo.currentData()
        office = kind in OFFICE_KINDS
        self.stage_activity_ap.setEnabled(office)
        if not office:
            self.stage_activity_ap.setValue(1)

    def _stage_pending(self, stage: str) -> list:
        return [item for item in self.session.state.activities
                if item.status == "pending" and item.turn_stage == stage]

    def _refresh_stages(self) -> None:
        self.stage_bar.setVisible(self.staged_mode)
        if not self.staged_mode:
            return
        state = self.session.state
        names = {"court": "Ⅰ 早朝", "work": "Ⅱ 工作", "private": "Ⅲ 私生活"}
        order = ("court", "work", "private", "finished")
        current = order.index(state.turn_stage)
        for index, stage in enumerate(order[:3]):
            budget = state.stage_budget[stage]
            spent = state.stage_spent[stage]
            label = self.stage_labels[stage]
            text = f"{names[stage]} · {spent} / {budget} AP"
            if stage == "court" and budget == 0:
                text = "Ⅰ 早朝 · 本旬不安排"
            label.setText(text)
            active = index == current and state.phase != Phase.PLANNING
            color = "#24574f" if active else "#e5ecdf" if index < current else "#f0f2e9"
            foreground = "#ffffff" if active else "#33584a"
            label.setStyleSheet(f"background: {color}; color: {foreground}; padding: 7px 5px; border-radius: 5px;")

    def _refresh_transfer(self, paused: bool) -> None:
        state = self.session.state
        if state.turn_stage != "work":
            return
        active = self.session.current_activity
        remaining = state.stage_remaining["work"]
        pending_count = len(self._stage_pending("work"))
        can_stop = active is None or (active.kind in OFFICE_KINDS and active.stage == "office")
        self.transfer_button.setVisible(True)
        self.transfer_button.setEnabled(not paused and can_stop)
        self.transfer_button.setText(f"结束工作，将剩余 {remaining} AP 转入私生活 →"
                                     if remaining else "工作时间已用完 · 进入私生活 →")
        details = f"转入后，私生活共有 {state.private_budget + remaining} AP。"
        if pending_count:
            details += f"尚未开始的 {pending_count} 项工作将撤下。"
        appointment_ids = {item.appointment_id for item in state.activities
                           if item.turn_stage == "work" and item.status in {"pending", "in_progress"}
                           and item.appointment_id}
        if appointment_ids:
            names = "、".join(item.label for item in state.appointments if item.id in appointment_ids)
            details += f"预约「{names}」将按缺席处理，并记下相应后果。"
        if active and can_stop:
            details += f"当前办公已投入的 {active.spent_ap} AP 与成果保留；提前结束不计完整完成。"
        elif active:
            details = "请先完成当前活动并确认小结，再结束工作阶段。"
        elif remaining:
            details += "已完成的工作与成果保留。"
        self.transfer_notice.setText(details)
        self.transfer_notice.setVisible(bool(remaining or active))

    def _refresh_stage_idle(self, paused: bool) -> None:
        state = self.session.state
        stage = state.turn_stage
        names = {"court": "早朝", "work": "工作", "private": "私生活", "finished": "旬末"}
        previous = next((item for item in reversed(state.activities)
                         if item.status in {"completed", "replaced", "stopped"}), None)
        self.scene_eyebrow.setText(f"{names[stage]}阶段")
        if previous:
            self.summary_label.setText(f"{previous.label} · 小结\n{previous.summary or STATUS_LABELS.get(previous.status, '')}")
            self.summary_label.show()
        if stage == "finished":
            self.scene_title.setText("本旬三阶段已完成")
            self.scene_meta.setText(f"本旬已投入 {state.ap_spent} AP")
            self.scene_text.setText("早朝、工作与私生活均已落定。确认旬末结算后，进入下一旬的新安排。")
            self.settle_button.show()
            self.settle_button.setEnabled(not paused)
            return
        remaining = state.stage_remaining[stage]
        unallocated = state.stage_unallocated[stage]
        pending = self._stage_pending(stage)
        self.scene_title.setText("继续本阶段的安排" if pending else
                                 f"这一段时间，{ '要办些什么' if stage == 'work' else '如何度过' }" if remaining else
                                 f"{names[stage]}阶段已完成")
        self.scene_meta.setText(f"本阶段尚余 {remaining} AP · 已预排待执行 {len(pending)} 项 · 待临时选择 {unallocated} AP")
        self.scene_text.setText(
            f"接下来：{pending[0].label}。仍按本阶段已排定的次序执行。" if pending else
            "可以继续选择一项工作，也可以结束办公，将真正尚未用到的时间转入私生活。" if stage == "work" and remaining else
            "从私生活活动中选一项，给这段时间一个去处。私生活时间只用于本阶段。" if stage == "private" and remaining else
            "确认后继续进入后面的阶段。")
        self.next_button.setVisible(bool(pending) or remaining <= 0)
        self.next_button.setText(f"开始{pending[0].label} →" if pending else "继续下一阶段 →")
        self.next_button.setEnabled(not paused)
        if stage not in {"work", "private"} or unallocated <= 0:
            return
        self.stage_picker.show()
        self.stage_picker.setEnabled(not paused)
        self.stage_picker_title.setText("临时选择一项工作" if stage == "work" else "临时选择一项私生活活动")
        self.stage_picker_hint.setText("新选择会排在本阶段已有活动之后。" if pending else
                                       f"本阶段有 {unallocated} AP 尚未预排，选定后开始这项活动。")
        self.stage_add_button.setText("加入阶段末尾" if pending else "选定并开始")
        previous_kind = self.stage_activity_combo.currentData()
        self.stage_activity_combo.blockSignals(True)
        self.stage_activity_combo.clear()
        for kind, name, description, cost in CATALOGUE:
            if kind == "court" or (kind in WORK_KINDS) != (stage == "work"):
                continue
            self.stage_activity_combo.addItem(name, kind)
            self.stage_activity_combo.setItemData(self.stage_activity_combo.count() - 1, description,
                                                  Qt.ItemDataRole.ToolTipRole)
        previous_index = self.stage_activity_combo.findData(previous_kind)
        if previous_index >= 0:
            self.stage_activity_combo.setCurrentIndex(previous_index)
        self.stage_activity_combo.blockSignals(False)
        self.stage_activity_ap.setMaximum(max(1, unallocated))
        self._picker_kind_changed()

    def _clear_choices(self) -> None:
        self.choice_buttons.clear()
        while self.choices_layout.count():
            item = self.choices_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_selected_record(self) -> None:
        row = self.schedule_table.currentRow()
        if 0 <= row < len(self.session.state.activities):
            activity = self.session.state.activities[row]
            summary = getattr(activity, "summary", "")
            self.record_label.setText(summary or
                                      ("尚未完成。活动过程中可随时保存，再从原处继续。"
                                       if activity.status != "replaced" else "此项活动已被急报中止，不计完整完成。"))

    def refresh(self, session: GameSession | None = None) -> None:
        if session is not None:
            self.session = session
        state = self.session.state
        self.staged_mode = getattr(self.session.config, "turn_rules_version", 2) >= 3
        active = self.session.current_activity
        current_id = active.id if active else None
        completed = sum(item.status == "completed" for item in state.activities)
        finished = sum(item.status in {"completed", "replaced", "cancelled", "stopped"} for item in state.activities)
        spent = getattr(state, "ap_spent", 0)
        self.progress_label.setText(f"已完成 {completed} / {len(state.activities)} 项    ·    已用 {spent} / {state.ap_capacity} AP")
        if self.staged_mode:
            stopped = sum(item.status == "stopped" for item in state.activities)
            self.progress_label.setText(f"已完成 {completed} 项"
                                        + (f" · 提前结束 {stopped} 项" if stopped else "")
                                        + f"    ·    已用 {spent} / {state.ap_capacity} AP")
        self.turn_progress.setRange(0, state.ap_capacity)
        self.turn_progress.setValue(spent)
        self._refresh_stages()
        selected_id = None
        row = self.schedule_table.currentRow()
        if 0 <= row < self.schedule_table.rowCount():
            item = self.schedule_table.item(row, 0)
            if item:
                selected_id = item.data(Qt.ItemDataRole.UserRole)
        self.schedule_table.blockSignals(True)
        self.schedule_table.setRowCount(len(state.activities))
        for index, activity in enumerate(state.activities):
            values = (f"{index + 1:02d}  {activity.label}",
                      str(activity.reserved_ap if self.staged_mode else activity.cost),
                      STATUS_LABELS.get(activity.status, activity.status))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, activity.id)
                if column:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.schedule_table.setItem(index, column, item)
            if activity.id == current_id or (not active and activity.id == selected_id):
                self.schedule_table.selectRow(index)
        self.schedule_table.blockSignals(False)
        self._show_selected_record()
        paused = state.phase in {Phase.INTERRUPTED, Phase.REMONSTRANCE}
        self.pause_label.setVisible(paused)
        self.pause_label.setText("日程已暂停。请到「朝政与急报」处理急报，随后从保存的活动进度继续。"
                                 if state.phase == Phase.INTERRUPTED else
                                 "诏令正等待裁决。请到「朝政与急报」回应劝谏，再继续活动。")
        self.command_button.setVisible(bool(active and active.kind == "court"))
        self.command_button.setEnabled(not paused and state.court_open)
        self.continue_button.hide()
        self.finish_button.hide()
        self.next_button.hide()
        self.settle_button.hide()
        self.work_table.hide()
        self.scene_detail.hide()
        self.summary_label.hide()
        self.stage_picker.hide()
        self.transfer_button.hide()
        self.transfer_notice.hide()
        self._clear_choices()
        self.choices_widget.setEnabled(not paused)

        if state.phase == Phase.PLANNING:
            self.scene_eyebrow.setText("旬初规划")
            self.scene_title.setText("这一旬，尚待安排")
            self.scene_meta.setText("工作与私生活共用整旬预算")
            self.scene_text.setText("在「本旬规划」确定早朝与两类时间预算。可以预排活动，也可以开始后到各阶段再选。"
                                    if self.staged_mode else "在「本旬规划」分配时间、排好活动顺序，开始后便可逐项亲历。")
            return

        if self.staged_mode:
            self._refresh_transfer(paused)
            if active is None:
                self._refresh_stage_idle(paused)
                return

        if active is None:
            previous = next((item for item in reversed(state.activities)
                             if item.status in {"completed", "replaced"}), None)
            all_finished = bool(state.activities) and finished == len(state.activities)
            self.scene_eyebrow.setText("旬末将至" if all_finished else "活动间歇")
            self.scene_title.setText("本旬日程已完成" if all_finished else "上一项已落定")
            self.scene_meta.setText("确认小结后，再进入下一步")
            self.scene_text.setText("所有安排均已走完。完成本旬后，人物目标与按旬持续的修正将统一结算。"
                                    if all_finished else "日程按原先排定的次序继续，下一项尚未开始。")
            if previous:
                self.summary_label.setText(f"{previous.label} · 小结\n{previous.summary or STATUS_LABELS.get(previous.status, '')}")
                self.summary_label.show()
            self.next_button.setVisible(not all_finished)
            self.next_button.setText("开始下一项 →")
            self.settle_button.setVisible(all_finished)
            self.next_button.setEnabled(not paused)
            self.settle_button.setEnabled(not paused)
            return

        scene = active.scene or {}
        self.scene_eyebrow.setText("早朝阶段" if self.staged_mode and active.kind == "court" else
                                  "工作时段" if active.category == "work" else "私人时光")
        self.scene_title.setText(str(scene.get("title") or active.label))
        self.scene_meta.setText(f"第 {state.activities.index(active) + 1} 项 · {active.label}    "
                                f"安排 {active.cost} AP · 已用 {active.spent_ap} AP")
        self.scene_text.setText(str(scene.get("text") or scene.get("description") or
                                    ("群臣列班，奏事有序。可听取议题，也可在诏书额度内下达命令。" if active.kind == "court" else
                                     "已进入这段安排。按本次活动提供的选项继续，完成后查看小结。")))
        detail_parts = []
        for key, label in (("opportunities", "剩余探索机会"), ("rounds", "已完成轮数"),
                           ("score", "本次成绩"), ("progress", "活动进度")):
            if key in scene and isinstance(scene[key], (str, int, float)):
                detail_parts.append(f"{label}：{scene[key]}")
        if detail_parts:
            self.scene_detail.setText("    ·    ".join(detail_parts))
            self.scene_detail.show()
        choices = scene.get("choices", [])
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            choice_id = str(choice.get("id", ""))
            if choice_id == "finish" and active.stage in {"ready", "court"}:
                continue
            button = QPushButton(str(choice.get("label", choice_id)))
            button.setMinimumHeight(38)
            button.setStyleSheet("text-align: left; padding: 10px 14px;")
            button.clicked.connect(lambda checked=False, key=choice_id: self.continue_activity(key))
            if choice.get("description"):
                button.setToolTip(str(choice["description"]))
            self.choices_layout.addWidget(button)
            self.choice_buttons[choice_id] = button
        ready = active.stage in {"ready", "court", "completed"}
        self.finish_button.setVisible(ready)
        self.finish_button.setEnabled(not paused)
        self.finish_button.setText("散朝 · 完成本项" if active.kind == "court" else "完成活动 · 查看小结")
        self.continue_button.setVisible(not ready and not choices)
        self.continue_button.setEnabled(not paused)
        if active.summary:
            self.summary_label.setText(active.summary)
            self.summary_label.show()
        if active.kind in {"paperwork", "audience", "palace"}:
            items = [item for item in getattr(state, "work_items", []) if item.get("kind") == active.kind]
            self.work_table.setRowCount(len(items))
            for index, item in enumerate(items):
                self.work_table.setItem(index, 0, QTableWidgetItem(str(item.get("title", "待办"))))
                self.work_table.setItem(index, 1, QTableWidgetItem(
                    "已办结" if item.get("status") == "completed" else
                    f"{item.get('progress', 0)} / {item.get('complexity', 0)}"))
            self.work_table.setVisible(bool(items))
