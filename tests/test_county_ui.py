"""The county projection stays read-only until an explicit, guarded session action."""

import copy
import math
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QLabel

from dynasty.content import create_county_demo
from dynasty.core import ActionResult, GameSession, Phase
from dynasty.ui.county_page import CountyPage
from dynasty.ui.main_window import MainWindow


def show_page(qtbot, session, on_changed=None):
    page = CountyPage(session, on_changed=on_changed)
    page.resize(1120, 760)
    qtbot.addWidget(page)
    page.show()
    qtbot.waitUntil(page.isVisible)
    return page


def click(qtbot, button):
    assert button.isEnabled()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def balances(session):
    return {pool["owner"]: copy.deepcopy(pool["balances"]) for pool in session.economy_view["pools"]}


def table_text(table):
    return "\n".join(table.item(row, column).text()
                     for row in range(table.rowCount()) for column in range(table.columnCount()))


def test_no_economy_does_not_display_fictional_balances_or_enable_actions(qtbot):
    session = GameSession.new_game({"simulation_enabled": False, "metrics": {}})
    before = session.to_dict()
    page = show_page(qtbot, session)
    assert page.disabled_label.isVisible()
    assert "未启用" in page.disabled_label.text()
    assert not page.tabs.isVisible()
    assert not page.advance_button.isEnabled()
    page.refresh()
    assert session.to_dict() == before


def test_eight_sections_show_actual_population_ownership_and_production_without_settling(qtbot):
    session = create_county_demo()
    session.state.economy["county"]["name"] = "<b>清河县</b>"
    before = session.to_dict()
    page = show_page(qtbot, session)
    view = session.economy_view
    assert [page.tabs.tabText(index) for index in range(page.tabs.count())] == [
        "人口", "土地", "当地特产", "当地修正", "钱粮与物资", "基础设施", "生产经营", "民情与秩序",
    ]
    assert page.name_label.text() == "<b>清河县</b>"
    assert page.name_label.textFormat() == Qt.TextFormat.PlainText
    assert "演示" in page.demo_notice.text()
    assert "正常" in page.scenario_label.text()
    assert page.population_table.rowCount() == 7
    assert [page.population_table.item(row, 0).text() for row in range(7)] == [
        "农民", "劳工", "手工业者", "商人", "地主", "贵族", "官员",
    ]
    assert [page.wealth_table.item(row, 0).text() for row in range(3)] == ["贫困", "普通", "富裕"]
    assert sum(float(page.population_table.item(row, 1).text().replace(",", ""))
               for row in range(7)) == view["population"]["total"]
    assert sum(float(page.wealth_table.item(row, 1).text().replace(",", ""))
               for row in range(3)) == view["population"]["total"]
    assert not hasattr(page, "age_table")
    assert not page.legacy_population_notice.isVisible()
    assert page.resource_table.rowCount() == len(view["resources"])
    assert [page.resource_table.horizontalHeaderItem(column).text() for column in range(1, 4)] == [
        "民间", "官府", "皇家",
    ]
    assert page.production_table.rowCount() == len(view["industries"])
    for group in ("land", "production", "resources", "facilities"):
        table = getattr(page, {"land": "land_table", "production": "production_table",
                               "resources": "resource_table", "facilities": "facilities_table"}[group])
        assert table.rowCount() > 0
    assert "farmland" not in table_text(page.land_table)
    for index in range(page.tabs.count()):
        page.tabs.setCurrentIndex(index)
        page.refresh()
    assert page.report_combo.count() == 0
    assert session.to_dict() == before


def test_resource_editor_validates_without_partial_changes_and_changes_only_selected_pool(qtbot):
    changed = []
    session = create_county_demo()
    page = show_page(qtbot, session, lambda: changed.append(True))
    page.tabs.setCurrentIndex(4)
    page.resource_owner_combo.setCurrentIndex(page.resource_owner_combo.findData("private"))
    page.resource_kind_combo.setCurrentIndex(page.resource_kind_combo.findData("grain"))
    before = session.to_dict()
    before_balances = balances(session)
    for invalid in ("-1", "nan", "不是数值"):
        page.resource_value_input.setText(invalid)
        click(qtbot, page.resource_apply_button)
        assert page.feedback_label.property("error") is True
        assert page.feedback_label.text().strip()
        assert session.to_dict() == before
    assert changed == []
    page.resource_value_input.setText("12.5")
    with qtbot.waitSignal(page.result) as signal:
        click(qtbot, page.resource_apply_button)
    assert signal.args[0].ok
    expected = copy.deepcopy(before_balances)
    expected["private"]["grain"] = 12.5
    assert balances(session) == expected
    after = session.to_dict()
    for key in ("economy", "logs"):
        before["state"].pop(key)
        after["state"].pop(key)
    assert after == before
    assert changed == [True]
    assert page.feedback_label.property("error") is False
    assert page.resource_value_input.text() == "12.5"


