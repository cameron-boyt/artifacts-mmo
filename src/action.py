from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
from enum import Enum, auto

class CharacterAction(Enum):
    MOVE = "Move"

    FIGHT = "Fight"
    REST = "Rest"

    GATHER = "Gather"
    CRAFT = "Craft"

    BANK_DEPOSIT_ITEM = "Bank Deposit Item"
    BANK_DEPOSIT_GOLD = "Bank Deposit Gold"
    BANK_WITHDRAW_ITEM = "Bank Withdraw Item"
    BANK_WITHDRAW_GOLD = "Bank Withdraw Gold"

    EQUIP = "Equip"
    UNEQUIP = "Unequip"
    USE = "Use"

class ActionCondition(Enum):
    NONE = auto()
    INVENTORY_FULL = auto()
    BANK_HAS_ITEM_OF_QUANTITY = auto()
    FOREVER = auto()

class LogicalOperator(Enum):
    AND = auto()
    OR = auto()
    NOT = auto()

class ControlOperator(Enum):
    IF = auto()
    REPEAT = auto()

@dataclass
class Action:
    """A data object representing a command to be executed."""
    type: CharacterAction
    params: Dict[str, Any] = None
    until: ActionConditionExpression = None

@dataclass
class ActionGroup:
    """A group or sequence of actions to be completed."""
    actions: List[Action | ActionGroup]
    until: ActionConditionExpression | None = None

@dataclass(frozen=True)
class ActionConditionExpression:
    operator: LogicalOperator | None = None
    condition: ActionCondition | None = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    children: List["ActionConditionExpression"] = field(default_factory=list)

    def is_leaf(self) -> bool:
        return self.condition is not None

@dataclass(frozen=True)
class ActionControlNode:
    control_operator: ControlOperator
    branches: List[Tuple[ActionConditionExpression, ActionGroup]] | None
    fail_path: ActionConditionExpression | None
    control_node: ActionControlNode | None
    until: ActionConditionExpression | None
