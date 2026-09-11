"""Version 2 county data: occupations and income classes, without age buckets."""

from __future__ import annotations

import math
from typing import Any


OWNERS = {"private": "民间", "public": "官府", "royal": "皇家"}
WEALTH = {"poor": "贫困", "ordinary": "普通", "wealthy": "富裕"}
OCCUPATIONS = {"farmer": "农民", "laborer": "劳工", "artisan": "手工业者",
               "merchant": "商人", "landowner": "地主", "noble": "贵族", "official": "官员"}
CATEGORIES = {"agriculture": "农业种植", "husbandry": "畜牧渔林",
              "craft": "手工业加工", "extraction": "资源采掘"}
RESOURCES = {"money": ("钱", "演示钱单位"), "grain": ("粮食", "演示粮单位"),
             "raw_material": ("原料", "演示物资单位"), "daily_goods": ("日用品", "演示物资单位"),
             "luxury_goods": ("享受品", "演示物资单位")}


def mapping(value: Any, keys: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"{label}字段缺失或含未知字段。")
    return value


def number(value: Any, label: str, minimum: float = 0, maximum: float | None = None,
           *, integer: bool = False) -> int | float:
    if type(value) not in ((int,) if integer else (int, float)):
        raise ValueError(f"{label}必须是{'整数' if integer else '数值'}，不能使用布尔值。")
    try:
        finite = math.isfinite(value)
    except (OverflowError, TypeError):
        finite = False
    if not finite or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{label}超出范围或不是有限数值。")
    return value


def text_value(value: Any, label: str, *, empty: bool = False) -> str:
    if (type(value) is not str or (not empty and not value.strip())
            or len(value) > 2000 or any(ord(c) < 32 for c in value)):
        raise ValueError(f"{label}须为有效文本。")
    return value


def records(value: Any, label: str) -> list:
    if type(value) is not list:
        raise ValueError(f"{label}须为列表。")
    return value


def resource_amounts(value: Any, label: str, *, complete: bool = False,
                     signed: bool = False) -> dict:
    if (type(value) is not dict or not set(value) <= set(RESOURCES)
            or (complete and set(value) != set(RESOURCES))):
        raise ValueError(f"{label}包含无效资源或缺失余额。")
    for key, amount in value.items():
        number(amount, f"{label}/{key}", -math.inf if signed else 0)
    return value


