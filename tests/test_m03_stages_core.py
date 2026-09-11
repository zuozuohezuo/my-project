"""Version 3 stage boundaries and resource conservation, with old-save coverage."""

import copy

import pytest

from dynasty.core import Activity, BodyCondition, DemoConfig, GameSession, Phase


def complete_activity(session):
    for _ in range(100):
        if session.current_activity is None:
            return
        assert session.continue_activity(session.current_activity.scene["choices"][-1]["id"]).ok
    pytest.fail("activity did not finish")


def finish_private_time(session):
    assert session.state.turn_stage == "private"
    for _ in range(120):
        if session.state.turn_stage == "finished":
            return
        if session.current_activity:
            complete_activity(session)
        else:
            if session.state.stage_unallocated["private"]:
                assert session.append_stage_activity("rest").ok
            assert session.start_next_activity().ok
    pytest.fail("private phase did not finish")


def test_new_game_default_court_and_stage_budgets():
    session = GameSession.new_game()
    assert session.config.turn_rules_version == 3
    assert [(a.kind, a.cost) for a in session.state.activities] == [("court", 5)]
    assert session.state.stage_budget == {"court": 5, "work": 15, "private": 10}
    assert session.state.stage_unallocated == {"court": 0, "work": 15, "private": 10}
    assert session.state.ap_spent == 0
    assert GameSession.from_dict(session.to_dict()).to_dict() == session.to_dict()


def test_court_is_optional_unique_first_and_categories_never_mix():
    session = GameSession.new_game()
    assert session.set_turn_plan(["study", "lecture", "court", "rest", "paperwork"], 20).ok
    assert [a.kind for a in session.state.activities] == ["court", "lecture", "paperwork", "study", "rest"]
    before = session.to_dict()
    assert not session.set_turn_plan(["court", "court"], 20).ok
    assert session.to_dict() == before
    assert session.set_turn_plan([], 20).ok
    assert session.state.stage_budget == {"court": 0, "work": 20, "private": 10}
    assert session.start_turn().ok
    assert session.state.turn_stage == "work"
    assert not session.state.activities


def test_partial_plan_starts_and_pauses_for_stage_choice_without_filling_time():
    session = GameSession.new_game()
    assert session.start_turn().ok
    assert session.current_activity.kind == "court"
    assert session.finish_activity().ok
    assert session.state.turn_stage == "work"
    assert session.advance_turn().status == "stage_choice_required"
    assert session.state.turn_index == 0 and len(session.state.activities) == 1
    assert session.state.ap_spent == 5


def test_late_choice_is_restricted_to_current_stage_and_budget():
    session = GameSession.new_game()
    session.start_turn()
    session.finish_activity()
    before = session.to_dict()
    for kind, cost in [("garden", 1), ("court", 5), ("paperwork", 16)]:
        assert not session.append_stage_activity(kind, cost).ok
    assert session.to_dict() == before
    assert session.append_stage_activity("paperwork", 4).ok
    assert session.current_activity is None
    assert session.state.stage_unallocated["work"] == 11
    assert session.start_next_activity().ok
    assert session.current_activity.kind == "paperwork"


def test_partial_office_end_keeps_work_progress_and_transfers_only_unused_time():
    session = GameSession.new_game()
    assert session.set_turn_plan(["court", Activity(kind="paperwork", cost=8), "lecture", "study"], 20).ok
    session.add_emperor_objective("desire", "完成办公", "", "paperwork", 1)
    session.start_turn()
    session.finish_activity()
    session.start_next_activity()
    session.continue_activity("work")
    session.continue_activity("work")
    assert session.finish_work_stage().ok
    assert session.state.turn_stage == "private"
    assert session.state.work_budget == 7
    assert session.state.stage_budget == {"court": 5, "work": 2, "private": 23}
    assert session.state.ap_spent == 7
    assert session.state.work_items[0]["progress"] == 2
    assert session.state.activities[1].status == "stopped"
    assert session.state.activities[2].status == "cancelled"
    assert not any(record["activity_kind"] == "paperwork" for record in session.state.completion_records)
    assert session.state.emperor.objectives[0].progress == 0
    restored = GameSession.from_dict(session.to_dict())
    assert restored.to_dict() == session.to_dict()
    finish_private_time(restored)
    assert restored.advance_turn().status == "advanced"
    assert restored.state.emperor.objectives[0].progress == 0
    assert restored.state.work_items[0]["progress"] == 2


