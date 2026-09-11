"""Cross-group population accounting; class movement never creates or kills people."""

from __future__ import annotations

import copy
import math

from .models import AGES, WEALTH


def population_total(county: dict) -> int:
    return sum(row["count"] for row in county["population"]["cohorts"])


def labor_for(cohort: dict, rules: dict) -> float:
    return (cohort["count"] * rules["age_labor"][cohort["age"]]
            * (cohort["health"] / 100) * cohort["labor_factor"])


def available_labor(county: dict, rules: dict) -> float:
    return sum(labor_for(row, rules) for row in county["population"]["cohorts"])


def weighted(rows: list[dict], key: str, default: float) -> float:
    total = sum(row["count"] for row in rows)
    return sum((row["count"] / total) * row[key] for row in rows) if total else default


def population_view(county: dict, rules: dict) -> tuple[dict, list, list, dict]:
    cohorts = county["population"]["cohorts"]
    total = population_total(county)
    population = {"total": total, "households": math.ceil(total / rules["household_size"]),
                  "available_labor": round(available_labor(county, rules), 3),
                  "transients": sum(row["count"] for row in cohorts if row["resident_status"] == "displaced"),
                  "shortage_turns": county["population"]["shortage_turns"]}
    wealth_groups = []
    for identifier, label in WEALTH.items():
        rows = [row for row in cohorts if row["wealth"] == identifier]
        wealth_groups.append({"id": identifier, "label": label,
                              "population": sum(row["count"] for row in rows),
                              "health": round(weighted(rows, "health", 100), 3),
                              "satisfaction": round(weighted(rows, "satisfaction", 100), 3),
                              "labor_factor": round(weighted(rows, "labor_factor", 1), 6),
                              "available_labor": round(sum(labor_for(row, rules) for row in rows), 3)})
    ages = [{"id": identifier, "label": label,
             "population": sum(row["count"] for row in cohorts if row["age"] == identifier)}
            for identifier, label in AGES.items()]
    sentiment = {"health": round(weighted(cohorts, "health", 100), 3),
                 "satisfaction": round(weighted(cohorts, "satisfaction", 100), 3),
                 "labor_factor": round(weighted(cohorts, "labor_factor", 1), 6)}
    return population, wealth_groups, ages, sentiment


def apply_shortages(county: dict, rules: dict, consumption: list[dict]) -> list[dict]:
    """Mutate a candidate county, computing every consequence from beginning-of-turn groups."""
    gaps = {row["resource"]: 1 - row["fulfillment"] for row in consumption}
    grain_gap = gaps["grain"]
    county["population"]["shortage_turns"] = (
        county["population"]["shortage_turns"] + 1 if grain_gap > 1e-9 else 0)
    streak = county["population"]["shortage_turns"]
    amplification = 1 + max(0, min(streak - 1, rules["streak_cap"])) * rules["streak_increment"]
    initial = copy.deepcopy(county["population"]["cohorts"])
    candidates = copy.deepcopy(initial)
    by_identity = {(row["wealth"], row["age"], row["resident_status"]): row for row in candidates}
    reports = {}
    consequences = {}
    for wealth, label in WEALTH.items():
        vulnerability = rules["wealth_effects"][wealth]
        mortality = min(1, grain_gap * rules["grain_death_rate"] * vulnerability * amplification)
        health_loss = min(100, grain_gap * rules["grain_health_penalty"] * vulnerability)
        # A class with no luxury demand is not penalized for that resource's absence.
        daily_gap = gaps["daily_goods"] if rules["needs"][wealth]["daily_goods"] else 0
        luxury_gap = gaps["luxury_goods"] if rules["needs"][wealth]["luxury_goods"] else 0
        satisfaction_loss = min(100, vulnerability * (
            grain_gap * rules["grain_satisfaction_penalty"]
            + daily_gap * rules["daily_satisfaction_penalty"]
            + luxury_gap * rules["luxury_satisfaction_penalty"]))
        labor_loss = min(1, grain_gap * rules["grain_labor_penalty"] * vulnerability)
        descent = min(1, vulnerability * (grain_gap * rules["descent_grain_rate"]
                                         + max(daily_gap, luxury_gap) * rules["descent_goods_rate"]))
        consequences[wealth] = (mortality, health_loss, satisfaction_loss, labor_loss, descent)
        reports[wealth] = {"id": wealth, "label": label,
                           "population_before": sum(row["count"] for row in initial if row["wealth"] == wealth),
                           "deaths": 0, "moved_down": 0, "mortality_risk": mortality,
                           "health_penalty": health_loss, "satisfaction_penalty": satisfaction_loss,
                           "labor_penalty": labor_loss}
    transfers = []
    for before, after in zip(initial, candidates):
        wealth = before["wealth"]
        mortality, health_loss, satisfaction_loss, labor_loss, descent = consequences[wealth]
        death_amount = before["count"] * mortality + before["death_remainder"]
        deaths = min(before["count"], math.floor(death_amount + 1e-12))
        survivors = before["count"] - deaths
        after["death_remainder"] = max(0, min(0.999999999999, death_amount - deaths)) if survivors else 0
        moved = 0
        if wealth != "poor":
            amount = survivors * descent + before["descent_remainder"]
            moved = min(survivors, math.floor(amount + 1e-12))
            after["descent_remainder"] = max(0, min(0.999999999999, amount - moved)) if survivors > moved else 0
        else:
            after["descent_remainder"] = 0
        after["health"] = max(0, min(100, before["health"] - health_loss
                                    + (rules["health_recovery"] if not grain_gap else 0)))
        after["satisfaction"] = max(0, min(100, before["satisfaction"] - satisfaction_loss
                                          + (rules["satisfaction_recovery"] if not satisfaction_loss else 0)))
        after["labor_factor"] = max(0, min(1, before["labor_factor"] - labor_loss
                                          + (rules["labor_recovery"] if not grain_gap else 0)))
        after["count"] = survivors - moved
        reports[wealth]["deaths"] += deaths
        reports[wealth]["moved_down"] += moved
        if moved:
            target = "ordinary" if wealth == "wealthy" else "poor"
            transfers.append((target, after["age"], after["resident_status"], moved,
                              after["health"], after["satisfaction"], after["labor_factor"]))
    # All transitions apply together; arrivals cannot descend a second time in this turn.
    for wealth, age, status, moved, health, satisfaction, labor_factor in transfers:
        destination = by_identity[(wealth, age, status)]
        old_count = destination["count"]
        for key, incoming in (("health", health), ("satisfaction", satisfaction), ("labor_factor", labor_factor)):
            destination[key] = (destination[key] * old_count + incoming * moved) / (old_count + moved)
        destination["count"] += moved
    county["population"]["cohorts"] = candidates
    return list(reports.values())
