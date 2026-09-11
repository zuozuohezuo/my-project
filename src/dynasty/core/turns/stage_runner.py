"""Version 3: morning court, work and private time with on-demand choices."""

from __future__ import annotations

from ..models import ActionResult, Activity, Phase


TURN_STAGES = ("court", "work", "private", "finished")
FINAL_ACTIVITY_STATUSES = {"completed", "replaced", "stopped", "cancelled"}


class StageRunnerMixin:
    def _stage_order(self, activities: list[Activity]) -> list[Activity]:
        if sum(activity.kind == "court" for activity in activities) > 1:
            raise ValueError("每旬只能安排一次早朝，并固定放在最上方。")
        return sorted(activities, key=lambda activity: TURN_STAGES.index(activity.turn_stage))

    def _stage_set_activities(self, activities: list) -> ActionResult:
        return self.set_turn_plan(activities, self.state.work_budget)

    def set_turn_plan(self, activities: list, work_budget: int) -> ActionResult:
        if self.config.turn_rules_version < 3:
            return super().set_turn_plan(activities, work_budget)
        if self.state.phase != Phase.PLANNING:
            return self._error("本旬已经开始；请在当前阶段选择活动或将剩余工作时间转为私生活。")
        if type(work_budget) is not int or not 0 <= work_budget <= self.state.ap_capacity:
            return self._error("工作预算须为本旬总AP范围内的整数，包含早朝投入。")
        try:
            parsed = self._stage_order(self._parse_activities(activities))
        except (TypeError, ValueError) as error:
            return self._error(str(error))
        work = sum(activity.cost for activity in parsed if activity.category == "work")
        private = sum(activity.cost for activity in parsed if activity.category == "private")
        if work > work_budget or private > self.state.ap_capacity - work_budget:
            return self._error("预排活动超过工作或私生活预算；可留空到所属阶段再选择。")
        result = self._m03_set_activities(parsed)
        if not result.ok:
            return result
        self.state.work_budget = work_budget
        self.state.stage_initial_work_budget = work_budget
        self.state.turn_stage = self._first_turn_stage()
        self._sync_current_plan_activities()
        return ActionResult("ok", "已按早朝、工作、私生活分组保存；未预排的时间可进入阶段后再选择。")

    def set_work_budget(self, work_budget: int) -> ActionResult:
        if self.config.turn_rules_version < 3:
            return super().set_work_budget(work_budget)
        return self.set_turn_plan(self.state.activities, work_budget)

    def _first_turn_stage(self) -> str:
        if self.state.stage_budget["court"]:
            return "court"
        return "work" if self.state.stage_budget["work"] else "private"

    def _stage_default_turn(self) -> None:
        """Only called at a new turn; an explicit empty player plan cancels court."""
        self.state.activities = []
        self.state.activity_cursor = 0
        self.state.stage_transfers = []
        self.state.work_budget = min(max(5, self.state.work_budget), self.state.ap_capacity)
        self.state.stage_initial_work_budget = self.state.work_budget
        self.state.activities.append(Activity(id=self._id("activity"), kind="court", cost=5))
        self.state.turn_stage = "court"

    def _stage_start_turn(self) -> ActionResult:
        if self.state.phase == Phase.INTERRUPTED:
            return ActionResult("interrupted", "请先处理当前急报。")
        if self.state.phase == Phase.REMONSTRANCE:
            return ActionResult("remonstrance", "请先决定是否听取劝谏。")
        if self.state.phase != Phase.PLANNING:
            return ActionResult("ok", "本旬已经开始。")
        if self.appointments_due:
            return ActionResult("appointment_required", "本旬有到期预约，请先选择执行、改期或不去。")
        if (self.state.work_allocated > self.state.work_budget
                or self.state.private_allocated > self.state.private_budget):
            return self._error("预排活动超出阶段预算，请先调整。")
        self.state.stage_initial_work_budget = self.state.work_budget
        self.state.turn_stage = self._first_turn_stage()
        self.state.phase = Phase.EXECUTING
        self.state.court_open = False
        self.state.activity_cursor = 0
        plan = self._current_plan()
        if plan:
            plan.status = "executing"
        self._log("旬开始", "按早朝、工作、私生活依次推进；未预排的时间进入相应阶段后再决定。")
        result = self.start_next_activity()
        if result.status == "stage_choice_required":
            return ActionResult("ok", result.message)
        return result

    def _stage_move_forward(self) -> None:
        """Advance exhausted stages, never consuming unassigned time."""
        if self.current_activity:
            return
        while self.state.turn_stage != "finished":
            stage = self.state.turn_stage
            pending = [index for index, activity in enumerate(self.state.activities)
                       if activity.turn_stage == stage and activity.status == "pending"]
            if pending:
                self.state.activity_cursor = pending[0]
                return
            if self.state.stage_remaining[stage] > 0:
                self.state.activity_cursor = next((index for index, activity in enumerate(self.state.activities)
                                                   if activity.status == "pending"), len(self.state.activities))
                return
            self.state.turn_stage = TURN_STAGES[TURN_STAGES.index(stage) + 1]
        self.state.activity_cursor = len(self.state.activities)

    def start_next_activity(self) -> ActionResult:
        if self.config.turn_rules_version < 3:
            return super().start_next_activity()
        if self.state.phase == Phase.PLANNING:
            return self.start_turn()
        if self.state.phase != Phase.EXECUTING:
            return self._error("请先处理当前急报或劝谏。")
        if self.current_activity:
            return ActionResult("choice_required", "当前活动尚未结束，请继续其过程。")
        self._stage_move_forward()
        if self._interrupt_if_due():
            return ActionResult("interrupted", "急报暂停了当前阶段，活动进度已保留。")
        if self.state.turn_stage == "finished":
            return ActionResult("ok", "本旬三个阶段已完成，可以提交旬末结算。")
        pending = next((index for index, activity in enumerate(self.state.activities)
                        if activity.turn_stage == self.state.turn_stage and activity.status == "pending"), None)
        if pending is None:
            name = "工作" if self.state.turn_stage == "work" else "私生活"
            return ActionResult("stage_choice_required", f"{name}阶段尚有{self.state.stage_remaining[self.state.turn_stage]} AP，请选择本阶段活动。")
        self.state.activity_cursor = pending
        return super().start_next_activity()

    def append_stage_activity(self, kind: str, cost: int = 1, parameters: dict | None = None) -> ActionResult:
        if self.config.turn_rules_version < 3:
            return self._error("当前旧规则存档须在旬初预排全部活动。")
        if self.state.phase != Phase.EXECUTING or self.state.turn_stage not in {"work", "private"}:
            return self._error("请在工作或私生活阶段选择活动。")
        try:
            activity = self._parse_activities([Activity(kind=kind, cost=cost, parameters=parameters or {})])[0]
        except (TypeError, ValueError) as error:
            return self._error(str(error))
        if activity.turn_stage != self.state.turn_stage:
            return self._error("只能选择当前阶段的活动；工作与私生活不能混排，早朝须在旬初决定。")
        if activity.cost > self.state.stage_unallocated[self.state.turn_stage]:
            return self._error("本阶段尚未预留的AP不足，不能挪用另一阶段的时间。")
        current = self.current_activity
        activity.id = self._id("activity")
        self.state.activities.append(activity)
        self.state.activities = self._stage_order(self.state.activities)
        if current:
            self.state.activity_cursor = self.state.activities.index(current)
        else:
            self._stage_move_forward()
        self._sync_current_plan_activities()
        self._log("阶段安排", f"在{'工作' if activity.category == 'work' else '私生活'}阶段安排{activity.label}，预留{activity.cost} AP。")
        return ActionResult("ok", "活动已加入当前阶段，可继续开始下一项。", activity.id)

    def transfer_work_to_private(self, amount: int | None = None) -> ActionResult:
        if self.config.turn_rules_version < 3:
            return self._error("当前旧规则存档不支持阶段间转移时间。")
        if self.state.phase != Phase.EXECUTING or self.state.turn_stage != "work":
            return self._error("只能在工作阶段的安全暂停点，将剩余工作时间单向转为私生活。")
        remaining = self.state.stage_remaining["work"]
        amount = remaining if amount is None else amount
        if type(amount) is not int or not 0 < amount <= remaining:
            return self._error("转入私生活的AP须为剩余工作时间内的正整数。")
        current = self.current_activity
        if amount == remaining and current and current.stage == "ready":
            return self._error("当前活动已经做完，请先确认小结，再转移尚未使用的时间。")
        if self._interrupt_if_due(leaving_work=amount == remaining):
            return ActionResult("interrupted", "工作阶段有待送达急报，请处理后再确认转入私生活。")
        candidates = [activity for activity in self.state.activities
                      if activity.turn_stage == "work" and activity.status in {"pending", "in_progress"}]
        if amount < remaining:
            needed = max(0, amount - self.state.stage_unallocated["work"])
            ordered = [a for a in reversed(candidates) if a.status == "pending" and not a.appointment_id]
            ordered += [a for a in reversed(candidates) if a.status == "pending" and a.appointment_id]
            ordered += [a for a in candidates if a.status == "in_progress"]
            candidates = []
            for activity in ordered:
                if needed <= 0:
                    break
                releasable = activity.cost - activity.spent_ap
                if releasable:
                    candidates.append(activity)
                    needed -= releasable
        affected = []
        for activity in candidates:
            activity.status = "stopped" if activity.status == "in_progress" else "cancelled"
            activity.stage = activity.status
            activity.summary = (f"提前结束{activity.label}，保留已投入{activity.spent_ap} AP及实际进度；未完成整项活动。"
                                if activity.spent_ap else f"已撤下尚未开始的{activity.label}，时间转入后续安排。")
            activity.scene["choices"] = []
            if activity.appointment_id:
                item = self._find_appointment(activity.appointment_id)
                if item and item.status in {"pending", "scheduled"}:
                    # Existing appointment saves already understand cancelled links, including partial time.
                    activity.status, activity.stage = "cancelled", "cancelled"
                    self._mark_appointment_missed(item, "提前结束工作阶段，未能按预约履约")
            affected.append(activity.id)
        before = self.state.work_budget
        self.state.work_budget -= amount
        self.state.stage_transfers.append({"turn": self.state.turn_index, "amount": amount,
                                           "work_before": before, "work_after": self.state.work_budget,
                                           "affected_activity_ids": affected})
        self.state.court_open = False
        self._stage_move_forward()
        self._log("工作转为私生活", f"将尚未使用的{amount} AP转入私生活；已投入的工作进度保留，不记作完整活动完成。")
        self._sync_current_plan_activities()
        return ActionResult("ok", f"已转入{amount} AP；{'现在进入私生活阶段。' if self.state.turn_stage == 'private' else '仍可在剩余工作时间内选择活动。'}")

    def finish_work_stage(self) -> ActionResult:
        if (self.config.turn_rules_version < 3 or self.state.turn_stage != "work"
                or self.state.phase != Phase.EXECUTING):
            return self._error("当前不在可提前结束的工作阶段。")
        if self.state.stage_remaining["work"]:
            return self.transfer_work_to_private()
        if self.current_activity:
            return self._error("请先确认当前工作活动的小结。")
        self._stage_move_forward()
        return ActionResult("ok", "工作阶段已结束，进入私生活。")

    def continue_activity(self, choice: str | None = None) -> ActionResult:
        if self.config.turn_rules_version < 3:
            return super().continue_activity(choice)
        result = super().continue_activity(choice)
        if result.ok and self.state.phase == Phase.EXECUTING:
            self._stage_move_forward()
            if self._interrupt_if_due():
                return ActionResult("interrupted", "本段活动进度已提交，急报在安全暂停点送达。")
        return result

    def finish_activity(self) -> ActionResult:
        result = super().finish_activity()
        if self.config.turn_rules_version >= 3 and result.ok and self.state.phase == Phase.EXECUTING:
            self._stage_move_forward()
        return result

    def _stage_advance_turn(self) -> ActionResult:
        if self.state.phase == Phase.PLANNING:
            return self.start_turn()
        if self.state.phase == Phase.INTERRUPTED:
            return ActionResult("interrupted", "请先处理当前急报。")
        if self.state.phase == Phase.REMONSTRANCE:
            return ActionResult("remonstrance", "请先决定是否听取劝谏。")
        if self.current_activity:
            return self.continue_activity()
        self._stage_move_forward()
        if self.state.turn_stage != "finished":
            return self.start_next_activity()
        if self._interrupt_if_due():
            return ActionResult("interrupted", "请先处理本旬急报。")
        return self._m03_settle_turn()

    def _stage_reset_after_settlement(self) -> None:
        self.state.stage_transfers = []
        plan = self._current_plan()
        if plan:
            self.state.stage_initial_work_budget = self.state.work_budget
            self.state.turn_stage = self._first_turn_stage()
        else:
            self.state.work_budget = min(self.state.stage_initial_work_budget, self.state.ap_capacity)
            self._stage_default_turn()

    def _validate_stage_state(self) -> None:
        state = self.state
        if state.turn_stage not in TURN_STAGES:
            raise ValueError("存档回合阶段无效。")
        if (type(state.stage_initial_work_budget) is not int
                or not 0 <= state.stage_initial_work_budget <= state.ap_capacity
                or not isinstance(state.stage_transfers, list)):
            raise ValueError("存档阶段初始预算或转移记录无效。")
        previous = state.stage_initial_work_budget
        for record in state.stage_transfers:
            required = {"turn", "amount", "work_before", "work_after", "affected_activity_ids"}
            if (not isinstance(record, dict) or set(record) != required
                    or any(type(record[key]) is not int for key in ("turn", "amount", "work_before", "work_after"))
                    or record["turn"] != state.turn_index or record["work_before"] != previous
                    or record["amount"] < 1 or record["work_after"] != previous - record["amount"]
                    or record["work_after"] < 0 or not isinstance(record["affected_activity_ids"], list)
                    or any(not isinstance(identifier, str) for identifier in record["affected_activity_ids"])):
                raise ValueError("存档工作时间转移记录不连续或存在反向转移。")
            previous = record["work_after"]
        if previous != state.work_budget:
            raise ValueError("存档工作预算与已提交转移记录不一致。")
        if any(value < 0 for value in [*state.stage_budget.values(), *state.stage_remaining.values(),
                                       *state.stage_unallocated.values()]):
            raise ValueError("存档阶段预算被透支或超额预留。")
        if sum(activity.kind == "court" for activity in state.activities) > 1:
            raise ValueError("存档每旬只能有一次早朝。")
        stages = [TURN_STAGES.index(activity.turn_stage) for activity in state.activities]
        if stages != sorted(stages):
            raise ValueError("存档活动必须按早朝、工作、私生活分组。")
        current_index = TURN_STAGES.index(state.turn_stage)
        if state.phase == Phase.PLANNING:
            if state.stage_transfers or state.turn_stage != self._first_turn_stage():
                raise ValueError("规划存档不能含有已经执行的阶段转移。")
        else:
            for activity in state.activities:
                index = TURN_STAGES.index(activity.turn_stage)
                if index < current_index and activity.status not in FINAL_ACTIVITY_STATUSES:
                    raise ValueError("存档提前跳过尚未完成的阶段活动。")
                if index > current_index and activity.status in {"in_progress", "completed", "stopped"}:
                    raise ValueError("存档提前执行了未来阶段的活动。")
            if any(state.stage_remaining[stage] for stage in TURN_STAGES[:current_index]):
                raise ValueError("存档无声跳过了尚未使用的阶段时间。")
            if self.current_activity and self.current_activity.turn_stage != state.turn_stage:
                raise ValueError("存档当前活动不属于当前回合阶段。")
        known = {activity.id for activity in state.activities}
        for record in state.stage_transfers:
            if any(identifier not in known for identifier in record["affected_activity_ids"]):
                raise ValueError("存档时间转移缺少对应的活动记录。")
        for activity in state.activities:
            if activity.status in {"stopped", "cancelled"}:
                if (activity.turn_stage != "work" or activity.stage != activity.status
                        or activity.scene.get("choices", []) or activity.spent_ap > activity.cost
                        or not any(activity.id in record["affected_activity_ids"] for record in state.stage_transfers)):
                    raise ValueError("存档提前结束的工作缺少有效转移记录。")
        for plan in state.month_plan:
            parsed = self._parse_activities(plan.activities)
            if [activity.turn_stage for activity in parsed] != [activity.turn_stage for activity in self._stage_order(parsed)]:
                raise ValueError("存档未来计划的阶段顺序无效。")
