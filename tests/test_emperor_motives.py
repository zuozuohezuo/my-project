"""Preferences are descriptive; objectives advance only through completed activities."""

import copy
from dataclasses import FrozenInstanceError

import pytest

from legacy_support import LegacyGameSession as GameSession
from dynasty.core.emperor import BodyCondition, EmperorModifier
from dynasty.core.motives import PERSONALITY_DIMENSIONS


def add_goal(session, *, kind="desire", title="读书心愿", activity="study", count=2):
    result = session.add_emperor_objective(kind, title, "", activity, count)
    assert result.ok
    return next(item for item in session.state.emperor.objectives if item.id == result.record_id)


def complete_activities(session, activities):
    assert session.set_activities(activities).ok
    assert session.advance_turn().ok


def test_nine_agreed_personality_axes_have_independent_demonstration_defaults():
    first, second = GameSession.new_game(), GameSession.new_game()
    assert [(item.left, item.right) for item in PERSONALITY_DIMENSIONS] == [
        ("仁厚", "严酷"), ("宽信", "多疑"), ("守成", "求变"), ("质朴", "奢华"),
        ("放权", "掌控"), ("谦逊", "自负"), ("重情", "秉公"), ("守信", "权宜"),
        ("合群", "独处"),
    ]
    assert first.state.emperor.personality == {item.id: 50 for item in PERSONALITY_DIMENSIONS}
    first.state.emperor.personality["trust"] = 0
    add_goal(first)
    assert second.state.emperor.personality["trust"] == 50
    assert second.state.emperor.objectives == []
    with pytest.raises(FrozenInstanceError):
        PERSONALITY_DIMENSIONS[0].left = "改名"


def test_personality_edit_preserves_all_other_state_and_copies_input():
    session = GameSession.new_game({"treasury": 400})
    assert session.update_emperor_health(90, 30, [BodyCondition("肺", "咳疾")]).ok
    assert session.update_emperor_modifiers([EmperorModifier("专注", "attribute", "insight", 5)]).ok
    session.state.emperor.traits = ["旧档特质"]
    add_goal(session)
    session.set_activities(["study"])
    before = session.to_dict()
    proposed = dict(session.state.emperor.personality, trust=0, luxury=100)
    assert session.update_emperor_personality(proposed).ok
    expected = copy.deepcopy(before)
    expected["state"]["emperor"]["personality"] = proposed.copy()
    assert session.to_dict() == expected
    proposed["trust"] = 99
    assert session.state.emperor.personality["trust"] == 0
    # Existing editors must preserve the new motive fields too.
    assert session.update_emperor_profile(session.state.emperor.attributes, session.state.emperor.skills).ok
    assert session.update_emperor_health(91, 29, []).ok
    assert session.update_emperor_modifiers([]).ok
    assert session.state.emperor.personality == expected["state"]["emperor"]["personality"]
    assert len(session.state.emperor.objectives) == 1


@pytest.mark.parametrize("invalid", [True, 10.0, -1, 101, "50"])
def test_personality_requires_strict_in_range_integers_atomically(invalid):
    session = GameSession.new_game()
    before = session.to_dict()
    proposed = dict(session.state.emperor.personality, trust=0, luxury=invalid)
    assert not session.update_emperor_personality(proposed).ok
    assert session.to_dict() == before


def test_personality_requires_exactly_the_nine_known_axes():
    session = GameSession.new_game()
    before = session.to_dict()
    missing = dict(session.state.emperor.personality)
    missing.pop("trust")
    for invalid in (missing, dict(session.state.emperor.personality, unknown=50), [], None):
        assert not session.update_emperor_personality(invalid).ok
        assert session.to_dict() == before


def test_goal_admission_is_atomic_and_rejects_only_identical_active_goals():
    session = GameSession.new_game()
    first = add_goal(session)
    before = session.to_dict()
    for parameters in [
        ("desire", "读书心愿", "", "study", 2),
        ("unknown", "目标", "", "study", 1),
        ("desire", " ", "", "study", 1),
        ("desire", "目标", "", "unknown", 1),
        ("desire", "目标", "", "study", True),
        ("desire", "目标", "", "study", 0),
    ]:
        assert not session.add_emperor_objective(*parameters).ok
        assert session.to_dict() == before
    second = add_goal(session, kind="ambition")
    assert second.id != first.id
    assert session.state.health == before["state"]["health"]
    assert session.state.ap_remaining == before["state"]["ap_capacity"]
    assert session.state.edict_available == before["state"]["edict_available"]


