"""The M03 player flow uses real planning and resumable activity state."""

import copy

from PySide6.QtCore import Qt

from dynasty.core import Activity, Phase
from legacy_support import SequentialDemoConfig as DemoConfig, SequentialGameSession as GameSession
from dynasty.ui.activity_page import ActivityPage
from dynasty.ui.appointments_dialog import AppointmentsDialog
from dynasty.ui.planning_page import PlanningPage


def session():
    return GameSession.new_game(config=DemoConfig(initial_year=1500))


def click(qtbot, button):
    assert button.isEnabled()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_planning_budget_example_order_and_atomic_capture(qtbot):
    game = session()
    page = PlanningPage(game)
    qtbot.addWidget(page)
    page.resize(1100, 680)
    page.show()
    click(qtbot, page.example_button)
    assert page.work_spin.value() == 20
    assert page.private_spin.value() == 10
    assert sum(item.cost for item in page.draft_activities()) == 30
    assert page.draft_activities()[0].kind == "court"
    assert page.draft_activities()[0].cost == 5
    assert page.draft_activities()[1].kind == "garden"
    page.schedule_table.selectRow(1)
    click(qtbot, page.up_button)
    assert page.draft_activities()[0].kind == "garden"
    assert page.capture_draft().ok
    assert game.state.activities[0].kind == "garden"
    assert game.state.ap_spent == 0
    page.work_spin.setValue(19)
    before = copy.deepcopy(game.to_dict())
    assert not page.start_button.isEnabled()
    assert not page.capture_draft().ok
    assert game.to_dict() == before


def test_partial_draft_survives_refresh_and_explicit_rest_fills_only_private(qtbot):
    game = session()
    page = PlanningPage(game)
    qtbot.addWidget(page)
    page.arrange_activity("court")
    page.refresh(game)
    assert len(page.draft_activities()) == 1
    page.fill_private_rest()
    assert sum(a.cost for a in page.draft_activities() if a.category == "private") == 10
    assert "工作还需安排 15 AP" in page.validation_label.text()
    assert page.capture_draft().ok
    assert game.state.ap_allocated == 15
    assert game.state.phase == Phase.PLANNING


def test_execution_choices_resume_and_finish_before_next_activity(qtbot):
    game = session()
    assert game.set_turn_plan([Activity(kind="exercise"), *[Activity(kind="rest") for _ in range(29)]], 0).ok
    assert game.start_turn().ok
    page = ActivityPage(game)
    qtbot.addWidget(page)
    page.resize(1100, 680)
    page.show()
    click(qtbot, page.choice_buttons["manual"])
    click(qtbot, page.choice_buttons["steady"])
    assert game.current_activity.scene["rounds"] == 1
    restored = GameSession.from_dict(game.to_dict())
    page.refresh(restored)
    click(qtbot, page.choice_buttons["quick"])
    click(qtbot, page.choice_buttons["steady"])
    assert restored.current_activity.stage == "ready"
    assert restored.state.activities[1].status == "pending"
    click(qtbot, page.finish_button)
    assert restored.current_activity is None
    assert restored.state.activities[0].status == "completed"
    assert restored.state.activities[1].status == "pending"
    click(qtbot, page.next_button)
    assert restored.current_activity.kind == "rest"
    assert restored.state.turn_index == 0


def test_garden_choices_are_finite_and_scene_progress_is_visible(qtbot):
    game = session()
    assert game.set_turn_plan([Activity(kind="garden"), *[Activity(kind="rest") for _ in range(29)]], 0).ok
    assert game.start_turn().ok
    page = ActivityPage(game)
    qtbot.addWidget(page)
    page.show()
    click(qtbot, page.choice_buttons["flowers"])
    assert "flowers" not in page.choice_buttons
    assert "剩余探索机会：1" in page.scene_detail.text()
    click(qtbot, page.choice_buttons["pond"])
    assert game.current_activity.stage == "ready"
    assert "pond" not in page.choice_buttons
    assert page.finish_button.isVisible()
    assert any(item["title"] == "花径修葺请托" for item in game.state.work_items)


def test_appointment_ui_records_reschedule_and_absence_once(qtbot):
    game = session()
    dialog = AppointmentsDialog(game)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.due_offset.setValue(0)
    click(qtbot, dialog.add_button)
    assert len(game.state.appointments) == 1
    item = game.state.appointments[0]
    assert dialog.execute_button.isEnabled()
    click(qtbot, dialog.reschedule_button)
    assert item.due_turn == 1 and item.original_turn == 0
    count = len(game.state.appointment_consequences)
    dialog.refresh()
    assert len(game.state.appointment_consequences) == count == 1
    click(qtbot, dialog.miss_button)
    assert item.status == "missed"
    assert len(game.state.appointment_consequences) == 2
    assert not dialog.miss_button.isEnabled()


def test_next_turn_prearranged_plan_is_loaded_before_capture(qtbot):
    game = session()
    plans = [
        {"activities": ["rest"] * 30, "work_budget": 0},
        {"activities": [Activity(kind="paperwork", cost=18), *["study"] * 12], "work_budget": 18},
        {"activities": [Activity(kind="court", cost=5), *["rest"] * 25], "work_budget": 5},
    ]
    assert game.set_month_plan(plans).ok
    page = PlanningPage(game)
    qtbot.addWidget(page)
    assert page.capture_draft().ok
    assert game.start_turn().ok
    while game.state.turn_index == 0:
        active = game.current_activity
        if active is None:
            game.advance_turn()
        elif active.stage == "ready":
            game.finish_activity()
        else:
            game.continue_activity(active.scene["choices"][0]["id"])
    assert game.state.activities[0].kind == "paperwork"
    assert game.state.activities[0].cost == 18
    page.refresh(game)
    assert page.work_spin.value() == 18
    assert page.draft_activities()[0].kind == "paperwork"
    assert page.draft_activities()[0].cost == 18
    assert page.capture_draft().ok
    assert game.state.activities[0].kind == "paperwork"
    assert game.state.work_budget == 18
    assert sum(item.cost for item in game.state.activities) == 30
