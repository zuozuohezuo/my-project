"""Stage-aware emergency timing uses actual AP, including time chosen on demand."""

import copy

import pytest

from dynasty.core import Activity, DemoConfig, GameSession, Phase


def new_session(cards=(), *, work=0, capacity=30, seed=7):
    session = GameSession.new_game(config=DemoConfig(turn_rules_version=3, seed=seed,
                                                    health_ap_thresholds=[[0, capacity]]))
    assert session.set_turn_plan(list(cards), work).ok
    return session


def latest(session, event_id):
    return session.state.emergency_timing[event_id]["attempts"][-1]


def finish_court(session):
    assert session.current_activity.kind == "court"
    assert session.finish_activity().ok
    assert session.state.phase == Phase.EXECUTING


def test_work_emergency_never_interrupts_court_and_fires_after_midpoint_ap_commit():
    session = new_session(["court", Activity(kind="paperwork", cost=6)], work=11)
    event = session.inject_emergency()
    assert session.start_turn().ok
    assert session.current_activity.kind == "court"
    assert session.state.phase == Phase.EXECUTING
    assert latest(session, event.id)["threshold"] == 3
    assert session.continue_activity(f"review:{session.state.work_items[-1]['id']}").ok
    finish_court(session)
    assert session.start_next_activity().ok
    for _ in range(2):
        assert session.continue_activity("work").ok
        assert event.status == "pending"
    assert session.continue_activity("work").status == "interrupted"
    assert session.current_activity.spent_ap == 3
    assert session.state.turn_stage == "work"
    restored = GameSession.from_dict(session.to_dict())
    before_ap = restored.state.ap_spent
    assert restored.resolve_emergency(command_id=None).ok
    assert restored.state.ap_spent == before_ap
    assert restored.continue_activity("work").ok
    assert restored.current_activity.spent_ap == 4
    assert restored.state.random_state["draws"] == 0


def test_unassigned_work_budget_counts_as_a_work_stage_before_any_card_is_chosen():
    session = new_session(["court"], work=15)
    event = session.inject_emergency()
    session.start_turn()
    finish_court(session)
    assert session.state.stage_unallocated["work"] == 10
    assert latest(session, event.id)["stage"] == "work"
    assert latest(session, event.id)["threshold"] == 5
    assert session.append_stage_activity("paperwork", 10).ok
    session.start_next_activity()
    for _ in range(4):
        assert session.continue_activity("work").ok
    assert session.continue_activity("work").status == "interrupted"
    assert session.current_activity.spent_ap == 5


def test_private_emergency_keeps_one_saved_position_and_never_uses_the_last_action():
    session = new_session(["court"], work=5, seed=31)
    event = session.inject_emergency()
    session.start_turn()
    initial = copy.deepcopy(latest(session, event.id))
    assert initial["stage"] == "private"
    assert 1 <= initial["threshold"] < 25
    assert session.state.random_state["draws"] == 1
    finish_court(session)
    session = GameSession.from_dict(session.to_dict())
    for position in range(1, initial["threshold"] + 1):
        assert session.append_stage_activity("study").ok
        assert session.start_next_activity().ok
        result = session.continue_activity("history")
        if position == initial["threshold"]:
            assert result.status == "interrupted"
            break
        assert result.ok
        assert session.finish_activity().ok
        session = GameSession.from_dict(session.to_dict())
        assert latest(session, event.id) == initial
    assert session.state.stage_spent["private"] < session.state.stage_budget["private"]
    assert session.state.random_state["draws"] == 1
    assert latest(session, event.id)["threshold"] == initial["threshold"]


def test_one_preplanned_private_card_is_eligible_when_later_budget_is_unassigned():
    session = new_session(["rest"], capacity=2)
    event = session.inject_emergency()
    assert session.start_turn().ok
    assert len(session.state.activities) == 1
    assert session.state.stage_unallocated["private"] == 1
    assert session.continue_activity("continue").status == "interrupted"
    assert latest(session, event.id)["threshold"] == 1
    assert session.resolve_emergency(session.current_activity.id, command_id=None).ok
    assert session.state.stage_remaining["private"] == 1


def test_only_one_private_ap_defers_instead_of_interrupting_court_or_last_action():
    session = new_session(["court"], work=5, capacity=6)
    event = session.inject_emergency()
    session.start_turn()
    assert event.trigger_turn == 1 and event.status == "pending"
    assert session.state.random_state["draws"] == 0
    finish_court(session)
    session.append_stage_activity("rest")
    session.start_next_activity()
    assert session.continue_activity("continue").ok
    assert session.finish_activity().ok
    assert session.state.turn_stage == "finished"
    assert len([log for log in session.logs if log["label"] == "急报顺延"]) == 1
    assert GameSession.from_dict(session.to_dict()).state.emergencies[0].trigger_turn == 1
    assert session.advance_turn().ok
    assert session.state.turn_index == 1
    session = GameSession.from_dict(session.to_dict())
    assert session.start_turn().ok
    assert session.state.emergencies[0].trigger_turn == 2
    assert len(session.state.emergency_timing[event.id]["attempts"]) == 2
    assert session.state.random_state["draws"] == 0


