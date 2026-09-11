"""Future commitments survive planning edits, rescheduling, and saved games."""

import copy
import json

import pytest

from legacy_support import SequentialDemoConfig as DemoConfig, SequentialGameSession as GameSession
from dynasty.core.models import Activity, Phase
from dynasty.core.turns.appointments import Appointment, validate_appointments


def new_session():
    session = GameSession.new_game({"treasury": 300, "trust": 50})
    assert session.set_work_budget(0).ok
    return session


def create(session, *, due=0, source="event", preparation="ready"):
    result = session.create_appointment(source, due, "private", "使团游苑", preparation=preparation,
                                        related_people=["来访使臣"])
    assert result.ok, result.message
    return session.state.appointments[-1]


def roundtrip(session):
    return GameSession.from_dict(json.loads(json.dumps(session.to_dict())))


def finish_turn(session):
    initial = session.state.turn_index
    session.start_turn()
    for _ in range(300):
        if session.state.turn_index > initial:
            return
        current = session.current_activity
        if current is not None:
            choices = current.scene.get("choices", [])
            session.continue_activity(choices[-1]["id"] if choices else None)
        else:
            session.advance_turn()
    pytest.fail("回合未在有限活动步骤内结束")


def test_future_appointment_is_outside_three_turn_plan_and_does_not_spend_resources():
    session = new_session()
    before_world = session.world_facts
    item = create(session, due=40, source="seasonal")
    assert item.original_turn == item.due_turn == 40
    assert session.state.ap_allocated == 0
    assert session.state.appointment_consequences == []
    assert session.state.month_plan == []
    assert session.appointments_due == []
    assert session.world_facts == before_world
    restored = roundtrip(session)
    assert restored.to_dict() == session.to_dict()
    assert restored.state.appointments[0].id == item.id


def test_appointment_dates_follow_opening_calendar_through_year_boundary():
    session = GameSession.new_game(config=DemoConfig(initial_year=1500, initial_month=12,
                                                    initial_xun=3))
    assert session.appointment_date_label(0) == "弘治13年12月下旬"
    assert session.appointment_date_label(1) == "弘治14年1月上旬"
    assert session.appointment_date_label(37) == "弘治15年1月上旬"


def test_future_plan_conflict_is_visible_without_overwriting_or_punishing():
    session = new_session()
    assert session.set_month_plan([["rest"] * 30 for _ in range(3)]).ok
    plan_before = copy.deepcopy(session.state.month_plan)
    item = create(session, due=1)
    before = session.to_dict()
    assert "AP冲突" in session.appointment_conflict(item)
    assert session.to_dict() == before
    assert session.state.month_plan == plan_before
    assert session.state.appointment_consequences == []
    assert session.reschedule_appointment(item.id, 6).ok
    assert session.appointment_conflict(item) == ""


def test_conflict_is_atomic_and_player_can_edit_schedule_then_execute():
    session = new_session()
    item = create(session)
    assert session.fill_rest().ok
    before = session.to_dict()
    assert session.execute_appointment(item.id).status == "conflict"
    assert session.to_dict() == before
    assert session.start_turn().status == "appointment_required"
    assert session.set_activities(session.state.activities[:-1]).ok
    assert session.execute_appointment(item.id).ok
    assert len(session.state.activities) == 30
    assert session.state.activities[-1].appointment_id == item.id
    assert session.state.activities[-1].spent_ap == 0
    assert session.appointments_due == []
    scheduled = session.to_dict()
    assert session.execute_appointment(item.id).ok
    assert session.to_dict() == scheduled
    assert roundtrip(session).to_dict() == scheduled


def test_execute_checks_category_budget_and_preparation_before_editing_plan():
    session = new_session()
    appointment = create(session, preparation="preparing")
    before = session.to_dict()
    assert session.execute_appointment(appointment.id).status == "preparation_required"
    assert session.to_dict() == before
    assert session.update_appointment_preparation(appointment.id, "ready").ok
    assert session.set_work_budget(30).ok
    before = session.to_dict()
    assert session.execute_appointment(appointment.id).status == "conflict"
    assert session.to_dict() == before


def test_explicit_execution_confirms_an_already_linked_pending_card_once():
    session = new_session()
    appointment = create(session)
    assert session.set_activities([Activity(kind="private", appointment_id=appointment.id)]).ok
    assert appointment.status == "pending"
    assert session.execute_appointment(appointment.id).ok
    assert appointment.status == "scheduled"
    saved = session.to_dict()
    assert session.execute_appointment(appointment.id).ok
    assert session.to_dict() == saved
    assert roundtrip(session).to_dict() == saved


def test_multiple_reschedules_keep_original_date_and_commit_each_choice_once():
    session = new_session()
    item = create(session, due=3, source="seasonal")
    assert session.reschedule_appointment(item.id, 8, "筹备迟延").ok
    assert session.reschedule_appointment(item.id, 11).ok
    assert item.original_turn == 3 and item.due_turn == 11
    assert [entry["to_turn"] for entry in item.history] == [3, 8, 11]
    assert len(session.state.appointment_consequences) == 2
    saved = roundtrip(session)
    before = saved.to_dict()
    assert saved.reschedule_appointment(item.id, 11).status == "error"
    assert saved.reschedule_appointment(item.id, 5).status == "error"
    assert saved.to_dict() == before
    assert all(record["kind"] == "ritual_dispute"
               for record in saved.state.appointment_consequences)
    assert "节令不随改期移动" in saved.state.appointment_consequences[0]["description"]


