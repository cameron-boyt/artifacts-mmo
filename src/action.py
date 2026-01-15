from dataclasses import dataclass
from typing import Any, Dict, List
from enum import Enum

class CharacterAction(Enum):
    MOVE = 0
    FIGHT = 1
    REST = 2
    GATHER = 3
    BANK = 4

class ActionCondition(Enum):
    NONE = 0
    INVENTORY_FULL = 1
    FOREVER = 999

@dataclass
class Action:
    """A data object representing a command to be executed."""
    type: CharacterAction
    params: Dict[str, Any] = None
    repeat: bool = False
    repeat_until: ActionCondition = ActionCondition.NONE

@dataclass
class ActionGroup:
    """A group or sequence of actions to be completed"""
    actions: List[Action | ActionGroup]
    repeat: bool = False
    repeat_until: ActionCondition = ActionCondition.NONE