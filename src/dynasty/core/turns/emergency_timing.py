"""Persisted safe delivery windows for court, work, and private turn stages."""

from __future__ import annotations

import hashlib
from typing import Any


ATTEMPT_FIELDS = {"turn", "stage", "budget", "threshold", "floor", "seed", "draw_index",
                  "initial_work_budget", "status", "reason"}


def _private_position(seed: int, event_id: str, turn: int, draw: int,
                      floor: int, ceiling: int) -> int:
    digest = hashlib.sha256(f"{seed}:{event_id}:{turn}:{draw}".encode("utf-8")).digest()
    return floor + int.from_bytes(digest[:8], "big") % (ceiling - floor + 1)


def _defer(session: Any, event: Any, attempt: dict, reason: str) -> bool:
    if attempt["status"] != "deferred":
        attempt["status"] = "deferred"
        attempt["reason"] = reason
        event.trigger_turn = session.state.turn_index + 1
        session._log("急报顺延", f"{event.title}：{reason}；改在下一旬按阶段重新安排送达。")
    return False


def _deliver(attempt: dict, reason: str) -> bool:
    attempt["status"] = "delivered"
    attempt["reason"] = reason
    return True


def _assign_private(session: Any, event: Any, attempt: dict) -> bool:
    state = session.state
    budget = state.stage_budget["private"]
    spent = state.stage_spent["private"]
    current = session.current_activity
    # Fixed private activities charge on entry: spent includes the activity being played.
    floor = max(1, spent if current is not None and current.category == "private" else spent + 1)
    attempt.update(stage="private", budget=budget, floor=floor)
    if budget < 2 or floor >= budget:
        return _defer(session, event, attempt, "本旬没有非最后一项的私生活行动位置")
    draw = state.random_state.get("draws", 0)
    seed = state.random_state.get("seed", 1)
    if type(seed) is not int or type(draw) is not int or draw < 0:
        raise ValueError("存档随机种子或调用计数无效。")
    attempt.update(seed=seed, draw_index=draw,
                   threshold=_private_position(seed, event.id, state.turn_index, draw,
                                               floor, budget - 1))
    state.random_state["draws"] = draw + 1
    return True


def _new_attempt(session: Any, event: Any, *, leaving_work: bool) -> dict:
    state = session.state
    initial_total = getattr(state, "stage_initial_work_budget",
                            state.stage_budget["court"] + state.stage_budget["work"])
    work = max(0, initial_total - state.stage_budget["court"])
    attempt = {"turn": state.turn_index, "stage": "work" if work > 0 else "private",
               "budget": work if work > 0 else state.stage_budget["private"],
               "threshold": (work + 1) // 2 if work > 0 else None,
               "floor": 0, "seed": state.random_state.get("seed", 1), "draw_index": None,
               "initial_work_budget": work, "status": "scheduled", "reason": ""}
    timing = state.emergency_timing.setdefault(event.id, {"attempts": []})
    timing["attempts"].append(attempt)
    if work > 0:
        if state.turn_stage == "private" and state.stage_spent["work"] == 0:
            _assign_private(session, event, attempt)
            return attempt
        # A freshly submitted report must not pretend it arrived at an already passed midpoint.
        if state.turn_stage in {"private", "finished"} or (
                state.turn_stage == "work" and state.stage_spent["work"] > attempt["threshold"]):
            _defer(session, event, attempt, "急报登记时已错过本旬工作阶段的中点")
    else:
        _assign_private(session, event, attempt)
    return attempt


def v3_emergency_can_interrupt(session: Any, event: Any, *, leaving_work: bool = False) -> bool:
    """Claim a safe delivery point once; the caller activates its existing emergency flow.

    Budget dictionaries include unassigned time. This never relies on how many cards were
    preplanned. Call with ``leaving_work=True`` before committing an early stage transition.
    """
    state = session.state
    if event.status != "pending" or event.trigger_turn > state.turn_index:
        return False
    if state.phase.value not in {"executing", "interrupted"}:
        return False
    if state.active_emergency_id is not None:
        return False
    timing = state.emergency_timing.get(event.id)
    attempt = timing["attempts"][-1] if timing and timing["attempts"] else None
    if attempt is None or attempt["turn"] != state.turn_index:
        attempt = _new_attempt(session, event, leaving_work=leaving_work)
    if attempt["status"] != "scheduled":
        return False
    # Court is never a delivery stage, even if a queued event's threshold has been reached.
    if state.turn_stage == "court" or (session.current_activity is not None
                                       and session.current_activity.kind == "court"):
        return False
    if state.turn_stage == "finished":
        return _defer(session, event, attempt, "本旬活动已结束，不能在最后行动之后送达急报")

    if attempt["stage"] == "work":
        spent = state.stage_spent["work"]
        if leaving_work:
            if spent > 0:
                return _deliver(attempt, "工作阶段提前结束，在转入私生活前的安全点送达")
            attempt.update(stage="await_private", threshold=None, floor=0, budget=0)
            attempt["reason"] = "工作阶段未实际投入时间，转入私生活后选择非最后行动位置"
            return False
        if state.turn_stage == "private":
            if spent == 0:
                attempt.update(stage="await_private", threshold=None, floor=0, budget=0)
            else:
                return _defer(session, event, attempt, "已离开工作阶段，错过了本旬工作急报窗口")
        elif state.turn_stage == "work" and spent >= attempt["threshold"]:
            replaceable = any(card.status in {"pending", "in_progress"} for card in state.activities)
            if (not state.court_assigned and not replaceable
                    and state.stage_unallocated["work"] < 1):
                # The caller can explicitly charge a new emergency period to unassigned time.
                return False
            return _deliver(attempt, "工作阶段达到最初预算中点，在已提交时间段的安全点送达")
        else:
            return False

    if attempt["stage"] == "await_private":
        if state.turn_stage != "private":
            return False
        if not _assign_private(session, event, attempt):
            return False
    if attempt["stage"] == "private":
        if state.turn_stage != "private":
            return False
        private_spent = state.stage_spent["private"]
        current_budget = state.stage_budget["private"]
        current = session.current_activity
        if private_spent >= current_budget:
            return _defer(session, event, attempt, "本旬已进入最后一个私生活行动，急报不能在此送达")
        if (current is not None and current.category == "private"
                and current.status == "in_progress" and private_spent >= attempt["threshold"]):
            return _deliver(attempt, "在已保存的私生活行动位置送达，仍留有后续活动时间")
    return False


