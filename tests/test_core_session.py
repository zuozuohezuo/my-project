"""Rule-boundary and interruption tests; no world economics are implemented."""

import copy
import json

import pytest

from dynasty.core import Phase, ScenarioProfile
from legacy_support import LegacyDemoConfig as DemoConfig, LegacyGameSession as GameSession


def ready_court(session: GameSession) -> None:
    assert session.set_activities(["court"]).ok
    assert session.fill_rest().ok
    assert session.start_turn().ok
    assert session.open_court().ok


def test_health_budget_shared_and_not_automatically_filled():
    session = GameSession.new_game(config=DemoConfig(initial_health=60))
    assert session.state.ap_capacity == 2
    assert session.set_activities(["court", "study", "rest"]).status == "error"
    assert session.set_activities(["court"]).ok
    assert session.advance_turn().status == "error"
    assert session.state.phase == Phase.PLANNING
    assert session.state.ap_remaining == 1
    assert session.fill_rest().ok
    assert [activity.kind for activity in session.state.activities] == ["court", "rest"]
    assert session.advance_turn().ok
    assert session.state.turn_index == 1
    assert session.state.ap_capacity == 2
    assert session.state.ap_remaining == 2
    assert session.state.activities == []


def test_input_world_and_world_facts_do_not_alias_session():
    original = {"provinces": [{"id": "a", "grain": 1200}], "treasury": 500}
    session = GameSession.new_game(original)
    original["provinces"][0]["grain"] = 0
    observed = session.world_facts
    observed["treasury"] = 0
    assert session.world_facts == {"provinces": [{"id": "a", "grain": 1200}], "treasury": 500}


def test_all_actions_preserve_world_and_health_and_only_log_effects():
    world = {"treasury": 500, "loyalty": 70, "reputation": 60,
             "provinces": [{"id": "a", "grain": 1200, "tax": 10, "morale": 50}]}
    session = GameSession.new_game(world)
    ready_court(session)
    assert session.issue_command("change_tax", {"target": "a", "rate": 8}).ok
    assert session.issue_command("change_tax", {"target": "a", "rate": 6}).status == "remonstrance"
    assert session.resolve_remonstrance(False).ok
    assert session.issue_command("build_canal", {"target": "a", "budget": None}).ok
    assert session.advance_turn().ok
    assert session.world_facts == world
    assert session.state.health == 100
    assert len(session.state.command_ledger) == 3
    assert any(effect["kind"] == "frequent_tax_change_penalty" for effect in session.state.pending_effects)
    assert all(effect["status"] == "not_simulated" for effect in session.state.pending_effects)


def test_one_court_allows_multiple_commands_but_quota_is_per_turn():
    session = GameSession.new_game()
    assert session.set_activities(["court", "court", "rest"]).ok
    assert session.open_court().ok
    for number in range(3):
        assert session.issue_command("appoint_official", {"office": f"office-{number}"}).ok
    assert session.open_court().ok
    before = session.to_dict()
    assert session.issue_command("build_canal").status == "error"
    assert session.to_dict() == before
    assert session.state.edict_debt == 0
    assert session.state.edict_available == 0


def test_emergency_only_debt_and_repayment_on_following_turn():
    session = GameSession.new_game(config=DemoConfig(edicts_per_turn=1))
    ready_court(session)
    assert session.issue_command("appoint_official").ok
    assert session.issue_command("emergency_response").status == "error"
    original_activities = copy.deepcopy(session.state.activities)
    session.inject_emergency()
    assert session.state.phase == Phase.INTERRUPTED
    assert session.resolve_emergency().ok
    assert session.state.activities == original_activities
    assert session.state.edict_debt == 1
    assert session.state.command_ledger[-1]["borrowed"] == 1
    assert session.advance_turn().ok
    assert session.state.edict_available == 0
    assert session.state.edict_debt == 0
    ready_court(session)
    assert session.issue_command("appoint_official").status == "error"
    assert session.advance_turn().ok
    assert session.state.edict_available == 1


