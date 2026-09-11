"""Personality preferences and explicit goals; no automatic motives or rewards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PersonalityDimension:
    id: str
    left: str
    right: str
    description: str


PERSONALITY_DIMENSIONS = (
    PersonalityDimension("benevolence", "仁厚", "严酷", "面对他人过失时，倾向宽待还是严惩。"),
    PersonalityDimension("trust", "宽信", "多疑", "与人相处时，倾向先给予信任还是保留怀疑。"),
    PersonalityDimension("tradition", "守成", "求变", "面对制度与惯例时，倾向维持还是改变。"),
    PersonalityDimension("luxury", "质朴", "奢华", "对生活排场与物质享受的偏好。"),
    PersonalityDimension("control", "放权", "掌控", "处理事务时，倾向委派还是亲自掌握。"),
    PersonalityDimension("humility", "谦逊", "自负", "面对不同意见时，倾向审视自身判断还是确信自己正确。"),
    PersonalityDimension("partiality", "重情", "秉公", "人情与共同规则冲突时的取舍倾向。"),
    PersonalityDimension("integrity", "守信", "权宜", "既有承诺与眼前处境冲突时的取舍倾向。"),
    PersonalityDimension("sociability", "合群", "独处", "倾向与人共处还是保留独自活动的空间。"),
)


def default_personality() -> dict[str, int]:
    """Neutral demonstration values on a left(0)-to-right(100) display scale."""
    return {dimension.id: 50 for dimension in PERSONALITY_DIMENSIONS}


def validate_personality(personality: Any) -> None:
    if (not isinstance(personality, dict)
            or set(personality) != {dimension.id for dimension in PERSONALITY_DIMENSIONS}):
        raise ValueError("人物性格须包含全部九项维度，且不能包含未知项目。")
    for dimension in PERSONALITY_DIMENSIONS:
        value = personality[dimension.id]
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError(f"{dimension.left}—{dimension.right}须为0至100的整数。")


def _valid_text(value: Any, *, required: bool, multiline: bool = False) -> bool:
    return (isinstance(value, str) and (not required or bool(value.strip()))
            and not any((ord(character) < 32 and not (multiline and character in "\n\r\t"))
                        or ord(character) == 127 for character in value))


@dataclass
class PersonalObjective:
    id: str
    kind: str
    title: str
    description: str
    activity_kind: str
    target_count: int
    progress: int = 0
    status: str = "active"
    completed_turn: int | None = None

    def validate(self) -> None:
        # Import when validating to keep the domain-model import graph acyclic.
        from .models import ACTIVITY_LABELS

        if not _valid_text(self.id, required=True):
            raise ValueError("人物目标编号须为非空单行文本。")
        if not isinstance(self.kind, str) or self.kind not in {"desire", "ambition"}:
            raise ValueError("人物目标类型须为近期欲望或长期野心。")
        if not _valid_text(self.title, required=True):
            raise ValueError("人物目标名称须为非空单行文本。")
        if not _valid_text(self.description, required=False, multiline=True):
            raise ValueError("人物目标说明须为文本，且不能包含无效控制字符。")
        if not isinstance(self.activity_kind, str) or self.activity_kind not in ACTIVITY_LABELS:
            raise ValueError("人物目标须使用已有活动作为完成条件。")
        if type(self.target_count) is not int or self.target_count < 1:
            raise ValueError("人物目标的完成次数须为正整数。")
        if type(self.progress) is not int or not 0 <= self.progress <= self.target_count:
            raise ValueError("人物目标进度须为0至目标次数的整数。")
        if not isinstance(self.status, str) or self.status not in {"active", "fulfilled"}:
            raise ValueError("人物目标状态无效。")
        if self.status == "active":
            if self.progress >= self.target_count or self.completed_turn is not None:
                raise ValueError("未完成的人物目标不能含有达标进度或完成旬数。")
        elif (self.progress != self.target_count or type(self.completed_turn) is not int
              or self.completed_turn < 0):
            raise ValueError("已满足的人物目标须达到目标次数并记录有效完成旬数。")

    @classmethod
    def from_dict(cls, raw: Any) -> PersonalObjective:
        required = {"id", "kind", "title", "description", "activity_kind", "target_count",
                    "progress", "status", "completed_turn"}
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError("人物目标记录字段缺失或无效。")
        objective = cls(**raw)
        objective.validate()
        return objective

    def record_completed_activities(self, count: int, turn: int) -> bool:
        """Count this settlement only; return whether fulfillment happens now."""
        if self.status != "active" or count <= 0:
            return False
        self.progress = min(self.target_count, self.progress + count)
        if self.progress == self.target_count:
            self.status = "fulfilled"
            self.completed_turn = turn
            return True
        return False
