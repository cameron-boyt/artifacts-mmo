from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Callable

if TYPE_CHECKING:
    from src.character import CharacterAgent

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

class MetaAction(Enum):
    FORCE_SUCCESS = "Force Succes"
    FORCE_FAIL = "Force Fail"

    SET_CONTEXT = "Set Context"
    UPDATE_CONTEXT = "Update Context"
    CLEAR_CONTEXT = "Clear Context"

    PREPARE_LOADOUT = "Prepare Loadout"
    CLEAR_PREPARED_LOADOUT = "Clear Prepped Loadout"

    CREATE_ITEM_RESERVATION = "Create Item Resevation"
    UPDATE_ITEM_RESERVATION = "Update Item Resevation"
    CLEAR_ITEM_RESERVATION = "Clear Item Resevation"

class ActionCondition(Enum):
    NONE = auto()
    FOREVER = auto()
    
    AT_LOCATION = auto()
    
    INVENTORY_FULL = auto()
    INVENTORY_EMPTY = auto()
    INVENTORY_HAS_AVAILABLE_SPACE = auto()
    INVENTORY_HAS_AVAILABLE_SPACE_FOR_ITEMS = auto()

    BANK_HAS_ITEM_OF_QUANTITY = auto()
    INVENTORY_HAS_ITEM_OF_QUANTITY = auto()
    BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY = auto()

    GLOBAL_AVAILABLE_QUANTIY_OF_ITEM = auto()

    CRAFT_INGREDIENTS_IN_INV = auto()
    CRAFT_INGREDIENTS_IN_BANK = auto()
    CRAFT_INGREDIENTS_IN_BANK_OR_INV = auto()

    PREPARED_LOADOUT_HAS_ITEMS = auto()
    PREPARED_LOADOUT_DIFFERS_FROM_EQUIPPED = auto()
    ITEMS_IN_EQUIP_QUEUE = auto()

    INVENTORY_CONTAINS_USABLE_FOOD = auto()
    BANK_CONTAINS_USABLE_FOOD = auto()
    HEALTH_LOW_ENOUGH_TO_EAT = auto()

    RESOURCE_FROM_FIGHTING = auto()
    RESOURCE_FROM_GATHERING = auto()
    RESOURCE_FROM_CRAFTING = auto()

    HAS_TASK = auto()
    HAS_TASK_OF_TYPE = auto()
    TASK_COMPLETE = auto()
    HAS_SKILL_LEVEL = auto()

    CONTEXT_VALUE_EQUALS = auto()

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
    WHILE = auto()
    DO_WHILE = auto()
    TRY = auto()

@dataclass(frozen=True)
class Action:
    """A command to be executed."""
    type: CharacterAction | MetaAction
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ActionGroup:
    """A group or sequence of actions to be completed."""
    actions: List[ActionExecutable] = field(default_factory=list)

@dataclass(frozen=True)
class ActionControlNode:
    """A sequencing control node determinine action flow such as conditions or repetition."""
    control_operator: ControlOperator
    node: ActionExecutable| None = None

    branches: List[Tuple[ActionConditionExpression, ActionExecutable]] | None = None
    fail_path: ActionExecutable | None = None

    condition: ActionConditionExpression | None = None

    success_path : ActionExecutable | None = None
    error_path: ActionExecutable | None = None
    finally_path: ActionExecutable | None = None

    def __post_init__(self):
        if self.control_operator == ControlOperator.IF:
            # There must be at least one branch
            assert(self.branches and len(self.branches) > 0)

            # There should be no child control_node or until condition defined
            assert(self.node is None)
            assert(self.condition is None)
            assert(self.success_path is None)
            assert(self.error_path is None)
            assert(self.finally_path is None)
        
        if self.control_operator == ControlOperator.WHILE or self.control_operator == ControlOperator.DO_WHILE:
            # A child node and until condition must be defined
            assert(self.node)
            assert(self.condition)
            
            # There should be no decision branches or fail_path defined
            assert(self.branches is None)
            assert(self.fail_path is None)
            assert(self.success_path is None)
            assert(self.error_path is None)
            assert(self.finally_path is None)

        if self.control_operator == ControlOperator.TRY:
            # A child node must be defined, note that error_path and finally_path are optional
            assert(self.node)

            # There should be no decision, branches, or conditions
            assert(self.branches is None)
            assert(self.fail_path is None)
            assert(self.condition is None)

@dataclass
class DeferredPlanNode:
    resolver: Callable[[CharacterAgent], ActionExecutable]

type ActionExecutable = Action | ActionGroup | ActionControlNode | DeferredPlanNode

@dataclass(frozen=True)
class ActionConditionExpression:
    """A condition or set of conditions subject to logical operations."""
    operator: LogicalOperator | None = None
    condition: ActionCondition | None = None
    params: Dict[str, Any] = field(default_factory=dict)
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
  