def test_part_transfer_reopens_remaining_work_slots_and_cannot_reverse():
    session = GameSession.new_game()
    session.start_turn()
    session.finish_activity()
    session.append_stage_activity("paperwork", 6)
    session.start_next_activity()
    session.continue_activity("work")
    assert session.transfer_work_to_private(3).ok
    assert session.state.turn_stage == "work"
    assert session.state.stage_remaining["work"] == 11
    assert session.state.private_budget == 13
    assert session.current_activity.kind == "paperwork"
    assert session.state.stage_unallocated["work"] == 6
    assert session.append_stage_activity("audience", 6).ok
    complete_activity(session)
    assert session.start_next_activity().ok
    complete_activity(session)
    assert session.state.turn_stage == "private"
    assert not session.transfer_work_to_private(1).ok
    assert not session.set_work_budget(20).ok
    assert not session.append_stage_activity("lecture").ok
    assert GameSession.from_dict(session.to_dict()).state.stage_remaining["private"] == 13


def test_ready_work_requires_its_summary_before_transferring_time():
    session = GameSession.new_game()
    session.start_turn()
    session.finish_activity()
    session.append_stage_activity("paperwork", 1)
    session.start_next_activity()
    session.continue_activity("work")
    before = session.to_dict()
    assert not session.finish_work_stage().ok
    assert session.to_dict() == before
    assert session.finish_activity().ok
    assert session.finish_work_stage().ok


def test_court_only_work_budget_skips_empty_work_phase():
    session = GameSession.new_game()
    assert session.set_turn_plan(["court"], 5).ok
    session.start_turn()
    session.finish_activity()
    assert session.state.turn_stage == "private"
    assert session.advance_turn().status == "stage_choice_required"
    assert len(session.state.activities) == 1


def test_private_budget_must_be_used_with_real_actions_before_settlement():
    session = GameSession.new_game()
    session.start_turn()
    session.finish_activity()
    session.finish_work_stage()
    assert session.state.private_budget == 25
    assert session.advance_turn().status == "stage_choice_required"
    finish_private_time(session)
    assert session.state.ap_spent == 30
    assert session.state.turn_stage == "finished"
    assert session.advance_turn().status == "advanced"
    assert session.state.phase == Phase.PLANNING
    assert [(activity.kind, activity.cost) for activity in session.state.activities] == [("court", 5)]
    assert session.state.work_budget == 20
    assert session.state.ap_spent == 0


def test_three_turn_partial_plans_preserve_next_plan_and_current_transfer_save():
    session = GameSession.new_game()
    assert session.set_month_plan([
        {"activities": ["court"], "work_budget": 20},
        {"activities": ["study"], "work_budget": 0},
        {"activities": ["lecture", "court"], "work_budget": 10},
    ]).ok
    session.start_turn()
    session.finish_activity()
    session.append_stage_activity("paperwork", 3)
    session.start_next_activity()
    session.continue_activity("work")
    assert session.finish_work_stage().ok
    session = GameSession.from_dict(session.to_dict())
    finish_private_time(session)
    assert session.advance_turn().status == "advanced"
    assert [activity.kind for activity in session.state.activities] == ["study"]
    assert session.state.work_budget == 0
    assert session.state.turn_stage == "private"
    assert GameSession.from_dict(session.to_dict()).state.turn_stage == "private"


def test_ending_work_records_cancelled_appointment_absence_once():
    session = GameSession.new_game()
    result = session.create_appointment("event", 0, "audience", "会见来使", cost=4)
    assert result.ok
    assert session.execute_appointment(result.record_id).ok
    session.start_turn()
    session.finish_activity()
    assert session.finish_work_stage().ok
    assert session.state.appointments[0].status == "missed"
    assert len(session.state.appointment_consequences) == 1
    session = GameSession.from_dict(session.to_dict())
    finish_private_time(session)
    session.advance_turn()
    assert len(session.state.appointment_consequences) == 1


