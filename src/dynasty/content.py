"""Read-only, provenance-aware historical content adapters."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from dynasty.core import DemoConfig, GameSession, ScenarioProfile


def project_root() -> Path:
    override = os.environ.get("DYNASTY_ROOT")
    if override:
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    location = base / "MingDynastySimulator"
    location.mkdir(parents=True, exist_ok=True)
    return location


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_demo_config(root: Path | None = None) -> DemoConfig:
    """Load new-game defaults; saves retain the configuration they were created with."""
    payload = read_json((root or project_root()) / "data" / "config" / "framework.json")
    if payload is None:
        return DemoConfig(initial_year=1500)
    if payload.get("schema_version") != 1:
        raise ValueError("不支持的框架配置版本。")
    if payload.get("world_simulation_enabled") is not False:
        raise ValueError("当前框架尚未实现世界数值模拟，配置必须保持 false。")
    config = DemoConfig(**payload["demo"])
    config.validate()
    return config


def create_county_demo(scenario: str = "normal", root: Path | None = None) -> GameSession:
    """New isolated county fixture; historical scenarios remain economically disabled."""
    from dynasty.core.regions.economy import create_demo_economy
    location = root or project_root()
    payload = read_json(location / "data" / "config" / "county_demo.json")
    if not isinstance(payload, dict):
        raise ValueError("缺少县级演示数据文件。")
    config = load_demo_config(location)
    config.turn_rules_version = 3
    config.initial_year = 1500
    config.initial_month = 1
    config.initial_xun = 1
    economy = create_demo_economy(payload, scenario)
    profile = ScenarioProfile("清河县 · 县级经济演示", "朱祐樘", "弘治", 1488)
    world = {"scenario": "county_economy_demo", "simulation_enabled": True,
             "simulation_scope": "one_demo_county", "reference_year": 1500,
             "regions": [], "metrics": {}, "notes": "虚构演示县；各项数据不是历史复原。"}
    return GameSession.new_game(world, config, profile, economy=economy)


class HistoryRepository:
    categories = {
        "people": "人物", "regions": "两京十三司", "prefectures": "府州",
        "counties": "州县", "offices": "官职", "laws": "法令",
    }

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or project_root()
        self.directory = self.root / "data" / "history"
        self.metadata: dict[str, dict] = {}
        self.tables: dict[str, list[dict]] = {}
        for key in self.categories:
            payload = read_json(self.directory / f"{key}.json", {})
            if isinstance(payload, list):
                self.tables[key] = payload
            else:
                self.metadata[key] = payload.get("metadata", {})
                self.tables[key] = payload.get("records", [])
        self.sources: dict[str, dict] = {}
        for path in sorted(self.directory.glob("sources_*.json")):
            payload = read_json(path, {})
            records = payload if isinstance(payload, list) else payload.get("records", payload.get("sources", []))
            if isinstance(records, dict):
                records = [{"id": key, **value} for key, value in records.items()]
            for record in records:
                self.sources[record.get("id", record.get("source_id", path.stem))] = record

    @property
    def regions(self) -> list[dict]:
        return self.tables["regions"]

    def by_id(self, category: str, identifier: str | None) -> dict | None:
        return next((row for row in self.tables[category] if row.get("id") == identifier), None)

    def region_rows(self, category: str, region_id: str) -> list[dict]:
        return [row for row in self.tables[category] if row.get("region_id") == region_id]

    def initial_world(self) -> dict:
        return {
            "scenario": "ming_1500_working_baseline",
            "reference_year": 1500,
            "simulation_enabled": False,
            "regions": [{"id": row["id"], "name": row["name"]} for row in self.regions],
            "metrics": {},
            "notes": "人口、钱粮、民心尚未建模；历史资料独立于运行存档。",
        }

    def summary(self) -> dict[str, int]:
        return {key: len(rows) for key, rows in self.tables.items()}
