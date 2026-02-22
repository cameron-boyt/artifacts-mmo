from typing import List, Tuple, Dict, Any

from src.action import ActionCondition, ActionConditionExpression, LogicalOperator, ActionControlNode

# Generic Condition Factory
def cond(condition: ActionCondition, **params) -> ActionConditionExpression:
    return ActionConditionExpression(
        condition=condition,
        parameters=params
    )

# Operator Factories
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

## Complex Condition Factories

# Items in Inventory
def cond__item_qty_in_inv(item: str, quantity: int) -> ActionConditionExpression:
    return cond(
        ActionCondition.INVENTORY_HAS_ITEM_OF_QUANTITY,
        item=item,
        quantity=quantity
    )

def cond__items_in_inv(items: List[Dict[str, Any]]) -> ActionConditionExpression:
    if len(items) == 1:
        item = items[0]["code"]
        quantity = items[0]["quantity"]
        return cond__item_qty_in_inv(item, quantity)
    else:
        return AND(*[
            cond__item_qty_in_inv(item["code"], item["quantity"])
            for item in items
        ])

def cond__inv_has_space_for_items(items: List[Dict[str, Any]]) -> ActionConditionExpression:
    return cond(
        ActionCondition.INVENTORY_HAS_AVAILABLE_SPACE_FOR_ITEMS,
        items=items
    )

# Items in Bank
def cond__item_qty_in_bank(item: str, quantity: int)-> ActionConditionExpression:
    return cond(
        ActionCondition.BANK_HAS_ITEM_OF_QUANTITY,
        item=item,
        quantity=quantity
    )

def cond__items_in_bank(items: List[Dict[str, Any]]) -> ActionConditionExpression:
    if len(items) == 1:
        item = items[0]["code"]
        quantity = items[0]["quantity"]
        return cond__item_qty_in_bank(item, quantity)
    else:
        return AND(*[
            cond__item_qty_in_bank(item["code"], item["quantity"])
            for item in items
        ])

# Items in Inventory or Bank
def cond__item_qty_in_inv_and_bank(item: str, quantity: int) -> ActionConditionExpression:
    return cond(
        ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY,
        item=item,
        quantity=quantity
    )

def cond__items_in_inv_and_bank(items: List[Dict[str, Any]]) -> ActionConditionExpression:
    if len(items) == 1:
        item = items[0]["code"]
        quantity = items[0]["quantity"]
        return cond__item_qty_in_inv_and_bank(item, quantity)
    else:
        return AND(*[
            cond__item_qty_in_inv_and_bank(item["code"], item["quantity"])
            for item in items
        ])