def test_large_emergency_debt_carries_without_negative_quota():
    session = GameSession.new_game(config=DemoConfig(edicts_per_turn=1))
    ready_court(session)
    assert session.issue_command("appoint_official").ok
    for _ in range(3):
        session.inject_emergency()
        assert session.resolve_emergency().ok
    assert session.state.edict_debt == 3
    assert session.advance_turn().ok
    assert session.state.edict_available == 0
    assert session.state.edict_debt == 2
    assert session.fill_rest().ok
    assert session.advance_turn().ok
    assert session.state.edict_available == 0
    assert session.state.edict_debt == 1


def test_emergency_context_cannot_be_used_for_ordinary_decrees():
    session = GameSession.new_game()
    ready_court(session)
    event = session.inject_emergency()
    before = session.to_dict()
    assert session.issue_command("change_tax", {"rate": 1}, emergency_event_id=event.id).status == "error"
    assert session.resolve_emergency(command_id="build_canal").status == "error"
    assert session.to_dict() == before
    assert session.resolve_emergency().ok
    after = session.to_dict()
    assert session.issue_command("emergency_response", emergency_event_id=event.id).status == "error"
    assert session.resolve_emergency().status == "error"
    assert session.to_dict() == after


def test_no_court_emergency_requires_explicit_unfinished_replacement():
    session = GameSession.new_game()
    assert session.set_activities(["study", "private", "rest"]).ok
    assert session.start_turn().ok
    session.inject_emergency()
    assert session.resolve_emergency().status == "replacement_required"
    replacement = session.state.activities[1]
    assert session.resolve_emergency(replacement_activity_id="missing").status == "replacement_required"
    assert session.resolve_emergency(replacement_activity_id=replacement.id).ok
    assert replacement.status == "replaced"
    assert session.state.ap_allocated == 3
    assert session.state.ap_remaining == 0
    assert session.advance_turn().ok
    completed_ids = [effect.get("activity_id") for effect in session.state.pending_effects]
    assert replacement.id not in completed_ids


def test_accepting_remonstrance_is_free_and_does_not_reset_cooldown():
    session = GameSession.new_game()
    ready_court(session)
    assert session.issue_command("change_tax", {"target": "a", "rate": 10}).ok
    assert session.advance_turn().ok
    ready_court(session)
    prior_cooldowns = dict(session.state.cooldowns)
    prior_effects = copy.deepcopy(session.state.pending_effects)
    assert session.issue_command("change_tax", {"target": "a", "rate": 8}).status == "remonstrance"
    assert session.state.edict_available == 3
    assert session.resolve_remonstrance(True).status == "cancelled"
    assert session.state.edict_available == 3
    assert session.state.cooldowns == prior_cooldowns
    assert session.state.pending_effects == prior_effects
    assert len(session.state.command_ledger) == 1
    assert session.resolve_remonstrance(True).status == "error"


def test_insistence_commits_exactly_once_after_roundtrip():
    session = GameSession.new_game()
    ready_court(session)
    assert session.issue_command("change_tax", {"rate": 10}).ok
    assert session.issue_command("change_tax", {"rate": 8}).status == "remonstrance"
    restored = GameSession.from_dict(json.loads(json.dumps(session.to_dict())))
    assert restored.state.phase == Phase.REMONSTRANCE
    assert restored.resolve_remonstrance(False).ok
    after = restored.to_dict()
    assert restored.resolve_remonstrance(False).status == "error"
    assert restored.to_dict() == after
    assert restored.state.edict_available == 1
    assert len(restored.state.command_ledger) == 2
    penalties = [effect for effect in restored.state.pending_effects
                 if effect["kind"] == "frequent_tax_change_penalty"]
    assert len(penalties) == 1


def test_cooldown_expires_and_target_scope_is_independent():
    session = GameSession.new_game(config=DemoConfig(tax_cooldown_turns=2))
    ready_court(session)
    assert session.issue_command("change_tax", {"target": "a"}).ok
    assert session.issue_command("change_tax", {"target": "b"}).ok
    assert session.advance_turn().ok
    assert session.fill_rest().ok
    assert session.advance_turn().ok
    ready_court(session)
    assert session.issue_command("change_tax", {"target": "a"}).status == "issued"


