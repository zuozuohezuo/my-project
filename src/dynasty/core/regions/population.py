"""Occupation and income cohorts, deterministic vital rates and shortage consequences."""

from __future__ import annotations

import copy
import math

from .models import OCCUPATIONS, WEALTH, income_in_band, wealth_for_income


def population_total(county: dict) -> int:
    return sum(row["count"] for row in county["population"]["cohorts"])


def labor_for(cohort: dict, rules: dict) -> float:
    return cohort["count"] * rules["labor_ratio"] * (cohort["health"] / 100) * cohort["labor_factor"]


def available_labor(county: dict, rules: dict) -> float:
    return sum(labor_for(row, rules) for row in sorted(county["population"]["cohorts"], key=lambda item: item["id"]))


def weighted(rows: list[dict], key: str, default: float) -> float:
    total = sum(row["count"] for row in rows)
    return sum((row["count"] / total) * row[key] for row in sorted(rows, key=lambda item: item["id"])) if total else default


def _group_view(rows: list[dict], identifier: str, label: str, rules: dict) -> dict:
    total = sum(row["count"] for row in rows)
    return {"id": identifier, "label": label, "population": total,
            "health": round(weighted(rows, "health", 100), 3),
            "satisfaction": round(weighted(rows, "satisfaction", 100), 3),
            "labor_factor": round(weighted(rows, "labor_factor", 1), 6),
            "base_labor": total * rules["labor_ratio"],
            "available_labor": round(sum(labor_for(row, rules) for row in rows), 3),
            "income_per_capita": weighted(rows, "income_per_capita", 0)}


def population_view(county: dict, rules: dict) -> tuple[dict, list, list, dict, list]:
    cohorts = county["population"]["cohorts"]
    total = population_total(county)
    population = {"total": total, "households": math.ceil(total / rules["household_size"]),
                  "available_labor": round(available_labor(county, rules), 3),
                  "base_labor": total * rules["labor_ratio"], "labor_ratio": rules["labor_ratio"],
                  "annual_birth_rate": rules["annual_birth_rate"], "annual_death_rate": rules["annual_death_rate"],
                  "turns_per_year": rules["turns_per_year"], "basic_living_cost": rules["basic_living_cost"],
                  "wealthy_income_multiplier": rules["wealthy_income_multiplier"],
                  "wealth_thresholds": {"ordinary": rules["basic_living_cost"],
                                        "wealthy": rules["basic_living_cost"] * rules["wealthy_income_multiplier"]},
                  "transients": sum(row["count"] for row in cohorts if row["resident_status"] == "displaced"),
                  "shortage_turns": county["population"]["shortage_turns"]}
    wealth_groups = [_group_view([row for row in cohorts if row["wealth"] == key], key, label, rules)
                     for key, label in WEALTH.items()]
    occupations = [_group_view([row for row in cohorts if row["occupation"] == key], key, label, rules)
                   for key, label in OCCUPATIONS.items()]
    sentiment = {"health": round(weighted(cohorts, "health", 100), 3),
                 "satisfaction": round(weighted(cohorts, "satisfaction", 100), 3),
                 "labor_factor": round(weighted(cohorts, "labor_factor", 1), 6)}
    rows = [{"id": row["id"], "occupation": row["occupation"], "occupation_label": OCCUPATIONS[row["occupation"]],
             "wealth": row["wealth"], "wealth_label": WEALTH[row["wealth"]],
             "resident_status": row["resident_status"],
             "resident_label": "流民" if row["resident_status"] == "displaced" else "定居人口",
             "population": row["count"], "income_per_capita": row["income_per_capita"],
             "health": row["health"], "satisfaction": row["satisfaction"], "labor_factor": row["labor_factor"],
             "base_labor": row["count"] * rules["labor_ratio"], "available_labor": labor_for(row, rules)}
            for row in cohorts]
    return population, wealth_groups, occupations, sentiment, rows


def _apportion(total: int, rows: list[dict], phase: float) -> dict[str, int]:
    """Rotate a systematic proportional sample instead of always choosing the largest cell."""
    count = sum(row["count"] for row in rows)
    allocated = {row["id"]: 0 for row in rows}
    if total <= 0 or count <= 0:
        return allocated
    prefix = 0
    phase %= 1
    for row in sorted(rows, key=lambda item: item["id"]):
        low = prefix / count * total - phase
        prefix += row["count"]
        high = prefix / count * total - phase
        first = max(0, min(total, math.ceil(low)))
        last = max(0, min(total, math.ceil(high)))
        allocated[row["id"]] = max(0, last - first)
    if sum(allocated.values()) != total:
        raise ValueError("人口比例分摊未能守恒。")
    return allocated


