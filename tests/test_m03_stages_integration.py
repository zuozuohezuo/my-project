"""Real desktop controls exercise v3 stages, optional plans, and one-way time."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from dynasty.content import HistoryRepository
from dynasty.core import Activity, GameSession, Phase
from dynasty.ui.main_window import MainWindow
from dynasty.ui.month_planning_dialog import SequentialMonthPlanDialog


def make_window(qtbot, tmp_path):
    game = GameSession.new_game()
    ui = MainWindow(HistoryRepository(tmp_path / "content"), game)
    qtbot.addWidget(ui)
    ui.show()
    ui.show_page(1)
    return ui


def click(qtbot, widget):
    assert widget.isEnabled()
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)


def enter_unplanned_work(qtbot, ui):
    click(qtbot, ui.planning_page.start_button)
    assert ui.session.current_activity.kind == "court"
    assert ui.session.state.ap_spent == 5
    click(qtbot, ui.activity_page.finish_button)
    if ui.session.state.turn_stage == "court":
        ui.activity_page.start_next_activity()
    assert ui.session.state.turn_stage == "work"


def test_default_court_and_unplanned_work_are_playable_in_shell(qtbot, tmp_path):
    ui = make_window(qtbot, tmp_path)
    assert ui.session.config.turn_rules_version == 3
    assert [a.kind for a in ui.session.state.activities] == ["court"]
    assert ui.planning_page.start_button.isEnabled()
    enter_unplanned_work(qtbot, ui)
    page = ui.activity_page
    kinds = {page.stage_activity_combo.itemData(i) for i in range(page.stage_activity_combo.count())}
    assert "paperwork" in kinds and "garden" not in kinds and "court" not in kinds
    page.stage_activity_combo.setCurrentIndex(page.stage_activity_combo.findData("paperwork"))
    page.stage_activity_ap.setValue(2)
    click(qtbot, page.stage_add_button)
    if ui.session.current_activity is None:
        page.start_next_activity()
    assert ui.session.current_activity.kind == "paperwork"
    assert ui.session.current_activity.cost == 2


def test_queued_emergency_waits_for_work_middle_and_restores_ui(qtbot, tmp_path):
    ui = make_window(qtbot, tmp_path)
    ui.inject_emergency()
    enter_unplanned_work(qtbot, ui)
    assert ui.session.state.phase == Phase.EXECUTING
    page = ui.activity_page
    page.stage_activity_combo.setCurrentIndex(page.stage_activity_combo.findData("paperwork"))
    page.stage_activity_ap.setValue(15)
    click(qtbot, page.stage_add_button)
    if ui.session.current_activity is None:
        page.start_next_activity()
    for _ in range(8):
        if ui.session.state.phase == Phase.INTERRUPTED:
            break
        page.continue_activity("work")
    assert ui.session.state.phase == Phase.INTERRUPTED
    assert ui.turn_tabs.currentIndex() == 2
    spent = ui.session.current_activity.spent_ap
    assert 7 <= spent <= 8
    ui.resolve_emergency(issue=False)
    assert ui.turn_tabs.currentIndex() == 1
    assert ui.session.current_activity.spent_ap == spent


def test_work_time_transfer_ui_and_roundtrip_retains_stage(qtbot, tmp_path, monkeypatch):
    ui = make_window(qtbot, tmp_path)
    enter_unplanned_work(qtbot, ui)
    click(qtbot, ui.activity_page.transfer_button)
    assert ui.session.state.turn_stage == "private"
    assert ui.session.state.private_budget == 25
    assert not ui.activity_page.transfer_button.isVisible()
    kinds = {ui.activity_page.stage_activity_combo.itemData(i)
             for i in range(ui.activity_page.stage_activity_combo.count())}
    assert "garden" in kinds and "paperwork" not in kinds
    path = tmp_path / "stage-private.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(path), "JSON"))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(path), "JSON"))
    ui.save_game()
    expected = ui.session.to_dict()
    ui.load_game()
    assert ui.session.to_dict() == expected
    assert ui.session.state.turn_stage == "private"
    assert not ui.session.set_work_budget(20).ok


def test_partial_three_turn_plan_keeps_default_courts_and_total_budget(qtbot, tmp_path):
    ui = make_window(qtbot, tmp_path)
    dialog = SequentialMonthPlanDialog(ui.repository, ui.session, ui)
    qtbot.addWidget(dialog)
    assert all([a.kind for a in page.draft_activities()] == ["court"] for page in dialog.pages)
    dialog.pages[0].work_spin.setValue(9)
    dialog._copy_first()
    dialog._submit(False)
    assert dialog.result() == dialog.DialogCode.Accepted
    assert all(plan["work_budget"] == 14 for plan in dialog.plans)
    assert all(sum(a["cost"] for a in plan["activities"]) == 5 for plan in dialog.plans)
    assert ui.session.set_month_plan(dialog.plans).ok
    assert len(ui.session.state.month_plan) == 3


def test_no_card_emergency_ui_explains_and_charges_unassigned_time(qtbot, tmp_path):
    ui = make_window(qtbot, tmp_path)
    game = ui.session
    assert game.set_turn_plan([Activity(kind="paperwork", cost=5)], work_budget=10).ok
    game.inject_emergency("第一份急报")
    game.inject_emergency("第二份急报")
    assert game.start_turn().ok
    for _ in range(5):
        game.continue_activity("work")
    assert game.resolve_emergency(game.current_activity.id, command_id=None).ok
    assert game.start_next_activity().status == "interrupted"
    ui.refresh()
    assert "尚未安排的 1 AP" in ui.replacement_combo.currentText()
    assert "尚未安排的 1 AP" in ui.decision_text.text()
    ui.resolve_emergency(issue=False)
    assert game.state.phase == Phase.EXECUTING
    assert game.state.stage_spent["work"] == 6
    assert game.state.stage_unallocated["work"] == 4


def test_draft_budget_metric_survives_refresh(qtbot, tmp_path):
    ui = make_window(qtbot, tmp_path)
    ui.planning_page.load_example()
    expected = sum(a.cost for a in ui.planning_page.draft_activities())
    ui.refresh()
    assert ui.metrics["ap"].text() == f"{expected} / 30"


def test_personal_goal_arrange_uses_current_private_stage(qtbot, tmp_path):
    ui = make_window(qtbot, tmp_path)
    enter_unplanned_work(qtbot, ui)
    before = len(ui.session.state.activities)
    ui._arrange_personal_activity("exercise")
    assert len(ui.session.state.activities) == before
    assert "当前阶段" in ui.feedback.text()
    click(qtbot, ui.activity_page.transfer_button)
    ui._arrange_personal_activity("exercise")
    assert ui.turn_tabs.currentIndex() == 1
    assert ui.session.current_activity.kind == "exercise"
    assert ui.session.state.turn_stage == "private"
