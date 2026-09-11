"""Exercise actual desktop controls and their domain transitions."""

import copy
import json

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton

from dynasty.content import HistoryRepository
from dynasty.core import Phase
from legacy_support import LegacyDemoConfig as DemoConfig, LegacyGameSession as GameSession
from dynasty.ui.dialogs import MonthPlanDialog
from dynasty.ui.main_window import MainWindow


@pytest.fixture
def repository(tmp_path):
    """Small explicit fixtures keep UI tests independent of downloaded history."""
    directory = tmp_path / "data" / "history"
    directory.mkdir(parents=True)
    tables = {
        "regions": [
            {"id": "test_west", "name": "测试西地", "longitude": 105, "latitude": 30},
            {"id": "test_east", "name": "测试东地", "longitude": 120, "latitude": 38},
        ],
        "people": [{"id": "test_person", "name": "测试人物"}],
        "offices": [{"id": "test_office", "name": "测试官职"}],
        "prefectures": [{"id": "test_prefecture", "name": "测试府", "region_id": "test_east"}],
        "counties": [{"id": "test_county", "name": "测试县", "region_id": "test_east",
                      "parent_id": "test_prefecture"}],
        "laws": [],
    }
    for category, rows in tables.items():
        (directory / f"{category}.json").write_text(
            json.dumps({"records": rows}, ensure_ascii=False), encoding="utf-8"
        )
    return HistoryRepository(tmp_path)


@pytest.fixture
def make_window(qtbot, repository, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user-data"))

    def create(*, edicts=3):
        world = repository.initial_world()
        world["metrics"] = {"treasury": 500, "grain": 1000, "morale": 60}
        session = GameSession.new_game(world, DemoConfig(initial_year=1500, edicts_per_turn=edicts))
        window = MainWindow(repository=repository, session=session)
        qtbot.addWidget(window)
        window.show()
        qtbot.waitUntil(window.isVisible)
        return window

    return create


def click(qtbot, widget):
    assert widget.isEnabled(), f"Expected enabled control: {widget.objectName()}"
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)


def named(window, name):
    widget = window.findChild(QPushButton, name)
    assert widget is not None, f"Missing control: {name}"
    return widget


def text_button(parent, text):
    matches = [widget for widget in parent.findChildren(QPushButton) if widget.text() == text]
    assert len(matches) == 1, f"Expected one control for {text!r}, found {len(matches)}"
    return matches[0]


def select(combo, value):
    index = combo.findData(value)
    assert index >= 0, f"Missing combo option {value!r}"
    combo.setCurrentIndex(index)


def arrange(window, kinds):
    for combo, kind in zip(window.activity_combos, kinds):
        select(combo, kind)


def enter_court(qtbot, window):
    click(qtbot, window.nav_buttons[1])
    arrange(window, ["court", "rest", "study"])
    # Deliberately no separate Save click: the primary control must use this draft.
    click(qtbot, named(window, "openCourt"))
    assert window.session.state.phase == Phase.EXECUTING
    assert window.session.state.court_open


def set_tax(editor, rate):
    select(editor.command, "change_tax")
    editor.delegated.setChecked(False)
    editor.amount.setText(str(rate))


def test_activity_draft_enters_court_and_one_court_issues_multiple_orders(qtbot, make_window):
    window = make_window()
    world = window.session.world_facts
    enter_court(qtbot, window)
    assert [activity.kind for activity in window.session.state.activities] == ["court", "rest", "study"]

    select(window.command_editor.command, "appoint_official")
    click(qtbot, named(window, "issueCommand"))
    select(window.command_editor.command, "build_canal")
    click(qtbot, named(window, "issueCommand"))
    set_tax(window.command_editor, 8)
    click(qtbot, named(window, "issueCommand"))
    assert [record["command_id"] for record in window.session.state.command_ledger] == [
        "appoint_official", "build_canal", "change_tax"
    ]
    assert window.session.state.command_ledger[0]["parameters"]["person_id"] is None
    assert window.session.state.command_ledger[1]["parameters"]["budget"] is None
    assert window.session.state.edict_available == 0
    select(window.command_editor.command, "appoint_official")
    click(qtbot, named(window, "issueCommand"))
    assert len(window.session.state.command_ledger) == 3
    assert window.session.state.edict_debt == 0
    assert window.session.world_facts == world


