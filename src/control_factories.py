from typing import Tuple

from src.action import ActionConditionExpression, ActionControlNode, ControlOperator, ActionExecutable

def IF(*branches: Tuple[ActionConditionExpression, ActionExecutable], fail_path: ActionExecutable | None = None) -> ActionControlNode:
    return ActionControlNode(
        control_operator=ControlOperator.IF ,
        branches=branches,
        fail_path=fail_path
    )

def WHILE(node: ActionExecutable, condition: ActionConditionExpression) -> ActionControlNode:
    return ActionControlNode(
        control_operator = ControlOperator.WHILE,
        node=node,
        condition=condition
    )

def DO_WHILE(node: ActionExecutable, condition: ActionConditionExpression) -> ActionControlNode:
    return ActionControlNode(
        control_operator = ControlOperator.DO_WHILE,
        node=node,
        condition=condition
    )

def TRY(node: ActionExecutable, success_path: ActionExecutable | None = None, error_path: ActionExecutable | None = None, finally_path: ActionExecutable | None = None) -> ActionControlNode:
    return ActionControlNode(
        control_operator = ControlOperator.TRY,
        node = node,
        success_path = success_path,
        error_path = error_path,
        finally_path = finally_path
    )