def test_month_plan_runs_three_distinct_turns_and_preserves_delegated_parameters():
    session = GameSession.new_game()
    plans = [{"activities": ["court", "rest", "private"], "commands": [
        {"command_id": "appoint_official", "parameters": {"office": None, "candidate": None}}
    ]} for _ in range(3)]
    assert session.set_month_plan(plans).ok
    assert session.run_month_plan().status == "completed"
    assert (session.state.turn_index, session.state.month, session.state.xun) == (3, 2, 1)
    assert [record["turn"] for record in session.state.command_ledger] == [0, 1, 2]
    assert all(record["parameters"] == {"office": None, "candidate": None}
               for record in session.state.command_ledger)
    assert len([entry for entry in session.logs if entry["label"] == "旬结算"]) == 3


def test_month_plan_pauses_in_second_turn_and_resumes_without_reissuing(tmp_path):
    session = GameSession.new_game({"treasury": 100})
    assert session.set_month_plan([{"activities": ["court", "rest", "study"], "commands": [
        {"command_id": "appoint_official", "parameters": {"turn_label": index}}
    ]} for index in range(3)]).ok
    session.inject_emergency(trigger_turn=1)
    assert session.run_month_plan().status == "interrupted"
    assert session.state.turn_index == 1
    assert len(session.state.command_ledger) == 1
    assert [plan.status for plan in session.state.month_plan] == ["completed", "executing", "pending"]
    path = tmp_path / "save.json"
    session.save_json(path)
    restored = GameSession.load_json(path)
    assert restored.to_dict() == session.to_dict()
    assert restored.resolve_emergency().ok
    assert restored.run_month_plan().ok
    assert restored.state.turn_index == 3
    appointments = [record for record in restored.state.command_ledger
                    if record["command_id"] == "appoint_official"]
    assert [record["turn"] for record in appointments] == [0, 1, 2]
    assert restored.world_facts == {"treasury": 100}
    assert restored.state.random_state == {"seed": 1, "draws": 0}


@pytest.mark.parametrize("accept", [True, False])
def test_month_plan_remonstrance_resume_does_not_reask_or_duplicate(accept):
    session = GameSession.new_game()
    plans = [{"activities": ["court", "rest", "study"], "commands": [
        {"command_id": "change_tax", "parameters": {"rate": rate}}
    ]} for rate in [10, 8, 6]]
    assert session.set_month_plan(plans).ok
    assert session.run_month_plan().status == "remonstrance"
    assert session.state.turn_index == 1
    restored = GameSession.from_dict(session.to_dict())
    assert restored.resolve_remonstrance(accept).ok
    assert restored.run_month_plan().status == "remonstrance"
    assert restored.state.turn_index == 2
    assert restored.resolve_remonstrance(True).ok
    assert restored.run_month_plan().ok
    assert len(restored.state.command_ledger) == (1 if accept else 2)
    assert restored.state.turn_index == 3


def test_year_rollover_and_save_version_rejection():
    session = GameSession.new_game(config=DemoConfig(initial_year=1368, initial_month=12, initial_xun=3))
    assert session.fill_rest().ok
    assert session.advance_turn().ok
    assert (session.state.year, session.state.month, session.state.xun) == (1369, 1, 1)
    snapshot = session.to_dict()
    snapshot["save_version"] = 999
    with pytest.raises(ValueError, match="存档版本"):
        GameSession.from_dict(snapshot)


def test_queued_emergency_during_remonstrance_waits_for_decision():
    session = GameSession.new_game()
    ready_court(session)
    assert session.issue_command("change_tax").ok
    assert session.issue_command("change_tax").status == "remonstrance"
    session.inject_emergency()
    assert session.state.phase == Phase.REMONSTRANCE
    assert session.resolve_remonstrance(True).ok
    assert session.advance_turn().status == "interrupted"
    assert session.state.turn_index == 0


def test_quota_shortage_in_plan_pauses_until_explicit_cancellation():
    session = GameSession.new_game(config=DemoConfig(edicts_per_turn=1))
    assert session.set_month_plan([{"activities": ["court", "rest", "study"], "commands": [
        {"command_id": "appoint_official"}, {"command_id": "build_canal"}
    ]}, ["rest", "study", "private"], ["rest", "rest", "rest"]]).ok
    assert session.run_month_plan().status == "error"
    assert session.state.turn_index == 0
    assert len(session.state.command_ledger) == 1
    assert session.state.month_plan[0].commands[1].status == "pending"
    assert session.cancel_planned_commands().ok
    assert session.run_month_plan().ok
    assert session.state.turn_index == 3
    assert len(session.state.command_ledger) == 1


