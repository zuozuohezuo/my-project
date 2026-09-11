"""One shared private pool. Demand is deducted directly, with no reserved stock."""

from .models import RESOURCES


def consume(county: dict, pools: dict, rules: dict) -> list[dict]:
    balances = pools[county["pool_ids"]["private"]]["balances"]
    report = []
    for resource in ("grain", "daily_goods", "luxury_goods"):
        demand = sum(row["count"] * rules["needs"][row["wealth"]][resource]
                     for row in county["population"]["cohorts"])
        consumed = min(balances[resource], demand)
        balances[resource] = max(0, balances[resource] - consumed)
        report.append({"resource": resource, "label": RESOURCES[resource][0],
                       "demand": demand, "consumed": consumed, "shortage": max(0, demand - consumed),
                       "fulfillment": min(1, consumed / demand) if demand else 1.0})
    return report

