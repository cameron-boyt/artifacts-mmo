from typing import Tuple

from src.action import Action, ActionGroup, ActionConditionExpression, ActionControlNode, ControlOperator

def IF(*branches: Tuple[ActionConditionExpression, ActionGroup], fail_path: Action | ActionGroup) -> ActionControlNode:
    return ActionControlNode(
        control_operator=ControlOperator.IF ,
        branches=branches,
        fail_path=fail_path
    )

def REPEAT(control_node: ActionControlNode, until: ActionConditionExpression) -> ActionControlNode:
    return ActionControlNode(
        control_operator = ControlOperator.REPEAT,
        control_node=control_node,
        until=until
    )