def test_current_activity_edits_and_explicit_rest_stay_in_sync_with_month_plan():
    session = GameSession.new_game()
    assert session.set_month_plan([["court", "rest", "study"] for _ in range(3)]).ok
    assert session.set_activities(["private"]).ok
    assert session.state.month_plan[0].activities == ["private"]
    assert session.fill_rest().ok
    assert session.state.month_plan[0].activities == ["private", "rest", "rest"]
    assert session.state.month_plan[1].activities == ["court", "rest", "study"]
    assert session.run_month_plan().ok


def test_cancelling_planned_confirmation_releases_phase_without_spending():
    session = GameSession.new_game()
    assert session.set_month_plan([{"activities": ["court", "rest", "study"], "commands": [
        {"command_id": "change_tax"}, {"command_id": "change_tax"}, {"command_id": "build_canal"}
    ]}, ["rest", "study", "private"], ["rest", "rest", "rest"]]).ok
    assert session.run_month_plan().status == "remonstrance"
    assert session.cancel_planned_commands().ok
    assert session.state.phase == Phase.EXECUTING
    assert session.state.pending_command is None
    assert session.state.edict_available == 2
    assert session.run_month_plan().ok
    assert len(session.state.command_ledger) == 1


def test_cancelling_future_orders_during_emergency_does_not_dismiss_event():
    session = GameSession.new_game()
    assert session.set_month_plan([{"activities": ["court", "rest", "study"], "commands": [
        {"command_id": "appoint_official"}
    ]} for _ in range(3)]).ok
    session.inject_emergency()
    assert session.run_month_plan().status == "interrupted"
    event_id = session.active_emergency.id
    assert session.cancel_planned_commands().ok
    assert session.active_emergency.id == event_id
    assert session.state.phase == Phase.INTERRUPTED
    assert session.advance_turn().status == "interrupted"
    assert session.resolve_emergency().ok
    assert session.run_month_plan().ok
    appointments = [record for record in session.state.command_ledger
                    if record["command_id"] == "appoint_official"]
    assert [record["turn"] for record in appointments] == [1, 2]


@pytest.mark.parametrize("corruption", ["partial_activity", "negative_debt", "date", "active_event", "pending_command"])
def test_loading_rejects_inconsistent_execution_state(corruption):
    session = GameSession.new_game()
    ready_court(session)
    snapshot = session.to_dict()
    if corruption == "partial_activity":
        snapshot["state"]["activities"].pop()
    elif corruption == "negative_debt":
        snapshot["state"]["edict_debt"] = -1
    elif corruption == "date":
        snapshot["state"]["xun"] = 2
    elif corruption == "active_event":
        snapshot["state"]["phase"] = "interrupted"
        snapshot["state"]["active_emergency_id"] = "missing"
    else:
        snapshot["state"]["phase"] = "remonstrance"
        snapshot["state"]["pending_command"] = {
            "command_id": "missing", "parameters": {}, "cooldown_key": "missing"
        }
    with pytest.raises(ValueError):
        GameSession.from_dict(snapshot)


@pytest.mark.parametrize("collection,field,value", [
    ("logs", "date", None),
    ("logs", "label", 42),
    ("logs", "message", ["wrong type"]),
    ("logs", "turn", "0"),
    ("command_ledger", "label", None),
    ("command_ledger", "parameters", []),
    ("command_ledger", "turn", "0"),
    ("command_ledger", "cost", -1),
    ("command_ledger", "borrowed", 2),
])
def test_damaged_display_and_accounting_records_are_rejected(collection, field, value):
    session = GameSession.new_game()
    ready_court(session)
    assert session.issue_command("appoint_official").ok
    snapshot = session.to_dict()
    if value is None:
        del snapshot["state"][collection][0][field]
    else:
        snapshot["state"][collection][0][field] = value
    with pytest.raises(ValueError, match="存档"):
        GameSession.from_dict(snapshot)


