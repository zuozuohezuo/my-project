"""Serializable domain data. Demo numbers are not settled game design."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol

from .emperor import EmperorProfile, validate_health_value
from .turns.appointments import Appointment


class Phase(str, Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    REMONSTRANCE = "remonstrance"
    INTERRUPTED = "interrupted"


ACTIVITY_LABELS = {
    "court": "早朝",
    "paperwork": "批阅章奏",
    "audience": "召见臣工",
    "palace": "处理宫廷事务",
    "lecture": "日讲",
    "rest": "休息",
    "study": "读书",
    "exercise": "习武",
    "private": "私生活",
    "garden": "宫苑游赏",
    "calligraphy": "书法",
}

WORK_ACTIVITIES = {"court", "paperwork", "audience", "palace", "lecture"}
OFFICE_ACTIVITIES = {"paperwork", "audience", "palace"}


@dataclass
class Activity:
    id: str = ""
    kind: str = "rest"
    status: str = "pending"
    cost: int = 1
    spent_ap: int = 0
    stage: str = "planned"
    scene: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    appointment_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def category(self) -> str:
        return "work" if self.kind in WORK_ACTIVITIES else "private"

    @property
    def turn_stage(self) -> str:
        return "court" if self.kind == "court" else self.category

    @property
    def reserved_ap(self) -> int:
        return self.spent_ap if self.status in {"stopped", "cancelled"} else self.cost

    @property
    def label(self) -> str:
        return self.parameters.get("appointment_label") or ACTIVITY_LABELS.get(self.kind, self.kind)


@dataclass(frozen=True)
class CommandDefinition:
    id: str
    label: str
    cost: int = 1
    cooldown_turns: int = 0
    emergency_only: bool = False
    notes: str = ""


@dataclass
class DemoConfig:
    edicts_per_turn: int = 3
    # Illustrative thresholds only; activities do not change health in this build.
    health_ap_thresholds: list[list[int]] = field(
        default_factory=lambda: [[0, 10], [40, 20], [80, 30]]
    )
    initial_health: int = 100
    initial_year: int = 1
    initial_month: int = 1
    initial_xun: int = 1
    tax_cooldown_turns: int = 3
    seed: int = 1
    turn_rules_version: int = 3

    def action_points(self, health: int) -> int:
        eligible = [points for threshold, points in self.health_ap_thresholds if health >= threshold]
        return eligible[-1] if eligible else 0

    def validate(self) -> None:
        if self.turn_rules_version not in {1, 2, 3}:
            raise ValueError("回合规则版本必须为1、2或3。")
        validate_health_value(self.initial_health)
        if type(self.initial_year) is not int or not 1 <= self.initial_year <= 9999:
            raise ValueError("开局公元年份必须为1至9999的整数。")
        if self.edicts_per_turn < 1 or self.tax_cooldown_turns < 0:
            raise ValueError("演示诏书上限必须为正，CD不能为负。")
        if not self.health_ap_thresholds or self.health_ap_thresholds != sorted(self.health_ap_thresholds):
            raise ValueError("行动力阈值必须按健康值升序配置。")
        if any(points < 1 for _, points in self.health_ap_thresholds):
            raise ValueError("演示行动力必须为正数。")
        if not 1 <= self.initial_month <= 12 or not 1 <= self.initial_xun <= 3:
            raise ValueError("初始月/旬超出范围。")


@dataclass(frozen=True)
class ScenarioProfile:
    """Player's opening identity, separate from the historical source snapshot."""

    scenario_name: str = "明朝·弘治十三年"
    emperor_name: str = "朱祐樘"
    era_name: str = "弘治"
    era_start_year: int = 1488

    def validate(self, initial_year: int) -> None:
        if type(initial_year) is not int or not 1 <= initial_year <= 9999:
            raise ValueError("开局公元年份必须为1至9999的整数。")
        for label, value, limit in (
            ("剧本名称", self.scenario_name, 80),
            ("皇帝姓名", self.emperor_name, 40),
            ("年号", self.era_name, 24),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"{label}须为1至{limit}个字符的非空文本。")
            if any(ord(character) < 32 or ord(character) == 127 for character in value):
                raise ValueError(f"{label}不能包含换行或控制字符。")
        if (type(self.era_start_year) is not int
                or not 1 <= self.era_start_year <= initial_year):
            raise ValueError("年号起算公元年必须为正整数，且不能晚于开局年份。")

    @classmethod
    def for_initial_year(cls, year: int, *, legacy: bool = False) -> ScenarioProfile:
        """Infer only missing identity; do not re-date the historical world data."""
        if year == 1500:
            return cls()
        return cls("旧版演示剧本" if legacy else "自定义剧本", "未设定皇帝", "元初", year)


@dataclass
class ActionResult:
    status: str
    message: str
    record_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"ok", "issued", "cancelled", "advanced", "completed", "resolved"}


@dataclass
class PlannedCommand:
    id: str
    command_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"


@dataclass
class TurnPlan:
    turn_index: int
    activities: list[str | dict[str, Any]]
    commands: list[PlannedCommand] = field(default_factory=list)
    status: str = "pending"
    work_budget: int | None = None


@dataclass
class EmergencyEvent:
    id: str
    title: str
    description: str
    trigger_turn: int
    status: str = "pending"
    allowed_commands: list[str] = field(default_factory=lambda: ["emergency_response"])
    replacement_activity_id: str | None = None
    demo: bool = True


