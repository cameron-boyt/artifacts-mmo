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
    INVENTORY_EMPTY = auto()
    INVENTORY_HAS_AVAILABLE_SPACE = auto()
    INVENTORY_HAS_AVAILABLE_SPACE_FOR_ITEMS = auto()
    BANK_HAS_ITEM_OF_QUANTITY = auto()
    INVENTORY_HAS_ITEM_OF_QUANTITY = auto()
    BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY = auto()
    FOREVER = auto()

class ActionOutcome(Enum):
    SUCCESS = auto()
    FAIL = auto()
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

@dataclass
class ActionControlNode:
    control_operator: ControlOperator
    branches: List[Tuple[ActionConditionExpression, ActionGroup]] | None = None
    fail_path: ActionConditionExpression | None = None
    control_node: ActionControlNode | None = None
    until: ActionConditionExpression | None = None

    def __post_init__(self):
        if self.control_operator == ControlOperator.IF:
            # There must be at least one branch
            assert(self.branches and len(self.branches) > 0)

            # There must be a fail_path defined
            assert(self.fail_path)

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
