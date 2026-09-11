"""Population parameter edits and natural change use the same saved turn state."""

import copy
from pathlib import Path

import pytest

from dynasty.content import create_county_demo
from dynasty.core import GameSession


def occupation_counts(session):
    return {row["id"]: row["population"] for row in session.economy_view["occupation_groups"]}


def test_population_edits_reclassify_income_without_paying_money_or_changing_occupation():
    session = create_county_demo()
    independent = create_county_demo()
    before_independent = independent.to_dict()
    populations = occupation_counts(session)
    before_pools = copy.deepcopy(session.state.economy["pools"])
    source = next(row for row in session.state.economy["county"]["population"]["cohorts"]
                  if row["count"] > 0 and row["wealth"] == "poor")
    wealthy_before = next(row["population"] for row in session.economy_view["wealth_groups"]
                          if row["id"] == "wealthy")
    source_count = source["count"]
    assert session.set_demo_population_income(source["id"], 10).ok
    assert occupation_counts(session) == populations
    assert next(row["population"] for row in session.economy_view["wealth_groups"]
                if row["id"] == "wealthy") == wealthy_before + source_count
    assert session.set_demo_population_parameters(.4, .03, .02, 100).ok
    assert next(row["population"] for row in session.economy_view["wealth_groups"]
                if row["id"] == "poor") == 1000
    assert session.economy_view["population"]["base_labor"] == 400
    assert occupation_counts(session) == populations
    assert session.state.economy["pools"] == before_pools
    assert session.state.turn_index == 0
    assert independent.to_dict() == before_independent


@pytest.mark.parametrize("bad", [True, -1, float("nan"), float("inf"), "50%"])
def test_invalid_population_inputs_leave_complete_session_unchanged(bad):
    session = create_county_demo()
    cohort_id = next(row["id"] for row in session.state.economy["county"]["population"]["cohorts"]
                     if row["count"] > 0)
    for edit in (
        lambda: session.set_demo_population_parameters(bad, .03, .02, 1),
        lambda: session.set_demo_population_parameters(.5, bad, .02, 1),
        lambda: session.set_demo_population_parameters(.5, .03, bad, 1),
        lambda: session.set_demo_population_parameters(.5, .03, .02, bad),
        lambda: session.set_demo_population_income(cohort_id, bad),
    ):
        before = session.to_dict()
        assert not edit().ok
        assert session.to_dict() == before


def test_population_edits_are_planning_only_and_restore_with_history():
    session = create_county_demo()
    assert session.set_demo_population_parameters(.5, .05, .01, 1).ok
    for _ in range(8):
        assert session.advance_economy_demo_turn().ok
    assert sum(report["births"] for report in session.economy_view["history"]) > 0
    assert sum(report["natural_deaths"] for report in session.economy_view["history"]) > 0
    historical = copy.deepcopy(session.economy_view["history"])
    assert session.set_demo_population_parameters(.6, .04, .02, 2).ok
    assert session.economy_view["history"] == historical
    assert session.start_turn().ok
    cohort_id = next(row["id"] for row in session.state.economy["county"]["population"]["cohorts"]
                     if row["count"] > 0)
    before = session.to_dict()
    assert not session.set_demo_population_parameters(.5, .03, .02, 1).ok
    assert not session.set_demo_population_income(cohort_id, 4).ok
    assert session.to_dict() == before
    restored = GameSession.from_dict(before)
    assert restored.to_dict() == before
    assert restored.economy_view == session.economy_view


def test_old_county_save_retains_its_original_rules_and_continues():
    fixture = Path(__file__).parent / "fixtures/county_v1_shortage_after_4_turns.json"
    session = GameSession.load_json(fixture)
    assert session.state.economy["schema_version"] == 1
    assert session.state.turn_index == 4
    before = session.to_dict()
    assert not session.set_demo_population_parameters(.5, .03, .02, 1).ok
    assert not session.set_demo_population_income("poor_adult_settled", 4).ok
    assert session.to_dict() == before
    resumed = GameSession.from_dict(before)
    assert session.advance_economy_demo_turn().ok
    assert resumed.advance_economy_demo_turn().ok
    assert resumed.to_dict() == session.to_dict()
    assert session.state.economy["schema_version"] == 1
    assert "annual_birth_rate" not in session.state.economy["rules"]
