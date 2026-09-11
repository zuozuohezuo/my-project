"""Emperor abilities; values are editable references, not growth or event rules."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from typing import Any

from .motives import PersonalObjective, default_personality, validate_personality


@dataclass(frozen=True)
class AbilityDefinition:
    id: str
    label: str
    description: str
    group: str = ""


ATTRIBUTE_GROUPS = (
    ("intelligence", "智力类"),
    ("body", "身体类"),
    ("will", "意志类"),
)

ATTRIBUTE_DEFINITIONS = (
    AbilityDefinition("logic", "逻辑", "分析关系、组织推理的基础能力。", "intelligence"),
    AbilityDefinition("emotional_intelligence", "情商", "理解与回应他人情绪的基础能力。", "intelligence"),
    AbilityDefinition("memory", "记忆力", "记住与回想信息的基础能力。", "intelligence"),
    AbilityDefinition("insight", "洞察力", "理解线索背后原因与意图的基础能力。", "intelligence"),
    AbilityDefinition("creativity", "创造力", "构想新思路与新方法的基础能力。", "intelligence"),
    AbilityDefinition("strength", "力量", "身体施力的基础能力。", "body"),
    AbilityDefinition("constitution", "体质", "长期身体基础，与当前健康状态分别记录。", "body"),
    AbilityDefinition("agility", "敏捷", "动作协调与身体反应的基础能力。", "body"),
    AbilityDefinition("perception", "感知", "通过感官察觉环境与细节的基础能力。", "body"),
    AbilityDefinition("appearance", "颜值", "人物外貌的基础特征。", "body"),
    AbilityDefinition("self_discipline", "自律能力", "坚持计划与约束自身行为的基础能力。", "will"),
    AbilityDefinition("emotional_resilience", "情绪抗性", "承受情绪冲击的基础能力。", "will"),
    AbilityDefinition("courage", "胆量", "面对风险与威胁时的基础勇气。", "will"),
)

SKILL_DEFINITIONS = (
    AbilityDefinition("administration", "政务处理", "梳理奏章、理解行政事务与处理政务。"),
    AbilityDefinition("military_strategy", "军事策略", "分析战局、谋划战略与判断攻守。"),
    AbilityDefinition("people_reading", "识人能力", "判断人物能力、性情与言行。"),
    AbilityDefinition("rhetoric", "话术", "表达、说服与交涉的技巧。"),
    AbilityDefinition("calligraphy", "书法", "运笔、结字与书写的技艺。"),
    AbilityDefinition("scholarship", "学识", "积累的知识及对其内容的理解。"),
)

# These are page demonstration values, not historical ratings or settled scales.
DEFAULT_ATTRIBUTE_VALUE = 50
DEFAULT_SKILL_VALUE = 0


def _validate_values(values: Any, definitions: tuple[AbilityDefinition, ...], label: str) -> None:
    if not isinstance(values, dict) or set(values) != {item.id for item in definitions}:
        raise ValueError(f"皇帝{label}须包含全部已定义项目，且不能包含未知项目。")
    for item in definitions:
        value = values[item.id]
        if type(value) is not int or value < 0:
            raise ValueError(f"{item.label}须为非负整数。")


def _validate_text(value: Any, label: str, *, allow_empty: bool = False) -> None:
    if (not isinstance(value, str) or (not allow_empty and not value.strip())
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise ValueError(f"{label}须为{'可留空的' if allow_empty else '非空'}单行文本。")


def _validate_meter(value: Any, label: str) -> None:
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError(f"{label}须为0至100的整数。")


def validate_health_value(value: Any) -> None:
    """Validate the single overall-health value kept by GameState."""
    _validate_meter(value, "整体健康")


@dataclass
class BodyCondition:
    part: str
    name: str
    kind: str = "disease"

    def validate(self) -> None:
        _validate_text(self.part, "异常部位")
        _validate_text(self.name, "异常名称")
        if not isinstance(self.kind, str) or self.kind not in {"disease", "disability", "injury"}:
            raise ValueError("身体异常类型须为疾病、残疾或伤势。")

    @classmethod
    def from_dict(cls, raw: Any) -> BodyCondition:
        if not isinstance(raw, dict) or set(raw) != {"part", "name", "kind"}:
            raise ValueError("身体异常记录字段缺失或无效。")
        condition = cls(**raw)
        condition.validate()
        return condition


@dataclass
class EmperorModifier:
    name: str
    target_type: str
    target: str
    amount: int
    source: str = ""
    duration: str = "long_term"
    remaining_turns: int | None = None

    def validate(self) -> None:
        _validate_text(self.name, "修正名称")
        _validate_text(self.source, "修正来源", allow_empty=True)
        if (not isinstance(self.target_type, str)
                or self.target_type not in {"attribute", "skill_effect"}):
            raise ValueError("修正目标类型须为基础属性或技能效果。")
        definitions = ATTRIBUTE_DEFINITIONS if self.target_type == "attribute" else SKILL_DEFINITIONS
        if not isinstance(self.target, str) or self.target not in {item.id for item in definitions}:
            raise ValueError("修正目标不是该类型下的已定义项目。")
        if type(self.amount) is not int:
            raise ValueError("修正数值须为整数；属性使用点数，技能效果使用百分比点。")
        if not isinstance(self.duration, str) or self.duration not in {"long_term", "short_term"}:
            raise ValueError("修正期限须为长期或短期。")
        if self.duration == "long_term":
            if self.remaining_turns is not None:
                raise ValueError("长期修正不能设置剩余旬数。")
        elif type(self.remaining_turns) is not int or self.remaining_turns < 1:
            raise ValueError("短期修正的剩余旬数须为正整数。")

    @classmethod
    def from_dict(cls, raw: Any) -> EmperorModifier:
        required = {"name", "target_type", "target", "amount", "source", "duration", "remaining_turns"}
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError("修正记录字段缺失或无效。")
        modifier = cls(**raw)
        modifier.validate()
        return modifier


@dataclass
class EmperorProfile:
    attributes: dict[str, int] = field(default_factory=lambda: {
        item.id: DEFAULT_ATTRIBUTE_VALUE for item in ATTRIBUTE_DEFINITIONS
    })
    skills: dict[str, int] = field(default_factory=lambda: {
        item.id: DEFAULT_SKILL_VALUE for item in SKILL_DEFINITIONS
    })
    # Preserve legacy freeform traits separately from the nine personality axes.
    traits: list[str] = field(default_factory=list)
    pressure: int = 0
    body_conditions: list[BodyCondition] = field(default_factory=list)
    modifiers: list[EmperorModifier] = field(default_factory=list)
    personality: dict[str, int] = field(default_factory=default_personality)
    objectives: list[PersonalObjective] = field(default_factory=list)

    def validate(self) -> None:
        _validate_values(self.attributes, ATTRIBUTE_DEFINITIONS, "基础属性")
        _validate_values(self.skills, SKILL_DEFINITIONS, "技能")
        if (not isinstance(self.traits, list)
                or any(not isinstance(trait, str) or not trait.strip()
                       or any(ord(character) < 32 or ord(character) == 127 for character in trait)
                       for trait in self.traits)):
            raise ValueError("皇帝性格须为非空文本组成的列表。")
        _validate_meter(self.pressure, "压力")
        if not isinstance(self.body_conditions, list):
            raise ValueError("身体异常须为BodyCondition列表。")
        for condition in self.body_conditions:
            if not isinstance(condition, BodyCondition):
                raise ValueError("身体异常须使用BodyCondition。")
            condition.validate()
        if not isinstance(self.modifiers, list):
            raise ValueError("皇帝修正须为EmperorModifier列表。")
        for modifier in self.modifiers:
            if not isinstance(modifier, EmperorModifier):
                raise ValueError("皇帝修正须使用EmperorModifier。")
            modifier.validate()
        validate_personality(self.personality)
        if not isinstance(self.objectives, list):
            raise ValueError("人物目标须为PersonalObjective列表。")
        identifiers: set[str] = set()
        for objective in self.objectives:
            if not isinstance(objective, PersonalObjective):
                raise ValueError("人物目标须使用PersonalObjective。")
            objective.validate()
            if objective.id in identifiers:
                raise ValueError("人物目标编号不能重复。")
            identifiers.add(objective.id)

    def attribute_bonus(self, identifier: str) -> int:
        if identifier not in self.attributes:
            raise KeyError(identifier)
        return sum(modifier.amount for modifier in self.modifiers
                   if modifier.target_type == "attribute" and modifier.target == identifier)

    def effective_attribute(self, identifier: str) -> int:
        return max(0, self.attributes[identifier] + self.attribute_bonus(identifier))

    def skill_effect_bonus(self, identifier: str) -> int:
        if identifier not in self.skills:
            raise KeyError(identifier)
        return sum(modifier.amount for modifier in self.modifiers
                   if modifier.target_type == "skill_effect" and modifier.target == identifier)

    def skill_effect_percent(self, identifier: str) -> int:
        return max(0, 100 + self.skill_effect_bonus(identifier))

    def advance_modifiers_turn(self) -> None:
        """Consume one completed turn, never a refresh, pause or failed action."""
        remaining: list[EmperorModifier] = []
        for modifier in self.modifiers:
            if modifier.duration == "long_term":
                remaining.append(modifier)
            elif modifier.remaining_turns > 1:
                remaining.append(replace(modifier, remaining_turns=modifier.remaining_turns - 1))
        self.modifiers = remaining

    @classmethod
    def from_dict(cls, raw: Any) -> EmperorProfile:
        required = {"attributes", "skills", "traits"}
        optional = {"pressure", "body_conditions", "modifiers", "personality", "objectives"}
        if (not isinstance(raw, dict) or not required.issubset(raw)
                or not set(raw).issubset(required | optional)):
            raise ValueError("存档皇帝属性技能档案字段缺失或无效。")
        try:
            data = copy.deepcopy(raw)
            for key, record_type in (("body_conditions", BodyCondition), ("modifiers", EmperorModifier),
                                     ("objectives", PersonalObjective)):
                if key in data:
                    if not isinstance(data[key], list):
                        raise ValueError("身体异常、修正及人物目标记录须为列表。")
                    data[key] = [record_type.from_dict(item) for item in data[key]]
            profile = cls(**data)
            profile.validate()
        except ValueError as error:
            raise ValueError(f"存档皇帝档案无效：{error}") from error
        return profile