def test_emergency_registered_during_last_private_action_is_deferred_without_redraw():
    session = new_session(["rest"] * 3, capacity=3)
    session.start_turn()
    for _ in range(2):
        session.continue_activity("continue")
        session.finish_activity()
        session.start_next_activity()
    assert session.state.stage_spent["private"] == 3
    event = session.inject_emergency()
    assert session.state.phase == Phase.EXECUTING
    assert event.trigger_turn == 1
    saved = copy.deepcopy(session.state.emergency_timing)
    assert session.continue_activity("continue").ok
    assert session.state.emergency_timing == saved
    assert GameSession.from_dict(session.to_dict()).state.emergency_timing == saved


def test_late_work_report_does_not_retroactively_trigger_a_passed_midpoint():
    session = new_session([Activity(kind="paperwork", cost=6)], work=6)
    session.start_turn()
    for _ in range(4):
        assert session.continue_activity("work").ok
    event = session.inject_emergency()
    assert event.trigger_turn == 1 and event.status == "pending"
    assert session.state.phase == Phase.EXECUTING
    assert latest(session, event.id)["threshold"] == 3
    assert "错过" in latest(session, event.id)["reason"]


def test_early_work_exit_delivers_a_queued_report_before_transferring_time():
    session = new_session([Activity(kind="paperwork", cost=2)], work=10)
    event = session.inject_emergency()
    session.start_turn()
    assert session.continue_activity("work").ok
    assert latest(session, event.id)["threshold"] == 5
    work_before = session.state.work_budget
    assert session.finish_work_stage().status == "interrupted"
    assert session.state.work_budget == work_before
    assert session.state.turn_stage == "work"
    assert session.resolve_emergency(session.current_activity.id, command_id=None).ok
    assert session.finish_work_stage().ok
    assert session.state.turn_stage == "private"
    assert latest(session, event.id)["status"] == "delivered"


def test_zero_work_exit_falls_back_to_private_time_and_draws_only_after_transfer():
    session = new_session(["court"], work=15)
    event = session.inject_emergency()
    session.start_turn()
    finish_court(session)
    assert session.finish_work_stage().ok
    assert session.state.stage_spent["work"] == 0
    assert session.state.stage_budget["private"] == 25
    assert latest(session, event.id)["stage"] == "await_private"
    assert session.state.random_state["draws"] == 0
    assert session.start_next_activity().status == "stage_choice_required"
    assert latest(session, event.id)["stage"] == "private"
    assert 1 <= latest(session, event.id)["threshold"] < 25
    assert session.state.random_state["draws"] == 1
    snapshot = session.to_dict()
    assert GameSession.from_dict(snapshot).to_dict() == snapshot


def test_private_saved_position_cannot_be_changed_to_the_last_action():
    session = new_session(["rest"], capacity=8)
    event = session.inject_emergency()
    session.start_turn()
    snapshot = session.to_dict()
    snapshot["state"]["emergency_timing"][event.id]["attempts"][0]["threshold"] = 8
    with pytest.raises(ValueError, match="存档"):
        GameSession.from_dict(snapshot)


def test_work_midpoint_does_not_move_when_unused_work_time_is_partially_transferred():
    session = new_session([Activity(kind="paperwork", cost=2)], work=10)
    event = session.inject_emergency()
    session.start_turn()
    session.continue_activity("work")
    assert session.transfer_work_to_private(5).ok
    assert session.state.stage_budget["work"] == 5
    assert latest(session, event.id)["threshold"] == 5
    assert latest(session, event.id)["budget"] == 10
    assert session.state.phase == Phase.EXECUTING
    assert GameSession.from_dict(session.to_dict()).state.emergency_timing == session.state.emergency_timing


def test_second_queued_report_can_use_unassigned_work_without_a_replacement_deadlock():
    session = new_session([Activity(kind="paperwork", cost=5)], work=10)
    first = session.inject_emergency("第一份急报")
    second = session.inject_emergency("第二份急报")
    session.start_turn()
    for _ in range(4):
        assert session.continue_activity("work").ok
    assert session.continue_activity("work").status == "interrupted"
    assert session.active_emergency.id == first.id
    assert session.resolve_emergency(session.current_activity.id, command_id=None).ok
    assert session.start_next_activity().status == "interrupted"
    assert session.active_emergency.id == second.id
    assert session.current_activity is None
    assert session.resolve_emergency(command_id=None).ok
    assert session.state.stage_spent["work"] == 6
    assert session.state.stage_unallocated["work"] == 4
    assert session.state.completion_records == []


def test_partial_transfer_of_unassigned_ap_preserves_office_appointment_and_emergency_midpoint():
    session = new_session([Activity(kind="paperwork", cost=2)], work=10)
    appointment = session.create_appointment("event", 0, "audience", "接见来使")
    assert session.execute_appointment(appointment.record_id).ok
    event = session.inject_emergency()
    session.start_turn()
    assert session.continue_activity("work").ok
    current_id = session.current_activity.id
    assert session.state.stage_unallocated["work"] == 7
    assert session.transfer_work_to_private(1).ok
    assert session.current_activity.id == current_id
    assert session.current_activity.spent_ap == 1
    assert session.state.appointments[0].status == "scheduled"
    assert session.state.appointment_consequences == []
    assert latest(session, event.id)["threshold"] == 5
    assert GameSession.from_dict(session.to_dict()).to_dict() == session.to_dict()