def _unique(rows: list, label: str) -> None:
    identifiers = [row["id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{label}编号重复。")


def wealth_for_income(income: float, rules: dict) -> str:
    if income < rules["basic_living_cost"]:
        return "poor"
    if income < rules["basic_living_cost"] * rules["wealthy_income_multiplier"]:
        return "ordinary"
    return "wealthy"


def income_in_band(income: float, wealth: str, rules: dict) -> float:
    """Keep a destination cohort's income inside its assigned interval."""
    lower = 0 if wealth == "poor" else rules["basic_living_cost"]
    upper = rules["basic_living_cost"] if wealth == "poor" else rules["basic_living_cost"] * rules["wealthy_income_multiplier"]
    if wealth == "wealthy":
        return max(upper, income)
    return max(lower, min(math.nextafter(upper, 0), income))


def validate_rules(rules: Any) -> None:
    mapping(rules, {"history_limit", "household_size", "labor_ratio", "annual_birth_rate", "annual_death_rate",
                    "turns_per_year", "basic_living_cost", "wealthy_income_multiplier", "needs", "wealth_effects",
                    "grain_death_rate", "grain_health_penalty", "grain_satisfaction_penalty",
                    "daily_satisfaction_penalty", "luxury_satisfaction_penalty", "grain_labor_penalty",
                    "health_recovery", "satisfaction_recovery", "labor_recovery",
                    "streak_increment", "streak_cap", "descent_grain_rate", "descent_goods_rate",
                    "settlement_order", "rounding"}, "经济规则")
    number(rules["history_limit"], "历史上限", 1, 360, integer=True)
    number(rules["household_size"], "演示平均户规模", 1)
    for key in ("labor_ratio", "annual_birth_rate", "annual_death_rate"):
        number(rules[key], key, 0, 1)
    number(rules["turns_per_year"], "每年旬数", 36, 36, integer=True)
    number(rules["basic_living_cost"], "基本生活成本", 0)
    number(rules["wealthy_income_multiplier"], "富裕收入倍率", 1)
    if rules["basic_living_cost"] <= 0 or rules["wealthy_income_multiplier"] <= 1:
        raise ValueError("生活成本须大于0，富裕倍率须大于1。")
    number(rules["basic_living_cost"] * rules["wealthy_income_multiplier"], "富裕收入阈值")
    mapping(rules["needs"], set(WEALTH), "群体需求")
    mapping(rules["wealth_effects"], set(WEALTH), "财富脆弱程度")
    for wealth in WEALTH:
        mapping(rules["needs"][wealth], {"grain", "daily_goods", "luxury_goods"}, "人均消费")
        resource_amounts(rules["needs"][wealth], "人均消费")
        number(rules["wealth_effects"][wealth], "财富脆弱系数", 0)
    grain_needs = {rules["needs"][wealth]["grain"] for wealth in WEALTH}
    if len(grain_needs) != 1 or next(iter(grain_needs)) <= 0:
        raise ValueError("三档人口必须使用相同且大于零的基本口粮需求。")
    effects = rules["wealth_effects"]
    if not effects["poor"] > effects["ordinary"] > effects["wealthy"] > 0:
        raise ValueError("缺粮脆弱系数必须贫困高于普通、普通高于富裕。")
    for key in ("grain_death_rate", "grain_labor_penalty", "labor_recovery",
                "descent_grain_rate", "descent_goods_rate"):
        number(rules[key], key, 0, 1)
    for key in ("grain_health_penalty", "grain_satisfaction_penalty", "daily_satisfaction_penalty",
                "luxury_satisfaction_penalty", "health_recovery", "satisfaction_recovery"):
        number(rules[key], key, 0, 100)
    number(rules["streak_increment"], "连续缺粮增幅", 0, 1)
    number(rules["streak_cap"], "连续缺粮放大上限", 0, 360, integer=True)
    if rules["settlement_order"] != "production_then_consumption" or rules["rounding"] != "carry_fraction":
        raise ValueError("本规则版本只支持先生产后消费、人口保留小数余量。")


def validate_county(county: Any, pools: dict, rules: dict) -> None:
    mapping(county, {"id", "name", "description", "parent_id", "pool_ids", "population", "land",
                     "facilities", "industries", "specialties", "modifiers", "notices"}, "县档案")
    for key in ("id", "name", "description", "parent_id"):
        text_value(county[key], f"县/{key}")
    mapping(county["pool_ids"], set(OWNERS), "县资源池引用")
    if len(set(county["pool_ids"].values())) != 3:
        raise ValueError("三种归属必须引用不同资源池。")
    for owner, identifier in county["pool_ids"].items():
        if identifier not in pools or pools[identifier]["owner"] != owner:
            raise ValueError("县资源池引用缺失或产权不匹配。")
    population = mapping(county["population"], {"cohorts", "shortage_turns", "birth_remainder", "natural_death_remainder"}, "人口底账")
    number(population["shortage_turns"], "连续缺粮旬数", integer=True)
    for key in ("birth_remainder", "natural_death_remainder"):
        number(population[key], key, 0, 1)
        if population[key] >= 1:
            raise ValueError("全县出生和自然死亡余量须小于1。")
    cohorts = records(population["cohorts"], "人口群体")
    identities = set()
    for cohort in cohorts:
        mapping(cohort, {"id", "occupation", "wealth", "resident_status", "count", "income_per_capita", "health", "satisfaction",
                         "labor_factor", "death_remainder", "descent_remainder"}, "人口群体")
        text_value(cohort["id"], "人口群体编号")
        if (cohort["wealth"] not in WEALTH or cohort["occupation"] not in OCCUPATIONS
                or cohort["resident_status"] not in {"settled", "displaced"}):
            raise ValueError("人口职业、财富或居住身份无效。")
        identity = (cohort["occupation"], cohort["wealth"], cohort["resident_status"])
        if identity in identities:
            raise ValueError("职业、财富与居住身份的交叉群体重复。")
        identities.add(identity)
        number(cohort["count"], "群体人数", integer=True)
        number(cohort["income_per_capita"], "人均旬收入")
        if wealth_for_income(cohort["income_per_capita"], rules) != cohort["wealth"]:
            raise ValueError("财富档须与人均收入相对基本生活成本的分档一致。")
        for key in ("health", "satisfaction"):
            number(cohort[key], key, 0, 100)
        number(cohort["labor_factor"], "劳力状态", 0, 1)
        for key in ("death_remainder", "descent_remainder"):
            # Income reclassification can merge multiple fractional expectations.
            number(cohort[key], key, 0)
    _unique(cohorts, "人口群体")
    number(sum(row["count"] for row in cohorts), "县总人口", integer=True)
    expected = {(occupation, wealth, status) for occupation in OCCUPATIONS for wealth in WEALTH
                for status in ("settled", "displaced")}
    if identities != expected:
        raise ValueError("须保留七职业、三财富档与两居住身份的42个群体，允许人数为零。")
    land = mapping(county["land"], {"total_area", "parcels"}, "土地")
    number(land["total_area"], "县域面积")
    parcels = records(land["parcels"], "土地分类")
    for parcel in parcels:
        mapping(parcel, {"id", "label", "area", "use", "owner", "fertility", "irrigation", "reclaimable"}, "土地")
        for key in ("id", "label"):
            text_value(parcel[key], f"土地/{key}")
        if parcel["owner"] not in OWNERS or parcel["use"] not in {"farmland", "forest", "mine", "settlement", "unused"}:
            raise ValueError("土地用途或产权无效。")
        number(parcel["area"], "土地面积")
        number(parcel["fertility"], "地力", 0, 2)
        number(parcel["irrigation"], "灌溉条件", 0, 1)
        number(parcel["reclaimable"], "可垦面积", 0, parcel["area"])
        if parcel["use"] != "unused" and parcel["reclaimable"]:
            raise ValueError("可垦潜力只属于未利用土地。")
    _unique(parcels, "土地")
    if not math.isclose(sum(row["area"] for row in parcels), land["total_area"], abs_tol=1e-6):
        raise ValueError("土地用途面积之和与县域面积不一致。")
    facilities = records(county["facilities"], "设施")
    for facility in facilities:
        mapping(facility, {"id", "label", "owner", "kind", "condition", "description"}, "设施")
        for key in ("id", "label", "kind", "description"):
            text_value(facility[key], f"设施/{key}")
        if facility["owner"] not in OWNERS:
            raise ValueError("设施产权无效。")
        number(facility["condition"], "设施状况", 0, 1)
    _unique(facilities, "设施")
    assets = {row["id"]: row for row in parcels + facilities}
    if len(assets) != len(parcels) + len(facilities):
        raise ValueError("土地和设施编号不得重复。")
    industries = records(county["industries"], "经营群体")
    used_assets = set()
    for industry in industries:
        mapping(industry, {"id", "label", "category", "asset_id", "scale", "workers_needed", "technology",
                           "inputs", "outputs", "cycle_turns", "sow_month", "sow_xun", "harvest_month", "harvest_xun",
                           "progress", "active", "sown_ratio", "state", "last_output", "last_input_ratio", "last_labor_ratio"}, "经营群体")
        for key in ("id", "label", "state"):
            text_value(industry[key], f"经营/{key}")
        if industry["category"] not in CATEGORIES or industry["asset_id"] not in assets:
            raise ValueError("产业类别或关联资产无效。")
        if industry["asset_id"] in used_assets:
            raise ValueError("同一资产不能重复登记生产规模。")
        used_assets.add(industry["asset_id"])
        for key in ("scale", "workers_needed", "technology", "progress"):
            number(industry[key], f"经营/{key}")
        if industry["scale"] > 0 and industry["workers_needed"] <= 0:
            raise ValueError("正在经营的产业须有正数劳力需求。")
        number(industry["cycle_turns"], "生产周期", 1, 360, integer=True)
        if industry["progress"] > industry["cycle_turns"]:
            raise ValueError("生产进度超过周期。")
        if type(industry["active"]) is not bool:
            raise ValueError("生产阶段标记须为布尔值。")
        for key in ("sown_ratio", "last_input_ratio", "last_labor_ratio"):
            number(industry[key], key, 0, 1)
        for key in ("inputs", "outputs", "last_output"):
            resource_amounts(industry[key], f"经营/{key}")
            if industry[key].get("money", 0) and key in {"outputs", "last_output"}:
                raise ValueError("实物生产不能凭空生成钱。")
        for key in ("sow_month", "harvest_month"):
            number(industry[key], key, 1, 12, integer=True)
        for key in ("sow_xun", "harvest_xun"):
            number(industry[key], key, 1, 3, integer=True)
        if industry["category"] == "agriculture":
            asset = assets[industry["asset_id"]]
            if asset.get("use") != "farmland" or industry["scale"] > asset["area"]:
                raise ValueError("农业种植须关联足够面积的耕地。")
            start = (industry["sow_month"] - 1) * 3 + industry["sow_xun"]
            end = (industry["harvest_month"] - 1) * 3 + industry["harvest_xun"]
            if end < start or industry["cycle_turns"] != end - start + 1:
                raise ValueError("演示农季须在同年内，生长周期与播收日期一致。")
    _unique(industries, "经营群体")
    for item in records(county["specialties"], "特产"):
        mapping(item, {"name", "description"}, "特产")
        for key in item:
            text_value(item[key], f"特产/{key}")
    for modifier in records(county["modifiers"], "当地修正"):
        mapping(modifier, {"name", "description", "target", "multiplier"}, "当地修正")
        for key in ("name", "description", "target"):
            text_value(modifier[key], f"修正/{key}")
        if modifier["target"] not in {"all", *CATEGORIES}:
            raise ValueError("当地修正目标无效。")
        number(modifier["multiplier"], "当地修正倍率", 0, 5)
    for notice in records(county["notices"], "范围说明"):
        text_value(notice, "范围说明")


def validate_report(report: Any) -> None:
    mapping(report, {"turn_index", "month", "xun", "summary", "production", "consumption", "groups", "deaths",
                     "moved_down", "population_before", "population_after", "grain_shortage_ratio", "pool_changes",
                     "births", "natural_deaths", "shortage_deaths"}, "旬报")
    number(report["turn_index"], "旬报编号", integer=True)
    number(report["month"], "旬报月份", 1, 12, integer=True)
    number(report["xun"], "旬报旬", 1, 3, integer=True)
    text_value(report["summary"], "旬报摘要")
    for key in ("deaths", "moved_down", "population_before", "population_after", "births", "natural_deaths", "shortage_deaths"):
        number(report[key], key, integer=True)
    number(report["grain_shortage_ratio"], "粮食缺口", 0, 1)
    if report["deaths"] != report["natural_deaths"] + report["shortage_deaths"]:
        raise ValueError("总死亡须等于自然死亡与缺粮额外死亡之和。")
    if report["population_before"] + report["births"] - report["deaths"] != report["population_after"]:
        raise ValueError("旬报人口变化不守恒。")
    for row in records(report["production"], "生产报告"):
        mapping(row, {"id", "label", "owner", "inputs", "outputs", "labor_used", "labor_ratio", "input_ratio", "progress", "state"}, "生产报告")
        for key in ("id", "label", "state"):
            text_value(row[key], key)
        if row["owner"] not in OWNERS:
            raise ValueError("生产报告产权无效。")
        resource_amounts(row["inputs"], "生产投入")
        resource_amounts(row["outputs"], "生产产出")
        for key in ("labor_used", "progress"):
            number(row[key], key)
        for key in ("labor_ratio", "input_ratio"):
            number(row[key], key, 0, 1)
    for row in records(report["consumption"], "消费报告"):
        mapping(row, {"resource", "label", "demand", "consumed", "shortage", "fulfillment"}, "消费报告")
        if row["resource"] not in {"grain", "daily_goods", "luxury_goods"}:
            raise ValueError("消费报告资源无效。")
        text_value(row["label"], "消费资源名")
        for key in ("demand", "consumed", "shortage"):
            number(row[key], key)
        number(row["fulfillment"], "需求满足率", 0, 1)
        if not math.isclose(row["consumed"] + row["shortage"], row["demand"], abs_tol=1e-5):
            raise ValueError("消费报告需求与实际缺口不一致。")
    if {row["resource"] for row in report["consumption"]} != {"grain", "daily_goods", "luxury_goods"} or len(report["consumption"]) != 3:
        raise ValueError("消费报告须包含三种消费资源。")
    for row in records(report["groups"], "群体报告"):
        mapping(row, {"id", "label", "population_before", "deaths", "moved_down", "mortality_risk", "health_penalty", "satisfaction_penalty", "labor_penalty",
                      "births", "natural_deaths", "shortage_deaths"}, "群体报告")
        if row["id"] not in WEALTH:
            raise ValueError("群体报告财富层无效。")
        text_value(row["label"], "群体名称")
        for key in ("population_before", "deaths", "moved_down", "births", "natural_deaths", "shortage_deaths"):
            number(row[key], key, integer=True)
        if row["deaths"] != row["natural_deaths"] + row["shortage_deaths"]:
            raise ValueError("群体总死亡与分项不一致。")
        if row["deaths"] + row["moved_down"] > row["population_before"]:
            raise ValueError("死亡及转出人口超过期初群体人数。")
        for key in ("mortality_risk", "labor_penalty"):
            number(row[key], key, 0, 1)
        for key in ("health_penalty", "satisfaction_penalty"):
            number(row[key], key, 0, 100)
    if {row["id"] for row in report["groups"]} != set(WEALTH) or len(report["groups"]) != 3:
        raise ValueError("群体报告须包含三档人口。")
    for key in ("deaths", "moved_down", "population_before", "births", "natural_deaths", "shortage_deaths"):
        if sum(row[key] for row in report["groups"]) != report[key]:
            raise ValueError("群体报告与全县汇总不一致。")
    if type(report["pool_changes"]) is not dict:
        raise ValueError("旬报资源流量须为字典。")
    for identifier, changes in report["pool_changes"].items():
        text_value(identifier, "旬报资源池编号")
        resource_amounts(changes, "资源流量", complete=True, signed=True)


def validate_economy(economy: Any) -> None:
    mapping(economy, {"schema_version", "rules_version", "demo", "scenario", "scenario_label", "scenario_description",
                      "last_settled_turn", "county", "pools", "rules", "history"}, "经济档案")
    if type(economy["schema_version"]) is not int or economy["schema_version"] != 2:
        raise ValueError("不支持的经济结构版本。")
    if type(economy["rules_version"]) is not int or economy["rules_version"] != 2 or economy["demo"] is not True:
        raise ValueError("新版人口仅支持规则版本2的一县演示。")
    for key in ("scenario", "scenario_label", "scenario_description"):
        text_value(economy[key], key)
    if economy["scenario"] not in {"normal", "shortage", "input_shortage"}:
        raise ValueError("经济演示情境无效。")
    number(economy["last_settled_turn"], "上次结算旬", -1, integer=True)
    if type(economy["pools"]) is not dict or len(economy["pools"]) != 3:
        raise ValueError("一县演示须有民间、官府、皇家三个资源池。")
    for identifier, pool in economy["pools"].items():
        text_value(identifier, "资源池编号")
        mapping(pool, {"id", "owner", "label", "balances"}, "资源池")
        if pool["id"] != identifier or pool["owner"] not in OWNERS:
            raise ValueError("资源池编号或产权无效。")
        text_value(pool["label"], "资源池名称")
        resource_amounts(pool["balances"], "资源池余额", complete=True)
    validate_rules(economy["rules"])
    validate_county(economy["county"], economy["pools"], economy["rules"])
    history = records(economy["history"], "经济历史")
    if len(history) > economy["rules"]["history_limit"]:
        raise ValueError("经济历史超过保存上限。")
    previous = None
    previous_report = None
    for report in history:
        validate_report(report)
        if previous is not None and report["turn_index"] != previous + 1:
            raise ValueError("经济历史旬编号不连续。")
        if set(report["pool_changes"]) != set(economy["pools"]):
            raise ValueError("经济报告资源池引用无效。")
        if previous_report is not None:
            expected_slot = ((previous_report["month"] - 1) * 3 + previous_report["xun"]) % 36
            if (report["month"] - 1) * 3 + report["xun"] - 1 != expected_slot:
                raise ValueError("经济历史的月份与旬不连续。")
            if report["population_before"] != previous_report["population_after"]:
                raise ValueError("经济历史的人口底账不连续。")
        previous = report["turn_index"]
        previous_report = report
    if (not history and economy["last_settled_turn"] != -1) or (history and previous != economy["last_settled_turn"]):
        raise ValueError("经济结算标记与旬报不一致。")
    if history and history[-1]["population_after"] != sum(c["count"] for c in economy["county"]["population"]["cohorts"]):
        raise ValueError("人口底账与最近旬报不一致。")