@pytest.mark.parametrize("source,kind", [("seasonal", "ritual_dispute"),
                                         ("event", "trust_and_reception"),
                                         ("preparation", "preparation_loss")])
def test_absence_has_distinct_nonquantified_consequence_once(source, kind):
    session = new_session()
    item = create(session, due=4, source=source)
    initial_world = session.world_facts
    assert session.miss_appointment(item.id).ok
    assert item.status == "missed"
    record = session.state.appointment_consequences[0]
    assert record["kind"] == kind
    assert record["status"] == "pending_simulation"
    assert record["quantified"] is False
    assert session.world_facts == initial_world
    restored = roundtrip(session)
    before = restored.to_dict()
    assert restored.miss_appointment(item.id).status == "error"
    restored.expire_appointments()
    assert restored.to_dict() == before


def test_removing_scheduled_card_retains_obligation_without_a_penalty():
    session = new_session()
    item = create(session)
    assert session.execute_appointment(item.id).ok
    assert session.set_activities([]).ok
    assert item.status == "pending"
    assert session.appointments_due == [item]
    assert session.state.appointment_consequences == []
    assert roundtrip(session).to_dict() == session.to_dict()
    assert session.execute_appointment(item.id).ok
    assert session.reschedule_appointment(item.id, 7).ok
    assert session.state.activities == []
    assert item.status == "pending" and item.due_turn == 7
    assert roundtrip(session).to_dict() == session.to_dict()


def test_appointment_is_completed_by_actual_activity_then_persists_across_turn():
    session = new_session()
    item = create(session)
    assert session.execute_appointment(item.id).ok
    assert session.fill_rest().ok
    session.start_turn()
    restored = roundtrip(session)
    finish_turn(restored)
    assert restored.state.turn_index == 1
    assert restored.state.phase == Phase.PLANNING
    completed = restored.state.appointments[0]
    assert completed.status == "completed"
    assert [entry["action"] for entry in completed.history] == ["created", "scheduled", "completed"]
    assert restored.state.appointment_consequences == []
    assert roundtrip(restored).to_dict() == restored.to_dict()


def test_pending_future_appointment_becomes_required_on_its_due_turn():
    session = new_session()
    item = create(session, due=1)
    assert session.fill_rest().ok
    finish_turn(session)
    assert session.appointments_due == [item]
    assert session.start_turn().status == "appointment_required"
    assert session.miss_appointment(item.id).ok
    assert roundtrip(session).state.appointments[0].status == "missed"


def test_expiration_is_idempotent_and_is_a_real_missed_commitment():
    session = new_session()
    item = create(session)
    session.expire_appointments()
    assert item.status == "missed"
    assert len(session.state.appointment_consequences) == 1
    before = session.to_dict()
    session.expire_appointments()
    assert session.to_dict() == before


@pytest.mark.parametrize("field,value", [("cost", True), ("original_turn", "1"),
                                         ("source", []), ("due_turn", -1),
                                         ("related_people", [42]), ("history", []),
                                         ("status", "completed"), ("label", "")])
def test_appointment_model_rejects_corruption(field, value):
    session = new_session()
    create(session)
    raw = copy.deepcopy(session.to_dict()["state"]["appointments"][0])
    raw[field] = value
    with pytest.raises(ValueError, match="存档"):
        Appointment.from_dict(raw)


@pytest.mark.parametrize("corruption", ["duplicate", "missing_consequence", "duplicate_consequence",
                                         "consequence_kind", "history_date", "orphan_link"])
def test_save_validation_rejects_broken_links_or_missing_committed_consequences(corruption):
    session = new_session()
    item = create(session)
    assert session.reschedule_appointment(item.id, 3).ok
    snapshot = session.to_dict()
    state = snapshot["state"]
    if corruption == "duplicate":
        state["appointments"].append(copy.deepcopy(state["appointments"][0]))
    elif corruption == "missing_consequence":
        state["appointment_consequences"].clear()
    elif corruption == "duplicate_consequence":
        state["appointment_consequences"].append(copy.deepcopy(state["appointment_consequences"][0]))
    elif corruption == "consequence_kind":
        state["appointment_consequences"][0]["kind"] = "cash_fine"
    elif corruption == "history_date":
        state["appointments"][0]["history"][1]["from_turn"] = 2
    else:
        session.set_activities(["rest"])
        snapshot = session.to_dict()
        snapshot["state"]["activities"][0]["appointment_id"] = "unknown-appointment"
    with pytest.raises(ValueError, match="存档"):
        GameSession.from_dict(snapshot)


def test_no_appointment_mutation_is_allowed_after_activity_has_started():
    session = new_session()
    item = create(session)
    assert session.execute_appointment(item.id).ok
    assert session.fill_rest().ok
    session.start_turn()
    before = session.to_dict()
    assert session.reschedule_appointment(item.id, 2).status == "error"
    assert session.miss_appointment(item.id).status == "error"
    assert session.to_dict() == before
    validate_appointments(session.state)
