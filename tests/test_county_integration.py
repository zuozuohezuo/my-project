"""County accounting is committed once with the real M03 turn and save state."""

import copy

import pytest

from dynasty.content import create_county_demo
from dynasty.core import GameSession, Phase


def complete_rest_turn(session):
    for _ in range(250):
        activity = session.current_activity
        if activity and activity.stage == "ready":
            result = session.finish_activity()
        elif activity and activity.stage == "intro":
            result = session.continue_activity("continue")
        else:
            result = session.advance_turn()
        if result.status == "advanced":
            return result
        assert result.status in {"ok", "choice_required", "completed"}, result.message
    pytest.fail("Rest activities did not reach the turn settlement")


def test_consumption_waits_for_actual_turn_and_survives_mid_activity_save(tmp_path):
    session = create_county_demo("shortage")
    initial = copy.deepcopy(session.state.economy)
    assert session.set_turn_plan(["rest"] * 30, work_budget=0).ok
    assert session.start_turn().ok
    assert session.state.economy == initial
    assert session.continue_activity("continue").ok
    assert session.finish_activity().ok
    assert session.state.economy == initial
    target = tmp_path / "in-progress.json"
    session.save_json(target)
    restored = GameSession.load_json(target)
    assert restored.state.phase == Phase.EXECUTING
    assert restored.state.economy == initial
    complete_rest_turn(session)
    complete_rest_turn(restored)
    assert session.state.turn_index == 1
    assert session.state.economy["last_settled_turn"] == 0
    assert session.to_dict() == restored.to_dict()


def test_demo_shortcut_uses_the_same_real_turn_and_preserves_emperor():
    fast = create_county_demo()
    normal = create_county_demo()
    emperor = copy.deepcopy(fast.state.emperor)
    assert fast.advance_economy_demo_turn().status == "advanced"
    assert normal.set_turn_plan(["rest"] * 30, work_budget=0).ok
    complete_rest_turn(normal)
    assert fast.to_dict() == normal.to_dict()
    assert fast.state.emperor == emperor
    assert fast.state.health == 100
    assert fast.state.ap_spent == 0
    assert fast.state.phase == Phase.PLANNING


@pytest.mark.parametrize("scenario", ["normal", "shortage", "input_shortage"])
def test_demo_continues_through_year_boundary_and_restores(scenario):
    session = create_county_demo(scenario)
    for _ in range(37):
        result = session.advance_economy_demo_turn()
        assert result.status == "advanced", result.message
    assert session.state.year == 1501
    restored = GameSession.from_dict(session.to_dict())
    assert restored.to_dict() == session.to_dict()
    assert session.advance_economy_demo_turn().ok
    assert restored.advance_economy_demo_turn().ok
    assert restored.to_dict() == session.to_dict()


def test_failed_economy_keeps_finished_activity_and_entire_previous_state(monkeypatch):
    session = create_county_demo()
    assert session.set_turn_plan(["rest"] * 30, work_budget=0).ok
    session.start_turn()
    for _ in range(150):
        if session.state.turn_stage == "finished":
            break
        if session.current_activity:
            if session.current_activity.stage == "intro":
                assert session.continue_activity("continue").ok
            assert session.finish_activity().ok
        else:
            assert session.start_next_activity().ok
    assert session.state.turn_stage == "finished"
    before = session.to_dict()

    def fail(*args):
        raise ValueError("injected settlement failure")

    monkeypatch.setattr("dynasty.core.regions.economy.settle_economy", fail)
    result = session.advance_turn()
    assert result.status == "error"
    assert session.to_dict() == before


def test_shortcut_does_not_skip_emergency_or_existing_schedule():
    session = create_county_demo()
    session.inject_emergency("县情急报", "必须在原流程处理。")
    before = session.to_dict()
    assert not session.advance_economy_demo_turn().ok
    assert session.to_dict() == before
    session = create_county_demo()
    assert session.set_turn_plan(["court", "lecture"], work_budget=20).ok
    before = session.to_dict()
    assert not session.advance_economy_demo_turn().ok
    assert session.to_dict() == before


def test_resource_edit_is_local_finite_and_planning_only():
    session = create_county_demo()
    independent = create_county_demo()
    untouched = independent.to_dict()
    assert session.set_demo_economy_resource("private", "grain", 0).ok
    assert independent.to_dict() == untouched
    for bad in [True, -1, float("nan"), float("inf")]:
        before = session.to_dict()
        assert not session.set_demo_economy_resource("private", "grain", bad).ok
        assert session.to_dict() == before
    assert session.start_turn().ok
    before = session.to_dict()
    assert not session.set_demo_economy_resource("private", "grain", 50).ok
    assert session.to_dict() == before


def test_save_rejects_missing_economy_fields_and_wrong_settlement_turn():
    for damage in [lambda e: e.pop("pools"), lambda e: e.update(last_settled_turn=8)]:
        data = create_county_demo().to_dict()
        damage(data["state"]["economy"])
        with pytest.raises(ValueError):
            GameSession.from_dict(data)
    data = create_county_demo().to_dict()
    data["state"]["economy"] = None
    with pytest.raises(ValueError):
        GameSession.from_dict(data)


def test_no_economy_save_keeps_original_mode_and_no_new_payload():
    old = GameSession.new_game()
    assert "economy" not in old.to_dict()["state"]
    restored = GameSession.from_dict(old.to_dict())
    assert restored.state.economy is None
    assert restored.economy_view is None
    assert not restored.advance_economy_demo_turn().ok
    assert restored.to_dict() == old.to_dict()


def test_damaged_economy_report_date_is_rejected_before_replacing_game():
    session = create_county_demo()
    assert session.advance_economy_demo_turn().ok
    data = session.to_dict()
    data["state"]["economy"]["history"][-1]["month"] = 2
    with pytest.raises(ValueError, match="日历"):
        GameSession.from_dict(data)
