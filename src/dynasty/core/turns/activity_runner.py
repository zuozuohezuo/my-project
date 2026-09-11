"""Ordered, saveable M03 activities; numeric efficiencies are prototype values."""

from __future__ import annotations

import copy
from dataclasses import asdict

from ..models import (
    ACTIVITY_LABELS, OFFICE_ACTIVITIES, ActionResult, Activity, Phase, PlannedCommand, TurnPlan,
)


class ActivityRunnerMixin:
    @property
    def current_activity(self) -> Activity | None:
        index = self.state.activity_cursor
        if 0 <= index < len(self.state.activities):
            activity = self.state.activities[index]
            if activity.status == "in_progress":
                return activity
        return None

    def _parse_activities(self, activities: list) -> list[Activity]:
        parsed = []
        for item in activities:
            if isinstance(item, Activity):
                activity = copy.deepcopy(item)
            elif isinstance(item, dict):
                activity = Activity(**item)
            elif isinstance(item, str):
                activity = Activity(kind=item, cost=5 if item == "court" else 1)
            else:
                raise ValueError("活动须为已定义的活动种类或活动卡片。")
            if activity.kind not in ACTIVITY_LABELS or type(activity.cost) is not int:
                raise ValueError("活动种类或AP成本无效。")
            fixed = 5 if activity.kind == "court" else 1
            if activity.kind in OFFICE_ACTIVITIES:
                if activity.cost < 1:
                    raise ValueError("办公须预分配至少1点整数AP。")
            elif activity.cost != fixed:
                raise ValueError(f"{activity.label}每项固定{fixed} AP。")
            if not isinstance(activity.parameters, dict):
                raise ValueError("活动参数须为字典。")
            priority = activity.parameters.get("work_item_ids", [])
            if not isinstance(priority, list) or any(not isinstance(item, str) for item in priority):
                raise ValueError("待办优先顺序须使用待办编号列表。")
            if ("appointment_label" in activity.parameters
                    and not isinstance(activity.parameters["appointment_label"], str)):
                raise ValueError("预约活动名称须为文本。")
            activity.status, activity.stage = "pending", "planned"
            activity.spent_ap, activity.scene, activity.summary = 0, {}, ""
            parsed.append(activity)
        return parsed

    def set_work_budget(self, work_budget: int) -> ActionResult:
        if self.state.phase != Phase.PLANNING:
            return self._error("请在旬初规划阶段调整比例。")
        if type(work_budget) is not int or not 0 <= work_budget <= self.state.ap_capacity:
            return self._error("工作预算须为本旬总AP范围内的整数。")
        self.state.work_budget = work_budget
        self._sync_current_plan_activities()
        return ActionResult("ok", "工作与私生活预算已调整；开始执行前统一检查日程。")

    def set_turn_plan(self, activities: list, work_budget: int) -> ActionResult:
        if self.state.phase != Phase.PLANNING:
            return self._error("本旬已开始，不能重新安排日程。")
        if type(work_budget) is not int or not 0 <= work_budget <= self.state.ap_capacity:
            return self._error("工作预算无效。")
        try:
            parsed = self._parse_activities(activities)
        except (TypeError, ValueError) as error:
            return self._error(str(error))
        work = sum(a.cost for a in parsed if a.category == "work")
        private = sum(a.cost for a in parsed if a.category == "private")
        if work > work_budget or private > self.state.ap_capacity - work_budget:
            return self._error("活动超过对应的工作或私生活预算。")
        result = self._m03_set_activities(parsed)
        if result.ok:
            self.state.work_budget = work_budget
            self._sync_current_plan_activities()
        return result

    def _m03_set_activities(self, activities: list) -> ActionResult:
        if self.state.phase != Phase.PLANNING:
            return self._error("本旬已经开始，不能重新安排活动。")
        try:
            parsed = self._parse_activities(activities)
        except (TypeError, ValueError) as error:
            return self._error(str(error))
        if sum(a.cost for a in parsed) > self.state.ap_capacity:
            return self._error("安排超过本旬行动力。")
        appointment_ids = {a.appointment_id for a in parsed if a.appointment_id}
        old_ids = {a.appointment_id for a in self.state.activities if a.appointment_id}
        if len(appointment_ids) != sum(bool(a.appointment_id) for a in parsed):
            return self._error("同一预约不能重复排入日程。")
        for activity in parsed:
            if activity.appointment_id:
                item = self._find_appointment(activity.appointment_id)
                if (item is None or item.due_turn != self.state.turn_index
                        or item.status not in {"pending", "scheduled"}
                        or item.kind != activity.kind or item.cost != activity.cost
                        or item.preparation != "ready"):
                    return self._error("预约关联、执行旬、准备状态或活动成本无效。")
        # Deleting a card retains its commitment; turn start requires a fresh explicit decision.
        for identifier in old_ids - appointment_ids:
            item = self._find_appointment(identifier)
            if item and item.status == "scheduled":
                item.status = "pending"
        for activity in parsed:
            activity.id = self._id("activity")
        self.state.activities = parsed
        self.state.activity_cursor = 0
        self._sync_current_plan_activities()
        return ActionResult("ok", "活动及顺序已保存；规划只预留AP，执行时记录实际消耗。")

    def _m03_fill_rest(self) -> ActionResult:
        if self.state.phase != Phase.PLANNING:
            return self._error("只有规划阶段可以补足休息。")
        count = min(self.state.ap_remaining,
                    self.state.private_budget - self.state.private_allocated)
        if count < 0:
            return self._error("现有私生活活动超出预算，请先调整。")
        for _ in range(count):
            self.state.activities.append(Activity(id=self._id("activity"), kind="rest"))
        self._sync_current_plan_activities()
        return ActionResult("ok", f"已补入{count}项休息；未安排的工作预算仍须选择工作活动。")

    def _m03_sync_plan(self) -> None:
        plan = self._current_plan()
        if plan:
            plan.activities = [asdict(a) for a in self.state.activities]
            plan.work_budget = self.state.work_budget

    def _m03_set_month_plan(self, plans: list) -> ActionResult:
        if self.state.phase != Phase.PLANNING or len(plans) != 3:
            return self._error("请在规划阶段保存连续三旬计划。")
        parsed = []
        appointment_ids = set()
        for offset, raw in enumerate(plans):
            data = {"activities": raw} if isinstance(raw, list) else raw
            try:
                activities = self._parse_activities(data.get("activities", []))
                if self.config.turn_rules_version >= 3:
                    activities = self._stage_order(activities)
            except (TypeError, ValueError) as error:
                return self._error(str(error))
            for activity in activities:
                if activity.appointment_id:
                    item = self._find_appointment(activity.appointment_id)
                    if (item is None or item.id in appointment_ids
                            or item.due_turn != self.state.turn_index + offset
                            or item.kind != activity.kind or item.cost != activity.cost
                            or item.status not in {"pending", "scheduled"}):
                        return self._error("三旬计划的预约须匹配执行旬、活动成本且不能重复。")
                    appointment_ids.add(item.id)
            work = sum(a.cost for a in activities if a.category == "work")
            budget = data.get("work_budget", work)
            private = sum(a.cost for a in activities if a.category == "private")
            valid = (type(budget) is int and 0 <= budget <= self.state.ap_capacity
                     and work <= budget and private <= self.state.ap_capacity - budget)
            if not valid or (self.config.turn_rules_version < 3 and (
                    sum(a.cost for a in activities) != self.state.ap_capacity or budget != work)):
                return self._error("每旬日程须独立填满AP，并与工作／私生活预算一致。")
            commands = []
            for command in data.get("commands", []):
                command_id = command.get("command_id", command.get("id", ""))
                definition = self.command_definitions.get(command_id)
                if definition is None or definition.emergency_only or not any(
                        a.kind == "court" for a in activities):
                    return self._error("预排普通政令须有早朝安排。")
                commands.append(PlannedCommand("", command_id,
                                               copy.deepcopy(command.get("parameters") or {})))
            parsed.append(TurnPlan(self.state.turn_index + offset,
                                   [asdict(a) for a in activities], commands,
                                   work_budget=budget))
        for plan in parsed:
            for command in plan.commands:
                command.id = self._id("planned")
        result = self.set_turn_plan(parsed[0].activities, parsed[0].work_budget)
        if not result.ok:
            return result
        self.state.month_plan = parsed
        self._sync_current_plan_activities()
        self._log("三旬日程", "三旬分别保存预算、活动成本与顺序，到期逐项执行。")
        return ActionResult("ok", "连续三旬日程已保存。")

    def _m03_start_turn(self) -> ActionResult:
        if self.state.phase == Phase.INTERRUPTED:
            return ActionResult("interrupted", "请先处理当前急报。")
        if self.state.phase == Phase.REMONSTRANCE:
            return ActionResult("remonstrance", "请先决定是否听取劝谏。")
        if self.state.phase != Phase.PLANNING:
            return ActionResult("ok", "本旬已经开始。")
        plan = self._current_plan()
        if not self.state.activities and plan:
            result = self.set_turn_plan(plan.activities, plan.work_budget if plan.work_budget is not None
                                        else self.state.work_budget)
            if not result.ok:
                return result
        if self.appointments_due:
            return ActionResult("appointment_required", "本旬有到期预约，请先选择执行、改期或不去。")
        if self.state.ap_remaining or self.state.work_allocated != self.state.work_budget:
            return self._error("请按工作与私生活预算填满整旬AP后再开始执行。")
        self.state.activity_cursor = 0
        self.state.phase = Phase.EXECUTING
        self.state.court_open = False
        if plan:
            plan.status = "executing"
        self._log("旬开始", f"按顺序执行{len(self.state.activities)}项活动，预留{self.state.ap_capacity} AP。")
        if self._interrupt_if_due():
            return ActionResult("interrupted", "急报中断本旬，日程与内部阶段已保留。")
        return self.start_next_activity()

    def _choices(self, activity: Activity, title: str, text: str, choices: list[tuple]) -> None:
        activity.scene.update(title=title, text=text,
                              choices=[{"id": key, "label": label} for key, label in choices])

    def start_next_activity(self) -> ActionResult:
        if self.state.phase == Phase.PLANNING:
            return self.start_turn()
        if self.state.phase != Phase.EXECUTING:
            return self._error("请先处理当前急报或劝谏。")
        if self.current_activity:
            return ActionResult("choice_required", "当前活动尚未结束，请继续其过程。")
        while (self.state.activity_cursor < len(self.state.activities)
               and self.state.activities[self.state.activity_cursor].status in {"completed", "replaced"}):
            self.state.activity_cursor += 1
        if self.state.activity_cursor == len(self.state.activities):
            return ActionResult("ok", "本旬日程已执行完毕，可以提交旬末结算。")
        if self._interrupt_if_due():
            return ActionResult("interrupted", "急报暂停推进。")
        activity = self.state.activities[self.state.activity_cursor]
        activity.status, activity.stage = "in_progress", "intro"
        # Fixed activities charge once on entry; office time charges per completed AP period.
        if activity.kind not in OFFICE_ACTIVITIES:
            activity.spent_ap = activity.cost
        if activity.kind == "court":
            self.state.court_open = True
            activity.stage = "court"
            self._court_scene(activity)
            result = self._execute_planned_commands()
            if not result.ok:
                return result
        elif activity.kind in OFFICE_ACTIVITIES:
            activity.stage = "office"
            self._office_scene(activity)
        elif activity.kind == "study":
            activity.stage = "reading"
            self._choices(activity, "书斋 · 选一卷细读", "案上备有经义与史论。选择本次阅读主题，结束后记录心得。",
                          [("classics", "研读经义"), ("history", "翻阅史论")])
        elif activity.kind == "exercise":
            activity.stage = "exercise_mode"
            self._choices(activity, "校场 · 射艺", "本次安排三轮练习。可手动选择节奏，也可按角色能力自动完成。",
                          [("manual", "亲自练习"), ("auto", "按能力自动处理")])
        elif activity.kind in {"garden", "private"}:
            activity.stage = "explore"
            activity.scene.update(visits=[], opportunities=2)
            self._garden_scene(activity)
        else:
            text = {"rest": "御榻旁帘影低垂。留一段安静的时间休息。",
                    "lecture": "讲官展开经筵讲义，就治国旧事做一段日讲。",
                    "calligraphy": "铺纸研墨，临写一页字帖。"}.get(activity.kind, "按既定日程展开活动。")
            self._choices(activity, activity.label, text, [("continue", "继续活动")])
        self._log("活动开始", f"第{self.state.activity_cursor + 1}项：{activity.label}，预留{activity.cost} AP。")
        return ActionResult("ok", f"已开始{activity.label}。")

    def _court_scene(self, activity: Activity) -> None:
        remaining = [item for item in self.state.work_items if item["status"] != "completed"]
        choices = [(f"review:{item['id']}", f"听取并处理：{item['title']}") for item in remaining]
        choices.append(("finish", "散朝，完成本次早朝"))
        self._choices(activity, "奉天殿 · 早朝",
                      "群臣列班，依次奏事。你可继续听取议题，也可下达诏令；诸事议毕后散朝。", choices)

    def office_efficiency(self, kind: str) -> float:
        skill = "people_reading" if kind == "audience" else "administration"
        emperor = self.state.emperor
        return round(max(0.1, (1 + emperor.skills[skill] / 50)
                             * emperor.skill_effect_percent(skill) / 100), 2)

    def _office_scene(self, activity: Activity) -> None:
        efficiency = self.office_efficiency(activity.kind)
        pending = [item for item in self.state.work_items
                   if item["kind"] == activity.kind and item["status"] != "completed"]
        priority = activity.parameters.get("work_item_ids", [])
        pending.sort(key=lambda item: priority.index(item["id"]) if item["id"] in priority else len(priority))
        activity.scene["queue"] = [item["id"] for item in pending]
        self._choices(activity, activity.label,
                      f"已投入 {activity.spent_ap}／{activity.cost} AP；每AP可推进约{efficiency:g}工作量。"
                      + (f"当前待办：{pending[0]['title']}。" if pending else "待办已清，可在预留时段整理案卷。"),
                      [("work", "投入下一段1 AP")])

    def _garden_scene(self, activity: Activity) -> None:
        visits = activity.scene["visits"]
        options = [(key, title) for key, title in [("pond", "到池畔观鱼"), ("pavilion", "到亭中听风"),
                                                   ("flowers", "走过花径")]
                   if key not in visits]
        options.append(("leave", "结束游赏"))
        self._choices(activity, "御花园 · 随步而行",
                      f"本次还有{activity.scene['opportunities']}次探索机会。各去处仅可访问一次；互动不另收AP。", options)

    def _ready(self, activity: Activity, summary: str) -> ActionResult:
        activity.stage = "ready"
        activity.summary = summary
        self._choices(activity, f"{activity.label} · 小结", summary, [("finish", "确认小结，完成活动")])
        return ActionResult("ok", "活动过程已结束，请确认小结。")

    def continue_activity(self, choice: str | None = None) -> ActionResult:
        if self.state.phase != Phase.EXECUTING:
            return self._error("请先处理急报或劝谏，随后恢复原活动。")
        activity = self.current_activity
        if activity is None:
            return self.start_next_activity()
        if self._interrupt_if_due():
            return ActionResult("interrupted", "活动阶段已保存，请处理急报。")
        if choice is None:
            return ActionResult("choice_required", "请选择当前活动的处理方式。")
        allowed = {entry["id"] for entry in activity.scene.get("choices", [])}
        if choice not in allowed:
            return self._error("该选择不属于当前活动阶段，未改变进度。")
        if activity.stage == "ready":
            return self.finish_activity()
        if activity.stage == "court":
            if choice == "finish":
                return self.finish_activity()
            item = next(item for item in self.state.work_items if item["id"] == choice[7:])
            item["progress"], item["status"] = item["complexity"], "completed"
            activity.scene.setdefault("handled", []).append(item["id"])
            self._log("早朝事务", f"已听取并处理：{item['title']}；不追加AP，世界效果待后续模块。")
            self._court_scene(activity)
            return ActionResult("ok", "事务已处理，可继续朝议或下达正式政令。")
        if activity.stage == "office":
            remaining = self.office_efficiency(activity.kind)
            progressed = 0.0
            for identifier in activity.scene["queue"]:
                item = next(item for item in self.state.work_items if item["id"] == identifier)
                amount = min(remaining, item["complexity"] - item["progress"])
                item["progress"] = round(item["progress"] + amount, 4)
                remaining -= amount
                progressed += amount
                if item["progress"] >= item["complexity"]:
                    item["status"] = "completed"
                else:
                    item["status"] = "in_progress"
                if remaining <= 0:
                    break
            activity.spent_ap += 1
            activity.scene["work_done"] = round(activity.scene.get("work_done", 0) + progressed, 4)
            if activity.spent_ap == activity.cost:
                return self._ready(activity, f"投入{activity.cost} AP，推进{activity.scene['work_done']:g}工作量；未完事项留在待办。")
            self._office_scene(activity)
            return ActionResult("ok", "已提交本段工作进度与1 AP；可继续下一段。")
        if activity.stage == "reading":
            activity.scene["topic"] = choice
            return self._ready(activity, "本次研读经义，记下了持身与治事的心得。" if choice == "classics"
                               else "本次翻阅史论，整理了前代治乱的线索。")
        if activity.stage == "exercise_mode":
            activity.scene.update(mode=choice, rounds=0, score=0)
            if choice == "auto":
                skill = self.state.emperor.skills["military_strategy"]
                activity.scene.update(rounds=3, score=min(9, 3 + skill // 20))
                return self._ready(activity, f"自动完成三轮练习，命中表现{activity.scene['score']}／9（原型场景评分）。")
            activity.stage = "exercise_round"
            self._choices(activity, "射艺 · 第1轮", "稳住弓身，再选择出箭节奏。",
                          [("steady", "稳住呼吸后放箭"), ("quick", "顺势快速放箭")])
            return ActionResult("ok", "进入手动练习。")
        if activity.stage == "exercise_round":
            activity.scene["rounds"] += 1
            activity.scene["score"] += 2 if choice == "steady" else 1
            if activity.scene["rounds"] == 3:
                return self._ready(activity, f"完成三轮射艺，命中表现{activity.scene['score']}／9（原型场景评分）。")
            self._choices(activity, f"射艺 · 第{activity.scene['rounds'] + 1}轮", "调整姿势，准备下一箭。",
                          [("steady", "稳住呼吸后放箭"), ("quick", "顺势快速放箭")])
            return ActionResult("ok", "本轮结果已保存。")
        if activity.stage == "explore":
            if choice == "leave":
                return self._ready(activity, f"结束宫苑游赏，共访问{len(activity.scene['visits'])}处。")
            activity.scene["visits"].append(choice)
            activity.scene["opportunities"] -= 1
            if choice == "flowers":
                item = {"id": self._id("work"), "title": "花径修葺请托", "kind": "palace",
                        "complexity": 2, "progress": 0, "status": "pending"}
                self.state.work_items.append(item)
                self._log("游赏见闻", "听得花径年久失修，已记入宫廷待办，须在后续工作中处理。")
            if activity.scene["opportunities"] == 0:
                return self._ready(activity, "走过两处宫苑，结束本次游赏。见闻已记录，后续事务仍须另作工作安排。")
            self._garden_scene(activity)
            return ActionResult("ok", "本处见闻已保存，可选择下一去处或结束。")
        return self._ready(activity, f"已按计划完成{activity.label}的常规过程。")

    def finish_activity(self) -> ActionResult:
        activity = self.current_activity
        if self.state.phase != Phase.EXECUTING or activity is None:
            return self._error("当前没有可完成的活动。")
        if activity.stage not in {"ready", "court"}:
            return self._error("请先完成当前活动的过程与必要选择。")
        if self._interrupt_if_due():
            return ActionResult("interrupted", "提交活动前收到急报，当前进度已保留。")
        if activity.stage == "court":
            result = self._execute_planned_commands()
            if not result.ok:
                return result
            activity.summary = f"早朝结束，固定投入5 AP，处理{len(activity.scene.get('handled', []))}项待办；政令另记诏令簿。"
        activity.spent_ap = activity.cost
        activity.status, activity.stage = "completed", "completed"
        activity.scene["choices"] = []
        self.state.completion_records.append({"id": self._id("completion"), "turn": self.state.turn_index,
            "activity_id": activity.id, "activity_kind": activity.kind, "summary": activity.summary,
            "spent_ap": activity.spent_ap, "settled": False})
        self.state.pending_effects.append({"turn": self.state.turn_index, "kind": "activity_effect",
            "activity_id": activity.id, "activity_kind": activity.kind, "status": "not_simulated"})
        self.complete_appointment(activity)
        self.state.court_open = False
        self.state.activity_cursor += 1
        self._log("活动完成", activity.summary)
        return ActionResult("completed", "活动已完成；下一项仍按日程执行，目标在旬末汇总。", activity.id)

    def _m03_open_court(self) -> ActionResult:
        if self.state.phase == Phase.PLANNING:
            result = self.start_turn()
            if not result.ok:
                return result
        if self.state.phase != Phase.EXECUTING:
            return self._error("请先处理当前急报或劝谏。")
        if self.current_activity is None:
            index = self.state.activity_cursor
            if index >= len(self.state.activities) or self.state.activities[index].kind != "court":
                return self._error("请按日程顺序执行，只有当前早朝开放普通政令。")
            result = self.start_next_activity()
            if not result.ok:
                return result
        if self.current_activity is None or self.current_activity.kind != "court":
            return self._error("当前活动没有普通政令权限；有工作预算或未来早朝均不等同于正在早朝。")
        self.state.court_open = True
        return ActionResult("ok", "正在早朝，可处理多项事务与正式政令。")

    def _m03_advance_turn(self) -> ActionResult:
        if self.state.phase == Phase.PLANNING:
            return self.start_turn()
        if self.state.phase == Phase.INTERRUPTED:
            return ActionResult("interrupted", "请先处理当前急报。")
        if self.state.phase == Phase.REMONSTRANCE:
            return ActionResult("remonstrance", "请先决定是否听取劝谏。")
        if self.current_activity:
            return self.continue_activity()
        if any(a.status == "pending" for a in self.state.activities):
            return self.start_next_activity()
        if self._interrupt_if_due():
            return ActionResult("interrupted", "旬末提交前收到急报。")
        return self._m03_settle_turn()

    def _m03_settle_turn(self) -> ActionResult:
        if self.state.economy is None:
            return self._m03_apply_turn_settlement()
        from ..regions.economy import settle_economy
        previous = self.state
        try:
            self._validate_economy_state()
            self.state = copy.deepcopy(previous)
            self.state.economy, report = settle_economy(
                self.state.economy, self.state.turn_index, self.state.month, self.state.xun)
            self._log("县情旬报", report["summary"])
            result = self._m03_apply_turn_settlement()
            self._validate_economy_state()
            self._validate_m03_state()
            self._validate_stage_state()
        except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as error:
            self.state = previous
            return self._error(f"旬末未提交，原进度已保留：{error}")
        return result

    def _m03_apply_turn_settlement(self) -> ActionResult:
        records = self.state.completion_records
        for objective in self.state.emperor.objectives:
            start = self.state.objective_record_starts.get(objective.id, 0)
            count = sum(1 for index, record in enumerate(records)
                        if index >= start and not record["settled"]
                        and record["turn"] == self.state.turn_index
                        and record["activity_kind"] == objective.activity_kind)
            if objective.record_completed_activities(count, self.state.turn_index):
                self._log("人物目标", f"已满足：{objective.title}。")
        for record in records:
            if record["turn"] == self.state.turn_index:
                record["settled"] = True
        self.state.emperor.advance_modifiers_turn()
        self.expire_appointments()
        plan = self._current_plan()
        if plan:
            plan.status = "completed"
        detail = "县经济已结算。" if self.state.economy is not None else "世界数值模拟尚未启用。"
        self._log("旬结算", f"本旬实际投入{self.state.ap_spent} AP，完成记录已汇总；{detail}")
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
        self.state.activity_cursor = 0
        self.state.court_open = False
        self.state.ap_capacity = self.config.action_points(self.state.health)
        self.state.work_budget = min(self.state.work_budget, self.state.ap_capacity)
        repayment = min(self.state.edict_debt, self.state.edict_limit)
        self.state.edict_debt -= repayment
        self.state.edict_available = self.state.edict_limit - repayment
        self.state.edicts_spent_this_turn = 0
        if repayment:
            self._log("诏书偿还", f"本旬扣还{repayment}份；剩余债务{self.state.edict_debt}。")
        next_plan = self._current_plan()
        if next_plan:
            result = self.set_turn_plan(next_plan.activities, next_plan.work_budget)
            if not result.ok:
                self._log("计划待调整", result.message)
        if self.config.turn_rules_version >= 3:
            self._stage_reset_after_settlement()
        return ActionResult("advanced", f"已进入{self.state.date_label}。")

    def _validate_m03_state(self) -> None:
        state = self.state
        if (not isinstance(state.work_items, list)
                or any(not isinstance(item, dict)
                       or not {"id", "title", "kind", "complexity", "progress", "status"}.issubset(item)
                       for item in state.work_items)):
            raise ValueError("存档待办缺少必要字段。")
        if (type(state.work_budget) is not int or not 0 <= state.work_budget <= state.ap_capacity
                or type(state.activity_cursor) is not int
                or not 0 <= state.activity_cursor <= len(state.activities)):
            raise ValueError("存档工作预算或活动游标无效。")
        if self.config.turn_rules_version < 3 and state.phase != Phase.PLANNING and state.work_allocated != state.work_budget:
            raise ValueError("执行存档的活动分类与预算不一致。")
        allowed_stages = {"planned", "intro", "court", "office", "reading", "exercise_mode",
                          "exercise_round", "explore", "ready", "completed", "terminated"}
        if self.config.turn_rules_version >= 3:
            allowed_stages |= {"stopped", "cancelled"}
        in_progress = []
        for index, activity in enumerate(state.activities):
            fixed = 5 if activity.kind == "court" else 1
            if ((activity.kind not in OFFICE_ACTIVITIES and activity.cost != fixed)
                    or type(activity.spent_ap) is not int or not 0 <= activity.spent_ap <= activity.cost
                    or not isinstance(activity.stage, str) or activity.stage not in allowed_stages
                    or not isinstance(activity.scene, dict)
                    or not isinstance(activity.summary, str) or not isinstance(activity.parameters, dict)):
                raise ValueError("存档活动成本、实际投入或场景字段无效。")
            if activity.status == "pending" and (activity.spent_ap or activity.stage != "planned"):
                raise ValueError("尚未开始的活动不能包含已用AP或执行阶段。")
            if activity.status == "completed" and (activity.spent_ap != activity.cost or activity.stage != "completed"):
                raise ValueError("已完成活动必须完整记录实际投入。")
            if activity.status == "replaced" and (activity.spent_ap != activity.cost or activity.stage != "terminated"):
                raise ValueError("已终止活动的急报时间记录不完整。")
            if activity.status == "in_progress":
                in_progress.append(index)
                if activity.stage in {"planned", "completed", "terminated"}:
                    raise ValueError("进行中活动的阶段不一致。")
                choices = activity.scene.get("choices")
                if (not isinstance(choices, list) or not choices
                        or any(not isinstance(choice, dict) or set(choice) != {"id", "label"}
                               or not all(isinstance(value, str) for value in choice.values()) for choice in choices)
                        or not isinstance(activity.scene.get("title"), str)
                        or not isinstance(activity.scene.get("text"), str)):
                    raise ValueError("进行中活动缺少可恢复的场景选择。")
                stages = ({"court"} if activity.kind == "court" else
                          {"office", "ready"} if activity.kind in OFFICE_ACTIVITIES else
                          {"reading", "ready"} if activity.kind == "study" else
                          {"exercise_mode", "exercise_round", "ready"} if activity.kind == "exercise" else
                          {"explore", "ready"} if activity.kind in {"garden", "private"} else
                          {"intro", "ready"})
                if activity.stage not in stages:
                    raise ValueError("存档场景阶段与所属活动不匹配。")
                if activity.kind not in OFFICE_ACTIVITIES and activity.spent_ap != activity.cost:
                    raise ValueError("固定成本活动开始时必须记账。")
                if activity.stage == "exercise_round" and (
                        type(activity.scene.get("rounds")) is not int
                        or not 0 <= activity.scene["rounds"] < 3
                        or type(activity.scene.get("score")) is not int
                        or not 0 <= activity.scene["score"] <= activity.scene["rounds"] * 2):
                    raise ValueError("存档习武内部阶段或成绩无效。")
                if activity.stage == "explore" and (
                        not isinstance(activity.scene.get("visits"), list)
                        or any(visit not in {"pond", "pavilion", "flowers"} for visit in activity.scene["visits"])
                        or len(set(activity.scene["visits"])) != len(activity.scene["visits"])
                        or activity.scene.get("opportunities") != 2 - len(activity.scene["visits"])
                        or not 1 <= activity.scene["opportunities"] <= 2):
                    raise ValueError("存档宫苑探索次数无效。")
                choice_ids = [entry["id"] for entry in choices]
                expected = {"ready": {"finish"}, "office": {"work"}, "reading": {"classics", "history"},
                            "exercise_mode": {"manual", "auto"}, "exercise_round": {"steady", "quick"},
                            "intro": {"continue"}}.get(activity.stage)
                if activity.stage == "explore":
                    expected = {"pond", "pavilion", "flowers"} - set(activity.scene["visits"]) | {"leave"}
                if activity.stage == "court":
                    expected = {f"review:{item['id']}" for item in state.work_items
                                if item["status"] != "completed"} | {"finish"}
                if len(choice_ids) != len(set(choice_ids)) or set(choice_ids) != expected:
                    raise ValueError("存档场景选择与保存阶段不一致，不能重复取得阶段结果。")
                if activity.stage == "ready" and activity.spent_ap != activity.cost:
                    raise ValueError("待确认小结的活动必须已完成全部投入。")
            final_statuses = {"completed", "replaced", "stopped", "cancelled"} if self.config.turn_rules_version >= 3 else {"completed", "replaced"}
            if index < state.activity_cursor and activity.status not in final_statuses:
                raise ValueError("存档游标跳过未完成活动。")
        if len(in_progress) > 1 or (in_progress and in_progress[0] != state.activity_cursor):
            raise ValueError("存档同时执行多个活动或游标错位。")
        if state.phase == Phase.PLANNING and (state.activity_cursor or in_progress or state.ap_spent):
            raise ValueError("旬初规划存档不能包含已执行活动。")
        if state.court_open and (self.current_activity is None or self.current_activity.kind != "court"):
            raise ValueError("存档普通朝政权限与当前活动不一致。")
        if not isinstance(state.completion_records, list):
            raise ValueError("存档活动完成记录无效。")
        identifiers, activity_ids = set(), set()
        for record in state.completion_records:
            required = {"id", "turn", "activity_id", "activity_kind", "summary", "spent_ap", "settled"}
            if (not isinstance(record, dict) or set(record) != required
                    or any(not isinstance(record[key], str) for key in ("id", "activity_id", "activity_kind", "summary"))
                    or not record["id"] or record["id"] in identifiers
                    or record["activity_id"] in activity_ids or record["activity_kind"] not in ACTIVITY_LABELS
                    or type(record["turn"]) is not int or not 0 <= record["turn"] <= state.turn_index
                    or type(record["spent_ap"]) is not int or record["spent_ap"] < 1
                    or type(record["settled"]) is not bool
                    or record["settled"] != (record["turn"] < state.turn_index)):
                raise ValueError("存档活动完成记录重复或结算状态无效。")
            identifiers.add(record["id"])
            activity_ids.add(record["activity_id"])
        completed = {a.id for a in state.activities if a.status == "completed"}
        current_records = {r["activity_id"] for r in state.completion_records if r["turn"] == state.turn_index}
        if completed != current_records:
            raise ValueError("存档当前活动与完成记录不一致。")
        for record in state.completion_records:
            if record["turn"] == state.turn_index:
                activity = next(a for a in state.activities if a.id == record["activity_id"])
                if (record["activity_kind"] != activity.kind or record["spent_ap"] != activity.spent_ap
                        or record["summary"] != activity.summary):
                    raise ValueError("存档完成记录的活动类型、投入或小结与实际活动不一致。")
        if (not isinstance(state.objective_record_starts, dict)
                or any(not isinstance(key, str) or type(value) is not int
                       or not 0 <= value <= len(state.completion_records)
                       for key, value in state.objective_record_starts.items())):
            raise ValueError("存档人物目标的创建记录游标无效。")
        if not isinstance(state.work_items, list):
            raise ValueError("存档待办必须为列表。")
        work_ids = set()
        for item in state.work_items:
            required = {"id", "title", "kind", "complexity", "progress", "status"}
            if (not isinstance(item, dict) or not required.issubset(item)
                    or not isinstance(item["id"], str) or not item["id"] or item["id"] in work_ids
                    or not isinstance(item["title"], str) or item["kind"] not in OFFICE_ACTIVITIES
                    or type(item["complexity"]) not in {int, float} or item["complexity"] <= 0
                    or type(item["progress"]) not in {int, float} or not 0 <= item["progress"] <= item["complexity"]
                    or item["status"] not in {"pending", "in_progress", "completed"}
                    or (item["status"] == "completed") != (item["progress"] == item["complexity"])):
                raise ValueError("存档待办进度、复杂度或编号无效。")
            work_ids.add(item["id"])
        for activity in state.activities:
            if activity.status == "in_progress" and activity.stage == "office":
                if (activity.spent_ap >= activity.cost
                        or not isinstance(activity.scene.get("queue"), list)
                        or len(set(activity.scene["queue"])) != len(activity.scene["queue"])
                        or any(identifier not in work_ids for identifier in activity.scene["queue"])
                        or any(item["kind"] != activity.kind or item["status"] == "completed"
                               for item in state.work_items if item["id"] in activity.scene["queue"])):
                    raise ValueError("存档办公阶段缺少有效待办队列。")
        appointment_ids = set()
        for plan in state.month_plan:
            if (type(plan.turn_index) is not int or plan.turn_index < 0
                    or plan.status not in {"pending", "executing", "completed"}):
                raise ValueError("存档三旬计划的日期或状态无效。")
            try:
                activities = self._parse_activities(plan.activities)
            except (TypeError, ValueError) as error:
                raise ValueError("存档三旬计划包含无效活动：" + str(error)) from error
            work = sum(a.cost for a in activities if a.category == "work")
            if self.config.turn_rules_version >= 3:
                saved_activities = [Activity(**raw) if isinstance(raw, dict) else activity
                                    for raw, activity in zip(plan.activities, activities)]
                if plan.turn_index > state.turn_index and any(activity.status != "pending"
                                                             for activity in saved_activities):
                    raise ValueError("存档尚未到期的计划不能包含已执行活动。")
                work = sum(a.reserved_ap for a in saved_activities if a.category == "work")
                private = sum(a.reserved_ap for a in saved_activities if a.category == "private")
                capacity = (max(points for _, points in self.config.health_ap_thresholds)
                            if plan.status == "completed" else state.ap_capacity)
                if (type(plan.work_budget) is not int or not 0 <= plan.work_budget <= capacity
                        or work > plan.work_budget or private > capacity - plan.work_budget):
                    raise ValueError("存档三旬计划的预排活动超过阶段预算。")
            elif ((plan.status != "completed" and sum(a.cost for a in activities) != state.ap_capacity)
                  or type(plan.work_budget) is not int or plan.work_budget != work):
                raise ValueError("存档三旬计划的AP或分类预算不完整。")
            for activity in activities:
                if activity.appointment_id:
                    item = self._find_appointment(activity.appointment_id)
                    historical_conflict = item is not None and any(
                        entry["action"] == "rescheduled" and entry["from_turn"] == plan.turn_index
                        for entry in item.history)
                    if (item is None or item.id in appointment_ids
                            or (item.due_turn != plan.turn_index and not historical_conflict)
                            or item.kind != activity.kind or item.cost != activity.cost):
                        raise ValueError("存档三旬预约链接、日期或成本无效，或预约重复。")
                    appointment_ids.add(item.id)
