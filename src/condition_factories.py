from action import ActionCondition, ActionConditionExpression, LogicalOperator, ActionControlNode

def cond(condition: ActionCondition, **params) -> ActionConditionExpression:
    return ActionConditionExpression(
        condition=condition,
        parameters=params
    )

def NOT(expr: ActionConditionExpression) -> ActionConditionExpression:
    return ActionConditionExpression(
        operator=LogicalOperator.NOT,
        children=[expr]
    )

def AND(*exprs: ActionConditionExpression) -> ActionConditionExpression:
    return ActionConditionExpression(
        operator=LogicalOperator.AND,
        children=list(exprs)
    )

def OR(*exprs: ActionConditionExpression) -> ActionConditionExpression:
    return ActionConditionExpression(
        operator=LogicalOperator.OR,
        children=list(exprs)
    )