def test_explicit_rest_turn_creates_one_report_and_reading_history_never_advances(qtbot):
    changed = []
    session = create_county_demo()
    page = show_page(qtbot, session, lambda: changed.append(session.state.turn_index))
    emperor_health = session.state.health
    with qtbot.waitSignal(page.result) as signal:
        click(qtbot, page.advance_button)
    assert signal.args[0].ok
    assert session.state.turn_index == 1
    assert session.state.health == emperor_health
    assert session.state.phase == Phase.PLANNING
    view = session.economy_view
    assert view["last_settled_turn"] == 0
    assert len(view["history"]) == 1
    assert page.tabs.currentIndex() == 7
    assert page.report_combo.currentData() == 0
    assert page.report_browser.toPlainText().startswith(view["last_report"]["summary"])
    assert page.consumption_table.rowCount() == len(view["last_report"]["consumption"])
    assert page.consequences_table.rowCount() == 3
    first_report = page.report_browser.toPlainText()
    click(qtbot, page.advance_button)
    assert page.report_combo.currentData() == 1
    assert page.report_combo.count() == 2
    before_reading = session.to_dict()
    page.report_combo.setCurrentIndex(page.report_combo.findData(0))
    assert page.report_browser.toPlainText() == first_report
    for _ in range(3):
        page.refresh()
    assert page.report_combo.currentData() == 0
    assert session.to_dict() == before_reading
    assert changed == [1, 2]


def test_active_turn_disables_resource_trial_and_rejected_shortcut_preserves_state(qtbot):
    session = create_county_demo()
    page = show_page(qtbot, session)
    assert session.start_turn().ok
    page.refresh()
    before = session.to_dict()
    page.tabs.setCurrentIndex(4)
    assert not page.resource_apply_button.isEnabled()
    assert not page.resource_value_input.isEnabled()
    assert not page.population_apply_button.isEnabled()
    assert not page.income_apply_button.isEnabled()
    with qtbot.waitSignal(page.result) as signal:
        click(qtbot, page.advance_button)
    assert not signal.args[0].ok
    assert page.feedback_label.property("error") is True
    assert session.to_dict() == before
    assert session.economy_view["last_report"] is None


def test_external_advance_guard_preserves_unsubmitted_planning_draft(qtbot):
    changed = []
    session = create_county_demo()
    page = show_page(qtbot, session, lambda: changed.append(True))
    before = session.to_dict()
    page.advance_guard = lambda: ActionResult("error", "有未保存的活动草稿，请先处理安排。")
    with qtbot.waitSignal(page.result) as signal:
        click(qtbot, page.advance_button)
    assert not signal.args[0].ok
    assert "草稿" in page.feedback_label.text()
    assert page.feedback_label.property("error") is True
    assert session.to_dict() == before
    assert changed == []


def test_loaded_replacement_edits_new_session_and_reports_real_shortage(qtbot, tmp_path):
    old_session = create_county_demo()
    page = show_page(qtbot, old_session)
    old_snapshot = old_session.to_dict()
    session = create_county_demo("shortage")
    path = tmp_path / "县经济缺粮.json"
    session.save_json(path)
    replacement = GameSession.load_json(path)
    page.refresh(replacement)
    assert page.session is replacement
    assert replacement.economy_view["scenario_label"] in page.scenario_label.text()
    page.tabs.setCurrentIndex(4)
    page.resource_owner_combo.setCurrentIndex(page.resource_owner_combo.findData("private"))
    page.resource_kind_combo.setCurrentIndex(page.resource_kind_combo.findData("grain"))
    page.resource_value_input.setText("0")
    click(qtbot, page.resource_apply_button)
    assert balances(replacement)["private"]["grain"] == 0
    click(qtbot, page.advance_button)
    report = replacement.economy_view["last_report"]
    assert report is not None and report["grain_shortage_ratio"] > 0
    assert report["deaths"] > 0
    assert report["moved_down"] > 0
    assert report["summary"] in page.report_browser.toPlainText()
    assert all(label.textFormat() == Qt.TextFormat.PlainText
               for label in page.findChildren(QLabel))
    assert old_session.to_dict() == old_snapshot


def test_input_shortage_explains_why_industry_cannot_produce(qtbot):
    session = create_county_demo("input_shortage")
    page = show_page(qtbot, session)
    assert session.economy_view["scenario_label"] in page.scenario_label.text()
    click(qtbot, page.advance_button)
    report = session.economy_view["last_report"]
    stalled = [row for row in report["production"] if row["input_ratio"] < 1]
    assert stalled
    assert any(row["state"] == "投入不足" for row in stalled)
    assert "投入不足" in page.report_browser.toPlainText()
    page.tabs.setCurrentIndex(6)
    assert "投入不足" in table_text(page.production_table)


