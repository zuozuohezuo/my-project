"""End-to-end checks for ordered M03 execution and once-only submissions."""

import copy

import pytest

from dynasty.core import Activity, EmperorModifier, Phase
from legacy_support import SequentialDemoConfig as DemoConfig, SequentialGameSession as GameSession


def planned(*activities, work=0):
    session = GameSession.new_game()
    private = sum(a.cost if isinstance(a, Activity) else 1 for a in activities
                  if (a.kind if isinstance(a, Activity) else a) not in
                  {"court", "paperwork", "audience", "palace", "lecture"})
    assert session.set_turn_plan([*activities, *(["rest"] * (30 - work - private))], work).ok
    return session


def finish_xun(session):
    turn = session.state.turn_index
    for _ in range(200):
        if session.state.turn_index != turn:
            return
        activity = session.current_activity
        if activity:
            choice = activity.scene["choices"][-1]["id"]
            assert session.continue_activity(choice).ok
        else:
            assert session.advance_turn().ok
    pytest.fail("turn did not settle")


def test_new_scale_fixed_and_office_costs_budget_atomicity():
    session = GameSession.new_game()
    assert session.state.ap_capacity == 30
    assert [session.config.action_points(h) for h in [0, 50, 100]] == [10, 20, 30]
    assert not session.set_activities([Activity(kind="court", cost=1)]).ok
    assert not session.set_activities([Activity(kind="paperwork", cost=0)]).ok
    assert not session.set_activities([Activity(kind="paperwork", cost=1.5)]).ok
    assert session.set_turn_plan(["court", Activity(kind="paperwork", cost=15)] + ["rest"] * 10, 20).ok
    before = session.to_dict()
    assert not session.set_turn_plan(["court"] + ["rest"] * 25, 20).ok
    assert session.to_dict() == before
    assert session.state.ap_spent == 0
    assert session.start_turn().ok
    assert session.state.ap_spent == 5


def test_order_and_court_coverage_are_distinct_and_court_work_unlimited():
    session = planned("study", "court", work=5)
    assert session.start_turn().ok
    assert session.state.court_assigned and not session.state.court_open
    assert not session.open_court().ok
    assert not session.issue_command("appoint_official").ok
    assert session.advance_turn().status == "choice_required"
    assert session.state.turn_index == 0
    assert session.continue_activity("history").ok
    assert session.finish_activity().ok
    assert session.start_next_activity().ok
    for item in session.state.work_items:
        assert session.continue_activity(f"review:{item['id']}").ok
    assert all(item["status"] == "completed" for item in session.state.work_items)
    assert session.current_activity.spent_ap == 5
    for _ in range(3):
        assert session.issue_command("appoint_official").ok
    assert not session.issue_command("appoint_official").ok
    assert session.finish_activity().ok
    assert not session.issue_command("appoint_official").ok


def test_office_partial_work_and_no_attribute_efficiency_leak():
    session = planned(Activity(kind="paperwork", cost=2), work=2)
    clone = GameSession.from_dict(session.to_dict())
    clone.state.emperor.attributes["logic"] = 900
    assert clone.office_efficiency("paperwork") == session.office_efficiency("paperwork")
    assert session.start_turn().ok
    assert session.state.ap_spent == 0
    assert not session.finish_activity().ok
    assert session.continue_activity("work").ok
    assert session.state.work_items[0]["progress"] == 1
    session = GameSession.from_dict(session.to_dict())
    assert session.continue_activity("work").ok
    assert session.state.work_items[0]["progress"] == 2
    assert session.current_activity.stage == "ready"
    assert session.finish_activity().ok
    assert session.state.completion_records[0]["spent_ap"] == 2
    finish_xun(session)
    assert session.state.work_items[0]["progress"] == 2