@dataclass
class PendingCommand:
    command_id: str
    parameters: dict[str, Any]
    cooldown_key: str
    planned_command_id: str | None = None
    emergency_event_id: str | None = None


@dataclass
class GameState:
    year: int = 1
    month: int = 1
    xun: int = 1
    turn_index: int = 0
    scenario_profile: ScenarioProfile = field(default_factory=ScenarioProfile)
    emperor: EmperorProfile = field(default_factory=EmperorProfile)
    phase: Phase = Phase.PLANNING
    health: int = 100
    ap_capacity: int = 30
    work_budget: int = 20
    activity_cursor: int = 0
    turn_stage: str = "court"
    stage_initial_work_budget: int = 20
    stage_transfers: list[dict[str, Any]] = field(default_factory=list)
    emergency_timing: dict[str, dict[str, Any]] = field(default_factory=dict)
    activities: list[Activity] = field(default_factory=list)
    completion_records: list[dict[str, Any]] = field(default_factory=list)
    objective_record_starts: dict[str, int] = field(default_factory=dict)
    work_items: list[dict[str, Any]] = field(default_factory=list)
    appointments: list[Appointment] = field(default_factory=list)
    appointment_consequences: list[dict[str, Any]] = field(default_factory=list)
    court_open: bool = False
    edict_limit: int = 3
    edict_available: int = 3
    edict_debt: int = 0
    edicts_spent_this_turn: int = 0
    month_plan: list[TurnPlan] = field(default_factory=list)
    emergencies: list[EmergencyEvent] = field(default_factory=list)
    active_emergency_id: str | None = None
    pending_command: PendingCommand | None = None
    cooldowns: dict[str, int] = field(default_factory=dict)
    command_ledger: list[dict[str, Any]] = field(default_factory=list)
    policy_settings: dict[str, Any] = field(default_factory=dict)
    pending_effects: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    world_snapshot: dict[str, Any] = field(default_factory=dict)
    economy: dict[str, Any] | None = None
    reports: list[dict[str, Any]] = field(default_factory=list)
    random_state: dict[str, Any] = field(default_factory=lambda: {"seed": 1, "draws": 0})
    next_id: int = 1
    notes: list[str] = field(default_factory=lambda: [
        "整旬共用30行动力；健康暂按10／20／30档，属于可配置演示值。",
        "每旬3份诏书、改税CD为3旬，属于可配置演示值。",
        "未使用行动力不会自动补齐；须显式选择补足休息后推进。",
        "诏书透支先扣下一旬额度；若债务超过单旬额度，演示暂按逐旬扣还。",
        "急报仅手动注入演示，不运行自然事件与地方自主决策。",
        "政令、活动、劝谏惩罚均只记录待模拟效果，不改变健康、钱粮、民心等世界指标。",
        "留空参数原样保留为委派意图，本版不运行官员补全与决策。",
        "存档记录种子及随机调用计数；本版没有随机抽取。",
    ])

    @property
    def ap_allocated(self) -> int:
        return sum(activity.reserved_ap for activity in self.activities)

    @property
    def ap_spent(self) -> int:
        return sum(activity.spent_ap for activity in self.activities)

    @property
    def private_budget(self) -> int:
        return self.ap_capacity - self.work_budget

    @property
    def work_allocated(self) -> int:
        return sum(activity.reserved_ap for activity in self.activities if activity.category == "work")

    @property
    def private_allocated(self) -> int:
        return self.ap_allocated - self.work_allocated

    @property
    def stage_budget(self) -> dict[str, int]:
        court = sum(activity.reserved_ap for activity in self.activities if activity.kind == "court")
        return {"court": court, "work": self.work_budget - court, "private": self.private_budget}

    @property
    def stage_spent(self) -> dict[str, int]:
        return {stage: sum(activity.spent_ap for activity in self.activities if activity.turn_stage == stage)
                for stage in ("court", "work", "private")}

    @property
    def stage_remaining(self) -> dict[str, int]:
        return {stage: budget - self.stage_spent[stage] for stage, budget in self.stage_budget.items()}

    @property
    def stage_unallocated(self) -> dict[str, int]:
        return {stage: budget - sum(activity.reserved_ap for activity in self.activities
                                   if activity.turn_stage == stage)
                for stage, budget in self.stage_budget.items()}

    @property
    def ap_remaining(self) -> int:
        return self.ap_capacity - self.ap_allocated

    @property
    def court_assigned(self) -> bool:
        return any(activity.kind == "court" and activity.status != "replaced" for activity in self.activities)

    @property
    def date_label(self) -> str:
        return f"{self.year}年{self.month}月{['上旬', '中旬', '下旬'][self.xun - 1]}"

    @property
    def era_year(self) -> int:
        return self.year - self.scenario_profile.era_start_year + 1

    @property
    def era_date_label(self) -> str:
        era_year = "元" if self.era_year == 1 else str(self.era_year)
        return f"{self.scenario_profile.era_name}{era_year}年{self.month}月{['上旬', '中旬', '下旬'][self.xun - 1]}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["phase"] = self.phase.value
        if self.economy is None:
            data.pop("economy")
        return data


class LocalDecisionProvider(Protocol):
    """Future extension point. This release never calls local-world simulation."""

    def propose_actions(self, local_observation: dict[str, Any], mandate: dict[str, Any]) -> list[dict[str, Any]]:
        ...
