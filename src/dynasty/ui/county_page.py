"""A readable county record for the explicitly enabled economy demonstration."""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser,
    QVBoxLayout, QWidget,
)

from dynasty.core import ActionResult, GameSession, Phase
from dynasty.ui.emperor_page import panel, scroll_content, text_label


OWNER_LABELS = {"private": "民间", "public": "官府", "royal": "皇家"}
LAND_USE_LABELS = {"farmland": "耕地", "forest": "林地", "mine": "矿地",
                   "settlement": "聚落", "unused": "未利用地"}
SECTION_LABELS = (
    "人口", "土地", "当地特产", "当地修正", "钱粮与物资", "基础设施", "生产经营", "民情与秩序",
)


def number(value: int | float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"


def percent(value: int | float) -> str:
    return f"{number(value * 100)}%"


def _input_number(value: int | float) -> str:
    """Keep editable numbers round-trippable, including wealth-band boundaries."""
    return str(int(value)) if value % 1 == 0 else repr(value)


def _income_display(income: int | float, wealth: str, thresholds: dict) -> str:
    rendered = number(income)
    upper_band = {"poor": ("ordinary", "普通"), "ordinary": ("wealthy", "富裕")}.get(wealth)
    if upper_band:
        threshold = number(thresholds[upper_band[0]])
        if float(rendered.replace(",", "")) >= float(threshold.replace(",", "")):
            return f"低于{upper_band[1]}线"
    return rendered


def _table(headers: list[str], *, stretch: int = 0) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setWordWrap(True)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(42)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    table.setMinimumHeight(90)
    return table


def _fill(table: QTableWidget, rows: list[list[str]], *, row_height: int = 42) -> None:
    table.setRowCount(len(rows))
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            table.setItem(row, column, item)
        table.setRowHeight(row, row_height)
    table.setFixedHeight(table.horizontalHeader().height() + max(1, min(len(rows), 9)) * row_height + 8)


class CountyPage(QWidget):
    """Read projections; route every mutation through the current GameSession."""

    result = Signal(object)

    def __init__(self, session: GameSession, on_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.session = session
        self.on_changed = on_changed
        self.advance_guard: Callable[[], ActionResult] | None = None
        self._view: dict | None = None
        self._reports: list[dict] = []
        self._resources: dict[str, dict] = {}
        self._industries: list[dict] = []
        self._cohorts: list[dict] = []
        self._occupation_model = False
        self._busy = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        identity = QVBoxLayout()
        self.scenario_label = text_label("一县经济 · 演示档案", "eyebrow")
        self.name_label = text_label("县级经济", "title")
        self.description_label = text_label("", "subtitle")
        identity.addWidget(self.scenario_label)
        identity.addWidget(self.name_label)
        identity.addWidget(self.description_label)
        heading.addLayout(identity, 1)
        self.advance_button = QPushButton("休息并推进一旬 →")
        self.advance_button.setObjectName("advanceCountyDemo")
        self.advance_button.setProperty("primary", True)
        self.advance_button.setToolTip("将本旬安排为完整休息，通过同一旬末结算推进县经济。")
        self.advance_button.clicked.connect(self.advance_turn)
        heading.addWidget(self.advance_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)

        self.demo_notice = text_label("", "notice")
        layout.addWidget(self.demo_notice)
        self.disabled_label = text_label(
            "本局未启用县级经济。请从一县经济演示入口建立演示局；历史县名目录不代表已有经济模拟。",
            "feedback",
        )
        layout.addWidget(self.disabled_label)

        self.metrics_widget = QWidget()
        metrics = QGridLayout(self.metrics_widget)
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setSpacing(10)
        self.metric_values: dict[str, QLabel] = {}
        for column, (key, title) in enumerate((
            ("population", "实际人口"), ("labor", "可用劳力"),
            ("grain", "民间粮食"), ("settlement", "最近结算"),
        )):
            card, content = panel()
            content.setContentsMargins(14, 10, 14, 10)
            content.setSpacing(3)
            content.addWidget(text_label(title, "metricLabel"))
            value = text_label("", "metricValue")
            self.metric_values[key] = value
            content.addWidget(value)
            metrics.addWidget(card, 0, column)
        layout.addWidget(self.metrics_widget)
        self.latest_summary_label = text_label("", "subtitle")
        layout.addWidget(self.latest_summary_label)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("QTabBar::tab { padding: 9px 12px; }")
        self.section_layouts = {}
        for title in SECTION_LABELS:
            scroll, content = scroll_content()
            content.setContentsMargins(14, 12, 14, 12)
            self.tabs.addTab(scroll, title)
            self.section_layouts[title] = content
        self._build_population()
        self._build_land()
        self._build_specialties()
        self._build_modifiers()
        self._build_resources()
        self._build_facilities()
        self._build_production()
        self._build_sentiment()
        layout.addWidget(self.tabs, 1)
        self.action_hint = text_label(
            "演示快捷推进会把皇帝本旬安排为完整休息，再结算一次县经济；已有活动、急报或预拟政令须先处理。",
            "subtitle",
        )
        layout.addWidget(self.action_hint)
        self.feedback_label = text_label("", "feedback")
        self.feedback_label.hide()
        layout.addWidget(self.feedback_label)
        self.refresh()

    def _section(self, title: str, heading: str, hint: str = "") -> QVBoxLayout:
        layout = self.section_layouts[title]
        layout.addWidget(text_label(heading, "sectionTitle"))
        if hint:
            layout.addWidget(text_label(hint, "subtitle"))
        return layout

    def _build_population(self) -> None:
        content = self._section(
            "人口", "职业与财富", "职业表示谋生与身份，财富表示生活水平；同一职业也有不同财富档。",
        )
        self.labor_summary_label = text_label("", "notice")
        content.addWidget(self.labor_summary_label)
        self.legacy_population_notice = text_label(
            "这是旧版县存档，继续沿用原人口规则。新建县级试玩后可使用职业、收入与自然人口模型。", "notice")
        content.addWidget(self.legacy_population_notice)

        self.population_columns = QWidget()
        columns = QHBoxLayout(self.population_columns)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(12)
        self.occupation_panel = QWidget()
        occupations = QVBoxLayout(self.occupation_panel)
        occupations.setContentsMargins(0, 0, 0, 0)
        occupations.addWidget(text_label("职业阶层", "sectionTitle"))
        self.population_table = _table(["职业", "人数", "基础劳力", "可用劳力", "健康 / 100"])
        self.occupation_table = self.population_table
        self.population_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        occupations.addWidget(self.population_table)
        occupations.addStretch()
        columns.addWidget(self.occupation_panel, 3)
        wealth_panel = QWidget()
        wealth = QVBoxLayout(wealth_panel)
        wealth.setContentsMargins(0, 0, 0, 0)
        wealth.addWidget(text_label("财富分档", "sectionTitle"))
        self.wealth_table = _table(["财富", "人数", "健康", "满意", "可用劳力"])
        self.wealth_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        wealth.addWidget(self.wealth_table)
        self.wealth_threshold_label = text_label("", "subtitle")
        wealth.addWidget(self.wealth_threshold_label)
        wealth.addStretch()
        columns.addWidget(wealth_panel, 2)
        content.addWidget(self.population_columns)
        self.population_detail_label = text_label("", "notice")
        content.addWidget(self.population_detail_label)
        self.population_rates_label = text_label("", "subtitle")
        content.addWidget(self.population_rates_label)

        self.income_section = QWidget()
        income = QVBoxLayout(self.income_section)
        income.setContentsMargins(0, 0, 0, 0)
        income.addWidget(text_label("收入群体", "sectionTitle"))
        self.cohorts_table = _table(["职业", "财富", "人数", "每人每旬收入", "基础劳力", "可用劳力"])
        self.cohorts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cohorts_table.itemSelectionChanged.connect(self._select_income_cohort)
        income.addWidget(self.cohorts_table)
        income.addWidget(text_label(
            "收入是人均旬收入估值，用于财富分档与短缺后果，不自动发薪或往钱池加钱。调整收入不改职业；"
            "跨档后并入同职业、同居住身份的群体，收入按人数加权。", "subtitle"))
        content.addWidget(self.income_section)

        self.population_editor, editor = panel()
        editor.addWidget(text_label("旬初试调 · 人口参数", "sectionTitle"))
        self.population_edit_hint = text_label("", "subtitle")
        editor.addWidget(self.population_edit_hint)
        parameters = QGridLayout()
        self.labor_ratio_input = QLineEdit()
        self.birth_rate_input = QLineEdit()
        self.death_rate_input = QLineEdit()
        self.basic_living_cost_input = QLineEdit()
        self.population_inputs = (
            self.labor_ratio_input, self.birth_rate_input,
            self.death_rate_input, self.basic_living_cost_input,
        )
        for index, (label, entry) in enumerate(zip((
            "劳动力比例（%）", "年出生率（%）", "年自然死亡率（%）", "基本生活成本（每人每旬）",
        ), self.population_inputs)):
            entry.setAccessibleName(label)
            entry.setPlaceholderText("非负数" if index < 3 else "正数")
            parameters.addWidget(text_label(label), index // 2 * 2, index % 2)
            parameters.addWidget(entry, index // 2 * 2 + 1, index % 2)
        self.population_apply_button = QPushButton("应用人口参数")
        self.population_apply_button.setObjectName("applyCountyPopulation")
        self.population_apply_button.clicked.connect(self.apply_population_parameters)
        parameters.addWidget(self.population_apply_button, 4, 1)
        editor.addLayout(parameters)
        income_edit = QGridLayout()
        self.income_cohort_combo = QComboBox()
        self.income_cohort_combo.setAccessibleName("选择收入群体")
        self.income_cohort_combo.setMinimumContentsLength(18)
        self.income_cohort_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.income_cohort_combo.currentIndexChanged.connect(self._load_income_value)
        self.income_value_input = QLineEdit()
        self.income_value_input.setAccessibleName("每人每旬收入")
        self.income_value_input.setPlaceholderText("每人每旬收入，非负数")
        self.income_apply_button = QPushButton("应用群体收入")
        self.income_apply_button.setObjectName("applyCountyIncome")
        self.income_apply_button.clicked.connect(self.apply_population_income)
        income_edit.addWidget(text_label("选择收入群体"), 0, 0)
        income_edit.addWidget(text_label("每人每旬收入"), 0, 1)
        income_edit.addWidget(self.income_cohort_combo, 1, 0)
        income_edit.addWidget(self.income_value_input, 1, 1)
        income_edit.addWidget(self.income_apply_button, 2, 1)
        income_edit.setColumnStretch(0, 1)
        income_edit.setColumnStretch(1, 1)
        editor.addLayout(income_edit)
        content.addWidget(self.population_editor)
        content.addStretch()

    def _build_land(self) -> None:
        content = self._section(
            "土地", "田地与产权", "面积采用演示单位；每块土地产出进入对应产权的资源池。",
        )
        self.land_summary_label = text_label("", "notice")
        content.addWidget(self.land_summary_label)
        self.land_table = _table(["地块", "用途", "产权", "面积", "肥力 / 2", "水利条件"])
        content.addWidget(self.land_table)
        content.addWidget(text_label("建筑产权与现有条件见“基础设施”；产业使用的土地和建筑见“生产经营”。", "subtitle"))
        content.addStretch()

    def _build_specialties(self) -> None:
        content = self._section("当地特产", "当地特产", "特产说明与产业实际产出分别展示。")
        self.specialties_table = _table(["特产", "说明"], stretch=1)
        content.addWidget(self.specialties_table)
        self.specialties_empty_label = text_label("本演示县尚未指定特产。", "subtitle")
        content.addWidget(self.specialties_empty_label)
        content.addStretch()

    def _build_modifiers(self) -> None:
        content = self._section("当地修正", "现有生产条件", "这里展示县级条件；建设、升级和随机事件尚未接入。")
        self.modifiers_table = _table(["条件", "说明", "效果倍率"], stretch=1)
        content.addWidget(self.modifiers_table)
        self.modifiers_empty_label = text_label("当前没有额外县级修正。", "subtitle")
        content.addWidget(self.modifiers_empty_label)
        content.addStretch()

    def _build_resources(self) -> None:
        content = self._section(
            "钱粮与物资", "三池分账", "居民消费共用民间池；官府、皇家资源不会因民间短缺自动补入。",
        )
        self.resource_table = _table(["物资与单位", "民间", "官府", "皇家"])
        content.addWidget(self.resource_table)
        card, editor = panel()
        editor.addWidget(text_label("演示试调 · 指定池余额", "sectionTitle"))
        editor.addWidget(text_label(
            "只在演示局的规划阶段开放。填写调整后的余额；设低民间粮食可观察短缺，设低产业原料可观察停产。", "subtitle"))
        form = QGridLayout()
        self.resource_owner_combo = QComboBox()
        for owner, title in OWNER_LABELS.items():
            self.resource_owner_combo.addItem(title, owner)
        self.resource_owner_combo.setAccessibleName("调整哪个资源池")
        self.resource_kind_combo = QComboBox()
        self.resource_kind_combo.setAccessibleName("调整哪种资源")
        self.resource_value_input = QLineEdit()
        self.resource_value_input.setAccessibleName("调整后的资源余额")
        self.resource_value_input.setPlaceholderText("非负数")
        self.resource_unit_label = text_label("", "subtitle")
        self.resource_apply_button = QPushButton("应用余额")
        self.resource_apply_button.setObjectName("applyCountyResource")
        self.resource_apply_button.clicked.connect(self.apply_resource)
        form.addWidget(self.resource_owner_combo, 0, 0)
        form.addWidget(self.resource_kind_combo, 0, 1)
        form.addWidget(self.resource_value_input, 1, 0)
        form.addWidget(self.resource_unit_label, 1, 1)
        form.addWidget(self.resource_apply_button, 1, 2)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        editor.addLayout(form)
        self.resource_edit_hint = text_label("", "subtitle")
        editor.addWidget(self.resource_edit_hint)
        self.resource_editor = card
        content.addWidget(card)
        self.resource_owner_combo.currentIndexChanged.connect(self._load_resource_value)
        self.resource_kind_combo.currentIndexChanged.connect(self._load_resource_value)
        content.addStretch()

    def _build_facilities(self) -> None:
        content = self._section(
            "基础设施", "建筑、归属与现有条件", "设施是本轮生产的条件输入，尚未提供建设或升级结算。",
        )
        self.facilities_table = _table(["设施", "产权", "状况", "说明"], stretch=3)
        content.addWidget(self.facilities_table)
        self.facilities_empty_label = text_label("当前没有登记设施。", "subtitle")
        content.addWidget(self.facilities_empty_label)
        content.addStretch()

    def _build_production(self) -> None:
        content = self._section(
            "生产经营", "产业按各自周期运行", "生产先投入，完成批次或到收获节点才入库；本旬成熟的产出可供本旬消费。",
        )
        self.production_table = _table(["产业 / 使用资产", "产权", "阶段", "周期进度", "需劳力", "劳力到位", "原料到位"])
        self.production_table.itemSelectionChanged.connect(self._show_industry)
        content.addWidget(self.production_table)
        self.production_detail_label = text_label("", "notice")
        content.addWidget(self.production_detail_label)
        content.addWidget(text_label("选择一项产业查看最近产出。经营自主推进，不逐项消耗皇帝行动力。", "subtitle"))
        content.addStretch()

    def _build_sentiment(self) -> None:
        content = self._section(
            "民情与秩序", "居民状况与逐旬记录", "短缺后果来自实际消费缺口；本轮不模拟治安、官员治理或奏报隐瞒。",
        )
        self.sentiment_label = text_label("", "notice")
        content.addWidget(self.sentiment_label)
        row = QHBoxLayout()
        row.addWidget(text_label("查看旬报"))
        self.report_combo = QComboBox()
        self.report_combo.setAccessibleName("选择已结算旬报")
        self.report_combo.currentIndexChanged.connect(self._show_report)
        row.addWidget(self.report_combo, 1)
        content.addLayout(row)
        self.report_summary_label = text_label("", "sectionTitle")
        content.addWidget(self.report_summary_label)
        self.consumption_table = _table(["消费物资", "需求", "实际消费", "缺口", "满足比例"])
        content.addWidget(self.consumption_table)
        self.consequences_table = _table(["财富层", "旬初人数", "死亡", "向下转层", "健康下降", "满意下降", "劳力下降"])
        content.addWidget(self.consequences_table)
        self.report_browser = QTextBrowser()
        self.report_browser.setObjectName("countyReport")
        self.report_browser.setOpenExternalLinks(False)
        self.report_browser.setMinimumHeight(230)
        content.addWidget(self.report_browser)
        self.boundary_label = text_label("", "subtitle")
        content.addWidget(self.boundary_label)
        content.addStretch()

    def refresh(self, session: GameSession | None = None) -> None:
        if session is not None:
            if session is not self.session:
                self.feedback_label.hide()
            self.session = session
        self._view = self.session.economy_view
        enabled = self._view is not None
        for widget in (self.metrics_widget, self.latest_summary_label, self.tabs, self.action_hint):
            widget.setVisible(enabled)
        self.disabled_label.setVisible(not enabled)
        self.advance_button.setEnabled(enabled and not self._busy)
        self.demo_notice.setVisible(enabled)
        if not enabled:
            self.name_label.setText("县级经济")
            self.scenario_label.setText("本局未启用")
            self.description_label.setText("普通局与旧存档继续沿用各自规则。")
            return
        view = self._view
        self.name_label.setText(view["name"])
        self.description_label.setText(view["description"])
        self.scenario_label.setText(f"一县经济演示 · {view['scenario_label']}")
        self.demo_notice.setText(view["demo_notice"])
        population = view["population"]
        self._resources = {entry["id"]: entry for entry in view["resources"]}
        pools = {entry["owner"]: entry for entry in view["pools"]}
        grain = pools["private"]["balances"].get("grain", 0)
        self.metric_values["population"].setText(f"{number(population['total'])} 人")
        self.metric_values["labor"].setText(f"{number(population['available_labor'])} 人")
        self.metric_values["grain"].setText(f"{number(grain)} {self._unit('grain')}")
        settled = view["last_settled_turn"]
        self.metric_values["settlement"].setText("尚未结算" if settled is None or settled < 0 else f"第 {settled + 1} 旬")
        last_report = view["last_report"]
        self.latest_summary_label.setText(
            last_report["summary"] if last_report else "尚无旬报。正常生产、缺粮或缺料的变化将在实际旬末结算后记录。")

        self._refresh_population(view)
        land = view["land"]
        self.land_summary_label.setText(
            f"总面积 {number(land['total_area'])}　·　已耕 {number(land['cultivated_area'])}"
            f"　·　可开垦 {number(land['reclaimable_area'])}　（演示面积单位）")
        _fill(self.land_table, [[
            item["label"], LAND_USE_LABELS.get(item["use"], item["use"]), item["owner_label"], number(item["area"]),
            number(item["fertility"]), percent(item["irrigation"]),
        ] for item in land["parcels"]])
        _fill(self.specialties_table, [[item["name"], item["description"]] for item in view["specialties"]], row_height=58)
        self.specialties_table.setVisible(bool(view["specialties"]))
        self.specialties_empty_label.setVisible(not view["specialties"])
        _fill(self.modifiers_table, [[
            item["name"], item["description"], f"× {number(item['multiplier'])}",
        ] for item in view["modifiers"]], row_height=58)
        self.modifiers_table.setVisible(bool(view["modifiers"]))
        self.modifiers_empty_label.setVisible(not view["modifiers"])
        _fill(self.resource_table, [[
            f"{resource['label']} · {resource['unit']}",
            *[number(pools[owner]["balances"].get(resource["id"], 0)) for owner in OWNER_LABELS],
        ] for resource in view["resources"]])
        resource_id = self.resource_kind_combo.currentData()
        self.resource_kind_combo.blockSignals(True)
        self.resource_kind_combo.clear()
        for resource in view["resources"]:
            self.resource_kind_combo.addItem(resource["label"], resource["id"])
        index = self.resource_kind_combo.findData(resource_id or "grain")
        self.resource_kind_combo.setCurrentIndex(max(0, index))
        self.resource_kind_combo.blockSignals(False)
        planning = self.session.state.phase == Phase.PLANNING
        for widget in (self.resource_owner_combo, self.resource_kind_combo,
                       self.resource_value_input, self.resource_apply_button):
            widget.setEnabled(planning and not self._busy)
        self.resource_edit_hint.setText(
            "只修改所选池，不自动补齐其他池；修改后可保存本局。" if planning
            else "本旬已开始：请完成当前旬后再试调资源。")
        self._load_resource_value()
        _fill(self.facilities_table, [[
            item["label"], item["owner_label"], percent(item["condition"]), item["description"],
        ] for item in view["facilities"]], row_height=60)
        self.facilities_table.setVisible(bool(view["facilities"]))
        self.facilities_empty_label.setVisible(not view["facilities"])

        selected_industry = self.production_table.currentRow()
        self._industries = view["industries"]
        self.production_table.blockSignals(True)
        _fill(self.production_table, [[
            f"{item['label']}\n{item['asset_label']}", item["owner_label"], item["state"],
            f"{number(item['progress'])} / {number(item['cycle_turns'])} 旬",
            number(item["workers_needed"]), percent(item["last_labor_ratio"]), percent(item["last_input_ratio"]),
        ] for item in self._industries], row_height=60)
        if self._industries:
            self.production_table.selectRow(max(0, min(selected_industry, len(self._industries) - 1)))
        self.production_table.blockSignals(False)
        self._show_industry()
        sentiment = view["sentiment"]
        self.sentiment_label.setText(
            f"居民平均健康 {number(sentiment['health'])} / 100"
            f"　·　平均满意 {number(sentiment['satisfaction'])} / 100"
            f"　·　劳力效能 {percent(sentiment['labor_factor'])}")
        selected_turn = self.report_combo.currentData()
        self._reports = sorted(view["history"], key=lambda report: report["turn_index"], reverse=True)
        if last_report and not any(item["turn_index"] == last_report["turn_index"] for item in self._reports):
            self._reports.insert(0, last_report)
        self.report_combo.blockSignals(True)
        self.report_combo.clear()
        for report in self._reports:
            self.report_combo.addItem(
                f"第 {report['turn_index'] + 1} 旬 · {report['month']}月{['上', '中', '下'][report['xun'] - 1]}旬",
                report["turn_index"],
            )
        index = self.report_combo.findData(selected_turn)
        self.report_combo.setCurrentIndex(max(0, index))
        self.report_combo.blockSignals(False)
        self.report_combo.setEnabled(bool(self._reports))
        self._show_report()
        self.boundary_label.setText("\n".join(view["notices"]))

    def _refresh_population(self, view: dict) -> None:
        population = view["population"]
        self._occupation_model = view.get("population_editable", False)
        self.legacy_population_notice.setVisible(not self._occupation_model)
        self.occupation_panel.setVisible(self._occupation_model)
        self.income_section.setVisible(self._occupation_model)
        _fill(self.wealth_table, [[
            group["label"], number(group["population"]), number(group["health"]),
            number(group["satisfaction"]), number(group["available_labor"]),
        ] for group in view["wealth_groups"]], row_height=34)
        self.population_detail_label.setText(
            f"户数 {number(population['households'])}　·　流民 {number(population['transients'])} 人"
            f"　·　持续缺粮 {population['shortage_turns']} 旬")
        planning = self.session.state.phase == Phase.PLANNING
        editable = self._occupation_model and planning and not self._busy
        for widget in (*self.population_inputs, self.population_apply_button,
                       self.income_cohort_combo, self.income_value_input, self.income_apply_button):
            widget.setEnabled(editable)
        self.income_cohort_combo.blockSignals(True)
        selected_id = self.income_cohort_combo.currentData()
        self.income_cohort_combo.clear()
        self._cohorts = [row for row in view.get("cohorts", []) if row["population"] > 0]
        if not self._occupation_model:
            self.labor_summary_label.setText(
                f"可用劳力 {number(population['available_labor'])} 人 · 沿用此存档的旧版折算规则")
            self.wealth_threshold_label.setText("沿用旧版财富分组；没有职业与收入记录。")
            self.population_rates_label.setText("旧版县未启用自然出生、自然死亡或新版劳动力比例。")
            self.population_edit_hint.setText("旧县存档不转换人口规则；新建县级试玩后可调整这些参数。")
            for entry in (*self.population_inputs, self.income_value_input):
                entry.clear()
            self.income_cohort_combo.blockSignals(False)
            return

        self.labor_summary_label.setText(
            f"基础劳力 = {number(population['total'])} 人 × {percent(population['labor_ratio'])}"
            f" = {number(population['base_labor'])} 人\n"
            f"可用劳力 {number(population['available_labor'])} 人 · 再按居民健康与劳力效能折算")
        _fill(self.population_table, [[
            group["label"], number(group["population"]), number(group["base_labor"]),
            number(group["available_labor"]), number(group["health"]),
        ] for group in view["occupation_groups"]], row_height=34)
        thresholds = population["wealth_thresholds"]
        self.wealth_threshold_label.setText(
            f"按每人每旬收入分档：\n贫困：低于 {number(thresholds['ordinary'])}\n"
            f"普通：{number(thresholds['ordinary'])} 至 {number(thresholds['wealthy'])} 以下\n"
            f"富裕：{number(thresholds['wealthy'])} 及以上\n"
            "职业表与财富表各自合计均为总人口，两者不相加。")
        self.population_rates_label.setText(
            f"年出生率 {percent(population['annual_birth_rate'])}　·　年自然死亡率 {percent(population['annual_death_rate'])}"
            f"　·　年率按 {population['turns_per_year']} 旬折算，逐旬积累小数余量。\n"
            f"基本生活成本 {number(population['basic_living_cost'])} / 人 / 旬；缺粮死亡在自然死亡之外另计。")
        self.cohorts_table.blockSignals(True)
        _fill(self.cohorts_table, [[
            group["occupation_label"], group["wealth_label"], number(group["population"]),
            _income_display(group["income_per_capita"], group["wealth"], thresholds),
            number(group["base_labor"]), number(group["available_labor"]),
        ] for group in self._cohorts], row_height=34)
        for row, group in enumerate(self._cohorts):
            self.cohorts_table.item(row, 3).setToolTip(f"每人每旬收入：{group['income_per_capita']}")
        self.cohorts_table.blockSignals(False)
        for group in self._cohorts:
            self.income_cohort_combo.addItem(
                f"{group['occupation_label']} · {group['wealth_label']} · {number(group['population'])}人"
                f" · {group['resident_label']}", group["id"],
            )
        index = self.income_cohort_combo.findData(selected_id)
        self.income_cohort_combo.setCurrentIndex(max(0, index))
        self.income_cohort_combo.blockSignals(False)
        self.income_apply_button.setEnabled(editable and bool(self._cohorts))
        for entry, value in zip(self.population_inputs, (
            population["labor_ratio"] * 100, population["annual_birth_rate"] * 100,
            population["annual_death_rate"] * 100, population["basic_living_cost"],
        )):
            entry.setText(_input_number(value))
        self.population_edit_hint.setText(
            "演示参数只在旬初调整。四项参数统一应用；基础劳力与财富分档会立即重算。" if planning
            else "本旬已开始，完成当前旬后才能调整人口参数与收入。")
        self._load_income_value()

    def _select_income_cohort(self) -> None:
        row = self.cohorts_table.currentRow()
        if 0 <= row < len(self._cohorts):
            index = self.income_cohort_combo.findData(self._cohorts[row]["id"])
            if index >= 0:
                self.income_cohort_combo.setCurrentIndex(index)

    def _load_income_value(self) -> None:
        identifier = self.income_cohort_combo.currentData()
        cohort = next((row for row in self._cohorts if row["id"] == identifier), None)
        self.income_value_input.setText(_input_number(cohort["income_per_capita"]) if cohort else "")

    def _unit(self, identifier: str) -> str:
        return self._resources.get(identifier, {}).get("unit", "演示单位")

    def _resource_text(self, balances: dict, *, signed: bool = False) -> str:
        parts = []
        for identifier, amount in balances.items():
            if not amount:
                continue
            resource = self._resources.get(identifier, {"label": identifier, "unit": ""})
            prefix = "+" if signed and amount > 0 else ""
            parts.append(f"{resource['label']} {prefix}{number(amount)} {resource['unit']}")
        return "；".join(parts) or "无"

    def _load_resource_value(self) -> None:
        if not self._view:
            return
        owner = self.resource_owner_combo.currentData()
        resource = self.resource_kind_combo.currentData()
        pool = next((item for item in self._view["pools"] if item["owner"] == owner), None)
        if pool is None or resource is None:
            return
        value = pool["balances"].get(resource, 0)
        self.resource_value_input.setText(str(value))
        self.resource_unit_label.setText(f"单位：{self._unit(resource)}")

    def _show_industry(self) -> None:
        row = self.production_table.currentRow()
        if not 0 <= row < len(self._industries):
            self.production_detail_label.setText("当前没有正在经营的产业。")
            return
        item = self._industries[row]
        self.production_detail_label.setText(
            f"{item['label']} · {item['category_label']}\n"
            f"规模 {number(item['scale'])}（演示规模单位），产出归{item['owner_label']}。\n"
            f"最近产出：{self._resource_text(item['last_output'])}")

    def _show_report(self) -> None:
        row = self.report_combo.currentIndex()
        if not 0 <= row < len(self._reports):
            self.report_summary_label.setText("尚无已结算旬报")
            self.consumption_table.hide()
            self.consequences_table.hide()
            self.report_browser.setPlainText("完成一旬后，这里会记录生产、消费、人口变化及财富变化。查看或刷新页面不会推进县经济。")
            return
        report = self._reports[row]
        self.consumption_table.show()
        self.consequences_table.show()
        natural_model = "births" in report
        if natural_model:
            self.report_summary_label.setText(
                f"人口 {number(report['population_before'])} → {number(report['population_after'])}"
                f"　·　财富降档 {number(report['moved_down'])} 人\n"
                f"出生 {number(report['births'])} 人　·　自然死亡 {number(report['natural_deaths'])} 人"
                f"　·　缺粮额外死亡 {number(report['shortage_deaths'])} 人")
        else:
            self.report_summary_label.setText(
                f"人口 {number(report['population_before'])} → {number(report['population_after'])}"
                f"　·　缺粮死亡 {number(report['deaths'])} 人　·　财富降档 {number(report['moved_down'])} 人（旧版规则）")
        _fill(self.consumption_table, [[
            f"{entry['label']} · {self._unit(entry['resource'])}", number(entry["demand"]),
            number(entry["consumed"]), number(entry["shortage"]), percent(entry["fulfillment"]),
        ] for entry in report["consumption"]])
        if natural_model:
            self.consequences_table.setHorizontalHeaderLabels([
                "财富层", "旬初人数", "出生", "自然死亡", "缺粮死亡", "财富降档", "健康下降",
            ])
            _fill(self.consequences_table, [[
                entry["label"], number(entry["population_before"]), number(entry["births"]),
                number(entry["natural_deaths"]), number(entry["shortage_deaths"]),
                number(entry["moved_down"]), number(entry["health_penalty"]),
            ] for entry in report["groups"]])
        else:
            self.consequences_table.setHorizontalHeaderLabels([
                "财富层", "旬初人数", "缺粮死亡", "财富降档", "健康下降", "满意下降", "劳力下降",
            ])
            _fill(self.consequences_table, [[
                entry["label"], number(entry["population_before"]), number(entry["deaths"]),
                number(entry["moved_down"]), number(entry["health_penalty"]),
                number(entry["satisfaction_penalty"]), percent(entry["labor_penalty"]),
            ] for entry in report["groups"]])
        lines = [report["summary"], "", "财富变化不等于职业变化。"]
        if natural_model:
            lines.extend(f"{entry['label']}：满意下降 {number(entry['satisfaction_penalty'])} 点，"
                         f"劳力效能下降 {percent(entry['labor_penalty'])}。" for entry in report["groups"])
        lines.extend(["", "生产记事"])
        for entry in report["production"]:
            lines.extend([
                f"{entry['label']}（{OWNER_LABELS.get(entry['owner'], entry['owner'])}）· {entry['state']}",
                f"  实际投入：{self._resource_text(entry['inputs'])}；用工 {number(entry['labor_used'])} 人。",
                f"  实际产出：{self._resource_text(entry['outputs'])}。",
            ])
        lines.extend(["", "各池净变化（生产与消费合计）"])
        pool_names = {item["id"]: item["label"] for item in self._view["pools"]}
        for pool_id, changes in report["pool_changes"].items():
            lines.append(f"{pool_names.get(pool_id, pool_id)}：{self._resource_text(changes, signed=True)}。")
        self.report_browser.setPlainText("\n".join(lines))

    def _feedback(self, message: str, *, error: bool = False) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setProperty("error", error)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.show()

    def _apply_result(self, result) -> None:
        self._feedback(result.message, error=not result.ok)
        self.refresh()
        if result.ok and self.on_changed:
            self.on_changed()
        self.result.emit(result)

    def apply_resource(self) -> None:
        if self._busy or not self._view:
            return
        try:
            value = float(self.resource_value_input.text().strip())
            if not math.isfinite(value) or value < 0:
                raise ValueError
        except ValueError:
            self._feedback("余额须为有效的非负数。尚未应用修改。", error=True)
            self.resource_value_input.setFocus()
            return
        result = self.session.set_demo_economy_resource(
            self.resource_owner_combo.currentData(), self.resource_kind_combo.currentData(), value,
        )
        self._apply_result(result)

    def _population_action_allowed(self) -> bool:
        if self._busy or not self._view:
            return False
        if not self._occupation_model:
            self._feedback("旧县存档沿用旧人口规则，请新建试玩使用职业模型。", error=True)
            return False
        if self.session.state.phase != Phase.PLANNING:
            self._feedback("本旬已开始，完成当前旬后才能调整人口参数与收入。", error=True)
            return False
        return True

    def apply_population_parameters(self) -> None:
        if not self._population_action_allowed():
            return
        population = self._view["population"]
        original = tuple(population[key] for key in (
            "labor_ratio", "annual_birth_rate", "annual_death_rate", "basic_living_cost",
        ))
        values = []
        for index, entry in enumerate(self.population_inputs):
            entered = entry.text().strip()
            try:
                value = float(entered)
                if not math.isfinite(value) or (index < 3 and not 0 <= value <= 100) or (index == 3 and value <= 0):
                    raise ValueError
            except ValueError:
                self._feedback(
                    "三个比例须为 0–100 的百分数，基本生活成本须为正数；尚未应用任何修改。", error=True)
                entry.setFocus()
                return
            displayed = original[index] * 100 if index < 3 else original[index]
            # Untouched percentage fields must not change through multiply/divide rounding.
            values.append(original[index] if entered == _input_number(displayed)
                          else value / 100 if index < 3 else value)
        self._apply_result(self.session.set_demo_population_parameters(*values))

    def apply_population_income(self) -> None:
        if not self._population_action_allowed():
            return
        identifier = self.income_cohort_combo.currentData()
        try:
            income = float(self.income_value_input.text().strip())
            if identifier is None or not math.isfinite(income) or income < 0:
                raise ValueError
        except ValueError:
            self._feedback("请选择收入群体，并输入有效的非负人均旬收入。尚未应用修改。", error=True)
            self.income_value_input.setFocus()
            return
        previous = {row["id"]: row for row in self._cohorts}
        selected = previous.get(identifier)
        if selected and self.income_value_input.text().strip() == _input_number(selected["income_per_capita"]):
            income = selected["income_per_capita"]
        result = self.session.set_demo_population_income(identifier, income)
        self._apply_result(result)
        if result.ok and selected and not any(row["id"] == identifier for row in self._cohorts):
            destination = next((row for row in self._cohorts
                                if row["occupation"] == selected["occupation"]
                                and row["resident_status"] == selected["resident_status"]
                                and row["population"] > previous.get(row["id"], {}).get("population", 0)), None)
            if destination:
                self.income_cohort_combo.setCurrentIndex(self.income_cohort_combo.findData(destination["id"]))
                self._feedback(f"{result.message} 已并入同职业的{destination['wealth_label']}群体，收入按人数加权。")

    def advance_turn(self) -> None:
        if self._busy or not self._view:
            return
        if self.advance_guard:
            guard_result = self.advance_guard()
            if not guard_result.ok:
                self._apply_result(guard_result)
                return
        self._busy = True
        self.advance_button.setEnabled(False)
        try:
            result = self.session.advance_economy_demo_turn()
        finally:
            self._busy = False
            self.advance_button.setEnabled(self._view is not None)
        if result.ok:
            self.report_combo.setCurrentIndex(-1)
        self._apply_result(result)
        if result.ok:
            self.tabs.setCurrentIndex(7)
