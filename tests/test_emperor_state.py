"""Attribute editing and persistence must remain independent of simulation."""

import copy
from dataclasses import FrozenInstanceError

import pytest

from dynasty.core import GameState, ScenarioProfile
from legacy_support import LegacyDemoConfig as DemoConfig, LegacyGameSession as GameSession
from dynasty.core.emperor import (
    ATTRIBUTE_DEFINITIONS, ATTRIBUTE_GROUPS, SKILL_DEFINITIONS, EmperorProfile,
)


def test_new_emperor_has_all_agreed_abilities_and_independent_defaults():
    first = GameSession.new_game()
    second = GameSession.new_game()
    assert [label for _, label in ATTRIBUTE_GROUPS] == ["智力类", "身体类", "意志类"]
    assert [item.label for item in ATTRIBUTE_DEFINITIONS] == [
        "逻辑", "情商", "记忆力", "洞察力", "创造力", "力量", "体质", "敏捷", "感知", "颜值",
        "自律能力", "情绪抗性", "胆量",
    ]
    assert [item.label for item in SKILL_DEFINITIONS] == [
        "政务处理", "军事策略", "识人能力", "话术", "书法", "学识",
    ]
    assert set(first.state.emperor.attributes.values()) == {50}
    assert set(first.state.emperor.skills.values()) == {0}
    first.state.emperor.attributes["logic"] = 77
    first.state.emperor.skills["rhetoric"] = 35
    first.state.emperor.traits.append("沉静")
    assert second.state.emperor == EmperorProfile()
    with pytest.raises(FrozenInstanceError):
        ATTRIBUTE_DEFINITIONS[0].label = "改名"


def test_manual_edit_only_changes_ability_values_and_copies_inputs():
    profile = ScenarioProfile("自定义剧本", "朱明远", "承平", 1510)
    session = GameSession.new_game(
        {"treasury": 100, "facts": {"year": 1500}},
        DemoConfig(initial_year=1512, initial_health=45), profile,
    )
    session.state.emperor.traits = ["沉静"]
    session.set_activities(["study", "exercise"])
    session.start_turn()
    before = session.to_dict()
    attributes = dict(session.state.emperor.attributes, constitution=900, insight=1234)
    skills = dict(session.state.emperor.skills, people_reading=321, scholarship=10**30)
    assert session.update_emperor_profile(attributes, skills).ok
    expected = copy.deepcopy(before)
    expected["state"]["emperor"]["attributes"] = attributes.copy()
    expected["state"]["emperor"]["skills"] = skills.copy()
    assert session.to_dict() == expected
    attributes["logic"] = 1
    skills["scholarship"] = 1
    assert session.state.emperor.attributes["logic"] == 50
    assert session.state.emperor.skills["scholarship"] == 10**30


@pytest.mark.parametrize("invalid", [-1, True, False, 1.0, float("nan"), float("inf"), "99", None])
@pytest.mark.parametrize("collection,key", [("attributes", "logic"), ("skills", "scholarship")])
def test_invalid_value_rejects_entire_edit_atomically(collection, key, invalid):
    session = GameSession.new_game()
    before = session.to_dict()
    proposed = copy.deepcopy(before["state"]["emperor"])
    proposed["attributes"]["insight"] = 101
    proposed["skills"]["calligraphy"] = 1000
    proposed[collection][key] = invalid
    result = session.update_emperor_profile(proposed["attributes"], proposed["skills"])
    assert not result.ok
    assert session.to_dict() == before


@pytest.mark.parametrize("collection", ["attributes", "skills"])
@pytest.mark.parametrize("damage", ["missing", "unknown", "empty", "list", "none"])
def test_invalid_ability_collections_reject_entire_edit(collection, damage):
    session = GameSession.new_game()
    before = session.to_dict()
    proposed = copy.deepcopy(before["state"]["emperor"])
    if damage == "missing":
        proposed[collection].pop(next(iter(proposed[collection])))
    elif damage == "unknown":
        proposed[collection]["unknown"] = 12
    elif damage == "empty":
        proposed[collection] = {}
    elif damage == "list":
        proposed[collection] = []
    else:
        proposed[collection] = None
    assert not session.update_emperor_profile(proposed["attributes"], proposed["skills"]).ok
    assert session.to_dict() == before


