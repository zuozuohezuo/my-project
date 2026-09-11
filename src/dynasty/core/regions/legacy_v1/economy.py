"""Public one-county API. Calculations return copies and never advance the game clock."""

from __future__ import annotations

import copy

from .consumption import consume
from .models import (CATEGORIES, OWNERS, RESOURCES, mapping, number, resource_amounts,
                     text_value, validate_economy as _validate_economy)
from .population import apply_shortages, population_total, population_view
from .production import produce


def validate_economy(economy: object) -> None:
    """All damaged or unsupported structures fail with ValueError, including bad nested types."""
    try:
        _validate_economy(economy)
    except (KeyError, TypeError, OverflowError, AttributeError) as error:
        raise ValueError(f"经济档案结构或数值无效：{error}") from error


def create_demo_economy(payload: dict, scenario: str = "normal") -> dict:
    """Build fresh fictional data from explicit configuration; no history records are changed."""
    try:
        mapping(payload, {"schema_version", "demo", "description", "county", "pools", "rules", "scenarios"}, "演示配置")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1 or payload["demo"] is not True:
            raise ValueError("仅支持版本1的虚构县演示配置。")
        text_value(payload["description"], "演示说明")
        mapping(payload["scenarios"], {"normal", "shortage", "input_shortage"}, "演示情境")
        for config in payload["scenarios"].values():
            mapping(config, {"label", "description", "pool_overrides"}, "演示情境")
            text_value(config["label"], "情境名称")
            text_value(config["description"], "情境说明")
            if type(config["pool_overrides"]) is not dict:
                raise ValueError("情境余额替换须为字典。")
            for pool_id, amounts in config["pool_overrides"].items():
                if pool_id not in payload["pools"]:
                    raise ValueError("情境引用不存在的资源池。")
                resource_amounts(amounts, "情境资源余额")
        if type(scenario) is not str or scenario not in payload["scenarios"]:
            raise ValueError("未知的一县演示情境。")
        choice = payload["scenarios"][scenario]
        economy = {"schema_version": 1, "rules_version": 1, "demo": True, "scenario": scenario,
                   "scenario_label": choice["label"], "scenario_description": choice["description"],
                   "last_settled_turn": -1, "county": copy.deepcopy(payload["county"]),
                   "pools": copy.deepcopy(payload["pools"]), "rules": copy.deepcopy(payload["rules"]), "history": []}
        validate_economy(economy)
        for identifier, amounts in choice["pool_overrides"].items():
            economy["pools"][identifier]["balances"].update(copy.deepcopy(amounts))
        validate_economy(economy)
        return economy
    except (KeyError, TypeError, OverflowError, AttributeError) as error:
        raise ValueError(f"演示配置结构无效：{error}") from error


def settle_economy(economy: dict, turn_index: int, month: int, xun: int) -> tuple[dict, dict]:
    """Compute one consecutive turn atomically. Repeated or skipped turn IDs are rejected."""
    try:
        return _settle_economy(economy, turn_index, month, xun)
    except (KeyError, TypeError, ArithmeticError, AttributeError) as error:
        raise ValueError(f"经济计算无法完成，原状态未改变：{error}") from error