def _fractional_events(population: dict, key: str, total: int, annual_rate: float, turns: int) -> int:
    if total == 0:
        population[key] = 0.0
        return 0
    expected = total * (annual_rate / turns) + population[key]
    events = min(total, math.floor(expected + 1e-12))
    population[key] = max(0.0, min(math.nextafter(1.0, 0.0), expected - events))
    return events


def _merge(destination: dict, count: int, attributes: dict, rules: dict) -> None:
    if count <= 0:
        return
    old = destination["count"]
    total = old + count
    for key in ("health", "satisfaction", "labor_factor", "income_per_capita"):
        destination[key] = destination[key] * (old / total) + attributes[key] * (count / total)
    for key in ("health", "satisfaction"):
        destination[key] = max(0.0, min(100.0, destination[key]))
    destination["labor_factor"] = max(0.0, min(1.0, destination["labor_factor"]))
    destination["income_per_capita"] = income_in_band(destination["income_per_capita"], destination["wealth"], rules)
    destination["count"] = total


def reclassify_income(county: dict, rules: dict) -> None:
    """Rebuild the same 42 cells after an income/cost edit; occupations and totals persist."""
    original = sorted(copy.deepcopy(county["population"]["cohorts"]), key=lambda row: row["id"])
    result = copy.deepcopy(original)
    by_identity = {(row["occupation"], row["wealth"], row["resident_status"]): row for row in result}
    for row in result:
        row["count"] = 0
        row["income_per_capita"] = income_in_band(row["income_per_capita"], row["wealth"], rules)
        row["death_remainder"] = row["descent_remainder"] = 0.0
    for source in original:
        if source["count"] <= 0:
            continue
        wealth = wealth_for_income(source["income_per_capita"], rules)
        target = by_identity[(source["occupation"], wealth, source["resident_status"])]
        _merge(target, source["count"], source, rules)
        # Merging fractional expectations can accumulate >=1; edits never realize deaths.
        target["death_remainder"] += source["death_remainder"]
        if wealth != "poor":
            target["descent_remainder"] += source["descent_remainder"]
    county["population"]["cohorts"] = result


