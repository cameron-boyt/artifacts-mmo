from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Tuple

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

    GET_TASK = "Get Task"
    COMPLETE_TASK = "Complete Task"
    CANCEL_TASK = "Cancel Task"
    TASK_EXCHANGE = "Task Exchange"
    TASK_TRADE = "Task Trade"

class ActionCondition(Enum):
    NONE = auto()
    INVENTORY_FULL = auto()
    INVENTORY_EMPTY = auto()
    INVENTORY_HAS_AVAILABLE_SPACE = auto()
    INVENTORY_HAS_AVAILABLE_SPACE_FOR_ITEMS = auto()
    BANK_HAS_ITEM_OF_QUANTITY = auto()
    INVENTORY_HAS_ITEM_OF_QUANTITY = auto()
    BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY = auto()
    ITEMS_IN_LAST_WITHDRAW_CONTEXT = auto()
    HAS_TASK = auto()
    HAS_TASK_OF_TYPE = auto()
    TASK_COMPLETE = auto()
    FOREVER = auto()

class ActionOutcome(Enum):
    SUCCESS = auto()
    FAIL = auto()
    FAIL_RETRY = auto()
    FAIL_CONTINUE = auto()
    CANCEL = auto()

class LogicalOperator(Enum):
    AND = auto()
    OR = auto()
    NOT = auto()

class ControlOperator(Enum):
    IF = auto()
    REPEAT = auto()

@dataclass
class Action:
    """A command to be executed."""
    type: CharacterAction
    params: Dict[str, Any] = field(default_factory=dict)
    until: ActionConditionExpression | None = None

@dataclass
class ActionGroup:
    """A group or sequence of actions to be completed."""
    actions: List["Action | ActionGroup | ActionControlNode"] = field(default_factory=list)
    until: ActionConditionExpression | None = None

@dataclass
class ActionControlNode:
    """A sequencing control node determinine action flow such as conditions or reptition."""
    control_operator: ControlOperator
    branches: List[Tuple[ActionConditionExpression, ActionGroup]] | None = None
    fail_path: "Action | ActionGroup | ActionControlNode" | None = None
    control_node: "ActionControlNode" | None = None
    until: ActionConditionExpression | None = None

    def __post_init__(self):
        if self.control_operator == ControlOperator.IF:
            # There must be at least one branch
            assert(self.branches and len(self.branches) > 0)

            # There should be no child control_node or until condition defined
            assert(self.control_node is None)
            assert(self.until is None)
        
        if self.control_operator == ControlOperator.REPEAT:
            # A control_node must be defined
            assert(self.control_node is not None)

            # An until condition must be defined
            assert(self.until)

            # There should be no decision branches or fail_path defined
            assert(self.branches is None)
            assert(self.fail_path is None)

@dataclass(frozen=True)
class ActionConditionExpression:
    """A condition or set of conditions subject to logical operations."""
    operator: LogicalOperator | None = None
    condition: ActionCondition | None = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    children: List["ActionConditionExpression"] = field(default_factory=list)

    def __post_init__(self):
        if self.operator:
            # Is a logical node
            assert(self.condition is None)

            if self.operator == LogicalOperator.NOT:
                # NOT nodes can only have one child
                assert(self.children and len(self.children) == 1)
            else:
                # Other logical nodes must have at least 2 children
                assert(self.children and len(self.children) >= 2)
        
        if not self.operator:
            # Is a leaf node
            assert(self.condition is not None)
            assert(not self.children)

    def is_leaf(self) -> bool:
        return self.condition is not None