def _settle_economy(economy: dict, turn_index: int, month: int, xun: int) -> tuple[dict, dict]:
    validate_economy(economy)
    number(turn_index, "结算旬编号", integer=True)
    number(month, "月份", 1, 12, integer=True)
    number(xun, "旬", 1, 3, integer=True)
    if turn_index != economy["last_settled_turn"] + 1:
        raise ValueError("经济只能按旬连续结算；本旬已结算或旬编号跳跃。")
    if economy["history"]:
        previous = economy["history"][-1]
        expected_slot = ((previous["month"] - 1) * 3 + previous["xun"]) % 36
        if (month - 1) * 3 + xun - 1 != expected_slot:
            raise ValueError("经济结算月份与上一旬不连续。")
    candidate = copy.deepcopy(economy)
    county, pools, rules = candidate["county"], candidate["pools"], candidate["rules"]
    before = population_total(county)
    production = produce(county, pools, rules, month, xun)
    consumption = consume(county, pools, rules)
    groups = apply_shortages(county, rules, consumption)
    after = population_total(county)
    deaths = sum(row["deaths"] for row in groups)
    moved = sum(row["moved_down"] for row in groups)
    grain = next(row for row in consumption if row["resource"] == "grain")
    changes = {identifier: {resource: pool["balances"][resource]
                            - economy["pools"][identifier]["balances"][resource] for resource in RESOURCES}
               for identifier, pool in pools.items()}
    produced_grain = sum(row["outputs"].get("grain", 0) for row in production)
    summary = (f"{county['name']}：本旬产粮{produced_grain:.1f}，口粮满足{grain['fulfillment']:.0%}；"
               f"死亡{deaths}人，向下转层{moved}人，期末人口{after}人。")
    report = {"turn_index": turn_index, "month": month, "xun": xun, "summary": summary,
              "production": production, "consumption": consumption, "groups": groups,
              "deaths": deaths, "moved_down": moved, "population_before": before, "population_after": after,
              "grain_shortage_ratio": 1 - grain["fulfillment"], "pool_changes": changes}
    candidate["last_settled_turn"] = turn_index
    candidate["history"].append(report)
    candidate["history"] = candidate["history"][-rules["history_limit"]:]
    validate_economy(candidate)
    return candidate, copy.deepcopy(report)


def county_view(economy: dict) -> dict:
    """Stable, detached demonstration view; this is not the future emperor intelligence filter."""
    validate_economy(economy)
    county = economy["county"]
    population, wealth_groups, age_groups, sentiment = population_view(county, economy["rules"])
    assets = {row["id"]: row for row in county["land"]["parcels"] + county["facilities"]}
    industries = []
    for row in county["industries"]:
        asset = assets[row["asset_id"]]
        industries.append({"id": row["id"], "label": row["label"], "category": row["category"],
                           "category_label": CATEGORIES[row["category"]], "owner": asset["owner"],
                           "owner_label": OWNERS[asset["owner"]], "asset_label": asset["label"],
                           "scale": row["scale"], "workers_needed": row["workers_needed"],
                           "technology": row["technology"], "inputs": row["inputs"], "products": row["outputs"],
                           "progress": row["progress"], "cycle_turns": row["cycle_turns"], "state": row["state"],
                           "last_output": row["last_output"], "last_labor_ratio": row["last_labor_ratio"],
                           "last_input_ratio": row["last_input_ratio"]})
    parcels = [{**row, "owner_label": OWNERS[row["owner"]]} for row in county["land"]["parcels"]]
    facilities = [{**row, "owner_label": OWNERS[row["owner"]]} for row in county["facilities"]]
    view = {"id": county["id"], "name": county["name"], "description": county["description"],
            "demo_notice": "虚构清河县 · 演示参数与真实状态视图，不是史实或正式平衡；情报过滤尚未接入。",
            "scenario": economy["scenario"], "scenario_label": economy["scenario_label"],
            "last_settled_turn": economy["last_settled_turn"], "population": population,
            "wealth_groups": wealth_groups, "age_groups": age_groups, "sentiment": sentiment,
            "resources": [{"id": key, "label": label, "unit": unit} for key, (label, unit) in RESOURCES.items()],
            "pools": [economy["pools"][county["pool_ids"][owner]] for owner in OWNERS],
            "land": {"total_area": county["land"]["total_area"],
                     "cultivated_area": sum(row["area"] for row in parcels if row["use"] == "farmland"),
                     "reclaimable_area": sum(row["reclaimable"] for row in parcels), "parcels": parcels},
            "industries": industries, "specialties": county["specialties"], "modifiers": county["modifiers"],
            "facilities": facilities, "last_report": economy["history"][-1] if economy["history"] else None,
            "history": economy["history"], "notices": [economy["scenario_description"], *county["notices"]]}
    return copy.deepcopy(view)
