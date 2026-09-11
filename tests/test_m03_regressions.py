"""Boundary regressions across planning, interrupted execution, and saved scenes."""

import copy
from dataclasses import asdict

import pytest

from dynasty.core import Activity, Phase
from legacy_support import SequentialDemoConfig as DemoConfig, SequentialGameSession as GameSession
from dynasty.ui.planning_page import PlanningPage


def session_with_plan(activities, *, work=0, config=None):
    session = GameSession.new_game(config=config)
    spent = sum(activity.cost if isinstance(activity, Activity)
                else 5 if activity == "court" else 1 for activity in activities)
    assert session.set_turn_plan([*activities, *(["rest"] * (30 - spent))], work).ok
    return session


def finish_turn(session):
    initial = session.state.turn_index
    for _ in range(250):
        if session.state.turn_index != initial:
            return
        current = session.current_activity
        if current is None:
            result = session.advance_turn()
        else:
            result = session.continue_activity(current.scene["choices"][-1]["id"])
        assert result.ok, result.message
    pytest.fail("本旬未在有限步骤内完成")


def test_next_month_plan_survives_planning_page_refresh_and_capture(qtbot):
    session = GameSession.new_game()
    next_plan = ["court", *(["study"] * 25)]
    assert session.set_month_plan([["rest"] * 30, next_plan, ["rest"] * 30]).ok
    finish_turn(session)
    assert session.state.turn_index == 1
    page = PlanningPage(session)
    qtbot.addWidget(page)
    page.refresh(force=True)
    assert [card.kind for card in page.draft_activities()] == next_plan
    assert page.work_spin.value() == 5
    assert page.capture_draft().ok
    restored = GameSession.from_dict(session.to_dict())
    assert [card.kind for card in restored.state.activities] == next_plan
    assert restored.state.month_plan[1].work_budget == 5
    assert restored.start_turn().ok
    assert restored.current_activity.kind == "court"


def test_planned_commands_after_remonstrance_are_processed_before_court_finishes():
    session = GameSession.new_game()
    commands = [{"command_id": "change_tax", "parameters": {"rate": 10}},
                {"command_id": "change_tax", "parameters": {"rate": 8}},
                {"command_id": "appoint_official", "parameters": {"office": "礼部"}}]
    assert session.set_month_plan([
        {"activities": ["court"] + ["rest"] * 25, "commands": commands},
        ["rest"] * 30, ["rest"] * 30,
    ]).ok
    assert session.start_turn().status == "remonstrance"
    restored = GameSession.from_dict(session.to_dict())
    assert restored.resolve_remonstrance(True).ok
    assert restored.finish_activity().ok
    assert [record["command_id"] for record in restored.state.command_ledger] == [
        "change_tax", "appoint_official",
    ]
    assert [command.status for command in restored.state.month_plan[0].commands] == [
        "issued", "cancelled", "issued",
    ]
    before = restored.to_dict()
    assert not restored.finish_activity().ok
    assert restored.to_dict() == before


def test_planned_command_quota_failure_blocks_court_until_explicit_cancellation():
    session = GameSession.new_game(config=DemoConfig(edicts_per_turn=1))
    assert session.set_month_plan([
        {"activities": ["court"] + ["rest"] * 25,
         "commands": [{"command_id": "appoint_official"}, {"command_id": "build_canal"}]},
        ["rest"] * 30, ["rest"] * 30,
    ]).ok
    assert not session.start_turn().ok
    assert session.current_activity.kind == "court"
    assert not session.finish_activity().ok
    assert session.current_activity.kind == "court"
    assert len(session.state.command_ledger) == 1
    assert session.state.month_plan[0].commands[1].status == "pending"
    assert session.cancel_planned_commands().ok
    assert session.finish_activity().ok
    finish_turn(session)
    assert len(session.state.command_ledger) == 1