def test_scene_save_resume_and_emergency_replacement_preserves_stage():
    session = planned("exercise", "study")
    assert session.start_turn().ok
    assert session.continue_activity("manual").ok
    assert session.continue_activity("steady").ok
    scene = copy.deepcopy(session.current_activity.scene)
    session.inject_emergency()
    session = GameSession.from_dict(session.to_dict())
    assert session.state.phase == Phase.INTERRUPTED
    assert session.resolve_emergency(session.state.activities[1].id, command_id=None).ok
    assert session.current_activity.scene == scene
    assert session.state.activities[1].status == "replaced"
    assert session.state.ap_spent == 2
    assert session.continue_activity("quick").ok
    assert session.continue_activity("steady").ok
    assert session.current_activity.scene["rounds"] == 3
    assert session.finish_activity().ok
    assert session.start_next_activity().ok
    assert session.current_activity.kind == "rest"
    assert not any(record["activity_kind"] == "study" for record in session.state.completion_records)


def test_current_scene_termination_does_not_count_completion():
    session = planned("garden")
    assert session.start_turn().ok
    identifier = session.current_activity.id
    session.inject_emergency()
    assert session.resolve_emergency(identifier, command_id=None).ok
    assert session.current_activity is None
    assert session.state.activities[0].stage == "terminated"
    assert not session.state.completion_records
    assert GameSession.from_dict(session.to_dict()).state.activities[0].status == "replaced"


def test_garden_opportunities_are_finite_and_generate_work_without_court_permission():
    session = planned("garden")
    assert session.start_turn().ok
    assert session.continue_activity("flowers").ok
    assert session.state.work_items[-1]["title"] == "花径修葺请托"
    assert not session.issue_command("appoint_official").ok
    before = copy.deepcopy(session.state.work_items)
    assert not session.continue_activity("flowers").ok
    assert session.state.work_items == before
    assert session.continue_activity("pond").ok
    assert session.current_activity.stage == "ready"
    assert not session.continue_activity("pavilion").ok


def test_goals_count_only_post_creation_completions_at_settlement_and_modifiers_once():
    session = planned("study", "study")
    session.state.emperor.modifiers.append(EmperorModifier("短期", "skill_effect", "scholarship", 10,
                                                        duration="short_term", remaining_turns=2))
    session.start_turn()
    session.continue_activity("history")
    session.finish_activity()
    result = session.add_emperor_objective("desire", "读一卷", "", "study", 1)
    assert result.ok
    objective = session.state.emperor.objectives[0]
    assert session.start_next_activity().ok
    session.continue_activity("classics")
    session.finish_activity()
    assert objective.progress == 0
    assert session.state.emperor.modifiers[0].remaining_turns == 2
    session = GameSession.from_dict(session.to_dict())
    finish_xun(session)
    assert session.state.emperor.objectives[0].progress == 1
    assert session.state.emperor.objectives[0].completed_turn == 0
    assert session.state.emperor.modifiers[0].remaining_turns == 1
    assert GameSession.from_dict(session.to_dict()).state.emperor.objectives[0].progress == 1


def test_goal_created_after_last_matching_completion_does_not_count_it():
    session = planned("study")
    session.start_turn()
    session.continue_activity("history")
    session.finish_activity()
    session.add_emperor_objective("desire", "后来新定的目标", "", "study", 1)
    finish_xun(session)
    assert session.state.emperor.objectives[0].progress == 0


def test_legacy_v1_keeps_own_scale_and_execution():
    session = GameSession.new_game(config=DemoConfig(turn_rules_version=1,
                                                    health_ap_thresholds=[[0, 1], [40, 2], [80, 3]]))
    assert session.set_activities(["court", "study", "rest"]).ok
    snapshot = session.to_dict()
    assert snapshot["save_version"] == 1
    snapshot["config"].pop("turn_rules_version")
    restored = GameSession.from_dict(snapshot)
    assert restored.config.turn_rules_version == 1
    assert restored.state.ap_capacity == 3
    assert restored.advance_turn().status == "advanced"


@pytest.mark.parametrize("damage", ["cursor", "spent", "scene"])
def test_damaged_execution_state_is_rejected(damage):
    session = planned("exercise")
    session.start_turn()
    session.continue_activity("manual")
    data = session.to_dict()
    if damage == "cursor":
        data["state"]["activity_cursor"] = 2
    elif damage == "spent":
        data["state"]["activities"][0]["spent_ap"] = -1
    else:
        data["state"]["activities"][0]["scene"]["rounds"] = 3
    with pytest.raises(ValueError):
        GameSession.from_dict(data)
