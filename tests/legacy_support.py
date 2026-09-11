"""Explicit v1 fixtures keep pre-M03 regressions exercising saved legacy games.

New M03 tests import the production classes directly and exercise 30 AP rules.
"""

from dynasty.core import DemoConfig, GameSession


def LegacyDemoConfig(**kwargs):
    kwargs.setdefault("turn_rules_version", 1)
    kwargs.setdefault("health_ap_thresholds", [[0, 1], [40, 2], [80, 3]])
    return DemoConfig(**kwargs)


class LegacyGameSession(GameSession):
    @classmethod
    def new_game(cls, world_snapshot=None, config=None, profile=None):
        return super().new_game(world_snapshot, config or LegacyDemoConfig(), profile)


def SequentialDemoConfig(**kwargs):
    """The original M03 v2 sequence remains an explicit saved-game contract."""
    kwargs.setdefault("turn_rules_version", 2)
    return DemoConfig(**kwargs)


class SequentialGameSession(GameSession):
    @classmethod
    def new_game(cls, world_snapshot=None, config=None, profile=None):
        return super().new_game(world_snapshot, config or SequentialDemoConfig(), profile)
