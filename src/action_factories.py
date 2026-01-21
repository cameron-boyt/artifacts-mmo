from action import Action, ActionGroup, CharacterAction, ActionConditionExpression

## Grouping Factory
def group(*actions: Action | ActionGroup, until: ActionConditionExpression | None = None) -> ActionGroup:
    return ActionGroup(actions=actions, until=until)

## Base Action Factories
def move(**params) -> Action:
    return Action(CharacterAction.MOVE, params=params)

def transition(**params) -> Action:
    raise NotImplementedError()

def rest() -> Action:
    return Action(CharacterAction.REST)

def equip(**params) -> Action:
    return Action(CharacterAction.EQUIP)

def unequip(**params) -> Action:
    return Action(CharacterAction.UNEQUIP, params=params)

def use() -> Action:
    raise NotImplementedError()

def fight(*, until: ActionConditionExpression | None = None) -> Action:
    return Action(CharacterAction.FIGHT, until=until)

def gather(*, until: ActionConditionExpression | None = None) -> Action:
    return Action(CharacterAction.GATHER, until=until)

def craft(**params) -> Action:
    return Action(CharacterAction.CRAFT, params=params)

def bank_deposit_item(**params) -> Action:
    return Action(CharacterAction.BANK_DEPOSIT_ITEM, params=params)

def bank_withdraw_item(**params) -> Action:
    return Action(CharacterAction.BANK_WITHDRAW_ITEM, params=params)

def bank_all_items() -> Action:
    return Action(CharacterAction.BANK_DEPOSIT_ITEM, params={"preset": "all"})

def bank_deposit_gold(**params) -> Action:
    return Action(CharacterAction.BANK_DEPOSIT_GOLD, params=params)

def bank_withdraw_gold(**params) -> Action:
    return Action(CharacterAction.BANK_WITHDRAW_GOLD, params=params)

def bank_all_gold() -> Action:
    return Action(CharacterAction.BANK_DEPOSIT_GOLD, params={"preset": "all"})