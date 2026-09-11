"""Version 3 exposes separate stages and preserves the real time transfer state."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from dynasty.core import Activity, DemoConfig, GameSession, Phase
from dynasty.ui.activity_page import ActivityPage
from dynasty.ui.planning_page import PlanningPage
from dynasty.ui.emperor_status_dialogs import EmperorHealthEditor


def new_game():
    return GameSession.new_game(config=DemoConfig(initial_year=1500, turn_rules_version=3))


def show(qtbot, page):
    qtbot.addWidget(page)
    page.resize(1100, 650)
    page.show()
    return page


def click(qtbot, button):
    assert button.isEnabled()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def choices(combo):
    return {combo.itemData(index) for index in range(combo.count())}


def test_default_court_and_unassigned_stage_time_can_start(qtbot):
    game = new_game()
    page = show(qtbot, PlanningPage(game))
    assert page.staged_mode
    assert page.court_checkbox.isChecked()
    assert [(item.kind, item.cost) for item in page.draft_activities()] == [("court", 5)]
    assert page.work_spin.value() == 15
    assert page.private_spin.value() == 10
    assert page.draft_work_budget() == 20
    assert "待临时选择 25 AP" in page.budget_status.text()
    click(qtbot, page.start_button)
    assert game.state.phase == Phase.EXECUTING
    assert game.state.turn_stage == "court"
    assert game.current_activity.kind == "court"
    assert game.state.ap_allocated == 5


def test_court_is_optional_but_cannot_move_and_other_stages_stay_grouped(qtbot):
    game = new_game()
    page = show(qtbot, PlanningPage(game))
    page.arrange_activity("rest")
    page.arrange_activity("paperwork")
    page.arrange_activity("lecture")
    assert [item.kind for item in page.draft_activities()] == ["court", "paperwork", "lecture", "rest"]
    page.schedule_table.selectRow(0)
    assert not page.down_button.isEnabled()
    page.move_selected(1)
    assert page.draft_activities()[0].kind == "court"
    page.schedule_table.selectRow(2)
    assert not page.down_button.isEnabled()
    click(qtbot, page.up_button)
    assert [item.kind for item in page.draft_activities()] == ["court", "lecture", "paperwork", "rest"]
    page.court_checkbox.setChecked(False)
    assert all(item.kind != "court" for item in page.draft_activities())
    assert page.work_spin.value() == 20
    assert page.private_spin.value() == 10
    assert page.capture_draft().ok
    assert not game.state.court_assigned
    assert game.state.turn_stage == "work"


def test_work_selection_and_partial_office_transfer_are_visible_and_saveable(qtbot):
    game = new_game()
    assert game.start_turn().ok
    page = show(qtbot, ActivityPage(game))
    click(qtbot, page.finish_button)
    assert game.state.turn_stage == "work"
    assert game.current_activity is None
    assert page.stage_picker.isVisible()
    assert choices(page.stage_activity_combo) == {"paperwork", "audience", "palace", "lecture"}
    page.stage_activity_combo.setCurrentIndex(page.stage_activity_combo.findData("paperwork"))
    page.stage_activity_ap.setValue(3)
    click(qtbot, page.stage_add_button)
    assert game.current_activity.kind == "paperwork"
    assert game.current_activity.cost == 3
    click(qtbot, page.choice_buttons["work"])
    assert game.current_activity.spent_ap == 1
    assert "剩余 14 AP" in page.transfer_button.text()
    assert "已投入的 1 AP" in page.transfer_notice.text()
    click(qtbot, page.transfer_button)
    assert game.state.turn_stage == "private"
    assert game.state.private_budget == 24
    office = next(item for item in game.state.activities if item.kind == "paperwork")
    assert office.status == "stopped" and office.spent_ap == 1
    restored = GameSession.from_dict(game.to_dict())
    page.refresh(restored)
    assert not page.transfer_button.isVisible()
    assert not choices(page.stage_activity_combo).intersection({"court", "paperwork", "audience", "palace", "lecture"})
    assert page.stage_activity_ap.value() == 1
    assert not page.stage_activity_ap.isEnabled()
    assert restored.state.private_budget == 24
    assert "提前结束" in [page.schedule_table.item(row, 2).text() for row in range(page.schedule_table.rowCount())]
    planning = show(qtbot, PlanningPage(restored))
    assert "工作 1 / 1 AP" in planning.budget_status.text()
    assert not planning.start_button.isEnabled()


def test_transferring_work_previews_cancelled_future_work_but_preserves_private(qtbot):
    game = new_game()
    assert game.set_turn_plan([
        Activity(kind="court", cost=5), Activity(kind="paperwork", cost=3),
        Activity(kind="lecture"), Activity(kind="garden"),
    ], 20).ok
    assert game.start_turn().ok
    page = show(qtbot, ActivityPage(game))
    click(qtbot, page.finish_button)
    click(qtbot, page.next_button)
    click(qtbot, page.choice_buttons["work"])
    assert "1 项工作将撤下" in page.transfer_notice.text()
    click(qtbot, page.transfer_button)
    lecture = next(item for item in game.state.activities if item.kind == "lecture")
    garden = next(item for item in game.state.activities if item.kind == "garden")
    assert lecture.status == "cancelled"
    assert garden.status == "pending"
    assert page.next_button.isVisible()
    click(qtbot, page.next_button)
    assert game.current_activity.kind == "garden"


def test_staged_example_keeps_time_for_later_choices_and_refresh_retains_draft(qtbot):
    game = new_game()
    page = show(qtbot, PlanningPage(game))
    click(qtbot, page.example_button)
    before = page.draft_activities()
    assert 5 < sum(item.cost for item in before) < 30
    assert [item.turn_stage for item in before] == sorted(
        [item.turn_stage for item in before], key={"court": 0, "work": 1, "private": 2}.get)
    assert page.draft_work_budget() == 20
    page.refresh(game)
    assert page.draft_activities() == before
    assert page.capture_draft().ok
    assert game.start_turn().ok


def test_health_editor_counts_retained_time_after_work_to_private_transfer(qtbot):
    game = new_game()
    assert game.set_turn_plan([
        Activity(kind="court", cost=5), Activity(kind="paperwork", cost=3),
        Activity(kind="audience", cost=12), *[Activity(kind="rest") for _ in range(10)],
    ], 20).ok
    assert game.start_turn().ok
    assert game.finish_activity().ok
    assert game.start_next_activity().ok
    assert game.continue_activity("work").ok
    assert game.finish_work_stage().ok
    for _ in range(14):
        assert game.append_stage_activity("rest").ok
    assert game.state.turn_stage == "private"
    assert sum(item.cost for item in game.state.activities) == 44
    assert sum(item.reserved_ap for item in game.state.activities) == 30
    dialog = EmperorHealthEditor(game, activity_draft=game.state.activities)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.health_input.setValue(99)
    dialog.pressure_input.setValue(25)
    dialog.apply_values()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert game.state.health == 99
    assert game.state.emperor.pressure == 25
    assert game.state.turn_stage == "private"
    assert game.state.ap_capacity == 30
    assert GameSession.from_dict(game.to_dict()).state.turn_stage == "private"
