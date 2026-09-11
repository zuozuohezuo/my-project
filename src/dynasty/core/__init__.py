"""UI-independent emperor-game framework."""

from .emperor import (
    ATTRIBUTE_DEFINITIONS, ATTRIBUTE_GROUPS, SKILL_DEFINITIONS,
    BodyCondition, EmperorModifier, EmperorProfile,
)
from .models import (
    ACTIVITY_LABELS, OFFICE_ACTIVITIES, WORK_ACTIVITIES, ActionResult, Activity, CommandDefinition, DemoConfig,
    EmergencyEvent, GameState, LocalDecisionProvider, PendingCommand, Phase,
    PlannedCommand, ScenarioProfile, TurnPlan,
)
from .session import SAVE_VERSION, GameSession
from .motives import PERSONALITY_DIMENSIONS, PersonalObjective, PersonalityDimension
from .turns.appointments import Appointment
from .turns.stage_runner import TURN_STAGES

__all__ = [
    "ATTRIBUTE_DEFINITIONS", "ATTRIBUTE_GROUPS", "SKILL_DEFINITIONS",
    "BodyCondition", "EmperorModifier", "EmperorProfile",
    "PERSONALITY_DIMENSIONS", "PersonalObjective", "PersonalityDimension",
    "ACTIVITY_LABELS", "OFFICE_ACTIVITIES", "WORK_ACTIVITIES", "TURN_STAGES", "Appointment", "ActionResult", "Activity", "CommandDefinition", "DemoConfig",
    "EmergencyEvent", "GameSession", "GameState", "LocalDecisionProvider",
    "PendingCommand", "Phase", "PlannedCommand", "SAVE_VERSION", "ScenarioProfile", "TurnPlan",
]
