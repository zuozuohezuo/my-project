"""Health edits and timed effects must preserve plans, base values and save validity."""

import copy
from dataclasses import asdict, replace

import pytest

from dynasty.core import Phase
from legacy_support import LegacyDemoConfig as DemoConfig, LegacyGameSession as GameSession
from dynasty.core.emperor import BodyCondition, EmperorModifier, EmperorProfile


def effect(**changes):
    return replace(EmperorModifier("专注", "attribute", "insight", 10), **changes)


def active_session(phase):
    session = GameSession.new_game()
    assert session.set_activities(["court", "study", "rest"]).ok
    assert session.start_turn().ok
    if phase == Phase.INTERRUPTED:
        session.inject_emergency()
    elif phase == Phase.REMONSTRANCE:
        assert session.open_court().ok
        assert session.issue_command("change_tax", {"rate": 10}).ok
        assert session.issue_command("change_tax", {"rate": 8}).status == "remonstrance"
    assert session.state.phase == phase
    return session


def test_new_health_collections_are_independent_and_ability_edits_preserve_them():
    first, second = GameSession.new_game(), GameSession.new_game()
    conditions = [BodyCondition("左眼", "失明", "disability")]
    modifiers = [effect(duration="short_term", remaining_turns=3)]
    assert first.update_emperor_health(91, 37, conditions).ok
    assert first.update_emperor_modifiers(modifiers).ok
    first.state.emperor.traits.append("沉静")
    original = copy.deepcopy(first.state.emperor)
    assert first.update_emperor_profile(
        dict(original.attributes, insight=777), dict(original.skills, people_reading=200)
    ).ok
    assert first.state.emperor.pressure == 37
    assert first.state.emperor.body_conditions == original.body_conditions
    assert first.state.emperor.modifiers == original.modifiers
    assert first.state.emperor.traits == ["沉静"]
    assert first.state.health == 91
    assert second.state.emperor == EmperorProfile()
    conditions[0].name = "已被调用者更改"
    modifiers[0].amount = -999
    conditions.clear()
    modifiers.clear()
    assert first.state.emperor.body_conditions[0].name == "失明"
    assert first.state.emperor.attribute_bonus("insight") == 10


def test_stacked_modifiers_apply_to_their_own_targets_without_changing_base_values():
    session = GameSession.new_game({"treasury": 500})
    before = session.to_dict()
    modifiers = [
        effect(amount=25), effect(name="疲惫", amount=-7),
        effect(name="强壮", target="strength", amount=80),
        effect(name="善辩", target_type="skill_effect", target="rhetoric", amount=35),
        effect(name="嘶哑", target_type="skill_effect", target="rhetoric", amount=-10),
    ]
    assert session.update_emperor_modifiers(modifiers).ok
    profile = session.state.emperor
    assert profile.attribute_bonus("insight") == 18
    assert profile.effective_attribute("insight") == 68
    assert profile.effective_attribute("strength") == 130
    assert profile.effective_attribute("logic") == 50
    assert profile.skill_effect_bonus("rhetoric") == 25
    assert profile.skill_effect_percent("rhetoric") == 125
    assert profile.skill_effect_percent("people_reading") == 100
    after = session.to_dict()
    after["state"]["emperor"]["modifiers"] = []
    assert after == before


@pytest.mark.parametrize("amount,attribute_value,skill_percent", [
    (-1000, 0, 0), (-100, 0, 0), (0, 50, 100), (10**30, 10**30 + 50, 10**30 + 100),
])
def test_modifier_results_have_a_zero_floor_and_no_upper_cap(amount, attribute_value, skill_percent):
    session = GameSession.new_game()
    assert session.update_emperor_modifiers([
        effect(amount=amount),
        effect(target_type="skill_effect", target="people_reading", amount=amount),
    ]).ok
    assert session.state.emperor.effective_attribute("insight") == attribute_value
    assert session.state.emperor.skill_effect_percent("people_reading") == skill_percent
    assert session.state.emperor.attributes["insight"] == 50
    assert session.state.emperor.skills["people_reading"] == 0


