"""Desktop shell for the first playable, deliberately non-simulating framework."""

from __future__ import annotations

import html
import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextBrowser, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from dynasty.content import HistoryRepository, load_demo_config, project_root, user_data_dir
from dynasty.core import ACTIVITY_LABELS, GameSession, Phase
from dynasty.ui.dialogs import CommandEditor, MonthPlanDialog
from dynasty.ui.emperor_page import EmperorPage
from dynasty.ui.county_page import CountyPage
from dynasty.ui.map_view import ProvinceMap
from dynasty.ui.theme import STYLE, initialize_fonts


def label(text: str, name: str | None = None) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if name:
        widget.setObjectName(name)
    return widget


def button(text: str, callback=None, *, primary=False, name="") -> QPushButton:
    widget = QPushButton(text)
    widget.setProperty("primary", primary)
    if name:
        widget.setObjectName(name)
    if callback:
        widget.clicked.connect(callback)
    return widget


def card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 15, 18, 15)
    layout.setSpacing(12)
    if title:
        layout.addWidget(label(title, "sectionTitle"))
    return frame, layout


def string_value(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


TYPE_NAMES = {"prefecture": "府", "subprefecture": "州", "county": "县",
              "military_or_native_office": "卫所 / 土司"}


def verification_label(record: dict) -> str:
    status = record.get("verification_status", "")
    if record.get("active_in_scenario") is False or "temporal_review" in status:
        return "原文已收录 · 1500 年建制待核"
    if "exact_1500_geometry_pending" in status:
        return "大区与治所已核 · 边界待复原"
    if status == "downloaded_hash_verified":
        return "已下载 · 文件校验通过"
    return record.get("verification_note", record.get("note", status or "见原文证据"))


class MainWindow(QMainWindow):
    main_menu_requested = Signal()
    new_game_requested = Signal()

    def __init__(self, repository: HistoryRepository | None = None, session: GameSession | None = None) -> None:
        super().__init__()
        initialize_fonts()
        self.repository = repository or HistoryRepository()
        self.session = session or GameSession.new_game(self.repository.initial_world(), load_demo_config(self.repository.root))
        self._m03_mode = getattr(self.session.config, "turn_rules_version", 1) >= 2
        self.menu_managed = False
        self.setWindowTitle("大明 · 御览 | 皇帝模拟框架")
        self.resize(1480, 940)
        self.setMinimumSize(1180, 800)
        self.setStyleSheet(STYLE)
        self.selected_region = None
        self.last_save: Path | None = None
        outer = QWidget()
        outer_layout = QHBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        self.setCentralWidget(outer)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(20, 27, 20, 22)
        nav.setSpacing(9)
        nav.addWidget(label("大 明", "seal"))
        nav.addWidget(label("御览", "brand"))
        nav.addWidget(label("皇帝角色模拟框架"))
        self.ruler_label = label("")
        nav.addWidget(self.ruler_label)
        nav.addSpacing(35)
        self.nav_buttons = []
        self.page_titles = ["天下舆图", "起居与朝政", "史料书库", "诏令与起居簿", "待议事项", "皇帝档案", "县档案"]
        for index, title in enumerate(self.page_titles):
            item = button(f"0{index + 1}   {title}", lambda _=False, i=index: self.show_page(i), name="nav")
            item.setCheckable(True)
            nav.addWidget(item)
            self.nav_buttons.append(item)
        nav.addStretch()
        self.scenario_label = label("")
        nav.addWidget(self.scenario_label)
        nav.addWidget(label("地图资料基准 · 明代约 1500"))
        nav.addSpacing(15)
        nav.addWidget(label("FRAMEWORK  /  0.1\nPython · PySide6"))
        outer_layout.addWidget(sidebar)
        main = QVBoxLayout()
        main.setContentsMargins(28, 24, 28, 16)
        main.setSpacing(10)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("MING DYNASTY  /  IMPERIAL DESK", "eyebrow"))
        self.title = label("天下舆图", "title")
        titles.addWidget(self.title)
        heading.addLayout(titles, 1)
        self.menu_button = button("主菜单", self.main_menu_requested.emit, name="returnMainMenu")
        self.menu_button.hide()
        heading.addWidget(self.menu_button)
        heading.addWidget(button("新局", self.new_game))
        heading.addWidget(button("读取", self.load_game))
        heading.addWidget(button("保存", self.save_game))
        heading.addSpacing(8)
        self.advance_button = button("推进本旬 →", self.advance_turn, primary=True, name="advanceTurn")
        heading.addWidget(self.advance_button)
        main.addLayout(heading)
        self.metrics = {}
        metric_row = QHBoxLayout()
        for key, title_text in [("date", "当前时点"), ("ap", "行动力 · 已安排 / 总量"), ("edicts", "本旬可用诏书"), ("debt", "待扣应急诏书")]:
            frame, metric_layout = card()
            if self._m03_mode:
                metric_layout.setContentsMargins(14, 7, 14, 7)
            metric_layout.setSpacing(3)
            metric_layout.addWidget(label(title_text, "metricLabel"))
            value = label("—", "metricValue")
            self.metrics[key] = value
            metric_layout.addWidget(value)
            metric_row.addWidget(frame)
        main.addLayout(metric_row)
        self.preview_notice = label("框架预览：已接入时间、指令流程与皇帝档案；人口、钱粮、忠心等国家数值尚未模拟。", "notice")
        self.preview_notice.setVisible(not self._m03_mode)
        main.addWidget(self.preview_notice)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._map_page())
        self.stack.addWidget(self._court_page())
        self.stack.addWidget(self._history_page())
        self.stack.addWidget(self._ledger_page())
        self.stack.addWidget(self._pending_page())
        self.emperor_page = EmperorPage(self.session)
        self.emperor_page.profile_updated.connect(self._message)
        self.emperor_page.activity_draft_provider = self._activity_draft
        self.emperor_page.health_updated.connect(self._emperor_health_updated)
        self.emperor_page.activity_requested.connect(self._arrange_personal_activity)
        self.stack.addWidget(self.emperor_page)
        self.county_page = CountyPage(self.session, on_changed=self.refresh)
        self.county_page.advance_guard = self._county_advance_guard
        self.stack.addWidget(self.county_page)
        main.addWidget(self.stack, 1)
        self.feedback = label("先安排本旬活动，再进入朝政。也可以统筹连续三旬。", "feedback")
        self.feedback.setMinimumHeight(28)
        main.addWidget(self.feedback)
        self.feedback.setVisible(not self._m03_mode)
        outer_layout.addLayout(main, 1)
        self.statusBar().showMessage("地方地图为治所参考点示意；明代行政边界尚未复原。")
        self.show_page(0)
        if self.repository.regions:
            self.select_region(self.repository.regions[0]["id"])
        self.refresh()

    def show_page(self, index: int) -> None:
        if not hasattr(self, "stack"):
            return
        self.stack.setCurrentIndex(index)
        self.title.setText(self.page_titles[index])
        for i, item in enumerate(self.nav_buttons):
            item.setChecked(i == index)
        if index == 0:
            self.map.reset_view()

    def _county_advance_guard(self):
        from dynasty.core.models import ActionResult
        if self._m03_mode and self.planning_page._dirty:
            return ActionResult("error", "起居规划有未保存的活动或预算，请先返回起居与朝政处理草稿。")
        return ActionResult("ok", "可以进入演示休息旬。")

    def _map_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.addWidget(label("两京十三布政使司  /  点击治所查看府州县", "sectionTitle"), 1)
        top.addWidget(button("复位", lambda: self.map.reset_view()))
        top.addWidget(button("1580 年参考图 ↗", self.open_reference_map))
        layout.addLayout(top)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.map = ProvinceMap(self.repository)
        self.map.region_selected.connect(self.select_region)
        split.addWidget(self.map)
        frame, side = card()
        self.region_select = QComboBox()
        self.region_select.setObjectName("regionSelect")
        for row in self.repository.regions:
            self.region_select.addItem(row["name"], row["id"])
        self.region_select.currentIndexChanged.connect(lambda: self.select_region(self.region_select.currentData()))
        side.addWidget(self.region_select)
        self.region_title = label("地方档案", "sectionTitle")
        self.region_description = label("请选择地区")
        side.addWidget(self.region_title)
        side.addWidget(self.region_description)
        self.region_tree = QTreeWidget()
        self.region_tree.setHeaderLabels(["行政单位", "类型"])
        self.region_tree.setAlternatingRowColors(True)
        self.region_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.region_tree.itemClicked.connect(self._local_record_clicked)
        side.addWidget(self.region_tree, 1)
        self.region_note = label("《明史》名录包含不同时期沿革，非全部为 1500 年同时存在。", "subtitle")
        side.addWidget(self.region_note)
        side.addWidget(button("对此地拟旨 →", self.order_for_selected_region, primary=True))
        split.addWidget(frame)
        split.setSizes([760, 330])
        layout.addWidget(split, 1)
        layout.addWidget(label("底图：Natural Earth 陆地轮廓，无现代国界或省界。点位采用治所所在现代城市的参考坐标，不代表精确明代城址。", "subtitle"))
        return page

    def select_region(self, identifier: str | None) -> None:
        row = self.repository.by_id("regions", identifier)
        if not row:
            return
        self.selected_region = identifier
        self.map.select_region(identifier)
        self.region_select.blockSignals(True)
        self.region_select.setCurrentIndex(self.region_select.findData(identifier))
        self.region_select.blockSignals(False)
        self.region_title.setText(row["name"])
        prefectures = self.repository.region_rows("prefectures", identifier)
        counties = self.repository.region_rows("counties", identifier)
        capital = row.get("capital", row.get("capital_name", "待核"))
        self.region_description.setText(f"治所参考：{capital}\n文献收录 {len(prefectures)} 个府州卫司条目 · {len(counties)} 个县名条目")
        self.region_tree.clear()
        parents = {}
        for record in prefectures:
            item = QTreeWidgetItem([record["name"], TYPE_NAMES.get(record.get("type"), record.get("level", "府州"))])
            item.setData(0, Qt.ItemDataRole.UserRole, record)
            self.region_tree.addTopLevelItem(item)
            parents[record["id"]] = item
        for record in counties:
            item = QTreeWidgetItem([record["name"], TYPE_NAMES.get(record.get("type"), record.get("level", "州县"))])
            item.setData(0, Qt.ItemDataRole.UserRole, record)
            parent = parents.get(record.get("parent_id", record.get("prefecture_id")))
            if parent:
                parent.addChild(item)
            else:
                self.region_tree.addTopLevelItem(item)
        if self.region_tree.topLevelItemCount():
            self.region_tree.topLevelItem(0).setExpanded(True)

    def _local_record_clicked(self, item, column) -> None:
        record = item.data(0, Qt.ItemDataRole.UserRole) or {}
        evidence = record.get("source_excerpt", record.get("evidence", record.get("note", "资料年代待核")))
        self.region_note.setText(f"{record.get('name', '')}：{string_value(evidence)[:260]}")

    def order_for_selected_region(self) -> None:
        self.show_page(1)
        if self._m03_mode:
            self.turn_tabs.setCurrentIndex(2)
        if self.selected_region:
            self.command_editor.select_target(self.selected_region)
        self._message("已选择目标地区。按日程进入早朝后，可以在此拟旨。" if self._m03_mode else
                      "已选择目标地区。请先安排处理朝政、用完本旬行动力，再进入朝政拟旨。")

    def open_reference_map(self) -> None:
        path = self.repository.directory / "raw/geography/ming_empire_1580_reference.svg"
        if not path.exists():
            self._message("参考地图文件尚未下载。", True)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("1580 年参考地图 · 不作为 1500 年精确边界")
        dialog.resize(1000, 780)
        column = QVBoxLayout(dialog)
        column.addWidget(label("资料对照图：约 1580 年，晚于当前工作基准。作者、许可和下载来源见史料书库。", "notice"))
        from PySide6.QtSvgWidgets import QSvgWidget
        svg = QSvgWidget(str(path))
        column.addWidget(svg, 1)
        close = button("关闭", dialog.accept)
        column.addWidget(close)
        dialog.exec()

    def _court_page(self) -> QWidget:
        if not self._m03_mode:
            return self._legacy_court_page()
        from dynasty.ui.planning_page import PlanningPage
        from dynasty.ui.activity_page import ActivityPage

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.turn_tabs = QTabWidget()
        self.planning_page = PlanningPage(self.session)
        self.activity_page = ActivityPage(self.session)
        self.planning_page.result.connect(self.apply_result)
        self.planning_page.changed.connect(self._refresh_draft_metrics)
        self.activity_page.result.connect(self.apply_result)
        self.planning_page.start_requested.connect(lambda: self.turn_tabs.setCurrentIndex(
            2 if self.session.state.phase in {Phase.INTERRUPTED, Phase.REMONSTRANCE} else 1))
        self.activity_page.command_requested.connect(lambda: self.turn_tabs.setCurrentIndex(2))
        self.turn_tabs.addTab(self.planning_page, "旬初 · 规划")
        self.turn_tabs.addTab(self.activity_page, "日程 · 执行")
        # Retain the proven order and emergency controls, without the old AP slots.
        court_page = self._legacy_court_page()
        obsolete = court_page.layout().takeAt(0).widget()
        obsolete.hide()
        obsolete.deleteLater()
        self.turn_tabs.addTab(court_page, "朝政 · 急报")
        layout.addWidget(self.turn_tabs, 1)
        tools = QHBoxLayout()
        self.month_button = button("安排连续三旬…", self.edit_month_plan, name="editMonth")
        self.run_month_button = button("继续三旬计划", self.run_month_plan, name="runMonth")
        tools.addWidget(self.month_button)
        tools.addWidget(self.run_month_button)
        tools.addWidget(button("未来预约…", self.edit_appointments, name="futureAppointments"))
        tools.addWidget(button("插入演示急报", self.inject_emergency, name="injectEmergency"))
        tools.addWidget(button("下一旬插入演示急报", lambda: self.inject_emergency(next_turn=True)))
        tools.addWidget(button("取消未执行预拟政令", self.cancel_planned))
        self.plan_summary = label("", "subtitle")
        tools.addWidget(self.plan_summary, 1)
        for index in range(tools.count()):
            widget = tools.itemAt(index).widget()
            if isinstance(widget, QPushButton):
                widget.setStyleSheet("padding: 5px 8px; min-height: 18px;")
        layout.addLayout(tools)
        return page

    def _legacy_court_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        left, layout = card("本旬起居")
        layout.setSpacing(7)
        left.setMinimumWidth(305)
        left.setMaximumWidth(440)
        layout.addWidget(label("每项安排占用 1 点行动力。活动效果暂不计算。", "subtitle"))
        self.activity_box = QVBoxLayout()
        self.activity_combos = []
        layout.addLayout(self.activity_box)
        self.apply_activities = button("保存本旬安排", self.save_activities, name="saveActivities")
        layout.addWidget(self.apply_activities)
        layout.addWidget(button("将空余安排为休息", self.fill_rest, name="fillRest"))
        self.open_court_button = button("进入本旬朝政", self.open_court, primary=True, name="openCourt")
        layout.addWidget(self.open_court_button)
        layout.addSpacing(8)
        layout.addWidget(label("统筹与演示", "sectionTitle"))
        self.month_button = button("安排连续三旬…", self.edit_month_plan, name="editMonth")
        layout.addWidget(self.month_button)
        self.run_month_button = button("继续三旬计划 →", self.run_month_plan, name="runMonth")
        layout.addWidget(self.run_month_button)
        layout.addWidget(button("取消本旬未执行预拟政令", self.cancel_planned))
        layout.addWidget(button("插入演示急报", self.inject_emergency, name="injectEmergency"))
        layout.addWidget(button("下一旬插入演示急报", lambda: self.inject_emergency(next_turn=True)))
        self.plan_summary = label("尚未安排月度计划", "subtitle")
        layout.addWidget(self.plan_summary)
        layout.addStretch()
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setWidget(left)
        left_scroll.setMinimumWidth(335)
        left_scroll.setMaximumWidth(440)
        for control in left.findChildren(QPushButton):
            control.setStyleSheet("QPushButton { padding: 5px 8px; min-height: 18px; }")
        row.addWidget(left_scroll, 1)
        right = QVBoxLayout()
        court, court_layout = card("上朝 · 拟定诏令")
        self.court_status = label("本旬尚未进入朝政", "subtitle")
        court_layout.addWidget(self.court_status)
        self.command_editor = CommandEditor(self.repository, self.session)
        self.command_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        court_layout.addWidget(self.command_editor)
        self.issue_button = button("下达诏令 · 登记意图", self.issue_command, primary=True, name="issueCommand")
        court_layout.addWidget(self.issue_button)
        court_layout.addWidget(label("任命与工程只记录意图，史料任职和世界指标不会改变。未指定的参数保留为委派。", "subtitle"))
        court_layout.addStretch(1)
        right.addWidget(court, 1)
        self.decision_card, decision = card("待裁决")
        self.decision_text = label("")
        decision.addWidget(self.decision_text)
        self.replacement_combo = QComboBox()
        decision.addWidget(self.replacement_combo)
        self.advice_buttons = QWidget()
        advice = QHBoxLayout(self.advice_buttons)
        advice.setContentsMargins(0, 0, 0, 0)
        advice.addWidget(button("听取劝谏 · 取消改税", lambda: self.resolve_advice(True), name="acceptAdvice"))
        insist = button("坚持下令", lambda: self.resolve_advice(False), name="insistOrder")
        insist.setProperty("danger", True)
        advice.addWidget(insist)
        decision.addWidget(self.advice_buttons)
        self.emergency_buttons = QWidget()
        responses = QHBoxLayout(self.emergency_buttons)
        responses.setContentsMargins(0, 0, 0, 0)
        responses.addWidget(button("应急下令 · 可透支诏书", self.resolve_emergency, primary=True, name="resolveEmergency"))
        responses.addWidget(button("阅报并交地方续处", lambda: self.resolve_emergency(issue=False)))
        decision.addWidget(self.emergency_buttons)
        right.addWidget(self.decision_card)
        row.addLayout(right, 2)
        return page

    def _history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label("史料书库 · 文献事实与游戏设定分开保存", "sectionTitle"))
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("检索人物、地名、官职、法律或来源…")
        self.history_search.textChanged.connect(self.filter_history)
        layout.addWidget(self.history_search)
        split = QSplitter(Qt.Orientation.Vertical)
        self.history_tabs = QTabWidget()
        self.history_tables = []
        for key, title_text in self.repository.categories.items():
            records = self.repository.tables[key]
            table = self._record_table(records)
            self.history_tabs.addTab(table, f"{title_text} · {len(records)}")
            self.history_tables.append(table)
        sources = list(self.repository.sources.values())
        table = self._record_table(sources, sources=True)
        self.history_tabs.addTab(table, f"来源 · {len(sources)}")
        self.history_tables.append(table)
        split.addWidget(self.history_tabs)
        self.history_detail = QTextBrowser()
        self.history_detail.setOpenExternalLinks(True)
        self.history_detail.setHtml("<h3>选择条目查看证据</h3><p>行政名录包含跨年代沿革；历史参考点不是精确疆界。史料未附会为人格、能力或经济数值。</p>")
        split.addWidget(self.history_detail)
        split.setSizes([360, 180])
        layout.addWidget(split, 1)
        return page

    def _record_table(self, records: list[dict], *, sources=False) -> QTableWidget:
        table = QTableWidget(len(records), 3)
        table.setHorizontalHeaderLabels(["名称 / 文献", "类型 / 时期", "核对说明"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for index, record in enumerate(records):
            name = record.get("name", record.get("title", record.get("id", "—")))
            kind = record.get("period", record.get("level", TYPE_NAMES.get(record.get("type"), "来源" if sources else "史料")))
            status = verification_label(record)
            for column, value in enumerate([name, kind, status]):
                item = QTableWidgetItem(string_value(value)[:220])
                item.setToolTip(string_value(value))
                item.setData(Qt.ItemDataRole.UserRole, record)
                table.setItem(index, column, item)
        table.itemSelectionChanged.connect(lambda: self.show_history_record(table))
        return table

    def show_history_record(self, table: QTableWidget) -> None:
        items = table.selectedItems()
        if not items:
            return
        record = items[0].data(Qt.ItemDataRole.UserRole)
        title_text = record.get("name", record.get("title", record.get("id", "资料")))
        pieces = [f"<h3>{html.escape(title_text)}</h3>"]
        field_labels = {"note": "说明", "summary": "内容", "evidence": "原文证据", "period": "时期", "verification_status": "核对状态", "temporal_note": "年代说明", "valid_from": "始年", "valid_to": "终年", "capital": "治所", "license_note": "复用说明", "source_ids": "来源索引", "roles": "任职", "role_at_baseline": "基准时点身份"}
        for key, value in record.items():
            if key in {"name", "title"} or value in (None, "", []):
                continue
            text = html.escape(string_value(value))
            if key in {"url", "source_url"} and str(value).startswith("https://"):
                text = f'<a href="{html.escape(str(value), quote=True)}">打开原始来源</a>'
            pieces.append(f"<p><b>{html.escape(field_labels.get(key, key))}</b>　{text}</p>")
        source_ids = record.get("source_ids", [])
        if isinstance(source_ids, str):
            source_ids = [source_ids]
        for source_id in source_ids:
            source = self.repository.sources.get(source_id, {})
            url = source.get("url", source.get("source_url", ""))
            if url.startswith("https://"):
                pieces.append(f'<p>来源：<a href="{html.escape(url, quote=True)}">{html.escape(source.get("title", source_id))}</a></p>')
        self.history_detail.setHtml("".join(pieces))

    def filter_history(self, query: str) -> None:
        query = query.strip().casefold()
        for table in self.history_tables:
            for row in range(table.rowCount()):
                text = " ".join(table.item(row, column).text() for column in range(table.columnCount()))
                table.setRowHidden(row, bool(query) and query not in text.casefold())

    def _ledger_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label("诏令簿 · 可追溯每次下令与暂停", "sectionTitle"))
        self.ledger_table = QTableWidget(0, 5)
        self.ledger_table.setHorizontalHeaderLabels(["旬序", "政务", "诏书", "透支", "参数与委派"])
        self.ledger_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ledger_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.ledger_table.verticalHeader().hide()
        layout.addWidget(self.ledger_table, 1)
        layout.addWidget(label("起居记录", "sectionTitle"))
        self.log_browser = QTextBrowser()
        layout.addWidget(self.log_browser, 1)
        return page

    def _pending_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label("待议事项 · 本轮可绕过的设计与史料问题", "sectionTitle"))
        self.pending_browser = QTextBrowser()
        self.pending_browser.setOpenExternalLinks(True)
        layout.addWidget(self.pending_browser, 1)
        layout.addWidget(button("打开项目文档文件夹 ↗", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(project_root() / "docs")))))
        return page

    def refresh(self) -> None:
        mode = getattr(self.session.config, "turn_rules_version", 1) >= 2
        if mode != self._m03_mode:
            self._m03_mode = mode
            old_page = self.stack.widget(1)
            index = self.stack.currentIndex()
            self.stack.removeWidget(old_page)
            old_page.deleteLater()
            self.stack.insertWidget(1, self._court_page())
            self.stack.setCurrentIndex(index)
        state = self.session.state
        self.preview_notice.setVisible(not self._m03_mode)
        self.emperor_page.refresh(self.session)
        self.county_page.refresh(self.session)
        profile = state.scenario_profile
        self.setWindowTitle(f"御览 · {profile.scenario_name} · {profile.emperor_name}")
        self.ruler_label.setText(f"{profile.emperor_name} · {profile.era_name}")
        self.scenario_label.setText(profile.scenario_name)
        self.metrics["date"].setText(state.era_date_label)
        self.metrics["date"].setToolTip(f"公元 {state.date_label}")
        self.metrics["ap"].setText(f"{state.ap_allocated} / {state.ap_capacity}")
        self.metrics["edicts"].setText(f"{state.edict_available} / {state.edict_limit}")
        self.metrics["debt"].setText(str(state.edict_debt))
        planning = state.phase == Phase.PLANNING
        if self._m03_mode:
            self.planning_page.refresh(self.session)
            self.activity_page.refresh(self.session)
            self.month_button.setEnabled(planning)
        else:
            while self.activity_box.count():
                child = self.activity_box.takeAt(0)
                if child.widget():
                    child.widget().hide()
                    child.widget().deleteLater()
            self.activity_combos = []
            for index in range(state.ap_capacity):
                widget = QWidget()
                widget.setMinimumHeight(37)
                row = QHBoxLayout(widget)
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(label(f"{index + 1:02}"))
                combo = QComboBox()
                combo.addItem("尚未安排", None)
                for kind, name in ACTIVITY_LABELS.items():
                    combo.addItem(name, kind)
                plan = next((item for item in state.month_plan if item.turn_index == state.turn_index), None)
                kinds = [item.kind for item in state.activities] or (plan.activities if plan else [])
                if index < len(kinds):
                    combo.setCurrentIndex(combo.findData(kinds[index]))
                combo.setEnabled(planning)
                row.addWidget(combo, 1)
                self.activity_combos.append(combo)
                self.activity_box.addWidget(widget)
            self.apply_activities.setEnabled(planning)
            self.month_button.setEnabled(planning)
            self.open_court_button.setEnabled(state.phase in {Phase.PLANNING, Phase.EXECUTING})
        self.issue_button.setEnabled(state.phase == Phase.EXECUTING and state.court_open)
        phases = {Phase.PLANNING: "等待安排", Phase.EXECUTING: "本旬执行中", Phase.REMONSTRANCE: "等待回应劝谏", Phase.INTERRUPTED: "急报暂停"}
        self.court_status.setText(f"{phases[state.phase]}  ·  健康 {state.health}  ·  " + ("已进入朝政" if state.court_open else "尚未进入朝政"))
        self.decision_card.setVisible(state.phase in {Phase.REMONSTRANCE, Phase.INTERRUPTED})
        advice = state.phase == Phase.REMONSTRANCE
        emergency = state.phase == Phase.INTERRUPTED
        self.advice_buttons.setVisible(advice)
        self.emergency_buttons.setVisible(emergency)
        self.replacement_combo.setVisible(emergency and not state.court_assigned)
        self.replacement_combo.clear()
        self.replacement_combo.addItem("请选择被终止的本旬活动", None)
        for activity in state.activities:
            if activity.status in {"pending", "in_progress"}:
                self.replacement_combo.addItem(f"{activity.label} · {activity.id}", activity.id)
        emergency_uses_free_time = (self.session.config.turn_rules_version >= 3
                                    and not state.court_assigned
                                    and self.replacement_combo.count() == 1
                                    and state.turn_stage in {"work", "private"}
                                    and state.stage_unallocated[state.turn_stage] >= 1)
        if emergency_uses_free_time:
            self.replacement_combo.setItemText(0, "使用当前阶段尚未安排的 1 AP 处理急报")
        if advice:
            self.decision_text.setText("大臣劝谏：近期方改税制，朝令夕改恐伤政信。听取则取消本次修改；坚持则登记忠心、声誉和政令效果惩罚，当前不实际改变世界数值。")
        elif emergency and self.session.active_emergency:
            event = self.session.active_emergency
            cost_notice = ("本旬已安排早朝，无额外行动力成本。" if state.court_assigned else
                           "本旬未安排早朝；处置将使用当前阶段尚未安排的 1 AP。" if emergency_uses_free_time else
                           "本旬未安排早朝，须终止一个未完成活动。")
            self.decision_text.setText(f"{event.title}\n{event.description}\n{cost_notice}应急命令可透支诏书，下旬扣还。")
        pending_plans = [plan for plan in state.month_plan if plan.status != "completed"]
        self.plan_summary.setText(f"计划剩余 {len(pending_plans)} 旬 · 待执行政令 " + str(sum(command.status == "pending" for plan in pending_plans for command in plan.commands)))
        self.run_month_button.setEnabled(bool(pending_plans))
        self.advance_button.setEnabled(state.phase not in {Phase.REMONSTRANCE, Phase.INTERRUPTED})
        if self._m03_mode:
            self.advance_button.setText("开始本旬 →" if planning else "继续日程 →")
            self.metrics["ap"].setToolTip(f"已安排 {state.ap_allocated} AP；实际已用 {state.ap_spent} AP")
            if state.phase in {Phase.REMONSTRANCE, Phase.INTERRUPTED}:
                self.turn_tabs.setCurrentIndex(2)
        else:
            self.advance_button.setText("推进本旬 →")
        self.ledger_table.setRowCount(len(state.command_ledger))
        for index, record in enumerate(state.command_ledger):
            values = [record["turn"] + 1, record["label"], record["cost"], record["borrowed"], json.dumps(record["parameters"], ensure_ascii=False)]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.ledger_table.setItem(index, column, item)
        self.log_browser.setHtml("".join(f"<p><span style='color:#89957f'>{html.escape(log['date'])}</span>　<b>{html.escape(log['label'])}</b>　{html.escape(log['message'])}</p>" for log in reversed(state.logs[-150:])))
        path = project_root() / "docs" / "00_项目总览" / "待确认事项.md"
        if path.exists():
            self.pending_browser.document().setBaseUrl(QUrl.fromLocalFile(str(path)))
            self.pending_browser.setMarkdown(path.read_text(encoding="utf-8"))
        else:
            self.pending_browser.setHtml("<h3>当前演示约定</h3>" + "".join(f"<p>• {html.escape(note)}</p>" for note in state.notes))
        self._refresh_draft_metrics()

    def _message(self, message: str, error=False) -> None:
        if self._m03_mode:
            self.feedback.setVisible(error)
            self.statusBar().showMessage(message)
        self.feedback.setText(message)
        self.feedback.setProperty("error", error)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

    def _refresh_draft_metrics(self) -> None:
        if self._m03_mode and self.session.state.phase == Phase.PLANNING:
            allocated = sum(activity.cost for activity in self.planning_page.draft_activities())
            self.metrics["ap"].setText(f"{allocated} / {self.session.state.ap_capacity}")
            self.metrics["ap"].setToolTip("当前规划草稿已预排的行动力；其余时间可在对应阶段选择活动。"
                                         if self.session.config.turn_rules_version >= 3 else
                                         "当前规划草稿已安排的行动力。")

    def _activity_draft(self):
        if self._m03_mode:
            return self.planning_page.draft_activities()
        return [combo.currentData() for combo in self.activity_combos]

    def _emperor_health_updated(self, message: str) -> None:
        if self._m03_mode:
            self.refresh()
            self._message(message)
            return
        draft = [combo.currentData() for combo in self.activity_combos]
        self.refresh()
        if self.session.state.phase == Phase.PLANNING:
            # Preserve slot positions when possible; compact only if the new AP
            # capacity is smaller. The editor has already rejected excess tasks.
            if len(draft) > len(self.activity_combos):
                draft = [kind for kind in draft if kind]
            for combo, kind in zip(self.activity_combos, draft):
                combo.setCurrentIndex(combo.findData(kind))
        self._message(message)

    def _arrange_personal_activity(self, kind: str) -> None:
        self.show_page(1)
        if self._m03_mode:
            if self.session.config.turn_rules_version >= 3 and self.session.state.phase != Phase.PLANNING:
                self.turn_tabs.setCurrentIndex(1)
                result = self.session.append_stage_activity(kind)
                self.apply_result(result)
                if result.ok and self.session.current_activity is None:
                    self.activity_page.start_next_activity()
                return
            self.turn_tabs.setCurrentIndex(0)
            self.planning_page.arrange_activity(kind)
            return
        if self.session.state.phase != Phase.PLANNING:
            self._message("本旬已开始，请完成本旬后安排目标所需活动。")
            return
        empty = next((combo for combo in self.activity_combos if combo.currentData() is None), None)
        if empty is None:
            self._message("本旬活动已排满，可在此调整安排以追求个人目标。")
            return
        index = empty.findData(kind)
        if index < 0:
            self._message("该目标需要的活动当前尚未开放。", error=True)
            return
        empty.setCurrentIndex(index)
        empty.setFocus()
        self._message(f"已将{ACTIVITY_LABELS[kind]}填入一个空闲行动位；完成相应活动后才会推进个人目标。")

    def apply_result(self, result) -> None:
        self._message(result.message, result.status in {"error", "replacement_required"})
        self.refresh()
        if self.session.state.phase in {Phase.REMONSTRANCE, Phase.INTERRUPTED}:
            self.show_page(1)
        elif self._m03_mode and result.status == "resolved":
            self.turn_tabs.setCurrentIndex(1)
        elif self._m03_mode and result.status == "advanced":
            self.turn_tabs.setCurrentIndex(0)

    def save_activities(self) -> None:
        if self._m03_mode:
            self.apply_result(self.planning_page.capture_draft())
            return
        kinds = [combo.currentData() for combo in self.activity_combos if combo.currentData()]
        self.apply_result(self.session.set_activities(kinds))

    def fill_rest(self) -> None:
        if self.session.state.phase == Phase.PLANNING:
            kinds = [combo.currentData() for combo in self.activity_combos if combo.currentData()]
            result = self.session.set_activities(kinds)
            if not result.ok:
                self.apply_result(result)
                return
        self.apply_result(self.session.fill_rest())

    def open_court(self) -> None:
        if not self._capture_activities():
            return
        self.apply_result(self.session.open_court())

    def issue_command(self) -> None:
        try:
            command_id, parameters = self.command_editor.payload()
        except ValueError as error:
            self._message(str(error), True)
            return
        self.apply_result(self.session.issue_command(command_id, parameters))

    def advance_turn(self) -> None:
        if not self._capture_activities():
            if self._m03_mode:
                self.show_page(1)
                self.turn_tabs.setCurrentIndex(0)
            return
        self.apply_result(self.session.advance_turn())
        if self._m03_mode:
            self.show_page(1)
            if self.session.state.phase == Phase.PLANNING:
                self.turn_tabs.setCurrentIndex(0)
            elif self.session.state.phase == Phase.EXECUTING:
                self.turn_tabs.setCurrentIndex(1)

    def _capture_activities(self) -> bool:
        if self.session.state.phase != Phase.PLANNING:
            return True
        if self._m03_mode:
            result = self.planning_page.capture_draft()
            if not result.ok:
                self._message(result.message, True)
            return result.ok
        kinds = [combo.currentData() for combo in self.activity_combos if combo.currentData()]
        result = self.session.set_activities(kinds)
        if not result.ok:
            self._message(result.message, True)
        return result.ok

    def resolve_advice(self, accept: bool) -> None:
        self.apply_result(self.session.resolve_remonstrance(accept))

    def inject_emergency(self, _checked=False, *, next_turn=False) -> None:
        state = self.session.state
        offset = 1 if next_turn else 0
        target_turn = state.turn_index + offset
        if any(event.demo and event.status in {"pending", "active"}
               and (event.trigger_turn == target_turn or (not next_turn and event.trigger_turn < target_turn))
               for event in state.emergencies):
            self._message("该旬已有待处理演示急报，请先处理后再插入。", True)
            return
        if (self.session.config.turn_rules_version < 3
                and not next_turn and state.phase == Phase.EXECUTING and not state.court_assigned
                and not any(item.status in {"pending", "in_progress"} for item in state.activities)):
            self._message("本旬已无可替换活动，请先推进，再演示新的急报。", True)
            return
        self.session.inject_emergency("演示急报 · 边关请示", "用于检验暂停、活动替代和诏书透支；不对应一条真实历史事件。", target_turn)
        self.refresh()
        self._message("已登记急报，将按所选旬的阶段规则送达；早朝期间不触发。"
                      if self.session.config.turn_rules_version >= 3 and state.phase != Phase.INTERRUPTED else
                      "已安排下一旬的演示急报。" if next_turn else
                      "演示急报已到，请先作出处置。" if self.session.state.phase == Phase.INTERRUPTED else
                      "演示急报已加入；本旬开始执行时将暂停。")
        if self.session.state.phase == Phase.INTERRUPTED:
            self.show_page(1)

    def resolve_emergency(self, _checked=False, *, issue=True) -> None:
        replacement = self.replacement_combo.currentData()
        self.apply_result(self.session.resolve_emergency(replacement, "emergency_response" if issue else None, {"target": self.selected_region}))

    def edit_month_plan(self) -> None:
        if self._m03_mode and not self._capture_activities():
            return
        if self._m03_mode:
            from dynasty.ui.month_planning_dialog import SequentialMonthPlanDialog
            dialog = SequentialMonthPlanDialog(self.repository, self.session, self)
        else:
            dialog = MonthPlanDialog(self.repository, self.session, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = self.session.set_month_plan(dialog.plans)
            self.apply_result(result)
            if result.ok and dialog.run_now:
                self.run_month_plan()

    def edit_appointments(self) -> None:
        if not self._capture_activities():
            return
        from dynasty.ui.appointments_dialog import AppointmentsDialog
        dialog = AppointmentsDialog(self.session, self)
        dialog.result.connect(self.apply_result)
        dialog.exec()
        self.planning_page.refresh(force=True)
        self.refresh()

    def run_month_plan(self) -> None:
        if not self._capture_activities():
            return
        self.apply_result(self.session.run_month_plan())
        if self._m03_mode and self.session.state.phase == Phase.EXECUTING:
            self.turn_tabs.setCurrentIndex(1)

    def cancel_planned(self) -> None:
        self.apply_result(self.session.cancel_planned_commands())

    def new_game(self) -> None:
        if self.menu_managed:
            self.new_game_requested.emit()
            return
        config = load_demo_config(self.repository.root)
        dialog = QDialog(self)
        dialog.setWindowTitle("新建框架演示存档")
        layout = QVBoxLayout(dialog)
        layout.addWidget(label(f"新局从 {config.initial_year} 年 {config.initial_month} 月第 {config.initial_xun} 旬开始。当前存档如需保留，请先取消并保存。健康仅用于验证初始行动力档位。"))
        form = QFormLayout()
        health = QSpinBox()
        health.setRange(0, 100)
        health.setValue(config.initial_health)
        form.addRow("初始健康（演示参数）", health)
        layout.addLayout(form)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        layout.addWidget(controls)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config.initial_health = health.value()
            self.session = GameSession.new_game(self.repository.initial_world(), config)
            self.last_save = None
            self.refresh()
            self._message("已建立新局；行动力取决于所选演示健康值。")

    def save_game(self) -> None:
        default = self.last_save or user_data_dir() / "弘治_存档.json"
        filename, _ = QFileDialog.getSaveFileName(self, "保存御览存档", str(default), "JSON 存档 (*.json)")
        if not filename:
            return
        if not self._capture_activities():
            return
        try:
            self.session.save_json(filename)
            self.last_save = Path(filename)
            self._message(f"已保存：{filename}")
        except (OSError, ValueError) as error:
            self._message(f"保存失败：{error}", True)

    def load_game(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "读取御览存档", str(user_data_dir()), "JSON 存档 (*.json)")
        if not filename:
            return
        try:
            replacement = GameSession.load_json(filename)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self._message(f"无法读取此存档：{error}", True)
            return
        self.session = replacement
        self.last_save = Path(filename)
        self.refresh()
        self._message(f"已恢复 {self.session.state.date_label}；计划和待回应事件保留。")
