"""Occupation/income population rules, natural events and v1 preservation."""

import copy
import json
from pathlib import Path

import pytest

from dynasty.core.regions.economy import (
    county_view, create_demo_economy, settle_economy, update_population_income,
    update_population_parameters, validate_economy,
)
from dynasty.core.regions.legacy_v1.economy import settle_economy as legacy_settle
from dynasty.core.regions.models import OCCUPATIONS, wealth_for_income


@pytest.fixture
def economy():
    payload = json.loads((Path(__file__).parents[1] / "data/config/county_demo.json").read_text(encoding="utf-8"))
    return create_demo_economy(payload)


def advance(economy, turns):
    reports = []
    for _ in range(turns):
        turn = economy["last_settled_turn"] + 1
        economy, report = settle_economy(economy, turn, (turn % 36) // 3 + 1, turn % 3 + 1)
        reports.append(report)
    return economy, reports


def cohort(economy, occupation, wealth="ordinary", status="settled"):
    return next(row for row in economy["county"]["population"]["cohorts"]
                if (row["occupation"], row["wealth"], row["resident_status"]) == (occupation, wealth, status))


def single_group(economy, count=1, occupation="farmer", wealth="ordinary"):
    for row in economy["county"]["population"]["cohorts"]:
        row["count"] = 0
    cohort(economy, occupation, wealth)["count"] = count
    return economy


def occupations(economy):
    return {row["id"]: row["population"] for row in county_view(economy)["occupation_groups"]}


def test_new_population_has_separate_occupations_and_income_with_no_age(economy):
    view = county_view(economy)
    assert economy["schema_version"] == economy["rules_version"] == 2
    assert view["population_editable"] is True
    assert "age_groups" not in view and "age_labor" not in economy["rules"]
    assert all("age" not in row for row in economy["county"]["population"]["cohorts"])
    assert set(occupations(economy)) == set(OCCUPATIONS)
    population = view["population"]
    assert population["total"] == 1000
    assert population["base_labor"] == population["available_labor"] == 500
    assert population["labor_ratio"] == 0.5
    assert population["annual_birth_rate"] == 0.03 and population["annual_death_rate"] == 0.02
    assert population["turns_per_year"] == 36
    assert population["wealth_thresholds"] == {"ordinary": 1, "wealthy": 3}
    assert sum(occupations(economy).values()) == sum(row["population"] for row in view["wealth_groups"]) == 1000
    assert len({row["wealth"] for row in view["cohorts"] if row["occupation"] == "farmer" and row["population"]}) == 3
    assert len({row["occupation"] for row in view["cohorts"] if row["wealth"] == "ordinary" and row["population"]}) > 1


def test_normal_two_years_have_natural_growth_and_separate_deaths(economy):
    before_pools = copy.deepcopy(economy["pools"])
    economy, reports = advance(economy, 72)
    assert sum(row["births"] for row in reports) == 60
    assert sum(row["natural_deaths"] for row in reports) == 40
    assert sum(row["shortage_deaths"] for row in reports) == 0
    assert county_view(economy)["population"]["total"] == 1020
    for report in reports:
        assert report["deaths"] == report["natural_deaths"] + report["shortage_deaths"]
        assert report["population_before"] + report["births"] - report["deaths"] == report["population_after"]
    for pool_id in economy["pools"]:
        assert economy["pools"][pool_id]["balances"]["money"] == before_pools[pool_id]["balances"]["money"]


@pytest.mark.parametrize("count,rate", [(1, 1.0), (10, 0.1)])
def test_small_population_carries_fractions_through_save_and_gets_births(economy, count, rate):
    single_group(economy, count)
    economy["rules"].update(annual_birth_rate=rate, annual_death_rate=0)
    midway, first = advance(economy, 17)
    assert sum(row["births"] for row in first) == 0
    assert midway["county"]["population"]["birth_remainder"] > 0
    restored = json.loads(json.dumps(midway))
    continued, reports = advance(midway, 19)
    resumed, restored_reports = advance(restored, 19)
    assert resumed == continued and reports == restored_reports
    assert sum(row["births"] for row in reports) == 1
    assert cohort(continued, "farmer")["count"] == count + 1
    assert sum(occupations(continued).values()) == count + 1


def test_zero_population_does_not_birth_from_leftover_fractions(economy):
    single_group(economy, 0)
    economy["county"]["population"].update(birth_remainder=0.99, natural_death_remainder=0.99)
    economy, reports = advance(economy, 3)
    assert all(row["population_after"] == row["births"] == row["deaths"] == 0 for row in reports)
    assert economy["county"]["population"]["birth_remainder"] == 0
    assert economy["county"]["population"]["natural_death_remainder"] == 0
    assert county_view(economy)["population"]["available_labor"] == 0


@pytest.mark.parametrize("natural_death", [False, True])
def test_newborns_do_not_die_twice_or_consume_in_birth_turn(economy, natural_death):
    single_group(economy, 1)
    economy["rules"].update(annual_birth_rate=1, annual_death_rate=1 if natural_death else 0,
                            grain_death_rate=1, descent_grain_rate=0)
    economy["county"]["population"].update(birth_remainder=0.99, natural_death_remainder=0.99 if natural_death else 0)
    economy["pools"]["qinghe_private"]["balances"]["grain"] = 0
    economy, reports = advance(economy, 1)
    report = reports[0]
    assert report["births"] == report["deaths"] == report["population_after"] == 1
    assert report["natural_deaths"] == int(natural_death)
    assert report["shortage_deaths"] == int(not natural_death)
    grain = next(row for row in report["consumption"] if row["resource"] == "grain")
    assert grain["demand"] == 1
    assert cohort(economy, "farmer")["count"] == 1


def test_shortage_moves_wealth_and_death_remainder_without_changing_occupation(economy):
    single_group(economy, 1, "noble", "wealthy")
    source = cohort(economy, "noble", "wealthy")
    source.update(death_remainder=0.9, descent_remainder=0.9)
    economy["rules"].update(annual_birth_rate=0, annual_death_rate=0,
                            grain_death_rate=0.001, descent_grain_rate=1)
    economy["pools"]["qinghe_private"]["balances"]["grain"] = 0
    result, reports = advance(economy, 1)
    assert reports[0]["deaths"] == 0 and reports[0]["moved_down"] == 1
    assert cohort(result, "noble", "wealthy")["count"] == 0
    ordinary = cohort(result, "noble")
    assert ordinary["count"] == 1 and 1 <= ordinary["income_per_capita"] < 3
    assert ordinary["death_remainder"] == pytest.approx(0.9005)
    assert cohort(result, "noble", "wealthy")["death_remainder"] == 0
    assert sum(count for name, count in occupations(result).items() if name != "noble") == 0
    result["pools"]["qinghe_private"]["balances"].update(grain=1000, daily_goods=1000, luxury_goods=1000)
    result, _ = advance(result, 2)
    assert cohort(result, "noble")["count"] == 1
    assert cohort(result, "noble", "wealthy")["count"] == 0
    assert cohort(result, "noble")["death_remainder"] == pytest.approx(0.9005)


def test_income_thresholds_preserve_occupation_and_money_and_use_weighted_merge(economy):
    original = copy.deepcopy(economy)
    poor = cohort(economy, "farmer", "poor")
    normal = cohort(economy, "farmer")
    expected = (normal["income_per_capita"] * normal["count"] + poor["count"] * 1) / (normal["count"] + poor["count"])
    changed = update_population_income(economy, poor["id"], 1)
    assert cohort(changed, "farmer", "poor")["count"] == 0
    assert cohort(changed, "farmer")["income_per_capita"] == pytest.approx(expected)
    assert occupations(changed) == occupations(economy)
    assert changed["pools"] == economy["pools"]
    changed = update_population_income(changed, normal["id"], 3)
    assert cohort(changed, "farmer")["count"] == 0
    assert cohort(changed, "farmer", "wealthy")["count"] == poor["count"] + normal["count"] + cohort(economy, "farmer", "wealthy")["count"]
    assert all(wealth_for_income(row["income_per_capita"], changed["rules"]) == row["wealth"]
               for row in changed["county"]["population"]["cohorts"])
    assert economy == original


def test_parameter_edit_reclassifies_by_cost_and_preserves_history_and_credits(economy):
    economy, _ = advance(economy, 8)
    history = copy.deepcopy(economy["history"])
    population = economy["county"]["population"]
    changed = update_population_parameters(economy, labor_ratio=.25, annual_birth_rate=.04,
                                           annual_death_rate=.01, basic_living_cost=2)
    assert occupations(changed) == occupations(economy)
    assert changed["pools"] == economy["pools"] and changed["history"] == history
    assert changed["county"]["population"]["birth_remainder"] == population["birth_remainder"]
    assert changed["county"]["population"]["natural_death_remainder"] == population["natural_death_remainder"]
    view = county_view(changed)
    assert view["population"]["wealth_thresholds"] == {"ordinary": 2, "wealthy": 6}
    assert view["population"]["base_labor"] == view["population"]["total"] * .25
    changed, _ = advance(changed, 1)
    validate_economy(changed)


@pytest.mark.parametrize("path,value", [
    (("rules", "labor_ratio"), True), (("rules", "annual_birth_rate"), 1.01),
    (("rules", "annual_death_rate"), float("nan")), (("rules", "basic_living_cost"), 0),
    (("rules", "turns_per_year"), 1), (("county", "population", "birth_remainder"), 1),
    (("county", "population", "cohorts", 0, "income_per_capita"), float("inf")),
    (("county", "population", "cohorts", 0, "income_per_capita"), 100),
    (("county", "population", "cohorts", 0, "occupation"), "poor"),
])
def test_malformed_population_parameters_or_classifications_are_rejected(economy, path, value):
    target = economy
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        validate_economy(economy)


def test_age_fields_are_not_silently_kept_or_upgraded_in_v2(economy):
    economy["county"]["population"]["cohorts"][0]["age"] = "adult"
    with pytest.raises(ValueError):
        validate_economy(economy)


def test_invalid_edits_and_reports_fail_without_mutating_original(economy):
    original = copy.deepcopy(economy)
    identifier = cohort(economy, "farmer")["id"]
    for invalid in (True, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            update_population_income(economy, identifier, invalid)
        assert economy == original
    with pytest.raises(ValueError):
        update_population_parameters(economy, labor_ratio=.5, annual_birth_rate=-.1,
                                     annual_death_rate=.02, basic_living_cost=1)
    result, _ = advance(economy, 2)
    result["history"][-1]["births"] += 1
    with pytest.raises(ValueError):
        validate_economy(result)


def test_v1_saved_snapshot_keeps_frozen_rules_and_rejects_new_edits():
    snapshot = json.loads((Path(__file__).parent / "fixtures/county_v1_shortage_after_4_turns.json").read_text(encoding="utf-8"))
    economy = snapshot["state"]["economy"]
    validate_economy(economy)
    expected, expected_report = legacy_settle(economy, 4, 2, 2)
    actual, actual_report = settle_economy(economy, 4, 2, 2)
    assert actual == expected and actual_report == expected_report
    assert actual["schema_version"] == actual["rules_version"] == 1
    assert "births" not in actual_report
    assert "age" in actual["county"]["population"]["cohorts"][0]
    view = county_view(actual)
    assert "age_groups" not in view and view["population_editable"] is False
    with pytest.raises(ValueError, match="旧版"):
        update_population_parameters(actual, labor_ratio=.5, annual_birth_rate=.03,
                                     annual_death_rate=.02, basic_living_cost=1)
    with pytest.raises(ValueError, match="旧版"):
        update_population_income(actual, "unused", 1)