@pytest.mark.parametrize("changes", [
    {"amount": True}, {"amount": False}, {"amount": 2.0}, {"amount": "3"}, {"amount": None},
    {"target_type": "skill"}, {"target_type": []}, {"target": "unknown"}, {"target": []},
    {"target": "rhetoric"}, {"target_type": "skill_effect", "target": "insight"},
    {"name": " "}, {"name": "前\n后"}, {"source": None}, {"source": "前\x7f后"},
    {"duration": "unknown"}, {"duration": []}, {"remaining_turns": 1},
    {"duration": "short_term", "remaining_turns": None},
    {"duration": "short_term", "remaining_turns": 0},
    {"duration": "short_term", "remaining_turns": -1},
    {"duration": "short_term", "remaining_turns": True},
    {"duration": "short_term", "remaining_turns": 1.0},
])
def test_invalid_modifier_rejects_the_whole_edit_atomically(changes):
    session = GameSession.new_game()
    assert session.update_emperor_modifiers([effect(amount=8)]).ok
    before = session.to_dict()
    invalid = effect(**changes)
    with pytest.raises(ValueError):
        invalid.validate()
    assert not session.update_emperor_modifiers([effect(amount=90), invalid]).ok
    assert session.to_dict() == before


@pytest.mark.parametrize("invalid", [None, {}, (), [None], [asdict(effect())]])
def test_modifier_api_requires_a_list_of_typed_records(invalid):
    session = GameSession.new_game()
    before = session.to_dict()
    assert not session.update_emperor_modifiers(invalid).ok
    assert session.to_dict() == before


@pytest.mark.parametrize("value", [-1, 101, True, False, 1.0, "50", None])
@pytest.mark.parametrize("meter", ["health", "pressure"])
def test_health_and_pressure_reject_invalid_values_atomically(meter, value):
    session = GameSession.new_game()
    before = session.to_dict()
    proposed = {"health": 95, "pressure": 30, "body_conditions": [BodyCondition("肺", "咳疾")]}
    proposed[meter] = value
    assert not session.update_emperor_health(**proposed).ok
    assert session.to_dict() == before


@pytest.mark.parametrize("health", [True, 101, "50"])
@pytest.mark.parametrize("entry_point", ["new_game", "saved_state"])
def test_invalid_overall_health_is_rejected_by_creation_and_save_loading(health, entry_point):
    with pytest.raises(ValueError):
        if entry_point == "new_game":
            GameSession.new_game(config=DemoConfig(initial_health=health))
        else:
            snapshot = GameSession.new_game().to_dict()
            snapshot["state"]["health"] = health
            GameSession.from_dict(snapshot)


@pytest.mark.parametrize("health,pressure,capacity", [(0, 100, 1), (100, 0, 3)])
def test_health_and_pressure_accept_their_inclusive_endpoints(health, pressure, capacity):
    session = GameSession.new_game()
    assert session.update_emperor_health(health, pressure, []).ok
    assert (session.state.health, session.state.emperor.pressure) == (health, pressure)
    assert session.state.ap_capacity == capacity
    assert GameSession.from_dict(session.to_dict()).to_dict() == session.to_dict()


@pytest.mark.parametrize("conditions", [
    None, {}, (), [None], [{"part": "肺", "name": "咳疾", "kind": "disease"}],
    [BodyCondition("", "咳疾")], [BodyCondition("肺", " ")],
    [BodyCondition("左\n眼", "失明")], [BodyCondition("肺", "咳疾", "unknown")],
])
def test_invalid_body_conditions_do_not_partially_change_health_or_pressure(conditions):
    session = GameSession.new_game()
    before = session.to_dict()
    assert not session.update_emperor_health(90, 45, conditions).ok
    assert session.to_dict() == before


@pytest.mark.parametrize("initial_health,new_health,capacity", [(100, 45, 2), (45, 100, 3)])
def test_planning_health_edit_updates_budget_and_preserves_existing_activities(
    initial_health, new_health, capacity
):
    session = GameSession.new_game(config=DemoConfig(initial_health=initial_health))
    assert session.set_activities(["study"]).ok
    activities = copy.deepcopy(session.state.activities)
    assert session.update_emperor_health(new_health, 20, [BodyCondition("右手", "扭伤", "injury")]).ok
    assert session.state.ap_capacity == capacity
    assert session.state.ap_remaining == capacity - 1
    assert session.state.activities == activities
    assert GameSession.from_dict(session.to_dict()).to_dict() == session.to_dict()