def test_advance_uses_unsaved_activity_draft_without_adding_activities(qtbot, make_window):
    window = make_window()
    click(qtbot, window.nav_buttons[1])
    world = window.session.world_facts
    arrange(window, ["rest", "private", "study"])
    click(qtbot, named(window, "advanceTurn"))
    assert window.session.state.turn_index == 1
    effects = [effect for effect in window.session.state.pending_effects
               if effect["kind"] == "activity_effect"]
    assert [effect["activity_kind"] for effect in effects] == ["rest", "private", "study"]
    assert window.session.state.ap_remaining == 3
    assert window.session.world_facts == world


def test_partial_draft_is_retained_and_only_explicit_rest_fills_budget(qtbot, make_window):
    window = make_window()
    click(qtbot, window.nav_buttons[1])
    select(window.activity_combos[0], "court")
    click(qtbot, named(window, "openCourt"))
    assert window.session.state.phase == Phase.PLANNING
    assert window.session.state.ap_remaining == 2
    assert [combo.currentData() for combo in window.activity_combos] == ["court", None, None]
    click(qtbot, named(window, "fillRest"))
    assert [activity.kind for activity in window.session.state.activities] == ["court", "rest", "rest"]
    click(qtbot, named(window, "openCourt"))
    assert window.session.state.court_open


def test_second_tax_order_pauses_and_accepting_advice_does_not_spend(qtbot, make_window):
    window = make_window()
    world = window.session.world_facts
    enter_court(qtbot, window)
    set_tax(window.command_editor, 10)
    click(qtbot, named(window, "issueCommand"))
    prior_effects = copy.deepcopy(window.session.state.pending_effects)
    set_tax(window.command_editor, 8)
    click(qtbot, named(window, "issueCommand"))
    assert window.session.state.phase == Phase.REMONSTRANCE
    assert window.decision_card.isVisible()
    assert not window.issue_button.isEnabled()
    assert not window.advance_button.isEnabled()
    assert window.session.state.edict_available == 2
    click(qtbot, named(window, "acceptAdvice"))
    assert window.session.state.phase == Phase.EXECUTING
    assert window.session.state.edict_available == 2
    assert len(window.session.state.command_ledger) == 1
    assert window.session.state.pending_effects == prior_effects
    assert window.session.world_facts == world
    click(qtbot, named(window, "advanceTurn"))
    assert window.session.state.turn_index == 1
    assert window.session.world_facts == world


def test_emergency_requires_explicit_replacement_and_debt_reduces_next_quota(qtbot, make_window):
    window = make_window(edicts=1)
    click(qtbot, window.nav_buttons[1])
    arrange(window, ["study", "private", "rest"])
    click(qtbot, named(window, "saveActivities"))
    world = window.session.world_facts
    click(qtbot, named(window, "injectEmergency"))
    click(qtbot, named(window, "advanceTurn"))
    assert window.session.state.phase == Phase.INTERRUPTED
    click(qtbot, named(window, "resolveEmergency"))
    assert window.session.state.phase == Phase.INTERRUPTED
    assert len(window.session.state.command_ledger) == 0
    first = window.session.state.activities[0].id
    select(window.replacement_combo, first)
    click(qtbot, named(window, "resolveEmergency"))
    assert window.session.state.activities[0].status == "replaced"
    assert window.session.state.edict_available == 0

    click(qtbot, named(window, "injectEmergency"))
    second = window.session.state.activities[1].id
    select(window.replacement_combo, second)
    click(qtbot, named(window, "resolveEmergency"))
    assert window.session.state.edict_debt == 1
    assert window.session.state.ap_allocated == 3
    assert sum(activity.status == "replaced" for activity in window.session.state.activities) == 2
    click(qtbot, named(window, "advanceTurn"))
    assert window.session.state.turn_index == 1
    assert window.session.state.edict_available == 0
    assert window.session.state.edict_debt == 0
    assert window.session.world_facts == world


