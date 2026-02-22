from typing import List
from src.action import *

## Grouping Factory
def group(*actions: ActionExecutable) -> ActionGroup:
    return ActionGroup(actions=actions)

def do_nothing() -> ActionGroup:
    return group()

def fail_action() -> Action:
    return Action(MetaAction.FAIL_OUT)

## Base Action Factories

# Movement
def move(**params) -> Action:
    return Action(CharacterAction.MOVE, params=params)

def transition(**params) -> Action:
    raise NotImplementedError()

# Fighting
def rest() -> Action:
    return Action(CharacterAction.REST)

def fight() -> Action:
    return Action(CharacterAction.FIGHT)

# Equipment
def equip(**params) -> Action:
    return Action(CharacterAction.EQUIP, params=params)

def unequip(**params) -> Action:
    return Action(CharacterAction.UNEQUIP, params=params)

def use(**params) -> Action:
    return Action(CharacterAction.USE, params=params)

# Skilling
def gather() -> Action:
    return Action(CharacterAction.GATHER)

def craft(**params) -> Action:
    return Action(CharacterAction.CRAFT, params=params)

# Banking
def bank_deposit_item(**params) -> Action:
    return Action(CharacterAction.BANK_DEPOSIT_ITEM, params=params)

def bank_withdraw_item(**params) -> Action:
    return Action(CharacterAction.BANK_WITHDRAW_ITEM, params=params)
                                                             
def bank_deposit_gold(**params) -> Action:
    return Action(CharacterAction.BANK_DEPOSIT_GOLD, params=params)

def bank_withdraw_gold(**params) -> Action:
    return Action(CharacterAction.BANK_WITHDRAW_GOLD, params=params)

# Custom Banking

def bank_all_items(exclude: List[str] = []) -> Action:
    return Action(CharacterAction.BANK_DEPOSIT_ITEM, params={"deposit_all": True, "exclude": exclude})

def bank_all_gold() -> Action:
    return Action(CharacterAction.BANK_DEPOSIT_GOLD, params={"preset": "all"})

# Tasks
def get_task() -> Action:
    return Action(CharacterAction.GET_TASK)

def task_trade(**params) -> Action:
    return Action(CharacterAction.TASK_TRADE, params=params)

def complete_task() -> Action:
    return Action(CharacterAction.COMPLETE_TASK)

def task_exchange() -> Action:
    return Action(CharacterAction.TASK_EXCHANGE)

## Meta Actions

# Item Reservation
def add_item_reservations(**params) -> Action:
    return Action(MetaAction.CREATE_ITEM_RESERVATION, params=params)

def update_item_reservations(**params) -> Action:
    return Action(MetaAction.UPDATE_ITEM_RESERVATION, params=params)

def clear_item_reservations(**params) -> Action:
    return Action(MetaAction.CLEAR_ITEM_RESERVATION, params=params)

# Loadout Preparaton
def prepare_best_loadout(**params) -> Action:
    return Action(MetaAction.PREPARE_LOADOUT, params=params)

def clear_prepared_loadout() -> Action:
    return Action(MetaAction.CLEAR_PREPARED_LOADOUT)

# Context Counters
def reset_context_counter(**params) -> Action:
    return Action(MetaAction.RESET_CONTEXT_COUNTER, params=params)

def increment_context_counter(**params) -> Action:
    return Action(MetaAction.INCREMENT_CONTEXT_COUNTER, params=params)

def clear_context_counter(**params) -> Action:
    return Action(MetaAction.CLEAR_CONTEXT_COUNTER, params=params)
