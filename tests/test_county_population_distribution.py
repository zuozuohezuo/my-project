"""Small per-turn demographic totals must not always go to the largest occupation."""

import copy

from dynasty.content import create_county_demo
from dynasty.core.regions.economy import county_view, settle_economy


def test_birth_distribution_accumulates_for_smaller_occupations():
    economy = create_county_demo().state.economy
    economy["rules"].update(annual_birth_rate=.036, annual_death_rate=0)
    cohorts = economy["county"]["population"]["cohorts"]
    starting = {"farmer": 600, "laborer": 300, "artisan": 100}
    for row in cohorts:
        row["count"] = (starting.get(row["occupation"], 0)
                        if row["wealth"] == "ordinary" and row["resident_status"] == "settled" else 0)
    for pool in economy["pools"].values():
        for resource in pool["balances"]:
            pool["balances"][resource] = 1_000_000
    original = copy.deepcopy(economy)
    births = 0
    for turn in range(36):
        economy, report = settle_economy(economy, turn, turn // 3 + 1, turn % 3 + 1)
        births += report["births"]
        assert report["deaths"] == report["moved_down"] == 0
    populations = {row["id"]: row["population"] for row in county_view(economy)["occupation_groups"]}
    for occupation, count in starting.items():
        assert populations[occupation] > count, "Natural change must also reach smaller occupations"
    assert sum(populations.values()) == 1000 + births
    assert original["last_settled_turn"] == -1


def test_demographics_are_independent_of_cohort_list_order():
    economy = create_county_demo("shortage").state.economy
    other = copy.deepcopy(economy)
    other["county"]["population"]["cohorts"].reverse()
    for turn in range(12):
        economy, report = settle_economy(economy, turn, turn // 3 + 1, turn % 3 + 1)
        other, other_report = settle_economy(other, turn, turn // 3 + 1, turn % 3 + 1)
        assert report == other_report
    assert county_view(economy)["occupation_groups"] == county_view(other)["occupation_groups"]
    assert economy["pools"] == other["pools"]