def test_exhausted_replacement_slots_block_new_manual_demo_event(qtbot, make_window):
    window = make_window()
    click(qtbot, window.nav_buttons[1])
    arrange(window, ["study", "private", "rest"])
    click(qtbot, named(window, "saveActivities"))
    click(qtbot, named(window, "injectEmergency"))
    click(qtbot, named(window, "advanceTurn"))
    for index in range(3):
        if index:
            click(qtbot, named(window, "injectEmergency"))
        select(window.replacement_combo, window.session.state.activities[index].id)
        click(qtbot, named(window, "resolveEmergency"))
    event_count = len(window.session.state.emergencies)
    inject = named(window, "injectEmergency")
    if inject.isEnabled():
        click(qtbot, inject)
    assert len(window.session.state.emergencies) == event_count
    assert window.session.state.phase == Phase.EXECUTING
    click(qtbot, named(window, "advanceTurn"))
    assert window.session.state.turn_index == 1


def test_month_dialog_orders_pause_in_second_turn_and_resume_after_ui_save_load(
    qtbot, make_window, monkeypatch, tmp_path
):
    window = make_window()
    click(qtbot, window.nav_buttons[1])
    world = window.session.world_facts
    callback_errors = []

    def fill_real_modal_dialog():
        dialog = QApplication.activeModalWidget()
        try:
            assert isinstance(dialog, MonthPlanDialog)
            select(dialog.editor.command, "appoint_official")
            select(dialog.editor.target, "test_east")
            for offset in range(3):
                dialog.tabs.setCurrentIndex(offset)
                for combo, kind in zip(dialog.activity_selectors[offset], ["court", "rest", "study"]):
                    select(combo, kind)
                dialog.editor.note.setText(f"第{offset + 1}旬预拟")
                click(qtbot, text_button(dialog, "加入左侧所选旬的计划"))
            click(qtbot, text_button(dialog, "保存计划"))
            assert not dialog.isVisible(), dialog.feedback.text()
        except BaseException as error:
            callback_errors.append(error)
            if dialog:
                dialog.reject()

    QTimer.singleShot(0, fill_real_modal_dialog)
    click(qtbot, named(window, "editMonth"))
    if callback_errors:
        raise callback_errors[0]
    assert len(window.session.state.month_plan) == 3
    assert all(len(plan.commands) == 1 for plan in window.session.state.month_plan)
    assert all(plan.commands[0].parameters["person_id"] is None for plan in window.session.state.month_plan)
    click(qtbot, text_button(window, "下一旬插入演示急报"))
    click(qtbot, named(window, "runMonth"))
    assert window.session.state.turn_index == 1
    assert window.session.state.phase == Phase.INTERRUPTED
    assert [record["turn"] for record in window.session.state.command_ledger] == [0]

    filename = tmp_path / "interrupted.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(filename), "JSON"))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(filename), "JSON"))
    expected = window.session.to_dict()
    click(qtbot, text_button(window, "保存"))
    assert filename.exists()
    window.session = GameSession.new_game({"temporary": True})
    window.refresh()
    click(qtbot, text_button(window, "读取"))
    assert window.session.to_dict() == expected
    assert window.decision_card.isVisible()
    click(qtbot, named(window, "resolveEmergency"))
    click(qtbot, named(window, "runMonth"))
    assert window.session.state.turn_index == 3
    appointments = [record for record in window.session.state.command_ledger
                    if record["command_id"] == "appoint_official"]
    assert [record["turn"] for record in appointments] == [0, 1, 2]
    assert all(record["parameters"]["target"] == "test_east" for record in appointments)
    assert len([entry for entry in window.session.logs if entry["label"] == "旬结算"]) == 3
    assert window.session.world_facts == world


