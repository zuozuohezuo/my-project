"""Public one-county API. Calculations return copies and never advance the game clock."""

from __future__ import annotations

import copy

from .consumption import consume
from .legacy_v1 import economy as legacy_v1
from .models import (CATEGORIES, OWNERS, RESOURCES, mapping, number, resource_amounts,
                     text_value, validate_economy as _validate_economy, wealth_for_income)
from .population import apply_shortages, population_total, population_view, reclassify_income
from .production import produce


def _version(data: object) -> int:
    if type(data) is not dict or type(data.get("schema_version")) is not int or data["schema_version"] not in {1, 2}:
        raise ValueError("不支持的经济结构版本。")
    return data["schema_version"]


def validate_economy(economy: object) -> None:
    """All damaged or unsupported structures fail with ValueError, including bad nested types."""
    try:
        if _version(economy) == 1:
            legacy_v1.validate_economy(economy)
        else:
            _validate_economy(economy)
    except (KeyError, TypeError, OverflowError, AttributeError) as error:
        raise ValueError(f"经济档案结构或数值无效：{error}") from error


def create_demo_economy(payload: dict, scenario: str = "normal") -> dict:
    """Build fresh fictional data from explicit configuration; no history records are changed."""
    try:
        if _version(payload) == 1:
            return legacy_v1.create_demo_economy(payload, scenario)
        mapping(payload, {"schema_version", "demo", "description", "county", "pools", "rules", "scenarios"}, "演示配置")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 2 or payload["demo"] is not True:
            raise ValueError("仅支持版本2的新版人口演示配置。")
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
        economy = {"schema_version": 2, "rules_version": 2, "demo": True, "scenario": scenario,
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
        if _version(economy) == 1:
            return legacy_v1.settle_economy(economy, turn_index, month, xun)
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
    groups = apply_shortages(county, rules, consumption, turn_index)
    after = population_total(county)
    deaths = sum(row["deaths"] for row in groups)
    births = sum(row["births"] for row in groups)
    natural_deaths = sum(row["natural_deaths"] for row in groups)
    shortage_deaths = sum(row["shortage_deaths"] for row in groups)
    moved = sum(row["moved_down"] for row in groups)
    grain = next(row for row in consumption if row["resource"] == "grain")
    changes = {identifier: {resource: pool["balances"][resource]
                            - economy["pools"][identifier]["balances"][resource] for resource in RESOURCES}
               for identifier, pool in pools.items()}
    produced_grain = sum(row["outputs"].get("grain", 0) for row in production)
    summary = (f"{county['name']}：本旬产粮{produced_grain:.1f}，口粮满足{grain['fulfillment']:.0%}；"
               f"出生{births}人，自然死亡{natural_deaths}人，缺粮额外死亡{shortage_deaths}人；"
               f"向下转层{moved}人，期末人口{after}人。")
    report = {"turn_index": turn_index, "month": month, "xun": xun, "summary": summary,
              "production": production, "consumption": consumption, "groups": groups,
              "deaths": deaths, "births": births, "natural_deaths": natural_deaths,
              "shortage_deaths": shortage_deaths, "moved_down": moved, "population_before": before, "population_after": after,
              "grain_shortage_ratio": 1 - grain["fulfillment"], "pool_changes": changes}
    candidate["last_settled_turn"] = turn_index
    candidate["history"].append(report)
    candidate["history"] = candidate["history"][-rules["history_limit"]:]
    validate_economy(candidate)
    return candidate, copy.deepcopy(report)


def county_view(economy: dict) -> dict:
    """Stable, detached demonstration view; this is not the future emperor intelligence filter."""
    validate_economy(economy)
    if _version(economy) == 1:
        view = legacy_v1.county_view(economy)
        view.pop("age_groups", None)
        view.update(schema_version=1, rules_version=1, population_editable=False, occupation_groups=[], cohorts=[])
        view["notices"].insert(0, "旧版人口存档按原规则继续计算；未推断职业，不提供新版人口参数调整。")
        return view
    county = economy["county"]
    population, wealth_groups, occupations, sentiment, cohorts = population_view(county, economy["rules"])
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
    view = {"schema_version": 2, "rules_version": 2, "population_editable": True, "id": county["id"], "name": county["name"], "description": county["description"],
            "demo_notice": "虚构清河县 · 演示参数与真实状态视图，不是史实或正式平衡；情报过滤尚未接入。",
            "scenario": economy["scenario"], "scenario_label": economy["scenario_label"],
            "last_settled_turn": economy["last_settled_turn"], "population": population,
            "wealth_groups": wealth_groups, "occupation_groups": occupations, "cohorts": cohorts, "sentiment": sentiment,
            "resources": [{"id": key, "label": label, "unit": unit} for key, (label, unit) in RESOURCES.items()],
            "pools": [economy["pools"][county["pool_ids"][owner]] for owner in OWNERS],
            "land": {"total_area": county["land"]["total_area"],
                     "cultivated_area": sum(row["area"] for row in parcels if row["use"] == "farmland"),
                     "reclaimable_area": sum(row["reclaimable"] for row in parcels), "parcels": parcels},
            "industries": industries, "specialties": county["specialties"], "modifiers": county["modifiers"],
            "facilities": facilities, "last_report": economy["history"][-1] if economy["history"] else None,
            "history": economy["history"], "notices": [economy["scenario_description"], *county["notices"]]}
    return copy.deepcopy(view)


def update_population_parameters(economy: dict, *, labor_ratio: float, annual_birth_rate: float,
                                 annual_death_rate: float, basic_living_cost: float) -> dict:
    """Pure demo parameter edit. Historical reports and all resource balances are retained."""
    validate_economy(economy)
    if _version(economy) != 2:
        raise ValueError("旧版人口存档不支持新版人口参数；请建立新版演示局。")
    for key, value in (("劳动力比例", labor_ratio), ("年出生率", annual_birth_rate), ("年自然死亡率", annual_death_rate)):
        number(value, key, 0, 1)
    number(basic_living_cost, "基本生活成本", 0)
    if basic_living_cost <= 0:
        raise ValueError("基本生活成本必须大于0。")
    candidate = copy.deepcopy(economy)
    candidate["rules"].update(labor_ratio=labor_ratio, annual_birth_rate=annual_birth_rate,
                              annual_death_rate=annual_death_rate, basic_living_cost=basic_living_cost)
    if basic_living_cost != economy["rules"]["basic_living_cost"]:
        reclassify_income(candidate["county"], candidate["rules"])
    validate_economy(candidate)
    return candidate


def update_population_income(economy: dict, cohort_id: str, income_per_capita: float) -> dict:
    """Change one occupied cell's income; crossing thresholds merges within its occupation."""
    validate_economy(economy)
    if _version(economy) != 2:
        raise ValueError("旧版人口存档不支持按收入重分档；请建立新版演示局。")
    text_value(cohort_id, "人口群体编号")
    number(income_per_capita, "人均旬收入")
    candidate = copy.deepcopy(economy)
    cohort = next((row for row in candidate["county"]["population"]["cohorts"] if row["id"] == cohort_id), None)
    if cohort is None:
        raise ValueError("未找到指定人口群体。")
    if cohort["count"] <= 0:
        raise ValueError("该群体没有实际人口，不能调整人均收入。")
    cohort["income_per_capita"] = income_per_capita
    if wealth_for_income(income_per_capita, candidate["rules"]) != cohort["wealth"]:
        reclassify_income(candidate["county"], candidate["rules"])
    validate_economy(candidate)
    return candidate
