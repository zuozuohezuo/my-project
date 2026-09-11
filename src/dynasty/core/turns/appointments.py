"""Future commitments, independent of the three-turn plan and world simulation."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields
from typing import Any


SOURCE_LABELS = {"seasonal": "时令", "event": "事件", "preparation": "筹备条件"}
PREPARATION_LABELS = {"ready": "已就绪", "preparing": "筹备中", "delayed": "筹备延误"}
STATUS_LABELS = {"pending": "待决定", "scheduled": "已排入本旬", "completed": "已履约", "missed": "已缺席"}
CONSEQUENCE_KINDS = {
    "seasonal": "ritual_dispute",
    "event": "trust_and_reception",
    "preparation": "preparation_loss",
}


def _text(value: Any, limit: int, *, empty: bool = False) -> bool:
    return (isinstance(value, str) and len(value) <= limit
            and (empty or bool(value.strip()))
            and all(ord(char) >= 32 and ord(char) != 127 for char in value))


@dataclass
class Appointment:
    id: str
    source: str
    original_turn: int
    due_turn: int
    kind: str
    label: str
    cost: int
    preparation: str = "ready"
    related_people: list[str] = field(default_factory=list)
    status: str = "pending"
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS[self.source]

    @property
    def preparation_label(self) -> str:
        return PREPARATION_LABELS[self.preparation]

    @property
    def status_label(self) -> str:
        return STATUS_LABELS[self.status]

    @property
    def postponed(self) -> bool:
        return self.due_turn > self.original_turn

    def validate(self) -> None:
        # Deferred imports allow GameState to own Appointment objects.
        from ..models import ACTIVITY_LABELS

        if (not _text(self.id, 120) or not isinstance(self.source, str)
                or self.source not in SOURCE_LABELS or not isinstance(self.kind, str)
                or self.kind not in ACTIVITY_LABELS or not _text(self.label, 120)
                or type(self.original_turn) is not int or self.original_turn < 0
                or type(self.due_turn) is not int or self.due_turn < self.original_turn
                or type(self.cost) is not int or self.cost < 1
                or not isinstance(self.preparation, str) or self.preparation not in PREPARATION_LABELS
                or not isinstance(self.status, str) or self.status not in STATUS_LABELS):
            raise ValueError("存档预约的名称、来源、日期、准备状态或成本无效。")
        expected_cost = 5 if self.kind == "court" else 1
        if self.kind not in {"paperwork", "audience", "palace"} and self.cost != expected_cost:
            raise ValueError("存档预约固定成本与活动定义不一致。")
        if (not isinstance(self.related_people, list)
                or any(not _text(person, 80) for person in self.related_people)
                or len(set(self.related_people)) != len(self.related_people)):
            raise ValueError("存档预约相关人物无效或重复。")
        if not isinstance(self.history, list) or not self.history:
            raise ValueError("存档预约缺少创建及变更历史。")
        due = self.original_turn
        terminal = None
        previous_turn = -1
        for index, entry in enumerate(self.history):
            required = {"id", "action", "turn", "from_turn", "to_turn", "reason"}
            if (not isinstance(entry, dict) or set(entry) != required
                    or entry["id"] != f"{self.id}:history:{index}"
                    or not isinstance(entry["action"], str)
                    or entry["action"] not in {"created", "rescheduled", "scheduled", "completed", "missed"}
                    or any(type(entry[key]) is not int or entry[key] < 0
                           for key in ("turn", "from_turn", "to_turn"))
                    or not _text(entry["reason"], 240, empty=True)
                    or entry["turn"] < previous_turn or terminal is not None):
                raise ValueError("存档预约历史字段或顺序无效。")
            if index == 0:
                if (entry["action"] != "created" or entry["from_turn"] != due
                        or entry["to_turn"] != due or entry["turn"] > due):
                    raise ValueError("存档预约创建记录与原定旬不一致。")
            elif entry["action"] == "created" or entry["from_turn"] != due:
                raise ValueError("存档预约日期变更历史不连续。")
            elif entry["action"] == "rescheduled":
                if entry["to_turn"] <= max(due, entry["turn"]):
                    raise ValueError("存档预约只能改到更后的旬。")
                due = entry["to_turn"]
            elif entry["to_turn"] != due:
                raise ValueError("存档预约非改期记录不能改变执行旬。")
            if entry["action"] in {"scheduled", "completed"} and entry["turn"] != due:
                raise ValueError("存档预约履约记录不在当前执行旬。")
            if entry["action"] in {"completed", "missed"}:
                terminal = entry["action"]
            previous_turn = entry["turn"]
        if due != self.due_turn or (terminal or self.status) != self.status:
            raise ValueError("存档预约状态与变更历史不一致。")
        if self.status in {"completed", "missed"} and terminal != self.status:
            raise ValueError("存档预约缺少最终履约记录。")
        if self.status == "scheduled" and self.history[-1]["action"] != "scheduled":
            raise ValueError("存档预约缺少排入日程记录。")

    @classmethod
    def from_dict(cls, data: Any) -> Appointment:
        if not isinstance(data, dict) or set(data) != {item.name for item in fields(cls)}:
            raise ValueError("存档预约字段缺失或无效。")
        item = cls(**copy.deepcopy(data))
        item.validate()
        return item


def validate_appointments(state: Any) -> None:
    """Check all ownership links and require exactly one consequence per choice."""
    if not isinstance(state.appointments, list) or not isinstance(state.appointment_consequences, list):
        raise ValueError("存档预约与后果记录必须为列表。")
    appointments = {}
    expected_consequences = {}
    for item in state.appointments:
        if not isinstance(item, Appointment):
            raise ValueError("存档预约对象无效。")
        item.validate()
        if item.id in appointments:
            raise ValueError("存档预约编号重复。")
        appointments[item.id] = item
        for history in item.history:
            if history["turn"] > state.turn_index:
                raise ValueError("存档预约历史不能发生在未来。")
            if history["action"] in {"rescheduled", "missed"}:
                expected_consequences[f'{history["id"]}:consequence'] = (item, history)
        if item.status in {"pending", "scheduled"} and item.due_turn < state.turn_index:
            raise ValueError("存档存在已经过期但未记载缺席的预约。")
    actual_consequences = set()
    required = {"id", "appointment_id", "history_id", "choice", "source", "kind", "status",
                "description", "turn", "quantified"}
    for record in state.appointment_consequences:
        if (not isinstance(record, dict) or set(record) != required
                or not isinstance(record["id"], str) or record["id"] in actual_consequences
                or record["id"] not in expected_consequences):
            raise ValueError("存档预约后果缺失、重复或没有对应选择。")
        item, history = expected_consequences[record["id"]]
        if (record["appointment_id"] != item.id or record["history_id"] != history["id"]
                or record["choice"] != history["action"] or record["source"] != item.source
                or record["kind"] != CONSEQUENCE_KINDS[item.source]
                or record["status"] != "pending_simulation" or record["quantified"] is not False
                or type(record["turn"]) is not int or record["turn"] != history["turn"]
                or not _text(record["description"], 500)):
            raise ValueError("存档预约后果与已提交选择不一致。")
        actual_consequences.add(record["id"])
    if actual_consequences != set(expected_consequences):
        raise ValueError("存档预约选择缺少对应后果，不能重复结算或跳过后果。")
    linked = set()
    for activity in state.activities:
        identifier = getattr(activity, "appointment_id", None)
        if not identifier:
            continue
        item = appointments.get(identifier)
        if (item is None or identifier in linked or item.due_turn != state.turn_index
                or item.kind != activity.kind or item.cost != activity.cost
                or item.status not in {"scheduled", "completed", "missed"}):
            raise ValueError("存档预约与当前活动的关联无效或重复。")
        if ((activity.status == "completed") != (item.status == "completed")
                or (item.status == "missed" and activity.status not in {"replaced", "cancelled"})):
            raise ValueError("存档预约与当前活动的履约状态不一致。")
        linked.add(identifier)
    if any(item.status == "scheduled" and item.id not in linked for item in state.appointments):
        raise ValueError("存档已排入本旬的预约缺少对应活动。")


class AppointmentMixin:
    @property
    def appointments_due(self) -> list[Appointment]:
        linked = {getattr(activity, "appointment_id", None) for activity in self.state.activities
                  if activity.status not in {"replaced", "cancelled"}}
        return [item for item in self.state.appointments
                if item.due_turn <= self.state.turn_index
                and (item.status == "pending" or item.status == "scheduled" and item.id not in linked)]

    def appointment_date_label(self, turn_index: int) -> str:
        if type(turn_index) is not int or turn_index < 0:
            raise ValueError("预约旬序号必须为非负整数。")
        current = self.state.year * 36 + (self.state.month - 1) * 3 + self.state.xun - 1
        year, slot = divmod(current - self.state.turn_index + turn_index, 36)
        month, xun = divmod(slot, 3)
        era = self.state.scenario_profile
        era_year = year - era.era_start_year + 1
        return f"{era.era_name}{'元' if era_year == 1 else era_year}年{month + 1}月{['上旬', '中旬', '下旬'][xun]}"

    def appointment_conflict(self, item: Appointment) -> str:
        """Read-only forecast; no future card is overwritten and no fee is inferred."""
        from ..models import Activity

        if item.status not in {"pending", "scheduled"}:
            return ""
        if item.preparation != "ready":
            return f"准备条件：{item.preparation_label}"
        if item.due_turn == self.state.turn_index:
            cards = self.state.activities
            work_budget = self.state.work_budget
        else:
            plan = next((plan for plan in self.state.month_plan
                         if plan.turn_index == item.due_turn), None)
            work_budget = plan.work_budget if plan is not None else None
            cards = []
            for raw in plan.activities if plan is not None else []:
                if isinstance(raw, Activity):
                    cards.append(raw)
                elif isinstance(raw, dict):
                    cards.append(Activity(**raw))
                else:
                    cards.append(Activity(kind=raw, cost=5 if raw == "court" else 1))
        linked = {card.appointment_id for card in cards if card.appointment_id}
        # Other commitments compete for the same time even before a three-turn plan exists.
        additional = [Activity(kind=other.kind, cost=other.cost) for other in self.state.appointments
                      if other.due_turn == item.due_turn and other.status in {"pending", "scheduled"}
                      and other.id not in linked]
        combined = [*cards, *additional]
        if sum(card.cost for card in combined) > self.state.ap_capacity:
            return "AP冲突：该旬既有日程与预约超过当前健康对应AP；须调整日程，到期重验"
        if work_budget is not None:
            work = sum(card.cost for card in combined if card.category == "work")
            private = sum(card.cost for card in combined if card.category == "private")
            if work > work_budget or private > self.state.ap_capacity - work_budget:
                return "比例冲突：该旬既有日程与预约超过分类预算，须调整工作／私生活比例"
        return ""

    @staticmethod
    def appointment_consequence_preview(item: Appointment, choice: str) -> str:
        verb = "改期" if choice == "rescheduled" else "缺席"
        explanation = {
            "seasonal": "登记礼制争议与相关臣属不满；节令不随改期移动，延期作为补办",
            "event": "登记来访方信任受损与额外接待成本",
            "preparation": "登记已经投入的筹备损耗与后续行程延误",
        }[item.source]
        return f"{verb}：{explanation}。本轮记录分类后果待结算，尚未设定数额或改动国家数值。"

    def _find_appointment(self, identifier: str) -> Appointment | None:
        return next((item for item in self.state.appointments if item.id == identifier), None)

    def _appointment_history(self, item: Appointment, action: str, *, old_turn: int | None = None,
                             reason: str = "") -> dict[str, Any]:
        entry = {"id": f"{item.id}:history:{len(item.history)}", "action": action,
                 "turn": self.state.turn_index,
                 "from_turn": item.due_turn if old_turn is None else old_turn,
                 "to_turn": item.due_turn, "reason": reason}
        item.history.append(entry)
        return entry

    def create_appointment(self, source: str, due_turn: int, kind: str, label: str = "",
                           cost: int | None = None, preparation: str = "ready",
                           related_people: list[str] | None = None):
        from ..models import ACTIVITY_LABELS, ActionResult

        if type(due_turn) is not int or due_turn < self.state.turn_index:
            return self._error("预约日期不能早于当前旬。")
        if not isinstance(kind, str) or not isinstance(label, str):
            return self._error("预约活动类型与名称必须为文本。")
        item = Appointment("appointment-pending", source, due_turn, due_turn, kind,
                           label or ACTIVITY_LABELS.get(kind, kind),
                           (5 if kind == "court" else 1) if cost is None else cost,
                           preparation, copy.deepcopy(related_people if related_people is not None else []))
        self._appointment_history(item, "created")
        try:
            item.validate()
        except (TypeError, ValueError) as error:
            return self._error(str(error))
        item.id = self._id("appointment")
        while self._find_appointment(item.id) is not None:
            item.id = self._id("appointment")
        item.history = []
        self._appointment_history(item, "created")
        self.state.appointments.append(item)
        self._log("未来预约", f"{item.label}：{item.source_label}，预定{self.appointment_date_label(due_turn)}，{item.cost} AP；创建不扣 AP。")
        conflict = self.appointment_conflict(item)
        return ActionResult("ok", "预约已进入未来日程；到期后选择执行、改期或缺席。" + conflict, item.id)

    def execute_appointment(self, appointment_id: str):
        from ..models import ActionResult, Activity, Phase

        item = self._find_appointment(appointment_id)
        if item is None:
            return self._error("未找到该预约。")
        if item.status not in {"pending", "scheduled"}:
            return self._error("该预约已经履约或记载缺席，不能重复执行。")
        if self.state.phase != Phase.PLANNING or item.due_turn != self.state.turn_index:
            return self._error("请在预约到期旬的规划阶段排入活动。")
        if item.preparation != "ready":
            return ActionResult("preparation_required", "预约准备尚未就绪；请完成准备、改期或缺席。", item.id)
        if any(getattr(activity, "appointment_id", None) == item.id for activity in self.state.activities):
            if item.status == "pending":
                item.status = "scheduled"
                self._appointment_history(item, "scheduled")
                self._log("预约排入", f"已确认本旬日程中的{item.label}，执行时才消耗{item.cost} AP。")
            return ActionResult("ok", "该预约已在本旬日程中。", item.id)
        activity = Activity(kind=item.kind, cost=item.cost, appointment_id=item.id,
                            parameters={"appointment_label": item.label})
        category_used = sum(card.cost for card in self.state.activities
                            if card.category == activity.category)
        category_budget = (self.state.work_budget if activity.category == "work"
                           else self.state.ap_capacity - self.state.work_budget)
        if category_used + item.cost > category_budget:
            return ActionResult("conflict", "预约超过对应的工作／私生活预算；请先调整比例或未开始日程再执行。本次冲突不产生惩罚。", item.id)
        result = self.set_activities([*self.state.activities, activity])
        if not result.ok:
            return ActionResult("conflict", f"预约未插入：{result.message}请先调整本旬日程或工作／私生活预算，再执行预约；本次冲突不产生惩罚。", item.id)
        item.status = "scheduled"
        self._appointment_history(item, "scheduled")
        self._log("预约排入", f"{item.label}已排入本旬日程，执行时才消耗{item.cost} AP。")
        return ActionResult("ok", "预约已加入日程末尾，可以继续调整顺序。", item.id)

    def update_appointment_preparation(self, appointment_id: str, preparation: str):
        from ..models import ActionResult

        item = self._find_appointment(appointment_id)
        if (item is None or item.status != "pending" or preparation not in PREPARATION_LABELS):
            return self._error("只能调整待决定预约的有效准备状态。")
        if item.preparation == preparation:
            return ActionResult("ok", "准备状态未变。", item.id)
        item.preparation = preparation
        self._log("预约准备", f"{item.label}：{item.preparation_label}（手动演示准备状态）。")
        return ActionResult("ok", "预约准备状态已更新。", item.id)

    def _detach_appointment(self, item: Appointment):
        linked = [activity for activity in self.state.activities
                  if getattr(activity, "appointment_id", None) == item.id]
        if any(activity.status != "pending" or getattr(activity, "spent_ap", 0) for activity in linked):
            return self._error("该预约活动已经开始，不能追回已使用时间。")
        if linked:
            return self.set_activities([activity for activity in self.state.activities
                                        if getattr(activity, "appointment_id", None) != item.id])
        return None

    def _appointment_consequence(self, item: Appointment, history: dict[str, Any]) -> None:
        identifier = f'{history["id"]}:consequence'
        if any(record["id"] == identifier for record in self.state.appointment_consequences):
            return
        self.state.appointment_consequences.append({
            "id": identifier, "appointment_id": item.id, "history_id": history["id"],
            "choice": history["action"], "source": item.source,
            "kind": CONSEQUENCE_KINDS[item.source], "status": "pending_simulation",
            "description": self.appointment_consequence_preview(item, history["action"]),
            "turn": self.state.turn_index, "quantified": False,
        })

    def reschedule_appointment(self, appointment_id: str, new_turn: int, reason: str = ""):
        from ..models import ActionResult, Phase

        item = self._find_appointment(appointment_id)
        if item is None or item.status not in {"pending", "scheduled"}:
            return self._error("该预约不存在或已经结束。")
        if self.state.phase != Phase.PLANNING:
            return self._error("请在规划阶段改期尚未开始的预约。")
        if (type(new_turn) is not int or new_turn <= max(item.due_turn, self.state.turn_index)
                or not _text(reason, 240, empty=True)):
            return self._error("改期须选择原执行旬与当前旬之后的日期，理由须为有效文本。")
        result = self._detach_appointment(item)
        if result is not None and not result.ok:
            return result
        original = item.due_turn
        item.due_turn = new_turn
        item.status = "pending"
        history = self._appointment_history(item, "rescheduled", old_turn=original, reason=reason)
        self._appointment_consequence(item, history)
        self._log("预约改期", f"{item.label}改至{self.appointment_date_label(new_turn)}；保留原定旬与历史。{self.appointment_consequence_preview(item, 'rescheduled')}")
        conflict = self.appointment_conflict(item)
        return ActionResult("ok", "预约已改期，分类后果已记录一次；到期会重新校验日程。" + conflict, item.id)

    def miss_appointment(self, appointment_id: str, reason: str = ""):
        from ..models import ActionResult, Phase

        item = self._find_appointment(appointment_id)
        if item is None or item.status not in {"pending", "scheduled"}:
            return self._error("该预约不存在或已经结束，不能重复记载缺席。")
        if self.state.phase != Phase.PLANNING or not _text(reason, 240, empty=True):
            return self._error("请在规划阶段决定不去，并使用有效文本记录原因。")
        result = self._detach_appointment(item)
        if result is not None and not result.ok:
            return result
        self._mark_appointment_missed(item, reason)
        return ActionResult("ok", "已记载缺席与分类后果，后果只提交一次。", item.id)

    def _mark_appointment_missed(self, item: Appointment, reason: str) -> None:
        item.status = "missed"
        history = self._appointment_history(item, "missed", reason=reason)
        self._appointment_consequence(item, history)
        self._log("预约缺席", f"{item.label}：{reason or '玩家选择不去'}。{self.appointment_consequence_preview(item, 'missed')}")

    def complete_appointment(self, activity: Any) -> None:
        item = self._find_appointment(getattr(activity, "appointment_id", None))
        if item is not None and item.status == "scheduled" and activity.status == "completed":
            item.status = "completed"
            self._appointment_history(item, "completed")
            self._log("预约履约", f"已完成{item.label}；预约与活动结果各只登记一次。")

    def expire_appointments(self) -> None:
        """Called once at turn settlement, before changing the calendar."""
        for item in self.state.appointments:
            if item.due_turn <= self.state.turn_index and item.status in {"pending", "scheduled"}:
                self._mark_appointment_missed(item, "本旬结束时未能履约")