def test_health_edit_cannot_remove_already_allocated_action_points():
    session = GameSession.new_game()
    assert session.fill_rest().ok
    before = session.to_dict()
    assert not session.update_emperor_health(45, 99, [BodyCondition("肺", "咳疾")]).ok
    assert session.to_dict() == before


@pytest.mark.parametrize("phase", [Phase.EXECUTING, Phase.INTERRUPTED, Phase.REMONSTRANCE])
def test_active_turn_blocks_capacity_changes_but_allows_health_changes_within_budget(phase):
    session = active_session(phase)
    before = session.to_dict()
    assert not session.update_emperor_health(45, 99, [BodyCondition("肺", "咳疾")]).ok
    assert session.to_dict() == before
    assert session.update_emperor_health(90, 40, [BodyCondition("肺", "咳疾")]).ok
    assert session.state.phase == phase
    assert session.state.ap_capacity == 3
    assert session.state.activities == GameSession.from_dict(before).state.activities
    assert session.state.health == 90
    assert session.state.emperor.pressure == 40
    assert GameSession.from_dict(session.to_dict()).to_dict() == session.to_dict()


def test_unfinished_month_plan_blocks_capacity_change_until_all_three_turns_finish():
    session = GameSession.new_game(config=DemoConfig(initial_health=45))
    assert session.set_month_plan([["study", "rest"] for _ in range(3)]).ok
    for completed in range(3):
        assert session.state.turn_index == completed
        assert session.state.phase == Phase.PLANNING
        before = session.to_dict()
        assert not session.update_emperor_health(100, 99, []).ok
        assert session.to_dict() == before
        assert session.update_emperor_health(60, completed, []).ok
        assert session.advance_turn().ok
    assert session.update_emperor_health(100, 0, []).ok
    assert session.state.ap_capacity == 3


def test_new_state_roundtrips_and_reading_does_not_consume_or_alias_timed_effects(tmp_path):
    session = GameSession.new_game()
    assert session.update_emperor_health(90, 66, [BodyCondition("左眼", "失明", "disability")]).ok
    assert session.update_emperor_modifiers([
        effect(source="读书", duration="short_term", remaining_turns=2),
        effect(name="口疾", target_type="skill_effect", target="rhetoric", amount=-35),
    ]).ok
    path = tmp_path / "conditions.json"
    session.save_json(path)
    restored = GameSession.load_json(path)
    assert restored.to_dict() == session.to_dict()
    snapshot = restored.to_dict()
    snapshot["state"]["emperor"]["modifiers"][0]["remaining_turns"] = 77
    snapshot["state"]["emperor"]["body_conditions"][0]["name"] = "改名"
    assert restored.state.emperor.modifiers[0].remaining_turns == 2
    copied = GameSession.from_dict(snapshot)
    snapshot["state"]["emperor"]["modifiers"][0]["amount"] = 999
    assert copied.state.emperor.modifiers[0].amount == 10
    restored.state.emperor.body_conditions[0].name = "另一档案"
    restored.state.emperor.modifiers[0].remaining_turns = 1
    assert session.state.emperor.body_conditions[0].name == "失明"
    assert session.state.emperor.modifiers[0].remaining_turns == 2


@pytest.mark.parametrize("absent", [
    ("pressure",), ("body_conditions",), ("modifiers",),
    ("pressure", "body_conditions", "modifiers"),
])
def test_older_emperor_save_defaults_only_missing_new_fields(absent):
    session = GameSession.new_game()
    assert session.update_emperor_health(90, 44, [BodyCondition("肺", "咳疾")]).ok
    assert session.update_emperor_modifiers([effect()]).ok
    legacy = session.to_dict()
    for key in absent:
        legacy["state"]["emperor"].pop(key)
    before = copy.deepcopy(legacy)
    restored = GameSession.from_dict(legacy)
    assert legacy == before
    expected = session.to_dict()
    for key in absent:
        expected["state"]["emperor"][key] = 0 if key == "pressure" else []
    assert restored.to_dict() == expected


@pytest.mark.parametrize("field", ["attributes", "skills", "traits"])
def test_legacy_migration_still_requires_original_profile_fields(field):
    snapshot = GameSession.new_game().to_dict()
    snapshot["state"]["emperor"].pop(field)
    with pytest.raises(ValueError):
        GameSession.from_dict(snapshot)