def apply_shortages(county: dict, rules: dict, consumption: list[dict], turn_index: int) -> list[dict]:
    """Use opening groups; natural deaths precede shortages and newborns join at the end."""
    gaps = {row["resource"]: max(0.0, 1 - row["fulfillment"]) for row in consumption}
    grain_gap = gaps["grain"]
    state = county["population"]
    state["shortage_turns"] = state["shortage_turns"] + 1 if grain_gap > 1e-9 else 0
    amplification = 1 + max(0, min(state["shortage_turns"] - 1, rules["streak_cap"])) * rules["streak_increment"]
    initial = sorted(copy.deepcopy(state["cohorts"]), key=lambda row: row["id"])
    population = sum(row["count"] for row in initial)
    birth_count = _fractional_events(state, "birth_remainder", population, rules["annual_birth_rate"], rules["turns_per_year"])
    natural_count = _fractional_events(state, "natural_death_remainder", population, rules["annual_death_rate"], rules["turns_per_year"])
    births = _apportion(birth_count, initial, (turn_index + 1) * 0.6180339887498949)
    natural = _apportion(natural_count, initial, (turn_index + 1) * 0.4142135623730951)
    candidates = copy.deepcopy(initial)
    by_identity = {(row["occupation"], row["wealth"], row["resident_status"]): row for row in candidates}
    reports, consequences = {}, {}
    for wealth, label in WEALTH.items():
        vulnerability = rules["wealth_effects"][wealth]
        mortality = min(1, grain_gap * rules["grain_death_rate"] * vulnerability * amplification)
        health_loss = min(100, grain_gap * rules["grain_health_penalty"] * vulnerability)
        daily_gap = gaps["daily_goods"] if rules["needs"][wealth]["daily_goods"] else 0
        luxury_gap = gaps["luxury_goods"] if rules["needs"][wealth]["luxury_goods"] else 0
        satisfaction_loss = min(100, vulnerability * (
            grain_gap * rules["grain_satisfaction_penalty"] + daily_gap * rules["daily_satisfaction_penalty"]
            + luxury_gap * rules["luxury_satisfaction_penalty"]))
        labor_loss = min(1, grain_gap * rules["grain_labor_penalty"] * vulnerability)
        descent = min(1, vulnerability * (grain_gap * rules["descent_grain_rate"]
                                         + max(daily_gap, luxury_gap) * rules["descent_goods_rate"]))
        consequences[wealth] = (mortality, health_loss, satisfaction_loss, labor_loss, descent)
        reports[wealth] = {"id": wealth, "label": label,
                           "population_before": sum(row["count"] for row in initial if row["wealth"] == wealth),
                           "deaths": 0, "natural_deaths": 0, "shortage_deaths": 0, "births": 0,
                           "moved_down": 0, "mortality_risk": mortality,
                           "health_penalty": health_loss, "satisfaction_penalty": satisfaction_loss,
                           "labor_penalty": labor_loss}
    transfers, newborns = [], []
    for before, after in zip(initial, candidates):
        wealth = before["wealth"]
        mortality, health_loss, satisfaction_loss, labor_loss, descent = consequences[wealth]
        natural_deaths = natural[before["id"]]
        living = before["count"] - natural_deaths
        amount = living * mortality + before["death_remainder"]
        shortage_deaths = min(living, math.floor(amount + 1e-12)) if mortality > 0 else 0
        survivors = living - shortage_deaths
        after["death_remainder"] = max(0.0, amount - shortage_deaths) if survivors else 0.0
        moved = 0
        if wealth != "poor" and descent > 0:
            expected = survivors * descent + before["descent_remainder"]
            moved = min(survivors, math.floor(expected + 1e-12))
            after["descent_remainder"] = max(0.0, expected - moved) if survivors > moved else 0.0
        elif wealth == "poor" or not survivors:
            after["descent_remainder"] = 0.0
        after["health"] = max(0, min(100, before["health"] - health_loss
                                    + (rules["health_recovery"] if not grain_gap else 0)))
        after["satisfaction"] = max(0, min(100, before["satisfaction"] - satisfaction_loss
                                          + (rules["satisfaction_recovery"] if not satisfaction_loss else 0)))
        after["labor_factor"] = max(0, min(1, before["labor_factor"] - labor_loss
                                          + (rules["labor_recovery"] if not grain_gap else 0)))
        after["count"] = survivors - moved
        group = reports[wealth]
        group["natural_deaths"] += natural_deaths
        group["shortage_deaths"] += shortage_deaths
        group["deaths"] += natural_deaths + shortage_deaths
        group["moved_down"] += moved
        target_wealth = "ordinary" if wealth == "wealthy" else "poor"
        incoming = copy.deepcopy(after)
        incoming["income_per_capita"] = income_in_band(after["income_per_capita"], target_wealth, rules)
        if moved:
            incoming["death_remainder"] = after["death_remainder"] * (moved / survivors)
            after["death_remainder"] -= incoming["death_remainder"]
            transfers.append(((after["occupation"], target_wealth, after["resident_status"]), moved, incoming))
        new = births[before["id"]]
        if new:
            # Stable id position keeps this family allocation independent of list order.
            phase = (turn_index + sum(ord(c) for c in before["id"]) + 1) * 0.6180339887498949
            split = _apportion(new, [{"id": "kept", "count": survivors - moved}, {"id": "moved", "count": moved}],
                               phase) if survivors else {"kept": new, "moved": 0}
            if split["kept"]:
                newborns.append(((after["occupation"], wealth, after["resident_status"]), split["kept"], copy.deepcopy(after)))
            if split["moved"]:
                newborns.append(((after["occupation"], target_wealth, after["resident_status"]), split["moved"], incoming))
    for identity, moved, attributes in sorted(transfers, key=lambda item: item[0]):
        _merge(by_identity[identity], moved, attributes, rules)
        by_identity[identity]["death_remainder"] += attributes["death_remainder"]
    for identity, born, attributes in sorted(newborns, key=lambda item: item[0]):
        _merge(by_identity[identity], born, attributes, rules)
        reports[identity[1]]["births"] += born
    state["cohorts"] = candidates
    return list(reports.values())