def test_cancelled_month_editor_does_not_mutate_session(qtbot, make_window):
    window = make_window()
    initial = window.session.to_dict()
    dialog = MonthPlanDialog(window.repository, window.session, window)
    qtbot.addWidget(dialog)
    dialog.show()
    select(dialog.editor.command, "build_canal")
    select(dialog.editor.target, "test_east")
    click(qtbot, text_button(dialog, "加入左侧所选旬的计划"))
    assert len(dialog.commands[0]) == 1
    click(qtbot, text_button(dialog, "取消"))
    assert window.session.to_dict() == initial


def test_map_marker_selection_is_used_as_issued_command_target(qtbot, make_window):
    window = make_window()
    click(qtbot, window.nav_buttons[0])
    dot = window.map.dots["test_east"]
    viewport_point = window.map.mapFromScene(dot.scenePos())
    with qtbot.waitSignal(window.map.region_selected, timeout=1000) as signal:
        qtbot.mouseClick(window.map.viewport(), Qt.MouseButton.LeftButton, pos=viewport_point)
    assert signal.args == ["test_east"]
    assert window.selected_region == "test_east"
    assert window.region_select.currentData() == "test_east"
    click(qtbot, text_button(window, "对此地拟旨 →"))
    assert window.command_editor.target.currentData() == "test_east"
    enter_court(qtbot, window)
    select(window.command_editor.command, "build_canal")
    click(qtbot, named(window, "issueCommand"))
    assert window.session.state.command_ledger[-1]["parameters"]["target"] == "test_east"


def test_save_game_captures_unsaved_activity_controls(qtbot, make_window, monkeypatch, tmp_path):
    window = make_window()
    click(qtbot, window.nav_buttons[1])
    arrange(window, ["court", "private", "study"])
    assert window.session.state.activities == []
    filename = tmp_path / "planning-draft.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(filename), "JSON"))
    click(qtbot, text_button(window, "保存"))
    restored = GameSession.load_json(filename)
    assert [activity.kind for activity in restored.state.activities] == ["court", "private", "study"]
    assert restored.state.phase == Phase.PLANNING
    assert restored.state.turn_index == 0


def test_damaged_log_in_save_is_rejected_without_replacing_current_game(
    qtbot, make_window, monkeypatch, tmp_path
):
    window = make_window()
    enter_court(qtbot, window)
    prior = window.session.to_dict()
    damaged = copy.deepcopy(prior)
    del damaged["state"]["logs"][0]["date"]
    filename = tmp_path / "damaged-log.json"
    filename.write_text(json.dumps(damaged, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(filename), "JSON"))
    click(qtbot, text_button(window, "读取"))
    assert window.session.to_dict() == prior
    assert window.feedback.property("error")


def test_repeated_queued_demo_reports_cannot_strand_a_turn_without_court(qtbot, make_window):
    window = make_window()
    click(qtbot, window.nav_buttons[1])
    arrange(window, ["study", "private", "rest"])
    click(qtbot, named(window, "saveActivities"))
    click(qtbot, named(window, "injectEmergency"))
    queued_count = len(window.session.state.emergencies)
    for _ in range(3):
        inject = named(window, "injectEmergency")
        if inject.isEnabled():
            click(qtbot, inject)
            assert window.feedback.property("error")
        assert len(window.session.state.emergencies) == queued_count
    click(qtbot, named(window, "advanceTurn"))
    for _ in range(3):
        if window.session.state.turn_index == 1:
            break
        assert window.session.state.phase == Phase.INTERRUPTED
        available = [activity for activity in window.session.state.activities
                     if activity.status in {"pending", "in_progress"}]
        assert available, "Queued manual reports exhausted every replaceable activity."
        select(window.replacement_combo, available[0].id)
        click(qtbot, named(window, "resolveEmergency"))
        click(qtbot, named(window, "advanceTurn"))
    assert window.session.state.turn_index == 1