def test_goals_count_future_completed_activities_and_fulfill_once_without_rewards():
    session = GameSession.new_game({"treasury": 500})
    complete_activities(session, ["study", "study", "rest"])
    goal = add_goal(session, count=3)
    assert goal.progress == 0
    original_attributes = session.state.emperor.attributes.copy()
    original_skills = session.state.emperor.skills.copy()
    assert not session.advance_turn().ok
    assert goal.progress == 0
    complete_activities(session, ["study", "study", "private"])
    assert (goal.progress, goal.status, goal.completed_turn) == (2, "active", None)
    complete_activities(session, ["study", "study", "study"])
    assert (goal.progress, goal.status, goal.completed_turn) == (3, "fulfilled", 2)
    complete_activities(session, ["study", "study", "study"])
    assert (goal.progress, goal.completed_turn) == (3, 2)
    assert len([entry for entry in session.logs if entry["label"] == "人物目标"]) == 1
    assert session.state.emperor.attributes == original_attributes
    assert session.state.emperor.skills == original_skills
    assert session.state.emperor.modifiers == []
    assert (session.state.health, session.state.emperor.pressure) == (100, 0)
    assert session.world_facts == {"treasury": 500}
    assert session.state.random_state == {"seed": 1, "draws": 0}
    assert add_goal(session, count=3).status == "active"


def test_replaced_activity_and_emergency_pauses_do_not_progress_goals(tmp_path):
    session = GameSession.new_game()
    goal = add_goal(session, count=2)
    session.set_activities(["study", "study", "rest"])
    session.start_turn()
    session.inject_emergency()
    assert session.advance_turn().status == "interrupted"
    assert session.advance_turn().status == "interrupted"
    assert goal.progress == 0
    assert session.resolve_emergency(replacement_activity_id=session.state.activities[0].id).ok
    assert session.advance_turn().ok
    assert goal.progress == 1
    path = tmp_path / "progress.json"
    session.save_json(path)
    restored = GameSession.load_json(path)
    assert restored.state.emperor.objectives[0].progress == 1
    complete_activities(restored, ["study", "rest", "private"])
    fulfilled = restored.state.emperor.objectives[0]
    assert (fulfilled.progress, fulfilled.status, fulfilled.completed_turn) == (2, "fulfilled", 1)
    assert GameSession.from_dict(restored.to_dict()).to_dict() == restored.to_dict()
    assert goal.progress == 1


def test_remonstrance_and_paused_month_plan_count_only_successful_settlements(tmp_path):
    session = GameSession.new_game()
    add_goal(session, kind="ambition", activity="court", count=3)
    assert session.set_month_plan([{"activities": ["court", "study", "rest"], "commands": [
        {"command_id": "change_tax"}, {"command_id": "change_tax"},
    ]}, ["court", "rest", "study"], ["court", "rest", "study"]]).ok
    assert session.run_month_plan().status == "remonstrance"
    assert session.state.emperor.objectives[0].progress == 0
    path = tmp_path / "paused.json"
    session.save_json(path)
    restored = GameSession.load_json(path)
    assert restored.run_month_plan().status == "remonstrance"
    assert restored.state.emperor.objectives[0].progress == 0
    assert restored.resolve_remonstrance(True).ok
    assert restored.run_month_plan().ok
    goal = restored.state.emperor.objectives[0]
    assert (goal.progress, goal.status, goal.completed_turn) == (3, "fulfilled", 2)
    assert len([entry for entry in restored.logs if entry["label"] == "人物目标"]) == 1


def test_discarding_active_goals_does_not_delete_completion_records():
    session = GameSession.new_game()
    active = add_goal(session)
    assert session.discard_emperor_objective(active.id).ok
    assert session.state.emperor.objectives == []
    fulfilled = add_goal(session, count=1)
    complete_activities(session, ["study", "rest", "rest"])
    before = session.to_dict()
    assert not session.discard_emperor_objective(fulfilled.id).ok
    assert not session.discard_emperor_objective("missing").ok
    assert session.to_dict() == before


def test_old_save_defaults_missing_motives_and_preserves_legacy_traits():
    session = GameSession.new_game()
    session.state.emperor.traits = ["沉静"]
    old = session.to_dict()
    old["state"]["emperor"].pop("personality")
    old["state"]["emperor"].pop("objectives")
    before = copy.deepcopy(old)
    restored = GameSession.from_dict(old)
    assert old == before
    assert restored.state.emperor.personality == session.state.emperor.personality
    assert restored.state.emperor.objectives == []
    assert restored.state.emperor.traits == ["沉静"]
    assert GameSession.from_dict(restored.to_dict()).to_dict() == restored.to_dict()


@pytest.mark.parametrize("damage", [
    "bad_personality", "missing_goal_field", "extra_goal_field", "duplicate_id",
    "fulfilled_without_progress", "future_completion", "bad_goal_type",
])
def test_malformed_motive_save_is_rejected_without_filling_defaults(damage):
    session = GameSession.new_game()
    add_goal(session, count=1)
    complete_activities(session, ["study", "rest", "rest"])
    snapshot = session.to_dict()
    profile = snapshot["state"]["emperor"]
    objective = profile["objectives"][0]
    if damage == "bad_personality":
        profile["personality"] = {}
    elif damage == "missing_goal_field":
        objective.pop("description")
    elif damage == "extra_goal_field":
        objective["reward"] = 10
    elif damage == "duplicate_id":
        profile["objectives"].append(copy.deepcopy(objective))
    elif damage == "fulfilled_without_progress":
        objective["progress"] = 0
    elif damage == "future_completion":
        objective["completed_turn"] = snapshot["state"]["turn_index"]
    else:
        profile["objectives"] = ["study"]
    with pytest.raises(ValueError):
        GameSession.from_dict(snapshot)