def test_future_emergency_replacement_preserves_office_progress_and_resumes_once():
    session = session_with_plan([Activity(kind="paperwork", cost=3), "study"], work=3)
    assert session.start_turn().ok
    assert session.continue_activity("work").ok
    partial = copy.deepcopy(session.state.work_items)
    current_scene = copy.deepcopy(session.current_activity.scene)
    session.inject_emergency()
    restored = GameSession.from_dict(session.to_dict())
    assert restored.resolve_emergency(restored.state.activities[1].id).ok
    assert restored.current_activity.scene == current_scene
    assert restored.state.work_items == partial
    assert restored.state.ap_spent == 2
    after = restored.to_dict()
    assert not restored.resolve_emergency().ok
    assert restored.to_dict() == after
    finish_turn(restored)
    assert len(restored.state.command_ledger) == 1
    assert not any(record["activity_kind"] == "study" for record in restored.state.completion_records)
    assert len([record for record in restored.state.completion_records
                if record["activity_kind"] == "paperwork"]) == 1


def test_current_office_emergency_keeps_committed_work_without_complete_reward():
    session = session_with_plan([Activity(kind="paperwork", cost=3)], work=3)
    session.start_turn()
    session.continue_activity("work")
    committed = copy.deepcopy(session.state.work_items)
    activity_id = session.current_activity.id
    session.inject_emergency()
    assert session.resolve_emergency(activity_id, command_id=None).ok
    assert session.current_activity is None
    assert session.state.ap_spent == 3
    restored = GameSession.from_dict(session.to_dict())
    finish_turn(restored)
    assert restored.state.work_items == committed
    assert all(record["activity_id"] != activity_id for record in restored.state.completion_records)
    assert all(effect.get("activity_id") != activity_id for effect in restored.state.pending_effects)


def test_saved_garden_choices_cannot_reintroduce_a_visit_and_duplicate_its_result():
    session = session_with_plan(["garden"])
    session.start_turn()
    session.continue_activity("flowers")
    snapshot = session.to_dict()
    snapshot["state"]["activities"][0]["scene"]["choices"].append(
        {"id": "flowers", "label": "再次听取花径请托"},
    )
    with pytest.raises(ValueError, match="存档"):
        GameSession.from_dict(snapshot)


def test_saved_activity_stage_must_belong_to_its_activity_kind():
    session = session_with_plan(["study"])
    session.start_turn()
    snapshot = session.to_dict()
    card = snapshot["state"]["activities"][0]
    card["stage"] = "exercise_round"
    card["scene"] = {"title": "假射艺", "text": "",
                     "choices": [{"id": "steady", "label": "放箭"}], "rounds": 0, "score": 0}
    with pytest.raises(ValueError, match="存档"):
        GameSession.from_dict(snapshot)


def test_completed_scene_reload_cannot_submit_another_completion_or_world_effect():
    session = session_with_plan(["garden"])
    session.start_turn()
    session.continue_activity("flowers")
    session.continue_activity("pond")
    session.finish_activity()
    restored = GameSession.from_dict(session.to_dict())
    before = restored.to_dict()
    assert not restored.finish_activity().ok
    assert restored.to_dict() == before
    assert len(restored.state.completion_records) == 1
    assert len([item for item in restored.state.work_items if item["title"] == "花径修葺请托"]) == 1
    assert restored.state.phase == Phase.EXECUTING
    corrupted = restored.to_dict()
    corrupted["state"]["completion_records"][0]["activity_kind"] = "study"
    with pytest.raises(ValueError, match="存档"):
        GameSession.from_dict(corrupted)


def test_copying_current_appointment_into_a_future_month_plan_is_rejected_atomically():
    session = GameSession.new_game()
    session.set_work_budget(0)
    result = session.create_appointment("event", 0, "private", "到访使团")
    assert session.execute_appointment(result.record_id).ok
    session.fill_rest()
    duplicated = [asdict(card) for card in session.state.activities]
    before = session.to_dict()
    assert not session.set_month_plan([duplicated, duplicated, ["rest"] * 30]).ok
    assert session.to_dict() == before


def test_saved_future_plan_must_validate_costs_before_becoming_live():
    session = GameSession.new_game()
    assert session.set_month_plan([["rest"] * 30, ["court"] + ["rest"] * 25,
                                   ["rest"] * 30]).ok
    snapshot = session.to_dict()
    snapshot["state"]["month_plan"][1]["activities"][0]["cost"] = 1
    with pytest.raises(ValueError, match="存档"):
        GameSession.from_dict(snapshot)
