"""Frozen version-1 economic invariants and public legacy save dispatch."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from dynasty.core.regions.economy import (
    create_demo_economy, settle_economy, validate_economy,
)
from dynasty.core.regions.legacy_v1.economy import county_view
from dynasty.core.regions.legacy_v1.population import available_labor


@pytest.fixture
def payload():
    return json.loads((Path(__file__).parent / "fixtures/county_demo_v1.json").read_text(encoding="utf-8"))


def advance(economy, count=1):
    reports = []
    for _ in range(count):
        turn = economy["last_settled_turn"] + 1
        economy, report = settle_economy(economy, turn, (turn % 36) // 3 + 1, turn % 3 + 1)
        reports.append(report)
    return economy, reports


def test_demo_is_explicit_and_view_has_eight_groups_without_duplicate_population(payload):
    economy = create_demo_economy(payload)
    view = county_view(economy)
    assert economy["demo"] is True and economy["schema_version"] == economy["rules_version"] == 1
    assert "虚构" in view["demo_notice"]
    assert {"population", "land", "specialties", "modifiers", "industries", "pools", "facilities", "sentiment"} <= set(view)
    assert sum(row["population"] for row in view["wealth_groups"]) == view["population"]["total"] == 1000
    assert sum(row["population"] for row in view["age_groups"]) == 1000
    assert view["population"]["transients"] == 20
    assert sum(row["area"] for row in view["land"]["parcels"]) == view["land"]["total_area"]
    assert view["land"]["reclaimable_area"] < view["land"]["total_area"]
    assert {row["category"] for row in view["industries"]} == {"agriculture", "husbandry", "craft", "extraction"}
    assert view["last_report"] is None
    assert not any("reserved" in str(pool) or "available" in pool for pool in view["pools"])


def test_normal_two_years_remain_fed_and_cash_is_not_minted(payload):
    economy = create_demo_economy(payload)
    starting = copy.deepcopy(economy["pools"])
    economy, reports = advance(economy, 72)
    assert all(row["grain_shortage_ratio"] == row["deaths"] == row["moved_down"] == 0 for row in reports)
    assert county_view(economy)["population"]["total"] == 1000
    private = economy["pools"]["qinghe_private"]["balances"]
    assert private["grain"] == pytest.approx(31200)
    for pool_id, pool in economy["pools"].items():
        assert pool["balances"]["money"] == starting[pool_id]["balances"]["money"]
        assert all(value >= 0 for value in pool["balances"].values())


def test_harvest_follows_calendar_and_asset_ownership_exactly_once(payload):
    economy = create_demo_economy(payload)
    economy, before = advance(economy, 26)
    assert all(not any(p["outputs"].get("grain", 0) for p in report["production"]) for report in before)
    previous = copy.deepcopy(economy)
    economy, reports = advance(economy)
    yields = {row["owner"]: row["outputs"]["grain"] for row in reports[0]["production"] if row["outputs"].get("grain")}
    assert yields == {"private": 37000, "public": 7000, "royal": 3500}
    assert economy["pools"]["qinghe_public"]["balances"]["grain"] == 2000 - 60 + 7000
    assert economy["pools"]["qinghe_royal"]["balances"]["grain"] == 1000 - 30 + 3500
    assert previous["last_settled_turn"] == 25
    with pytest.raises(ValueError, match="已结算"):
        settle_economy(economy, 26, 9, 3)
    economy, later = advance(economy)
    assert not any(row["outputs"].get("grain") for row in later[0]["production"])


def test_workshop_output_follows_building_owner_not_a_second_industry_owner(payload):
    payload["county"]["facilities"][0]["owner"] = "royal"
    economy = create_demo_economy(payload)
    original = copy.deepcopy(economy["pools"])
    economy, reports = advance(economy)
    output = next(row for row in reports[0]["production"] if row["id"] == "craft_daily")
    assert output["owner"] == "royal" and output["outputs"] == {"daily_goods": 50}
    assert economy["pools"]["qinghe_royal"]["balances"]["daily_goods"] == original["qinghe_royal"]["balances"]["daily_goods"] + 50
    assert economy["pools"]["qinghe_private"]["balances"]["daily_goods"] == original["qinghe_private"]["balances"]["daily_goods"] - 45


def test_common_food_gap_has_wealth_weighted_consequences_without_public_bailout(payload):
    economy = create_demo_economy(payload, "shortage")
    public = copy.deepcopy(economy["pools"]["qinghe_public"])
    royal = copy.deepcopy(economy["pools"]["qinghe_royal"])
    economy, reports = advance(economy)
    report = reports[0]
    assert report["grain_shortage_ratio"] == 1
    assert report["deaths"] > 0 and report["moved_down"] > 0
    assert report["population_before"] - report["deaths"] == report["population_after"]
    poor, ordinary, wealthy = report["groups"]
    for key in ("mortality_risk", "health_penalty", "satisfaction_penalty", "labor_penalty"):
        assert poor[key] > ordinary[key] > wealthy[key]
    assert economy["pools"]["qinghe_public"] == public
    assert economy["pools"]["qinghe_royal"] == royal
    view = county_view(economy)
    assert sum(row["population"] for row in view["age_groups"]) == view["population"]["total"]
    assert sum(row["population"] for row in view["wealth_groups"]) == view["population"]["total"]


def test_partial_common_consumption_and_improvement_shortage_are_distinct(payload):
    economy = create_demo_economy(payload)
    economy["pools"]["qinghe_private"]["balances"]["grain"] = 500
    _, reports = advance(economy)
    grain = next(row for row in reports[0]["consumption"] if row["resource"] == "grain")
    assert grain == {"resource": "grain", "label": "粮食", "demand": 1000, "consumed": 500, "shortage": 500, "fulfillment": 0.5}
    economy = create_demo_economy(payload, "input_shortage")
    economy, reports = advance(economy)
    report = reports[0]
    assert report["grain_shortage_ratio"] == 0 and report["deaths"] == 0
    assert all(row["mortality_risk"] == row["health_penalty"] == 0 for row in report["groups"])
    assert any(row["satisfaction_penalty"] > 0 for row in report["groups"])
    assert {row["resource"] for row in report["consumption"]} == {"grain", "daily_goods", "luxury_goods"}


def test_class_descent_uses_starting_groups_and_does_not_cascade(payload):
    for cohort in payload["county"]["population"]["cohorts"]:
        cohort["count"] = 100 if cohort["id"] == "wealthy_adult_settled" else 0
    payload["rules"].update(grain_death_rate=0, descent_grain_rate=1,
                            wealth_effects={"poor": 3, "ordinary": 2, "wealthy": 1})
    economy = create_demo_economy(payload, "shortage")
    economy, reports = advance(economy)
    report = reports[0]
    groups = {row["id"]: row for row in county_view(economy)["wealth_groups"]}
    assert report["deaths"] == 0 and report["moved_down"] == 100
    assert groups["wealthy"]["population"] == groups["poor"]["population"] == 0
    assert groups["ordinary"]["population"] == 100
    assert report["groups"][1]["moved_down"] == 0
    assert sum(row["population"] for row in groups.values()) == 100


def test_materials_are_shared_fairly_and_reordering_does_not_change_results(payload):
    economy = create_demo_economy(payload)
    economy["pools"]["qinghe_private"]["balances"]["raw_material"] = 12.5
    reversed_economy = copy.deepcopy(economy)
    reversed_economy["county"]["industries"].reverse()
    result, reports = advance(economy)
    other, other_reports = advance(reversed_economy)
    assert reports == other_reports and result["pools"] == other["pools"]
    workshops = [row for row in reports[0]["production"] if row["id"].startswith("craft_")]
    assert all(row["input_ratio"] == 0.5 and row["progress"] == 0.5 for row in workshops)
    assert sum(row["inputs"].get("raw_material", 0) for row in workshops) == 12.5
    assert result["pools"]["qinghe_private"]["balances"]["raw_material"] == 0


def test_labor_is_finite_and_material_replenishment_restarts_production(payload):
    economy = create_demo_economy(payload)
    for cohort in economy["county"]["population"]["cohorts"]:
        cohort["labor_factor"] = 0.01
    opening_labor = available_labor(economy["county"], economy["rules"])
    _, reports = advance(economy)
    assert sum(row["labor_used"] for row in reports[0]["production"]) <= opening_labor + 1e-9
    assert all(row["labor_ratio"] < 1 for row in reports[0]["production"])
    economy = create_demo_economy(payload, "input_shortage")
    economy, reports = advance(economy, 4)
    assert next(row for row in reports[0]["production"] if row["id"] == "craft_daily")["state"] == "投入不足"
    assert next(row for row in reports[2]["production"] if row["id"] == "forest_material")["outputs"]["raw_material"] == 75
    assert next(row for row in reports[3]["production"] if row["id"] == "craft_daily")["outputs"]["daily_goods"] == 50


def test_json_restore_continues_identically_and_history_is_bounded(payload):
    payload["rules"]["history_limit"] = 3
    economy, _ = advance(create_demo_economy(payload), 28)
    restored = json.loads(json.dumps(economy, ensure_ascii=False))
    validate_economy(restored)
    continued, reports = advance(economy, 20)
    resumed, resumed_reports = advance(restored, 20)
    assert resumed == continued and resumed_reports == reports
    assert len(continued["history"]) == 3 and continued["history"][-1]["turn_index"] == 47


def test_inputs_results_reports_and_views_are_detached(payload):
    original_payload = copy.deepcopy(payload)
    economy = create_demo_economy(payload)
    second = create_demo_economy(payload)
    original = copy.deepcopy(economy)
    result, report = settle_economy(economy, 0, 1, 1)
    report["groups"][0]["deaths"] = 999
    view = county_view(result)
    view["pools"][0]["balances"]["grain"] = 123
    view["industries"][0]["last_output"]["grain"] = 456
    assert economy == original == second and payload == original_payload
    assert result["history"][-1]["groups"][0]["deaths"] == 0
    assert result["pools"]["qinghe_private"]["balances"]["grain"] != 123


@pytest.mark.parametrize("path,value", [
    (("schema_version",), True), (("last_settled_turn",), False),
    (("pools", "qinghe_private", "balances", "grain"), float("nan")),
    (("pools", "qinghe_private", "balances", "money"), float("inf")),
    (("pools", "qinghe_private", "balances", "daily_goods"), -1),
    (("pools", "qinghe_private", "owner"), "emperor"),
    (("pools", "qinghe_private", "owner"), []),
    (("county", "population", "cohorts", 0, "count"), 1.5),
    (("county", "population", "cohorts", 0, "health"), True),
    (("county", "population", "cohorts", 0, "death_remainder"), 1),
    (("county", "land", "total_area"), 999),
    (("county", "land", "parcels", 0, "reclaimable"), 10),
    (("county", "industries", 0, "outputs"), {"money": 100}),
    (("county", "industries", 0, "asset_id"), "missing"),
    (("county", "industries", 0, "active"), 1),
    (("rules", "needs", "poor", "grain"), 2),
])
def test_malformed_data_is_rejected_without_mutation(payload, path, value):
    economy = create_demo_economy(payload)
    node = economy
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValueError):
        validate_economy(economy)
    with pytest.raises(ValueError):
        settle_economy(economy, 0, 1, 1)


def test_missing_and_inconsistent_history_is_not_silently_rebuilt(payload):
    economy = create_demo_economy(payload)
    del economy["county"]["population"]["cohorts"][0]["age"]
    with pytest.raises(ValueError):
        validate_economy(economy)
    economy, _ = advance(create_demo_economy(payload), 2)
    economy["history"][-1]["month"] = 10
    with pytest.raises(ValueError, match="月份"):
        validate_economy(economy)
    economy, _ = advance(create_demo_economy(payload))
    economy["history"][-1]["groups"][0]["deaths"] = 1
    with pytest.raises(ValueError):
        validate_economy(economy)


def test_bad_turn_or_date_and_bad_scenario_fail_atomically(payload):
    economy = create_demo_economy(payload)
    original = copy.deepcopy(economy)
    for args in ((1, 1, 1), (0, 13, 1), (False, 1, 1), (0, 1, True)):
        with pytest.raises(ValueError):
            settle_economy(economy, *args)
        assert economy == original
    economy, _ = advance(economy)
    with pytest.raises(ValueError):
        settle_economy(economy, 1, 2, 1)
    with pytest.raises(ValueError):
        create_demo_economy(payload, "unknown")
    with pytest.raises(ValueError):
        validate_economy(None)
