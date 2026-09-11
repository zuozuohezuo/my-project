"""Pure-Python turn orchestration and optional, explicitly initialized county economy."""

from __future__ import annotations

import copy
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .emperor import BodyCondition, EmperorModifier, EmperorProfile, validate_health_value
from .motives import PersonalObjective
from .turns.activity_runner import ActivityRunnerMixin
from .turns.stage_runner import StageRunnerMixin
from .turns.appointments import Appointment, AppointmentMixin, validate_appointments

from .models import (
    ACTIVITY_LABELS, ActionResult, Activity, CommandDefinition, DemoConfig,
    EmergencyEvent, GameState, PendingCommand, Phase, PlannedCommand, ScenarioProfile, TurnPlan,
)


SAVE_VERSION = 3


class GameSession(StageRunnerMixin, ActivityRunnerMixin, AppointmentMixin):
    def __init__(self, state: GameState, config: DemoConfig | None = None) -> None:
        self.config = config or DemoConfig()
        self.config.validate()
        if not isinstance(state.scenario_profile, ScenarioProfile):
            raise ValueError("开局档案必须使用ScenarioProfile。")
        state.scenario_profile.validate(self.config.initial_year)
        if not isinstance(state.emperor, EmperorProfile):
            raise ValueError("皇帝属性技能档案必须使用EmperorProfile。")
        state.emperor.validate()
        validate_health_value(state.health)
        self.state = state
        self._validate_economy_state()
        self.command_definitions = {
            "change_tax": CommandDefinition("change_tax", "调整税率", 1, self.config.tax_cooldown_turns,
                                            notes="CD内再次改税触发劝谏；税率仅写入设置记录。"),
            "appoint_official": CommandDefinition("appoint_official", "任命官员", 1,
                                                  notes="只记录任命意图，不改历史人物任职事实。"),
            "build_canal": CommandDefinition("build_canal", "修建水利", 1,
                                             notes="只登记项目意图，不扣钱粮、不计算工程。"),
            "emergency_response": CommandDefinition("emergency_response", "紧急处置", 1,
                                                    emergency_only=True, notes="仅用于指定演示急报，可以透支。"),
        }

    @classmethod
    def new_game(cls, world_snapshot: dict[str, Any] | None = None,
                  config: DemoConfig | None = None,
                  profile: ScenarioProfile | None = None,
                  economy: dict[str, Any] | None = None) -> GameSession:
        config = copy.deepcopy(config or DemoConfig())
        config.validate()
        if profile is None:
            profile = ScenarioProfile.for_initial_year(config.initial_year)
        if not isinstance(profile, ScenarioProfile):
            raise ValueError("开局档案必须使用ScenarioProfile。")
        profile.validate(config.initial_year)
        state = GameState(
            year=config.initial_year, month=config.initial_month, xun=config.initial_xun,
            scenario_profile=copy.deepcopy(profile),
            health=config.initial_health, ap_capacity=config.action_points(config.initial_health),
            edict_limit=config.edicts_per_turn, edict_available=config.edicts_per_turn,
            world_snapshot=copy.deepcopy(world_snapshot or {}),
            economy=copy.deepcopy(economy),
            random_state={"seed": config.seed, "draws": 0},
            work_budget=min(20, config.action_points(config.initial_health)),
        )
        state.notes[0] = "健康→行动力阈值为" + "、".join(
            f"{threshold}→{points}" for threshold, points in config.health_ap_thresholds
        ) + "，属于可配置演示值。"
        state.notes[1] = f"每旬{config.edicts_per_turn}份诏书、改税CD为{config.tax_cooldown_turns}旬，属于可配置演示值。"
        session = cls(state, config)
        if config.turn_rules_version >= 2:
            state.work_items = [
                {"id": "work-demo-1", "title": "核阅地方仓储奏报", "kind": "paperwork", "complexity": 4, "progress": 0, "status": "pending"},
                {"id": "work-demo-2", "title": "会核河工勘报", "kind": "paperwork", "complexity": 7, "progress": 0, "status": "pending"},
                {"id": "work-demo-3", "title": "听取吏部用人陈述", "kind": "audience", "complexity": 5, "progress": 0, "status": "pending"},
                {"id": "work-demo-4", "title": "审阅宫苑修葺清册", "kind": "palace", "complexity": 4, "progress": 0, "status": "pending"},
            ]
        if config.turn_rules_version >= 3:
            session._stage_default_turn()
            state.notes[2] = "按早朝、工作、私生活依次推进；活动可预排或进入阶段后选择，早朝每旬默认安排且可取消。"
            state.notes[-1] = "工作剩余时间可单向转为私生活；急报位置按工作中点或私生活非最后行动排定，并保存送达位置。"
        if economy is not None:
            state.notes[3] = "县级经济演示已启用：实际旬末结算生产、消费和人口；其他国家系统仍待开发。"
            state.notes[5] = "县档案展示演示真值；历史全国经济和正式奏报过滤尚未启用。"
            session._log("开局", "建立县级经济演示；数值为可调整的游戏样例，不代表历史县情。")
        else:
            session._log("开局", "建立演示存档；世界数值模拟尚未启用。")
        return session

    def _validate_economy_state(self) -> None:
        if self.state.economy is None:
            return
        from .regions.economy import validate_economy
        validate_economy(self.state.economy)
        if self.config.turn_rules_version != 3:
            raise ValueError("县级经济演示须使用版本3行动规则；旧局保持原规则。")
        if self.state.economy["last_settled_turn"] != self.state.turn_index - 1:
            raise ValueError("县经济结算旬与存档日期不一致。")
        initial = (self.config.initial_year * 36 + (self.config.initial_month - 1) * 3
                   + self.config.initial_xun - 1)
        for report in self.state.economy["history"]:
            date = initial + report["turn_index"]
            if report["month"] != date % 36 // 3 + 1 or report["xun"] != date % 3 + 1:
                raise ValueError("县经济旬报日期与当前剧本的日历不一致。")

    @property
    def economy_view(self) -> dict[str, Any] | None:
        """Explicit demonstration view; never expose it as an imperial intelligence report."""
        if self.state.economy is None:
            return None
        from .regions.economy import county_view
        return copy.deepcopy(county_view(self.state.economy))

    def set_demo_economy_resource(self, owner: str, resource: str, value: float) -> ActionResult:
        if self.state.economy is None or self.state.economy.get("demo") is not True:
            return self._error("资源调整只用于县级演示局。")
        if self.state.phase != Phase.PLANNING:
            return self._error("请在旬初调整演示资源；本旬执行中保持结算条件不变。")
        if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
            return self._error("资源余额须为有限的非负数。")
        candidate = copy.deepcopy(self.state.economy)
        pool = next((item for item in candidate["pools"].values() if item["owner"] == owner), None)
        if pool is None or resource not in pool["balances"]:
            return self._error("请选择有效的资源归属与种类。")
        pool["balances"][resource] = value
        from .regions.economy import validate_economy
        try:
            validate_economy(candidate)
        except ValueError as error:
            return self._error(str(error))
        self.state.economy = candidate
        self._log("演示资源调整", f"{owner} / {resource} 余额设为 {value:g}；只影响当前演示存档。")
        return ActionResult("ok", "当前演示局的资源余额已调整。")

    def _demo_population_edit_error(self) -> ActionResult | None:
        economy = self.state.economy
        if economy is None or economy.get("demo") is not True or economy.get("schema_version") != 2:
            return self._error("人口参数调整只用于新版县级演示局；请从主菜单新建县级试玩。")
        if self.state.phase != Phase.PLANNING:
            return self._error("请在旬初调整人口参数；本旬执行中保持结算条件不变。")
        return None

    def set_demo_population_parameters(self, labor_ratio: float, annual_birth_rate: float,
                                       annual_death_rate: float, basic_living_cost: float) -> ActionResult:
        """Edit the current demo's population rules without advancing time or paying income."""
        error = self._demo_population_edit_error()
        if error is not None:
            return error
        from .regions.economy import update_population_parameters
        try:
            candidate = update_population_parameters(
                self.state.economy, labor_ratio=labor_ratio, annual_birth_rate=annual_birth_rate,
                annual_death_rate=annual_death_rate, basic_living_cost=basic_living_cost)
        except ValueError as error:
            return self._error(str(error))
        self.state.economy = candidate
        self._log("演示人口调整", f"劳动力比例{labor_ratio:.1%}，年出生率{annual_birth_rate:.2%}，"
                  f"年自然死亡率{annual_death_rate:.2%}；人均每旬基本生活成本{basic_living_cost:g}。")
        return ActionResult("ok", "人口参数已调整，后续按新参数结算；财富按当前收入重新评定。")

    def set_demo_population_income(self, cohort_id: str, income_per_capita: float) -> ActionResult:
        """Change an income cohort's means assessment while preserving occupation and pools."""
        error = self._demo_population_edit_error()
        if error is not None:
            return error
        from .regions.economy import update_population_income
        try:
            candidate = update_population_income(self.state.economy, cohort_id, income_per_capita)
        except ValueError as error:
            return self._error(str(error))
        self.state.economy = candidate
        self._log("演示收入调整", f"群体{cohort_id}人均每旬收入设为{income_per_capita:g}；按收入重新评定财富。")
        return ActionResult("ok", "人均收入与财富评定已更新，职业和资源池余额保持原值。")

    def advance_economy_demo_turn(self) -> ActionResult:
        """Explicit full-rest shortcut, through the same M03 activity and settlement path."""
        state = self.state
        if state.economy is None or state.economy.get("demo") is not True:
            return self._error("请先从主菜单开启县级经济演示。")
        if state.phase != Phase.PLANNING:
            return self._error("本旬已经开始，请在起居与朝政中完成活动后结算。")
        if any(event.status in {"pending", "active"} and event.trigger_turn <= state.turn_index
               for event in state.emergencies):
            return self._error("本旬有待送达急报，请通过起居与朝政处理。")
        if any(item.due_turn <= state.turn_index and item.status in {"pending", "scheduled"}
               for item in state.appointments):
            return self._error("本旬有预约，请先在起居与朝政处理。")
        plan = self._current_plan()
        if plan is not None and (plan.commands or plan.activities):
            return self._error("本旬已有三旬计划，请通过起居与朝政执行。")
        if any(activity.kind != "court" or activity.status != "pending" or activity.appointment_id
               for activity in state.activities):
            return self._error("本旬已有具体活动，请在起居与朝政执行或先撤下安排。")
        candidate = GameSession(copy.deepcopy(state), copy.deepcopy(self.config))
        result = candidate.set_turn_plan(["rest"] * state.ap_capacity, work_budget=0)
        if not result.ok:
            return result
        initial_turn = state.turn_index
        for _ in range(state.ap_capacity * 6 + 12):
            activity = candidate.current_activity
            if activity is not None and activity.stage == "ready":
                result = candidate.finish_activity()
            elif activity is not None and activity.kind == "rest" and activity.stage == "intro":
                result = candidate.continue_activity("continue")
            else:
                result = candidate.advance_turn()
            if result.status == "advanced":
                if candidate.state.turn_index != initial_turn + 1:
                    return self._error("演示推进未停在下一旬，原状态已保留。")
                self.state = candidate.state
                return ActionResult("advanced", "本旬已完整安排休息，县级经济结算一次并进入下一旬。")
            if result.status not in {"ok", "choice_required", "completed"}:
                return self._error(f"本旬需要手动处理，原状态已保留：{result.message}")
        return self._error("本旬尚有未完成活动，请通过起居与朝政继续。")

    @property
    def world_facts(self) -> dict[str, Any]:
        """Debug/research facts, not an in-world information entitlement."""
        return copy.deepcopy(self.state.world_snapshot)

    @property
    def logs(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.state.logs)

    @property
    def active_emergency(self) -> EmergencyEvent | None:
        return next((event for event in self.state.emergencies
                     if event.id == self.state.active_emergency_id), None)

    def _id(self, prefix: str) -> str:
        identifier = f"{prefix}-{self.state.next_id}"
        self.state.next_id += 1
        return identifier

    def _log(self, label: str, message: str) -> None:
        self.state.logs.append({"turn": self.state.turn_index, "label": label,
                                "message": message, "date": self.state.date_label})

    @staticmethod
    def _error(message: str) -> ActionResult:
        return ActionResult("error", message)

    def update_emperor_profile(self, attributes: dict[str, int],
                               skills: dict[str, int]) -> ActionResult:
        """Manual/cheat editor; validate every value before changing any state."""
        candidate = copy.deepcopy(self.state.emperor)
        candidate.attributes = attributes
        candidate.skills = skills
        try:
            candidate.validate()
        except ValueError as error:
            return self._error(str(error))
        self.state.emperor = copy.deepcopy(candidate)
        return ActionResult("ok", "皇帝属性与技能已更新。")

    def update_emperor_modifiers(self, modifiers: list[EmperorModifier]) -> ActionResult:
        """Replace explicit effects without changing base abilities or time."""
        candidate = copy.deepcopy(self.state.emperor)
        candidate.modifiers = modifiers
        try:
            candidate.validate()
        except ValueError as error:
            return self._error(str(error))
        self.state.emperor = copy.deepcopy(candidate)
        return ActionResult("ok", "皇帝长期与短期修正已更新。")

    def update_emperor_personality(self, personality: dict[str, int]) -> ActionResult:
        """Edit preferences without imposing formulas, costs or automatic actions."""
        candidate = copy.deepcopy(self.state.emperor)
        candidate.personality = personality
        try:
            candidate.validate()
        except ValueError as error:
            return self._error(str(error))
        self.state.emperor = copy.deepcopy(candidate)
        return ActionResult("ok", "皇帝九项性格倾向已更新。")

    def add_emperor_objective(self, kind: str, title: str, description: str,
                              activity_kind: str, target_count: int) -> ActionResult:
        objective = PersonalObjective("pending-objective", kind, title, description,
                                      activity_kind, target_count)
        try:
            objective.validate()
        except ValueError as error:
            return self._error(str(error))
        if any(item.status == "active"
               and (item.kind, item.title, item.description, item.activity_kind, item.target_count)
               == (kind, title, description, activity_kind, target_count)
               for item in self.state.emperor.objectives):
            return self._error("已有完全相同且尚未满足的人物目标。")
        objective.id = self._id("objective")
        existing_ids = {item.id for item in self.state.emperor.objectives}
        while objective.id in existing_ids:
            objective.id = self._id("objective")
        self.state.emperor.objectives.append(objective)
        self.state.objective_record_starts[objective.id] = len(self.state.completion_records)
        return ActionResult("ok", "已开始追求目标；完成对应活动后才会积累进度。", objective.id)

    def discard_emperor_objective(self, objective_id: str) -> ActionResult:
        objective = next((item for item in self.state.emperor.objectives
                          if item.id == objective_id), None)
        if objective is None:
            return self._error("未找到该人物目标。")
        if objective.status != "active":
            return self._error("已满足的目标保留为完成记录，不能撤下。")
        self.state.emperor.objectives.remove(objective)
        return ActionResult("ok", "已撤下未完成的人物目标。", objective.id)

    def update_emperor_health(self, health: int, pressure: int,
                              body_conditions: list[BodyCondition]) -> ActionResult:
        """Edit health atomically, preserving the validity of committed plans."""
        candidate = copy.deepcopy(self.state.emperor)
        candidate.pressure = pressure
        candidate.body_conditions = body_conditions
        try:
            validate_health_value(health)
            candidate.validate()
        except ValueError as error:
            return self._error(str(error))
        capacity = self.config.action_points(health)
        if capacity != self.state.ap_capacity:
            if self.state.phase != Phase.PLANNING:
                return self._error("健康变化会改变行动力；本旬已开始或正在暂停，请在下一旬规划阶段调整。")
            if any(plan.status != "completed" for plan in self.state.month_plan):
                return self._error("健康变化会改变行动力；已有未完成的三旬计划，请完成计划后再调整。")
            if self.state.ap_allocated > capacity:
                return self._error("健康变化后的行动力不足以容纳已安排活动，请先减少本旬活动。")
        self.state.emperor = copy.deepcopy(candidate)
        self.state.health = health
        self.state.ap_capacity = capacity
        if self.state.phase == Phase.PLANNING:
            if self.config.turn_rules_version >= 3:
                # A smaller capacity must still hold both classes of preplanned activities.
                self.state.work_budget = min(self.state.work_budget, capacity - self.state.private_allocated)
                self.state.stage_initial_work_budget = self.state.work_budget
                self.state.turn_stage = self._first_turn_stage()
            else:
                self.state.work_budget = min(self.state.work_budget, capacity)
        return ActionResult("ok", "皇帝健康、压力与身体异常已更新。")

    def set_activities(self, activities: list[str | Activity]) -> ActionResult:
        if self.config.turn_rules_version >= 3:
            return self._stage_set_activities(activities)
        if self.config.turn_rules_version == 2:
            return self._m03_set_activities(activities)
        if self.state.phase != Phase.PLANNING:
            return self._error("本旬已经开始，不能重新安排活动。")
        parsed: list[Activity] = []
        for item in activities:
            activity = copy.deepcopy(item) if isinstance(item, Activity) else Activity(kind=item)
            if activity.kind not in ACTIVITY_LABELS or activity.cost != 1:
                return self._error("演示活动须使用已定义种类，且每项消耗1行动力。")
            activity.status = "pending"
            parsed.append(activity)
        if sum(item.cost for item in parsed) > self.state.ap_capacity:
            return self._error("安排超过本旬行动力。")
        for activity in parsed:
            activity.id = self._id("activity")
        self.state.activities = parsed
        self._sync_current_plan_activities()
        return ActionResult("ok", "本旬活动已安排；未占用的行动力须显式补齐。")

    def fill_rest(self) -> ActionResult:
        if self.config.turn_rules_version >= 2:
            return self._m03_fill_rest()
        if self.state.phase != Phase.PLANNING:
            return self._error("只有规划阶段可以补足休息。")
        for _ in range(self.state.ap_remaining):
            self.state.activities.append(Activity(id=self._id("activity"), kind="rest"))
        self._sync_current_plan_activities()
        return ActionResult("ok", "已将本旬剩余行动力安排为休息。")

    def _sync_current_plan_activities(self) -> None:
        if self.config.turn_rules_version >= 2:
            return self._m03_sync_plan()
        plan = self._current_plan()
        if plan:
            plan.activities = [activity.kind for activity in self.state.activities]

    def set_month_plan(self, plans: list[list[str] | dict[str, Any]]) -> ActionResult:
        if self.config.turn_rules_version >= 2:
            return self._m03_set_month_plan(plans)
        if self.state.phase != Phase.PLANNING:
            return self._error("请在规划阶段设置连续三旬计划。")
        if len(plans) != 3:
            return self._error("月度计划须包含连续三旬。")
        parsed: list[TurnPlan] = []
        for offset, raw in enumerate(plans):
            data = {"activities": raw, "commands": []} if isinstance(raw, list) else raw
            kinds = list(data.get("activities", []))
            if any(kind not in ACTIVITY_LABELS for kind in kinds):
                return self._error("计划含未知活动种类。")
            if len(kinds) != self.state.ap_capacity:
                return self._error("请为计划的每旬显式安排全部行动力。")
            commands: list[PlannedCommand] = []
            for command in data.get("commands", []):
                command_id = command.get("command_id", command.get("id", ""))
                definition = self.command_definitions.get(command_id)
                if definition is None or definition.emergency_only:
                    return self._error("月度计划只能预排普通政令。")
                if "court" not in kinds:
                    return self._error("预排政令的旬必须安排处理朝政。")
                commands.append(PlannedCommand("", command_id, copy.deepcopy(command.get("parameters") or {})))
            parsed.append(TurnPlan(self.state.turn_index + offset, kinds, commands))
        for plan in parsed:
            for command in plan.commands:
                command.id = self._id("planned")
        self.state.month_plan = parsed
        self.set_activities(parsed[0].activities)
        self._log("月度计划", "已保存连续三旬的活动及预排政令；每旬仍独立执行。")
        return ActionResult("ok", "连续三旬计划已保存。")

    def add_planned_command(self, xun_offset: int, command_id: str,
                            parameters: dict[str, Any] | None = None) -> ActionResult:
        if self.state.phase != Phase.PLANNING:
            return self._error("请在规划阶段编辑预排政令。")
        plan = next((plan for plan in self.state.month_plan
                     if plan.turn_index == self.state.turn_index + xun_offset), None)
        definition = self.command_definitions.get(command_id)
        if (plan is None or definition is None or definition.emergency_only
                or not any((item if isinstance(item, str) else item.get("kind")) == "court"
                           for item in plan.activities)):
            return self._error("请先设置包含朝政的目标旬计划，并选择普通政令。")
        plan.commands.append(PlannedCommand(self._id("planned"), command_id, copy.deepcopy(parameters or {})))
        return ActionResult("ok", "政令已加入计划；执行时才校验并扣除诏书。")

    def _current_plan(self) -> TurnPlan | None:
        return next((plan for plan in self.state.month_plan if plan.turn_index == self.state.turn_index), None)

    def cancel_planned_commands(self, xun_offset: int = 0) -> ActionResult:
        """Explicitly skip unissued orders, e.g. after an emergency uses their quota."""
        plan = next((plan for plan in self.state.month_plan
                     if plan.turn_index == self.state.turn_index + xun_offset), None)
        if plan is None or xun_offset < 0:
            return self._error("没有可取消的目标旬计划。")
        count = 0
        for command in plan.commands:
            if command.status == "awaiting_confirmation":
                pending = self.state.pending_command
                if pending and pending.planned_command_id == command.id:
                    self.resolve_remonstrance(True)
                    count += 1
            elif command.status == "pending":
                command.status = "cancelled"
                count += 1
        self._log("计划调整", f"显式取消目标旬尚未执行的{count}项预排政令；不撤销已下达命令。")
        return ActionResult("cancelled", f"已取消{count}项尚未执行的预排政令。")

    def start_turn(self) -> ActionResult:
        if self.config.turn_rules_version >= 3:
            return self._stage_start_turn()
        if self.config.turn_rules_version == 2:
            return self._m03_start_turn()
        if self.state.phase == Phase.INTERRUPTED:
            return ActionResult("interrupted", "请先处理当前演示急报。")
        if self.state.phase == Phase.REMONSTRANCE:
            return ActionResult("remonstrance", "请先决定是否听取劝谏。")
        if self.state.phase != Phase.PLANNING:
            return ActionResult("ok", "本旬已经开始。")
        plan = self._current_plan()
        if not self.state.activities and plan:
            self.set_activities(plan.activities)
        if self.state.ap_remaining != 0:
            return self._error("当旬行动力必须用完；请继续安排或显式点击补足休息。")
        self.state.phase = Phase.EXECUTING
        if plan:
            plan.status = "executing"
        self._log("旬开始", f"开始{self.state.date_label}；本旬{self.state.ap_capacity}行动力。")
        if self._interrupt_if_due():
            return ActionResult("interrupted", "演示急报中断本旬，未来计划保持。")
        return ActionResult("ok", "本旬已开始，可进入朝政发令或推进。")

    def open_court(self) -> ActionResult:
        if self.config.turn_rules_version >= 2:
            return self._m03_open_court()
        if self.state.phase == Phase.PLANNING:
            result = self.start_turn()
            if not result.ok:
                return result
        if self.state.phase != Phase.EXECUTING:
            return self._error("当前须先处理劝谏或急报。")
        if not self.state.court_assigned:
            return self._error("本旬没有安排处理朝政。")
        self.state.court_open = True
        for activity in self.state.activities:
            if activity.kind == "court" and activity.status == "pending":
                activity.status = "in_progress"
                break
        return ActionResult("ok", "已进入朝政，可在本旬诏书额度内下达多项政令。")

    def _cooldown_key(self, command_id: str, parameters: dict[str, Any]) -> str:
        # Scope is explicit demo data; unspecified/None targets share the realm scope.
        target = parameters.get("target") or parameters.get("province_id") or "realm"
        return f"{command_id}:{target}"

    def _command_error(self, command_id: str, emergency_event_id: str | None) -> str | None:
        definition = self.command_definitions.get(command_id)
        if definition is None:
            return "未知政令。"
        if emergency_event_id is not None:
            event = self.active_emergency
            if (self.state.phase != Phase.INTERRUPTED or event is None
                    or event.id != emergency_event_id or event.status != "active"):
                return "只有当前尚未处理的急报可以授权应急诏书。"
            if command_id not in event.allowed_commands or not definition.emergency_only:
                return "紧急上下文不能用于普通政令；只能执行该急报指定的应急命令。"
            if not self.state.court_assigned and not event.replacement_activity_id:
                return "本旬未安排朝政，须先选择终止一个尚未完成的活动。"
            return None
        if definition.emergency_only:
            return "应急政令需要当前急报授权。"
        if self.state.phase != Phase.EXECUTING or not self.state.court_open:
            return "请先进入本旬朝政。"
        if (self.config.turn_rules_version >= 2
                and (self.current_activity is None or self.current_activity.kind != "court")):
            return "只有正在执行的早朝可以下达普通政令。"
        if self.state.edict_available < definition.cost:
            return "本旬诏书不足；普通朝政不能透支。"
        return None

    def issue_command(self, command_id: str, parameters: dict[str, Any] | None = None,
                      emergency_event_id: str | None = None,
                      *, _planned_command_id: str | None = None) -> ActionResult:
        error = self._command_error(command_id, emergency_event_id)
        if error:
            return self._error(error)
        parameters = copy.deepcopy(parameters or {})
        definition = self.command_definitions[command_id]
        key = self._cooldown_key(command_id, parameters)
        last_turn = self.state.cooldowns.get(key)
        if definition.cooldown_turns and last_turn is not None and self.state.turn_index - last_turn < definition.cooldown_turns:
            self.state.pending_command = PendingCommand(command_id, parameters, key, _planned_command_id, emergency_event_id)
            self.state.phase = Phase.REMONSTRANCE
            self._mark_planned(_planned_command_id, "awaiting_confirmation")
            self._log("大臣劝谏", "改税仍在CD内：听取则取消，坚持则记录待模拟惩罚。")
            return ActionResult("remonstrance", "大臣劝谏：是否听取并取消本次改税？尚未消耗诏书。")
        return self._commit_command(command_id, parameters, emergency_event_id, key, False, _planned_command_id)

    def _mark_planned(self, command_id: str | None, status: str) -> None:
        if command_id:
            for plan in self.state.month_plan:
                for command in plan.commands:
                    if command.id == command_id:
                        command.status = status

    def _commit_command(self, command_id: str, parameters: dict[str, Any], event_id: str | None,
                        cooldown_key: str, insisted: bool,
                        planned_command_id: str | None = None) -> ActionResult:
        definition = self.command_definitions[command_id]
        from_available = min(self.state.edict_available, definition.cost)
        borrowed = definition.cost - from_available
        self.state.edict_available -= from_available
        self.state.edict_debt += borrowed
        self.state.edicts_spent_this_turn += definition.cost
        record_id = self._id("command")
        self.state.command_ledger.append({
            "id": record_id, "turn": self.state.turn_index, "command_id": command_id,
            "label": definition.label, "parameters": copy.deepcopy(parameters),
            "cost": definition.cost, "borrowed": borrowed, "emergency_event_id": event_id,
            "insisted": insisted, "planned_command_id": planned_command_id,
        })
        if definition.cooldown_turns:
            self.state.cooldowns[cooldown_key] = self.state.turn_index
        self.state.policy_settings[cooldown_key] = {
            "command_id": command_id, "parameters": copy.deepcopy(parameters),
            "record_id": record_id, "turn": self.state.turn_index,
        }
        self.state.pending_effects.append({
            "record_id": record_id, "turn": self.state.turn_index,
            "kind": "command_effect", "command_id": command_id,
            "parameters": copy.deepcopy(parameters), "status": "not_simulated",
        })
        if insisted:
            self.state.pending_effects.append({
                "record_id": record_id, "turn": self.state.turn_index,
                "kind": "frequent_tax_change_penalty", "status": "not_simulated",
                "intended_effects": ["官员忠心下降", "政府声誉下降", "其他政令执行效果降低"],
                "tax_cut_note": "若实际为降税，民心正向收益仍存在，但大量收益被惩罚抵消；本版不运算。",
            })
        self._mark_planned(planned_command_id, "issued")
        self._log("政令登记", f"{definition.label}：消耗{definition.cost}诏书，透支{borrowed}；效果尚未模拟。")
        return ActionResult("issued", "政令已登记；世界数值保持原样。", record_id)

    def resolve_remonstrance(self, accept_advice: bool) -> ActionResult:
        pending = self.state.pending_command
        if self.state.phase != Phase.REMONSTRANCE or pending is None:
            return self._error("当前没有待决定的劝谏。")
        if accept_advice:
            self._mark_planned(pending.planned_command_id, "cancelled")
            self.state.pending_command = None
            self.state.phase = Phase.EXECUTING
            self._log("听取劝谏", "取消本次改税；不扣诏书、不刷新CD、不产生坚持惩罚。")
            return ActionResult("cancelled", "已听取劝谏并取消改税。")
        # No other command can be issued while the confirmation is pending.
        if self.state.edict_available < self.command_definitions[pending.command_id].cost:
            return self._error("可用诏书不足，无法坚持下令。")
        result = self._commit_command(pending.command_id, pending.parameters, pending.emergency_event_id,
                                      pending.cooldown_key, True, pending.planned_command_id)
        self.state.pending_command = None
        self.state.phase = Phase.EXECUTING
        return result

    def inject_emergency(self, title: str = "演示：边关急报", description: str = "手动注入的演示事件，不代表历史事实。",
                         trigger_turn: int | None = None) -> EmergencyEvent:
        event = EmergencyEvent(self._id("event"), title, description,
                               self.state.turn_index if trigger_turn is None else trigger_turn)
        self.state.emergencies.append(event)
        self._log("演示急报", f"已手动登记：{title}，触发旬序号{event.trigger_turn}。")
        if self.state.phase == Phase.EXECUTING:
            self._interrupt_if_due()
        return event

    def _interrupt_if_due(self, *, leaving_work: bool = False) -> bool:
        if self.state.active_emergency_id:
            return True
        if self.config.turn_rules_version >= 3:
            from .turns.emergency_timing import v3_emergency_can_interrupt
            event = next((event for event in self.state.emergencies
                          if event.status == "pending" and event.trigger_turn <= self.state.turn_index
                          and v3_emergency_can_interrupt(self, event, leaving_work=leaving_work)), None)
        else:
            event = next((event for event in self.state.emergencies
                          if event.status == "pending" and event.trigger_turn <= self.state.turn_index), None)
        if event is None:
            return False
        if (self.config.turn_rules_version == 2 and not self.state.court_assigned
                and not any(a.status in {"pending", "in_progress"} for a in self.state.activities)):
            # No retroactive cancellation of completed activities; deliver next turn instead.
            event.trigger_turn = self.state.turn_index + 1
            return False
        event.status = "active"
        self.state.active_emergency_id = event.id
        self.state.phase = Phase.INTERRUPTED
        self._log("计划暂停", f"{event.title}；本旬尚未完成，等待处置。")
        return True

    def resolve_emergency(self, replacement_activity_id: str | None = None,
                          command_id: str | None = "emergency_response",
                          parameters: dict[str, Any] | None = None) -> ActionResult:
        event = self.active_emergency
        if self.state.phase != Phase.INTERRUPTED or event is None:
            return self._error("当前没有待处理急报。")
        replacement: Activity | None = None
        if not self.state.court_assigned and not event.replacement_activity_id:
            replacement = next((activity for activity in self.state.activities
                                if activity.id == replacement_activity_id
                                and activity.status in {"pending", "in_progress"}), None)
            if (replacement is None and self.config.turn_rules_version >= 3
                    and not any(activity.status in {"pending", "in_progress"} for activity in self.state.activities)
                    and self.state.turn_stage in {"work", "private"}
                    and self.state.stage_unallocated[self.state.turn_stage] >= 1):
                replacement = Activity(kind="palace" if self.state.turn_stage == "work" else "rest",
                                       cost=1, parameters={"appointment_label": "紧急处置"})
            if replacement is None:
                return ActionResult("replacement_required", "请指定终止一个尚未完成的活动，以处理急报。")
        if command_id is not None:
            definition = self.command_definitions.get(command_id)
            if definition is None or not definition.emergency_only or command_id not in event.allowed_commands:
                return self._error("该急报只允许指定的应急命令，不能借机执行普通政令。")
        if replacement:
            if not replacement.id:
                replacement.id = self._id("activity")
                self.state.activities.append(replacement)
                self.state.activities = self._stage_order(self.state.activities)
            replacement.status = "replaced"
            if self.config.turn_rules_version >= 2:
                replacement.spent_ap = replacement.cost
                replacement.stage = "terminated"
                replacement.summary = "因急报终止；本卡剩余预留AP由急报占用，不获得完整活动完成记录。"
                replacement.scene["choices"] = []
                self.state.court_open = False
            event.replacement_activity_id = replacement.id
            self._log("活动终止", f"终止{replacement.label}以处理急报；不返还或增加行动力。")
        result = ActionResult("ok", "已阅急报，未下达应急诏书。")
        if command_id is not None:
            result = self.issue_command(command_id, parameters, emergency_event_id=event.id)
            if not result.ok:
                return result
        event.status = "resolved"
        self.state.active_emergency_id = None
        self.state.phase = Phase.EXECUTING
        self._log("急报已处理", f"{event.title}；可继续本旬及后续月计划。")
        return ActionResult("resolved", result.message, result.record_id)

    def _execute_planned_commands(self) -> ActionResult:
        plan = self._current_plan()
        if not plan:
            return ActionResult("ok", "没有预排政令。")
        for command in plan.commands:
            if command.status != "pending":
                continue
            court = self.open_court()
            if not court.ok:
                return court
            result = self.issue_command(command.command_id, command.parameters,
                                        _planned_command_id=command.id)
            if not result.ok:
                return result
        return ActionResult("ok", "预排政令已处理。")

    def advance_turn(self) -> ActionResult:
        if self.config.turn_rules_version >= 3:
            return self._stage_advance_turn()
        if self.config.turn_rules_version == 2:
            return self._m03_advance_turn()
        if self.state.phase == Phase.PLANNING:
            result = self.start_turn()
            if not result.ok:
                return result
        if self.state.phase == Phase.REMONSTRANCE:
            return ActionResult("remonstrance", "请先决定是否听取劝谏。")
        if self.state.phase == Phase.INTERRUPTED:
            return ActionResult("interrupted", "请先处理当前急报。")
        if self._interrupt_if_due():
            return ActionResult("interrupted", "急报暂停推进。")
        result = self._execute_planned_commands()
        if not result.ok:
            return result
        completed_counts: dict[str, int] = {}
        for activity in self.state.activities:
            if activity.status != "replaced":
                activity.status = "completed"
                completed_counts[activity.kind] = completed_counts.get(activity.kind, 0) + 1
                self.state.pending_effects.append({
                    "turn": self.state.turn_index, "kind": "activity_effect",
                    "activity_id": activity.id, "activity_kind": activity.kind,
                    "status": "not_simulated",
                })
        plan = self._current_plan()
        if plan:
            plan.status = "completed"
        for objective in self.state.emperor.objectives:
            if objective.record_completed_activities(
                    completed_counts.get(objective.activity_kind, 0), self.state.turn_index):
                self._log("人物目标", f"已满足：{objective.title}。")
        self.state.emperor.advance_modifiers_turn()
        self._log("旬结算", "本旬活动与政令流程完成；世界指标未作任何数值模拟。")
        self.state.turn_index += 1
        self.state.xun += 1
        if self.state.xun == 4:
            self.state.xun = 1
            self.state.month += 1
            if self.state.month == 13:
                self.state.month = 1
                self.state.year += 1
        self.state.phase = Phase.PLANNING
        self.state.activities = []
        self.state.court_open = False
        self.state.ap_capacity = self.config.action_points(self.state.health)
        repayment = min(self.state.edict_debt, self.state.edict_limit)
        self.state.edict_debt -= repayment
        self.state.edict_available = self.state.edict_limit - repayment
        self.state.edicts_spent_this_turn = 0
        if repayment:
            self._log("诏书偿还", f"本旬扣还{repayment}份；剩余债务{self.state.edict_debt}，可用{self.state.edict_available}。")
        return ActionResult("advanced", f"已进入{self.state.date_label}。")

    def run_month_plan(self) -> ActionResult:
        if not self.state.month_plan:
            return self._error("请先保存连续三旬计划。")
        if self.config.turn_rules_version >= 2:
            return self.advance_turn()
        while self._current_plan() is not None:
            result = self.advance_turn()
            if not result.ok:
                return result
        return ActionResult("completed", "三旬计划已逐旬完成。")

    def to_dict(self) -> dict[str, Any]:
        return {"save_version": self.config.turn_rules_version, "config": asdict(self.config), "state": self.state.to_dict()}

    @classmethod
    def from_dict(cls, snapshot: dict[str, Any]) -> GameSession:
        data = copy.deepcopy(snapshot)
        if data.get("save_version") not in {1, 2, SAVE_VERSION}:
            raise ValueError("不支持的存档版本；本版支持版本1、2旧规则与版本3阶段行动。")
        data["config"].setdefault("turn_rules_version", data["save_version"])
        if data["config"]["turn_rules_version"] != data["save_version"]:
            raise ValueError("存档版本与回合规则不一致。")
        config = DemoConfig(**data["config"])
        config.validate()
        raw = data["state"]
        if "economy" in raw and raw["economy"] is None:
            raise ValueError("县经济存档字段损坏；未启用经济的存档应省略该字段。")
        if config.turn_rules_version >= 3 and not {
                "turn_stage", "stage_initial_work_budget", "stage_transfers", "emergency_timing"}.issubset(raw):
            raise ValueError("版本3存档缺少阶段或时间转移状态；旧版存档须保留自身规则版本。")
        raw.setdefault("work_budget", min(20, raw["ap_capacity"]))
        if not isinstance(raw.get("appointments", []), list):
            raise ValueError("存档预约须为列表。")
        raw["appointments"] = [Appointment.from_dict(item) for item in raw.get("appointments", [])]
        if "scenario_profile" not in raw:
            raw["scenario_profile"] = ScenarioProfile.for_initial_year(config.initial_year, legacy=True)
        else:
            profile_data = raw["scenario_profile"]
            required_profile_keys = {"scenario_name", "emperor_name", "era_name", "era_start_year"}
            if not isinstance(profile_data, dict) or set(profile_data) != required_profile_keys:
                raise ValueError("存档开局档案字段缺失或无效。")
            raw["scenario_profile"] = ScenarioProfile(**profile_data)
        raw["scenario_profile"].validate(config.initial_year)
        # Version 1 saves created before the emperor page lack this entire field.
        # A present but malformed profile is corruption, not a migration request.
        raw["emperor"] = (EmperorProfile.from_dict(raw["emperor"])
                          if "emperor" in raw else EmperorProfile())
        raw["phase"] = Phase(raw["phase"])
        raw["activities"] = [Activity(**item) for item in raw["activities"]]
        raw["emergencies"] = [EmergencyEvent(**item) for item in raw["emergencies"]]
        raw["month_plan"] = [TurnPlan(**{**plan, "commands": [PlannedCommand(**command) for command in plan["commands"]]})
                             for plan in raw["month_plan"]]
        if raw["pending_command"] is not None:
            raw["pending_command"] = PendingCommand(**raw["pending_command"])
        state = GameState(**raw)
        if any(objective.completed_turn is not None
               and objective.completed_turn >= state.turn_index
               for objective in state.emperor.objectives):
            raise ValueError("存档人物目标的完成旬数必须早于当前旬。")
        try:
            validate_health_value(state.health)
        except ValueError as error:
            raise ValueError(f"存档皇帝健康无效：{error}") from error
        cls._validate_record_collections(state)
        if (state.edict_debt < 0 or not 0 <= state.edict_available <= state.edict_limit
                or state.edict_limit != config.edicts_per_turn or state.edicts_spent_this_turn < 0):
            raise ValueError("存档中的诏书账目无效。")
        if state.ap_remaining < 0 or not 1 <= state.xun <= 3 or not 1 <= state.month <= 12:
            raise ValueError("存档中的活动或日期无效。")
        if state.ap_capacity != config.action_points(state.health):
            raise ValueError("存档行动力与健康配置不一致。")
        if config.turn_rules_version < 3 and state.phase != Phase.PLANNING and state.ap_remaining != 0:
            raise ValueError("执行阶段的存档必须已安排全部行动力。")
        if any(activity.kind not in ACTIVITY_LABELS
               or type(activity.cost) is not int or activity.cost < 1
               or (config.turn_rules_version == 1 and activity.cost != 1)
               or activity.status not in ({"pending", "in_progress", "completed", "replaced", "stopped", "cancelled"}
                                          if config.turn_rules_version >= 3 else {"pending", "in_progress", "completed", "replaced"})
               for activity in state.activities):
            raise ValueError("存档包含无效活动。")
        activity_ids = [activity.id for activity in state.activities]
        if any(not identifier for identifier in activity_ids) or len(activity_ids) != len(set(activity_ids)):
            raise ValueError("存档活动编号无效或重复。")
        initial_date = config.initial_year * 36 + (config.initial_month - 1) * 3 + config.initial_xun - 1
        saved_date = state.year * 36 + (state.month - 1) * 3 + state.xun - 1
        if state.turn_index < 0 or saved_date != initial_date + state.turn_index:
            raise ValueError("存档日期与旬序号不一致。")
        if (state.phase == Phase.REMONSTRANCE) != (state.pending_command is not None):
            raise ValueError("存档劝谏阶段不一致。")
        if (state.phase == Phase.INTERRUPTED) != (state.active_emergency_id is not None):
            raise ValueError("存档急报阶段不一致。")
        session = cls(state, config)
        if state.active_emergency_id and (session.active_emergency is None or session.active_emergency.status != "active"):
            raise ValueError("存档缺失当前急报。")
        active_events = [event for event in state.emergencies if event.status == "active"]
        if len(active_events) != (1 if state.active_emergency_id else 0):
            raise ValueError("存档急报活动状态不一致。")
        if session.active_emergency and session.active_emergency.replacement_activity_id:
            if not any(activity.id == session.active_emergency.replacement_activity_id
                       and activity.status == "replaced" for activity in state.activities):
                raise ValueError("存档急报缺少已替换的活动。")
        plan_turns = [plan.turn_index for plan in state.month_plan]
        if len(plan_turns) != len(set(plan_turns)):
            raise ValueError("存档包含重复的旬计划。")
        awaiting_ids = []
        for plan in state.month_plan:
            for command in plan.commands:
                definition = session.command_definitions.get(command.command_id)
                if (definition is None or definition.emergency_only
                        or command.status not in {"pending", "awaiting_confirmation", "issued", "cancelled"}):
                    raise ValueError("存档含无效预排政令。")
                if command.status == "awaiting_confirmation":
                    awaiting_ids.append(command.id)
        pending = state.pending_command
        if pending:
            definition = session.command_definitions.get(pending.command_id)
            if definition is None or not definition.cooldown_turns or pending.emergency_event_id:
                raise ValueError("存档含无效待劝谏命令。")
            if not state.court_open or not state.court_assigned:
                raise ValueError("待劝谏命令缺少本旬朝政安排。")
        expected_awaiting = [pending.planned_command_id] if pending and pending.planned_command_id else []
        if awaiting_ids != expected_awaiting:
            raise ValueError("存档的预排政令与劝谏状态不一致。")
        if config.turn_rules_version >= 2:
            session._validate_m03_state()
        if config.turn_rules_version >= 3:
            from .turns.emergency_timing import validate_emergency_timing
            session._validate_stage_state()
            validate_emergency_timing(state)
        validate_appointments(state)
        return session

    @staticmethod
    def _validate_record_collections(state: GameState) -> None:
        """Reject damaged history before the caller replaces its live session."""
        if not isinstance(state.logs, list):
            raise ValueError("存档日志必须为列表。")
        for entry in state.logs:
            if (not isinstance(entry, dict)
                    or not {"turn", "date", "label", "message"}.issubset(entry)
                    or any(not isinstance(entry[key], str) for key in ("date", "label", "message"))
                    or type(entry["turn"]) is not int
                    or not 0 <= entry["turn"] <= state.turn_index):
                raise ValueError("存档日志缺少必要字段，或字段类型、旬序号无效。")
        if not isinstance(state.command_ledger, list):
            raise ValueError("存档诏令簿必须为列表。")
        identifiers = set()
        required = {"id", "turn", "command_id", "label", "parameters", "cost", "borrowed",
                    "emergency_event_id", "insisted", "planned_command_id"}
        for entry in state.command_ledger:
            if not isinstance(entry, dict) or not required.issubset(entry):
                raise ValueError("存档诏令簿缺少必要字段。")
            if (any(not isinstance(entry[key], str) or not entry[key] for key in ("id", "command_id", "label"))
                    or not isinstance(entry["parameters"], dict)
                    or any(type(entry[key]) is not int for key in ("turn", "cost", "borrowed"))
                    or not 0 <= entry["turn"] <= state.turn_index
                    or entry["cost"] <= 0 or not 0 <= entry["borrowed"] <= entry["cost"]
                    or type(entry["insisted"]) is not bool
                    or any(entry[key] is not None and not isinstance(entry[key], str)
                           for key in ("emergency_event_id", "planned_command_id"))):
                raise ValueError("存档诏令簿字段类型或资源记录无效。")
            if entry["id"] in identifiers:
                raise ValueError("存档诏令簿编号重复。")
            identifiers.add(entry["id"])

    def save_json(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(destination)

    @classmethod
    def load_json(cls, path: str | Path) -> GameSession:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
