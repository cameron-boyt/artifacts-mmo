from typing import Tuple

from src.action import Action, ActionGroup, ActionConditionExpression, ActionControlNode, ControlOperator, ActionExecutable

def IF(*branches: Tuple[ActionConditionExpression, ActionExecutable], fail_path: ActionExecutable | None = None) -> ActionControlNode:
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

def DO_WHILE(action_node: ActionExecutable, condition: ActionConditionExpression) -> ActionControlNode:
    return ActionControlNode(
        control_operator = ControlOperator.DO_WHILE,
        action_node=action_node,
        condition=condition
    )

def TRY(node: ActionExecutable, error_path: ActionExecutable, finally_path: ActionExecutable) -> ActionControlNode:
    return ActionControlNode(
        control_operator = ControlOperator.TRY,
        on_error = error_path,
        finally_path = finally_path
    )