def test_population_defaults_show_occupation_wealth_and_fifty_percent_base_labor(qtbot):
    session = create_county_demo()
    page = show_page(qtbot, session)
    view = session.economy_view
    assert view["population"]["total"] == 1000
    assert view["population"]["base_labor"] == 500
    assert view["population"]["available_labor"] == 500
    assert "50%" in page.labor_summary_label.text()
    assert "500" in page.labor_summary_label.text()
    assert page.labor_ratio_input.text() == "50"
    assert page.birth_rate_input.text() == "3"
    assert page.death_rate_input.text() == "2"
    assert "36" in page.population_rates_label.text()
    populated = [row for row in view["cohorts"] if row["population"]]
    assert page.cohorts_table.rowCount() == len(populated)
    assert any(len({row["wealth"] for row in populated if row["occupation"] == occupation["id"]}) > 1
               for occupation in view["occupation_groups"])
    assert "年龄组" not in "\n".join(label.text() for label in page.findChildren(QLabel))


def test_population_parameter_draft_is_atomic_and_immediately_recomputes_labor(qtbot):
    changed = []
    session = create_county_demo()
    page = show_page(qtbot, session, lambda: changed.append(True))
    before = session.to_dict()
    original_pools = balances(session)
    page.labor_ratio_input.setText("60")
    page.birth_rate_input.setText("4")
    page.death_rate_input.setText("2")
    page.basic_living_cost_input.setText("0")
    click(qtbot, page.population_apply_button)
    assert session.to_dict() == before
    assert changed == []
    assert page.feedback_label.property("error") is True
    assert page.labor_ratio_input.text() == "60"
    page.basic_living_cost_input.setText("1")
    with qtbot.waitSignal(page.result) as signal:
        click(qtbot, page.population_apply_button)
    assert signal.args[0].ok
    view = session.economy_view
    assert view["population"]["base_labor"] == 600
    assert view["population"]["available_labor"] == 600
    assert view["population"]["annual_birth_rate"] == .04
    assert session.state.turn_index == 0
    assert balances(session) == original_pools
    assert changed == [True]


def test_income_trial_reclassifies_wealth_keeps_occupation_and_does_not_mint_money(qtbot):
    session = create_county_demo()
    page = show_page(qtbot, session)
    view = session.economy_view
    group = next(row for row in view["cohorts"] if row["population"] and row["wealth"] == "poor")
    occupation_counts = {row["id"]: row["population"] for row in view["occupation_groups"]}
    old_wealth = {row["id"]: row["population"] for row in view["wealth_groups"]}
    old_pools = balances(session)
    page.income_cohort_combo.setCurrentIndex(page.income_cohort_combo.findData(group["id"]))
    old_snapshot = session.to_dict()
    page.income_value_input.setText("nan")
    click(qtbot, page.income_apply_button)
    assert session.to_dict() == old_snapshot
    threshold = view["population"]["wealth_thresholds"]["wealthy"]
    page.income_value_input.setText(str(threshold))
    with qtbot.waitSignal(page.result) as signal:
        click(qtbot, page.income_apply_button)
    assert signal.args[0].ok
    view = session.economy_view
    destination = next(row for row in view["cohorts"] if row["occupation"] == group["occupation"]
                       and row["resident_status"] == group["resident_status"] and row["wealth"] == "wealthy")
    assert destination["population"] >= group["population"]
    assert destination["income_per_capita"] >= threshold
    assert {row["id"]: row["population"] for row in view["occupation_groups"]} == occupation_counts
    new_wealth = {row["id"]: row["population"] for row in view["wealth_groups"]}
    assert new_wealth["poor"] == old_wealth["poor"] - group["population"]
    assert new_wealth["wealthy"] == old_wealth["wealthy"] + group["population"]
    assert "富裕" in page.income_cohort_combo.currentText()
    assert page.income_cohort_combo.currentData() == destination["id"]
    assert balances(session) == old_pools
    assert session.state.turn_index == 0