def test_custom_opening_profile_persists_and_crosses_year_without_changing_history(tmp_path):
    history = {"scenario": "ming_1500", "year": 1500, "simulation_enabled": False}
    profile = ScenarioProfile("自定·承平开局", "朱明远", "承平", 1520)
    session = GameSession.new_game(
        history, DemoConfig(initial_year=1524, initial_month=12, initial_xun=3), profile=profile,
    )
    assert session.state.era_date_label == "承平5年12月下旬"
    assert session.state.date_label == "1524年12月下旬"
    assert session.fill_rest().ok
    assert session.advance_turn().ok
    assert session.state.era_date_label == "承平6年1月上旬"
    path = tmp_path / "custom-opening.json"
    session.save_json(path)
    restored = GameSession.load_json(path)
    assert restored.state.scenario_profile == profile
    assert restored.state.era_year == 6
    assert restored.state.era_date_label == "承平6年1月上旬"
    assert restored.to_dict() == session.to_dict()
    assert restored.world_facts == history
    assert restored.world_facts["year"] != restored.state.year


@pytest.mark.parametrize("year,expected_name,expected_label", [
    (1500, "明朝·弘治十三年", "弘治13年1月中旬"),
    (1, "旧版演示剧本", "元初元年1月中旬"),
    (1368, "旧版演示剧本", "元初元年1月中旬"),
])
def test_legacy_save_without_opening_profile_uses_compatible_defaults(year, expected_name, expected_label):
    session = GameSession.new_game(config=DemoConfig(initial_year=year))
    assert session.fill_rest().ok
    assert session.advance_turn().ok
    legacy = session.to_dict()
    del legacy["state"]["scenario_profile"]
    restored = GameSession.from_dict(legacy)
    assert restored.state.scenario_profile.scenario_name == expected_name
    assert restored.state.era_date_label == expected_label
    assert restored.state.turn_index == 1
    upgraded = restored.to_dict()
    assert upgraded["save_version"] == 1
    assert GameSession.from_dict(upgraded).to_dict() == upgraded


@pytest.mark.parametrize("field,value", [
    ("scenario_name", "  "),
    ("scenario_name", "剧" * 81),
    ("emperor_name", None),
    ("emperor_name", "名" * 41),
    ("era_name", 123),
    ("era_name", "号" * 25),
    ("era_name", "承平\n元始"),
    ("era_start_year", "1488"),
    ("era_start_year", True),
    ("era_start_year", 0),
    ("era_start_year", 1501),
])
def test_new_game_and_saved_profile_reject_invalid_identity_fields(field, value):
    session = GameSession.new_game(config=DemoConfig(initial_year=1500))
    snapshot = session.to_dict()
    snapshot["state"]["scenario_profile"][field] = value
    with pytest.raises(ValueError):
        GameSession.from_dict(snapshot)
    with pytest.raises(ValueError):
        GameSession.new_game(
            config=DemoConfig(initial_year=1500),
            profile=ScenarioProfile(**snapshot["state"]["scenario_profile"]),
        )


@pytest.mark.parametrize("profile_data", [None, [], "弘治", {"era_name": "弘治"}])
def test_present_but_malformed_saved_profile_is_not_silently_replaced(profile_data):
    snapshot = GameSession.new_game().to_dict()
    snapshot["state"]["scenario_profile"] = profile_data
    with pytest.raises(ValueError, match="档案"):
        GameSession.from_dict(snapshot)


def test_new_game_requires_profile_object_and_checks_era_against_opening_year():
    with pytest.raises(ValueError, match="ScenarioProfile"):
        GameSession.new_game(profile={"scenario_name": "剧本"})
    session = GameSession.new_game(
        config=DemoConfig(initial_year=1500, initial_month=12, initial_xun=3),
    )
    session.fill_rest()
    session.advance_turn()
    snapshot = session.to_dict()
    snapshot["state"]["scenario_profile"]["era_start_year"] = 1501
    with pytest.raises(ValueError, match="开局年份"):
        GameSession.from_dict(snapshot)


@pytest.mark.parametrize("year", [True, "1500", 1500.5, 0, 10000])
def test_opening_year_rejects_wrong_types_and_out_of_range_values(year):
    with pytest.raises(ValueError, match="公元年份"):
        GameSession.new_game(config=DemoConfig(initial_year=year))