@pytest.mark.parametrize("version", [1, 2])
def test_prior_save_rules_remain_unchanged_and_stage_less_v2_loads(version):
    config = DemoConfig(turn_rules_version=version,
                        health_ap_thresholds=[[0, 1], [40, 2], [80, 3]] if version == 1
                        else [[0, 10], [40, 20], [80, 30]])
    session = GameSession.new_game(config=config)
    assert not session.state.activities
    if version == 1:
        session.set_activities(["court", "rest", "rest"])
    else:
        session.set_turn_plan(["study", "court"] + ["rest"] * 24, 5)
    data = session.to_dict()
    for key in ("turn_stage", "stage_initial_work_budget", "stage_transfers", "emergency_timing"):
        data["state"].pop(key)
    restored = GameSession.from_dict(data)
    assert restored.to_dict()["save_version"] == version
    if version == 1:
        assert restored.advance_turn().status == "advanced"
    else:
        restored.start_turn()
        assert restored.current_activity.kind == "study"
        assert restored.advance_turn().status == "choice_required"


@pytest.mark.parametrize("damage", ["phase", "order", "budget", "reverse", "missing"])
def test_corrupt_stage_saves_are_rejected(damage):
    session = GameSession.new_game()
    session.start_turn()
    session.finish_activity()
    session.append_stage_activity("paperwork", 3)
    session.start_next_activity()
    session.continue_activity("work")
    session.transfer_work_to_private(2)
    data = copy.deepcopy(session.to_dict())
    if damage == "phase":
        data["state"]["turn_stage"] = "private"
    elif damage == "order":
        data["state"]["activities"].reverse()
    elif damage == "budget":
        data["state"]["work_budget"] += 1
    elif damage == "reverse":
        data["state"]["stage_transfers"][0]["amount"] = -2
    else:
        data["state"].pop("turn_stage")
    with pytest.raises(ValueError):
        GameSession.from_dict(data)


@pytest.mark.parametrize("health,pressure,conditions", [
    (99, 0, []),
    (100, 40, [BodyCondition("左臂", "轻伤", "injury")]),
])
def test_same_capacity_health_edits_preserve_transferred_stage_and_save(health, pressure, conditions):
    session = GameSession.new_game()
    session.start_turn()
    session.finish_activity()
    session.append_stage_activity("paperwork", 3)
    session.start_next_activity()
    session.continue_activity("work")
    session.finish_work_stage()
    session.inject_emergency("稍后送达", "已过工作阶段的急报应保留其顺延记录")
    before = copy.deepcopy(session.to_dict()["state"])
    assert session.update_emperor_health(health, pressure, conditions).ok
    for field in ("work_budget", "stage_initial_work_budget", "turn_stage", "stage_transfers",
                  "emergency_timing", "activities", "activity_cursor", "completion_records"):
        assert session.to_dict()["state"][field] == before[field]
    restored = GameSession.from_dict(session.to_dict())
    assert restored.state.turn_stage == "private"
    assert restored.state.work_budget == 6 and restored.state.stage_initial_work_budget == 20
    assert restored.state.health == health and restored.state.emperor.pressure == pressure
    assert restored.to_dict() == session.to_dict()


def test_same_capacity_health_edit_preserves_interrupted_work_and_resume():
    session = GameSession.new_game()
    session.start_turn()
    session.finish_activity()
    session.append_stage_activity("paperwork", 10)
    session.start_next_activity()
    session.continue_activity("work")
    session.transfer_work_to_private(2)
    session.inject_emergency("工作中点送达")
    while session.state.phase == Phase.EXECUTING:
        session.continue_activity("work")
    assert session.state.phase == Phase.INTERRUPTED
    before = copy.deepcopy(session.to_dict()["state"])
    assert session.update_emperor_health(99, 20, []).ok
    for field in ("phase", "work_budget", "stage_initial_work_budget", "turn_stage", "stage_transfers",
                  "emergency_timing", "activities", "activity_cursor", "active_emergency_id"):
        assert session.to_dict()["state"][field] == before[field]
    restored = GameSession.from_dict(session.to_dict())
    assert restored.resolve_emergency(command_id=None).ok
    assert restored.current_activity.kind == "paperwork"
    assert restored.current_activity.spent_ap == 8


def test_planning_health_capacity_reduction_keeps_reserved_private_budget_valid():
    session = GameSession.new_game()
    assert session.set_turn_plan(["court"] + ["rest"] * 10, 20).ok
    assert session.update_emperor_health(79, 0, []).ok
    assert session.state.ap_capacity == 20
    assert session.state.work_budget == 10
    assert session.state.private_budget == 10
    assert session.state.stage_initial_work_budget == 10
    assert all(value >= 0 for value in session.state.stage_unallocated.values())
    assert GameSession.from_dict(session.to_dict()).to_dict() == session.to_dict()