def test_population_report_separates_births_natural_and_extra_shortage_deaths(qtbot):
    session = create_county_demo()
    page = show_page(qtbot, session)
    page.birth_rate_input.setText("36")
    page.death_rate_input.setText("18")
    click(qtbot, page.population_apply_button)
    click(qtbot, page.advance_button)
    report = session.economy_view["last_report"]
    assert report["births"] > 0
    assert report["natural_deaths"] > 0
    assert report["shortage_deaths"] == 0
    assert report["deaths"] == report["natural_deaths"] + report["shortage_deaths"]
    assert report["population_after"] == report["population_before"] + report["births"] - report["deaths"]
    for label in ("出生", "自然死亡", "缺粮额外死亡", "财富降档"):
        assert label in page.report_summary_label.text()
    headers = [page.consequences_table.horizontalHeaderItem(index).text()
               for index in range(page.consequences_table.columnCount())]
    assert headers[2:5] == ["出生", "自然死亡", "缺粮死亡"]
    before_reading = session.to_dict()
    page.refresh()
    assert session.to_dict() == before_reading


def test_unchanged_population_inputs_preserve_exact_parameters_and_wealth_boundaries(qtbot):
    session = create_county_demo()
    precise = (0.5012345678901234, 0.03123456789012345, 0.02123456789012345, 1.0000000000000002)
    assert session.set_demo_population_parameters(*precise).ok
    page = show_page(qtbot, session)
    original = session.economy_view
    click(qtbot, page.population_apply_button)
    population = session.economy_view["population"]
    assert tuple(population[key] for key in (
        "labor_ratio", "annual_birth_rate", "annual_death_rate", "basic_living_cost",
    )) == precise
    assert session.economy_view["cohorts"] == original["cohorts"]
    old_pools = balances(session)
    for wealth, threshold_key in (("poor", "ordinary"), ("ordinary", "wealthy")):
        view = session.economy_view
        group = next(row for row in view["cohorts"] if row["population"] and row["wealth"] == wealth)
        income = math.nextafter(view["population"]["wealth_thresholds"][threshold_key], 0)
        assert session.set_demo_population_income(group["id"], income).ok
        page.refresh()
        page.income_cohort_combo.setCurrentIndex(page.income_cohort_combo.findData(group["id"]))
        assert float(page.income_value_input.text()) == income
        table_row = next(index for index, row in enumerate(page._cohorts) if row["id"] == group["id"])
        income_cell = page.cohorts_table.item(table_row, 3)
        assert "低于" in income_cell.text()
        assert str(income) in income_cell.toolTip()
        before = session.economy_view
        click(qtbot, page.income_apply_button)
        after = session.economy_view
        assert after["cohorts"] == before["cohorts"]
        assert after["wealth_groups"] == before["wealth_groups"]
        assert balances(session) == old_pools
    assert session.state.turn_index == 0


def test_legacy_county_keeps_old_population_and_disables_new_forms(qtbot):
    path = Path(__file__).parent / "fixtures" / "county_v1_shortage_after_4_turns.json"
    session = GameSession.load_json(path)
    before = session.to_dict()
    page = show_page(qtbot, session)
    assert page.legacy_population_notice.isVisible()
    assert "旧版" in page.legacy_population_notice.text()
    assert not page.occupation_panel.isVisible()
    assert page.wealth_table.rowCount() == 3
    assert not page.population_apply_button.isEnabled()
    assert not page.income_apply_button.isEnabled()
    assert page.labor_ratio_input.text() == ""
    assert not hasattr(page, "age_table")
    page.apply_population_parameters()
    assert session.to_dict() == before
    assert page.feedback_label.property("error") is True
    page.tabs.setCurrentIndex(7)
    assert "旧版" in page.report_summary_label.text()


def test_population_forms_remain_reachable_in_full_and_minimum_windows(qtbot):
    session = create_county_demo()
    window = MainWindow(session=session)
    qtbot.addWidget(window)
    window.show()
    window.show_page(6)
    page = window.county_page
    scroll = page.tabs.widget(0)
    original = session.to_dict()

    def scroll_to_visible(widget):
        def located_after_layout():
            # A preceding window can leave font/layout events queued; recalculate
            # the scroll position against the current geometry on each bounded retry.
            scroll.ensureWidgetVisible(widget, 0, 32)
            rectangle = QRect(widget.mapTo(scroll.viewport(), QPoint()), widget.size())
            assert scroll.viewport().rect().contains(rectangle), (
                f"{widget.accessibleName() or widget.objectName()}: "
                f"{rectangle} outside {scroll.viewport().rect()} at {window.size()}"
            )

        qtbot.waitUntil(located_after_layout)

    for width, height in ((1480, 940), (1180, 800)):
        window.resize(width, height)
        qtbot.waitUntil(lambda: window.width() == width and window.height() == height)
        for entry in (*page.population_inputs, page.income_value_input):
            scroll_to_visible(entry)
            entry.setFocus()
            entry.selectAll()
            qtbot.keyClicks(entry, "12.3456789")
            assert entry.text() == "12.3456789"
        for button in (page.population_apply_button, page.income_apply_button):
            scroll_to_visible(button)
    assert session.to_dict() == original