def test_large_and_zero_values_roundtrip_without_clamping(tmp_path):
    session = GameSession.new_game(config=DemoConfig(initial_year=1500))
    attributes = dict(session.state.emperor.attributes, logic=0, appearance=9999999999)
    skills = dict(session.state.emperor.skills, people_reading=10**30, rhetoric=0)
    assert session.update_emperor_profile(attributes, skills).ok
    path = tmp_path / "emperor.json"
    session.save_json(path)
    restored = GameSession.load_json(path)
    assert restored.to_dict() == session.to_dict()
    restored.state.emperor.skills["people_reading"] = 1
    assert session.state.emperor.skills["people_reading"] == 10**30


def test_legacy_version_one_save_fills_only_absent_emperor_profile(tmp_path):
    session = GameSession.new_game(
        {"scenario": "ming_1500", "treasury": 25},
        DemoConfig(initial_year=1500, initial_health=45),
    )
    session.fill_rest()
    session.advance_turn()
    legacy = session.to_dict()
    del legacy["state"]["emperor"]
    original_legacy = copy.deepcopy(legacy)
    restored = GameSession.from_dict(legacy)
    assert legacy == original_legacy
    assert restored.state.emperor == EmperorProfile()
    upgraded = restored.to_dict()
    assert upgraded.pop("save_version") == 1
    upgraded["state"].pop("emperor")
    assert upgraded == {key: value for key, value in legacy.items() if key != "save_version"}
    path = tmp_path / "upgraded.json"
    restored.save_json(path)
    assert GameSession.load_json(path).to_dict() == restored.to_dict()


@pytest.mark.parametrize("invalid", [None, [], "皇帝", {}, {"attributes": {}, "skills": {}}])
def test_present_but_malformed_saved_profile_is_rejected(invalid):
    snapshot = GameSession.new_game().to_dict()
    snapshot["state"]["emperor"] = invalid
    with pytest.raises(ValueError, match="存档皇帝"):
        GameSession.from_dict(snapshot)


@pytest.mark.parametrize("damage", [
    "missing_attribute", "unknown_skill", "negative", "boolean", "float", "string",
    "traits_string", "traits_item", "traits_empty", "traits_control", "extra_field",
])
def test_saved_profile_rejects_corruption_without_defaulting(damage):
    snapshot = GameSession.new_game().to_dict()
    emperor = snapshot["state"]["emperor"]
    if damage == "missing_attribute":
        emperor["attributes"].pop("logic")
    elif damage == "unknown_skill":
        emperor["skills"]["unknown"] = 10
    elif damage == "negative":
        emperor["skills"]["calligraphy"] = -1
    elif damage == "boolean":
        emperor["attributes"]["strength"] = True
    elif damage == "float":
        emperor["attributes"]["strength"] = 5.0
    elif damage == "string":
        emperor["skills"]["rhetoric"] = "50"
    elif damage == "traits_string":
        emperor["traits"] = "沉静"
    elif damage == "traits_item":
        emperor["traits"] = [10]
    elif damage == "traits_empty":
        emperor["traits"] = ["  "]
    elif damage == "traits_control":
        emperor["traits"] = ["沉\n静"]
    else:
        emperor["unknown"] = 1
    with pytest.raises(ValueError, match="存档皇帝"):
        GameSession.from_dict(snapshot)


def test_activities_do_not_implicitly_grow_skills_or_run_event_checks():
    session = GameSession.new_game({"treasury": 300})
    before = copy.deepcopy(session.state.emperor)
    session.set_activities(["study", "exercise", "private"])
    assert session.advance_turn().ok
    assert session.state.emperor == before
    assert session.world_facts == {"treasury": 300}
    assert session.state.random_state == {"seed": 1, "draws": 0}


def test_session_rejects_invalid_direct_emperor_state():
    with pytest.raises(ValueError, match="EmperorProfile"):
        GameSession(GameState(emperor={}), DemoConfig(initial_year=1500))
    invalid = EmperorProfile()
    invalid.skills["scholarship"] = False
    with pytest.raises(ValueError, match="非负整数"):
        GameSession(GameState(emperor=invalid), DemoConfig(initial_year=1500))