def validate_emergency_timing(state: Any) -> None:
    """Reject redraws, impossible positions, and timing detached from event history."""
    timings = state.emergency_timing
    if not isinstance(timings, dict):
        raise ValueError("存档急报调度记录必须为字典。")
    if (not isinstance(state.random_state, dict)
            or type(state.random_state.get("seed")) is not int
            or type(state.random_state.get("draws")) is not int
            or state.random_state["draws"] < 0):
        raise ValueError("存档急报随机种子或调用计数无效。")
    events = {event.id: event for event in state.emergencies}
    draw_indices = set()
    for identifier, timing in timings.items():
        if (not isinstance(identifier, str) or identifier not in events
                or not isinstance(timing, dict) or set(timing) != {"attempts"}
                or not isinstance(timing["attempts"], list) or not timing["attempts"]):
            raise ValueError("存档急报调度缺少对应事件或尝试记录。")
        previous_turn = -1
        for index, attempt in enumerate(timing["attempts"]):
            if (not isinstance(attempt, dict) or set(attempt) != ATTEMPT_FIELDS
                    or any(type(attempt[key]) is not int for key in
                           ("turn", "budget", "floor", "seed", "initial_work_budget"))
                    or not previous_turn < attempt["turn"] <= state.turn_index
                    or min(attempt["budget"], attempt["floor"], attempt["initial_work_budget"]) < 0
                    or not isinstance(attempt["stage"], str)
                    or attempt["stage"] not in {"work", "private", "await_private"}
                    or not isinstance(attempt["status"], str)
                    or attempt["status"] not in {"scheduled", "delivered", "deferred"}
                    or not isinstance(attempt["reason"], str)
                    or (index < len(timing["attempts"]) - 1 and attempt["status"] != "deferred")):
                raise ValueError("存档急报调度阶段、预算或历史顺序无效。")
            previous_turn = attempt["turn"]
            stage, threshold = attempt["stage"], attempt["threshold"]
            if stage == "work":
                if (attempt["budget"] < 1 or attempt["initial_work_budget"] != attempt["budget"]
                        or type(threshold) is not int or threshold != (attempt["budget"] + 1) // 2
                        or attempt["draw_index"] is not None or attempt["floor"] != 0):
                    raise ValueError("存档工作急报必须保持最初预算的中点。")
            elif stage == "await_private":
                if (threshold is not None or attempt["draw_index"] is not None
                        or attempt["budget"] != 0 or attempt["floor"] != 0
                        or attempt["initial_work_budget"] < 1 or attempt["status"] != "scheduled"):
                    raise ValueError("存档工作转私生活的急报等待状态无效。")
            elif threshold is None:
                if (attempt["status"] != "deferred" or attempt["draw_index"] is not None
                        or not (attempt["budget"] < 2 or attempt["floor"] >= attempt["budget"])):
                    raise ValueError("存档私生活急报缺少有效排点。")
            else:
                draw = attempt["draw_index"]
                if (type(draw) is not int or draw < 0 or draw in draw_indices
                        or type(threshold) is not int
                        or not 1 <= attempt["floor"] <= threshold < attempt["budget"]
                        or threshold != _private_position(attempt["seed"], identifier, attempt["turn"],
                                                          draw, attempt["floor"], attempt["budget"] - 1)):
                    raise ValueError("存档私生活急报位置无效或与已保存种子不一致。")
                draw_indices.add(draw)
        event = events[identifier]
        last = timing["attempts"][-1]
        if (last["status"] == "deferred" and event.trigger_turn <= last["turn"]
                or last["status"] == "delivered" and event.status not in {"active", "resolved"}
                or last["status"] == "scheduled" and event.status != "pending"):
            raise ValueError("存档急报状态与已提交送达点不一致。")
    draws = state.random_state.get("draws", 0)
    if type(draws) is not int or draws < 0 or any(index >= draws for index in draw_indices):
        raise ValueError("存档急报随机调用计数不完整。")