@pytest.mark.parametrize("collection,record", [
    ("body_conditions", BodyCondition("肺", "咳疾")), ("modifiers", effect()),
])
@pytest.mark.parametrize("damage", ["missing", "unknown", "wrong_type"])
def test_nested_saved_records_reject_missing_extra_or_untyped_fields(collection, record, damage):
    snapshot = GameSession.new_game().to_dict()
    serialized = asdict(record)
    if damage == "missing":
        serialized.pop("kind" if collection == "body_conditions" else "source")
    elif damage == "unknown":
        serialized["unknown"] = 1
    else:
        serialized = None
    snapshot["state"]["emperor"][collection] = [serialized]
    with pytest.raises(ValueError):
        GameSession.from_dict(snapshot)


@pytest.mark.parametrize("field,invalid", [
    ("pressure", True), ("pressure", -1), ("pressure", 101),
    ("body_conditions", None), ("modifiers", {}), ("unknown", 1),
])
def test_saved_profile_does_not_silently_default_invalid_new_data(field, invalid):
    snapshot = GameSession.new_game().to_dict()
    snapshot["state"]["emperor"][field] = invalid
    with pytest.raises(ValueError):
        GameSession.from_dict(snapshot)


def test_short_effects_expire_only_on_completed_turns_and_leave_long_term_records():
    session = GameSession.new_game()
    conditions = [BodyCondition("右手", "扭伤", "injury")]
    assert session.update_emperor_health(90, 30, conditions).ok
    assert session.update_emperor_modifiers([
        effect(name="一旬", duration="short_term", remaining_turns=1),
        effect(name="两旬", duration="short_term", remaining_turns=2),
        effect(name="长期", amount=-4),
    ]).ok
    initial = copy.deepcopy(session.state.emperor.modifiers)
    assert not session.advance_turn().ok
    assert session.state.emperor.modifiers == initial
    assert session.set_activities(["court", "study", "rest"]).ok
    assert session.start_turn().ok
    assert session.state.emperor.modifiers == initial
    session.inject_emergency()
    assert session.advance_turn().status == "interrupted"
    assert session.advance_turn().status == "interrupted"
    assert session.state.emperor.modifiers == initial
    assert session.resolve_emergency().ok
    assert session.advance_turn().ok
    assert [(item.name, item.remaining_turns) for item in session.state.emperor.modifiers] == [
        ("两旬", 1), ("长期", None),
    ]
    assert session.fill_rest().ok
    assert session.advance_turn().ok
    assert [(item.name, item.remaining_turns) for item in session.state.emperor.modifiers] == [
        ("长期", None),
    ]
    assert session.state.emperor.effective_attribute("insight") == 46
    assert session.state.emperor.body_conditions == conditions
    assert (session.state.health, session.state.emperor.pressure) == (90, 30)


def test_paused_month_plan_and_reload_do_not_double_consume_short_effects(tmp_path):
    session = GameSession.new_game()
    assert session.update_emperor_modifiers([
        effect(duration="short_term", remaining_turns=3), effect(name="长期", amount=5),
    ]).ok
    assert session.set_month_plan([["court", "study", "rest"] for _ in range(3)]).ok
    session.inject_emergency(trigger_turn=1)
    assert session.run_month_plan().status == "interrupted"
    assert session.state.turn_index == 1
    assert session.state.emperor.modifiers[0].remaining_turns == 2
    path = tmp_path / "paused.json"
    session.save_json(path)
    restored = GameSession.load_json(path)
    assert restored.run_month_plan().status == "interrupted"
    assert restored.state.emperor.modifiers[0].remaining_turns == 2
    assert restored.resolve_emergency().ok
    assert restored.run_month_plan().status == "completed"
    assert restored.state.turn_index == 3
    assert [(item.name, item.remaining_turns) for item in restored.state.emperor.modifiers] == [
        ("长期", None),
    ]


def test_remonstrance_pause_does_not_consume_a_short_effect():
    session = active_session(Phase.REMONSTRANCE)
    assert session.update_emperor_modifiers([effect(duration="short_term", remaining_turns=1)]).ok
    assert session.advance_turn().status == "remonstrance"
    assert session.state.emperor.modifiers[0].remaining_turns == 1
    assert session.resolve_remonstrance(True).ok
    assert session.advance_turn().ok
    assert session.state.emperor.modifiers == []
