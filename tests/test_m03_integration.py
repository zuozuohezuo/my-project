"""Exercise the integrated desktop shell, saves, and three-turn editor under M03."""

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from dynasty.content import HistoryRepository
from dynasty.core import Phase
from legacy_support import SequentialDemoConfig as DemoConfig, SequentialGameSession as GameSession
from dynasty.ui.launcher import AppWindow
from dynasty.ui.main_window import MainWindow
from dynasty.ui.month_planning_dialog import SequentialMonthPlanDialog


def window(qtbot, tmp_path):
    repository = HistoryRepository(tmp_path / "content")
    ui = MainWindow(repository, GameSession.new_game(config=DemoConfig(initial_year=1500)))
    qtbot.addWidget(ui)
    ui.show()
    ui.show_page(1)
    return ui


def click(qtbot, button):
    assert button.isEnabled()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_integrated_early_emergency_routes_to_decision_then_restores_court(qtbot, tmp_path):
    ui = window(qtbot, tmp_path)
    ui.planning_page.load_example()
    ui.inject_emergency()
    click(qtbot, ui.planning_page.start_button)
    assert ui.session.state.phase == Phase.INTERRUPTED
    assert ui.turn_tabs.currentIndex() == 2
    assert ui.decision_card.isVisible()
    ui.resolve_emergency(issue=False)
    ui.advance_turn()
    assert ui.turn_tabs.currentIndex() == 1
    assert ui.session.current_activity.kind == "court"
    click(qtbot, ui.activity_page.command_button)
    assert ui.turn_tabs.currentIndex() == 2
    assert ui.issue_button.isEnabled()
    ui.command_editor.command.setCurrentIndex(ui.command_editor.command.findData("appoint_official"))
    click(qtbot, ui.issue_button)
    assert len(ui.session.state.command_ledger) == 1
    assert ui.session.state.ap_spent == 5


def test_save_load_in_garden_keeps_choices_and_new_to_legacy_ui_switch(qtbot, tmp_path, monkeypatch):
    ui = window(qtbot, tmp_path)
    ui.planning_page.load_example()
    ui.planning_page.schedule_table.selectRow(1)
    ui.planning_page.move_selected(-1)
    click(qtbot, ui.planning_page.start_button)
    assert ui.session.current_activity.kind == "garden"
    click(qtbot, ui.activity_page.choice_buttons["pond"])
    before_scene = copy.deepcopy(ui.session.current_activity.scene)
    filename = tmp_path / "garden.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(filename), "JSON"))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(filename), "JSON"))
    ui.save_game()
    expected = ui.session.to_dict()
    ui.session = GameSession.new_game(config=DemoConfig(
        turn_rules_version=1, health_ap_thresholds=[[0, 1], [40, 2], [80, 3]]))
    ui.refresh()
    assert not ui._m03_mode
    assert len(ui.activity_combos) == 3
    ui.load_game()
    assert ui._m03_mode
    assert ui.session.to_dict() == expected
    assert ui.session.current_activity.scene == before_scene
    ui.turn_tabs.setCurrentIndex(1)
    assert "pond" not in ui.activity_page.choice_buttons
    click(qtbot, ui.activity_page.choice_buttons["flowers"])
    assert ui.session.current_activity.stage == "ready"
    click(qtbot, ui.activity_page.finish_button)
    assert len(ui.session.state.completion_records) == 1


def test_month_editor_keeps_three_budgets_and_cancellation_is_atomic(qtbot, tmp_path):
    ui = window(qtbot, tmp_path)
    before = ui.session.to_dict()
    dialog = SequentialMonthPlanDialog(ui.repository, ui.session, ui)
    qtbot.addWidget(dialog)
    dialog.pages[0].load_example()
    dialog._copy_first()
    dialog._submit(False)
    assert dialog.result() == dialog.DialogCode.Accepted
    assert ui.session.to_dict() == before
    assert all(sum(a["cost"] for a in p["activities"]) == 30 for p in dialog.plans)
    assert all(p["work_budget"] == 20 for p in dialog.plans)
    assert ui.session.set_month_plan(dialog.plans).ok
    assert len(ui.session.state.month_plan) == 3
    assert GameSession.from_dict(ui.session.to_dict()).state.month_plan == ui.session.state.month_plan


def test_new_launcher_uses_30_ap_and_preserves_m03_draft_on_return(qtbot, tmp_path):
    app = AppWindow(HistoryRepository(tmp_path / "content"), data_directory=tmp_path / "player")
    qtbot.addWidget(app)
    app.enter_game(GameSession.new_game(config=DemoConfig(initial_year=1500)))
    ui = app.game
    assert ui._m03_mode and ui.session.state.ap_capacity == 30
    ui.planning_page.arrange_activity("court")
    ui.planning_page.arrange_activity("garden")
    app.return_from_game()
    assert app.pages.currentWidget() == app.home_page
    app.continue_game()
    assert [a.kind for a in ui.planning_page.draft_activities()] == ["court", "garden"]
    assert ui.session.state.ap_allocated == 6


def test_entire_sample_turn_plays_via_visible_controls(qtbot, tmp_path):
    ui = window(qtbot, tmp_path)
    ui.planning_page.load_example()
    click(qtbot, ui.planning_page.start_button)
    original_ids = {a.id for a in ui.session.state.activities}
    for _ in range(160):
        if ui.session.state.turn_index == 1:
            break
        page = ui.activity_page
        if page.finish_button.isVisible():
            click(qtbot, page.finish_button)
        elif page.choice_buttons:
            click(qtbot, list(page.choice_buttons.values())[-1])
        elif page.next_button.isVisible():
            click(qtbot, page.next_button)
        elif page.settle_button.isVisible():
            click(qtbot, page.settle_button)
        else:
            raise AssertionError("No visible way to continue the M03 schedule")
    assert ui.session.state.turn_index == 1
    assert {r["activity_id"] for r in ui.session.state.completion_records} == original_ids
    assert all(r["settled"] for r in ui.session.state.completion_records)
    assert sum(r["spent_ap"] for r in ui.session.state.completion_records) == 30
    assert len([log for log in ui.session.logs if log["label"] == "旬结算"]) == 1
