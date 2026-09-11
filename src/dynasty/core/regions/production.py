"""Limited labor and materials, followed by completed batches and seasonal harvests."""

from .population import available_labor


def produce(county: dict, pools: dict, rules: dict, month: int, xun: int) -> list[dict]:
    assets = {row["id"]: row for row in county["land"]["parcels"] + county["facilities"]}
    industries = sorted(county["industries"], key=lambda row: row["id"])
    slot = (month - 1) * 3 + xun
    requests = {}
    for industry in industries:
        agricultural = industry["category"] == "agriculture"
        start = (industry["sow_month"] - 1) * 3 + industry["sow_xun"]
        end = (industry["harvest_month"] - 1) * 3 + industry["harvest_xun"]
        in_season = not agricultural or (start <= slot <= end and (
            industry["active"] or month == industry["sow_month"]))
        requests[industry["id"]] = industry["workers_needed"] if in_season and industry["scale"] > 0 else 0
    demand = sum(requests.values())
    labor_ratio = min(1, available_labor(county, rules) / demand) if demand else 1.0
    # Share scarce materials proportionally against the same opening balances.
    # These are local calculation inputs, never an additional inventory or reserved balance.
    material_requests = {}
    totals = {identifier: {} for identifier in pools}
    for industry in industries:
        asset = assets[industry["asset_id"]]
        pool_id = county["pool_ids"][asset["owner"]]
        condition = asset.get("condition", 0.75 + 0.25 * asset.get("irrigation", 1))
        capacity = labor_ratio * condition
        agricultural = industry["category"] == "agriculture"
        needs = {}
        if requests[industry["id"]] > 0 and capacity > 0:
            if not agricultural:
                needs = {key: amount * capacity for key, amount in industry["inputs"].items()}
            elif not industry["active"] and month == industry["sow_month"]:
                needs = dict(industry["inputs"])
        material_requests[industry["id"]] = needs
        for resource, amount in needs.items():
            totals[pool_id][resource] = totals[pool_id].get(resource, 0) + amount
    material_ratios = {identifier: {resource: min(1, pools[identifier]["balances"][resource] / amount)
                                    if amount else 1 for resource, amount in needs.items()}
                       for identifier, needs in totals.items()}
    reports = []
    for industry in industries:
        asset = assets[industry["asset_id"]]
        owner = asset["owner"]
        pool_id = county["pool_ids"][owner]
        balances = pools[pool_id]["balances"]
        shared_fraction = min([1.0] + [material_ratios[pool_id][key]
                                       for key, amount in material_requests[industry["id"]].items() if amount > 0])
        report = {"id": industry["id"], "label": industry["label"], "owner": owner,
                  "inputs": {}, "outputs": {}, "labor_used": 0.0, "labor_ratio": labor_ratio,
                  "input_ratio": 1.0, "progress": industry["progress"], "state": "未到农时"}
        industry["last_output"] = {}
        agricultural = industry["category"] == "agriculture"
        start = (industry["sow_month"] - 1) * 3 + industry["sow_xun"]
        end = (industry["harvest_month"] - 1) * 3 + industry["harvest_xun"]
        eligible = (not agricultural or start <= slot <= end) and industry["scale"] > 0
        if eligible:
            condition = asset.get("condition", 0.75 + 0.25 * asset.get("irrigation", 1))
            capacity = labor_ratio * condition
            if agricultural:
                if not industry["active"] and month == industry["sow_month"] and slot >= start and capacity > 0:
                    fraction = shared_fraction
                    report["input_ratio"] = fraction
                    if fraction > 0:
                        for key, amount in industry["inputs"].items():
                            paid = amount * fraction
                            balances[key] = max(0, balances[key] - paid)
                            report["inputs"][key] = paid
                        industry["active"] = True
                        industry["sown_ratio"] = fraction
                        industry["progress"] = 0
                if industry["active"]:
                    step = capacity * industry["sown_ratio"]
                    industry["progress"] = min(industry["cycle_turns"], industry["progress"] + step)
                    report["labor_used"] = requests[industry["id"]] * step
                    report["state"] = "生长中"
                    if slot == end:
                        yield_ratio = industry["progress"] / industry["cycle_turns"]
                        report["outputs"] = {key: amount * yield_ratio for key, amount in industry["outputs"].items()}
                        industry["active"] = False
                        report["state"] = "已收获"
                else:
                    report["state"] = "投入不足" if month == industry["sow_month"] else "等待下次播种"
                    report["input_ratio"] = 0.0
            else:
                wanted = material_requests[industry["id"]]
                fraction = shared_fraction
                step = capacity * fraction
                report["input_ratio"] = fraction
                for key, amount in wanted.items():
                    paid = amount * fraction
                    balances[key] = max(0, balances[key] - paid)
                    report["inputs"][key] = paid
                industry["progress"] += step
                industry["active"] = step > 0
                report["labor_used"] = requests[industry["id"]] * step
                report["state"] = "生产中" if fraction > 0 else "投入不足"
                if industry["progress"] + 1e-9 >= industry["cycle_turns"]:
                    industry["progress"] = max(0, industry["progress"] - industry["cycle_turns"])
                    report["outputs"] = dict(industry["outputs"])
                    report["state"] = "本旬完工"
            if capacity <= 0:
                report["state"] = "设施停工" if condition <= 0 else "劳力不足"
            elif labor_ratio < 1 and report["state"] in {"生长中", "生产中"}:
                report["state"] += "（劳力不足）"
            multiplier = industry["technology"] * (asset.get("fertility", 1) if agricultural else 1)
            for modifier in county["modifiers"]:
                if modifier["target"] in {"all", industry["category"]}:
                    multiplier *= modifier["multiplier"]
            report["outputs"] = {key: amount * multiplier for key, amount in report["outputs"].items()}
        industry["state"] = report["state"]
        industry["last_output"] = dict(report["outputs"])
        industry["last_input_ratio"] = report["input_ratio"]
        industry["last_labor_ratio"] = labor_ratio
        report["progress"] = industry["progress"]
        reports.append(report)
    # Inputs are taken before any output enters a pool, so list order cannot create same-turn chains.
    for report in reports:
        balances = pools[county["pool_ids"][report["owner"]]]["balances"]
        for resource, amount in report["outputs"].items():
            balances[resource] += amount
    return reports
