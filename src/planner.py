import logging
from typing import Dict, List, Any
from character import CharacterAction, CharacterAgent
from action import ActionConditionExpression
from condition_factories import *
from control_factories import *
from dataclasses import dataclass
from action_factories import *
from enum import Enum, auto
from worldstate import WorldState
from helpers import *

class Intention(Enum):
    MOVE = auto()
    TRANSITION = auto()

    FIGHT = auto()
    REST = auto()
    
    GATHER = auto()
    CRAFT = auto()

    EQUIP = auto()
    UNEQUIP = auto()
    USE = auto()

    WITHDRAW = auto()
    DEPOSIT = auto()
    DEPOSIT_ALL = auto()

    # Complex Intentions
    PREPARE_FOR_GATHERING =  auto()
    PREPARE_FOR_FIGHTING = auto()

    COLLECT_THEN_CRAFT = auto()

    FIGHT_THEN_REST = auto()
    BANK_THEN_RETURN = auto()
    CRAFT_OR_GATHER_INTERMEDIARIES = auto()

@dataclass
class ActionIntent:
    intention: Intention
    params: Dict[str, Any]
    until: ActionConditionExpression | None = None

    def __init__(self, intention: Intention, until: ActionConditionExpression | None = None, **params: Any):
        self.intention = intention
        self.params = params
        self.until = until

class ActionPlanner:
    """Interprets action intent and generates action plans."""
    def __init__(self, world_state: WorldState):
        self.logger = logging.getLogger(__name__)

        self.world_state = world_state

    def plan(self, intent: ActionIntent) -> Action | ActionGroup | ActionControlNode:
        match intent.intention:
            # Basic Intentions
            case Intention.MOVE:
                return move(**intent.params)
            
            case Intention.TRANSITION:
                raise NotImplementedError()
            
            case Intention.FIGHT:
                if monster := intent.params.get("monster"):
                    monster_locations = self.world_state.get_locations_of_monster(monster)
                    return action_group(
                        move(closest_of=monster_locations),
                        fight(until=intent.until)
                    )
                else:
                    return fight(until=intent.until)

            case Intention.REST:
                return rest()
            
            case Intention.GATHER:
                if resource := intent.params.get("resource"):
                    resource_locations = self.world_state.get_locations_of_resource(resource)
                    return action_group(
                        move(closest_of=resource_locations),
                        gather(until=intent.until)
                    )
                else:
                    return gather(until=intent.until)
            
            case Intention.CRAFT:
                item: str = intent.params.get("item")
                quantity: int = intent.params.get("quantity")
                as_many_as_possible: bool = intent.params.get("as_many_as_possible")
                skill_workshop = self.world_state.get_workshop_for_item(item)
                workshop_locations = self.world_state.get_workshop_locations(skill_workshop)
                return action_group(
                    move(closest_of=workshop_locations),
                    craft(item=item, quantity=quantity, as_many_as_possible=as_many_as_possible)
                )
            
            case Intention.EQUIP:
                return equip()
            
            case Intention.UNEQUIP:
                return unequip()
            
            case Intention.USE:
                raise NotImplementedError()
            
            case Intention.WITHDRAW:
                items: List[ItemSelection] = intent.params.get("items")
                needed_quantity_only: bool = intent.params.get("needed_quantity_only", False)
                withdraw_until_inv_full: bool = intent.params.get("withdraw_until_inv_full", False)
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_of=bank_locations),
                    bank_withdraw_item(items=items, needed_quantity_only=needed_quantity_only, withdraw_until_inv_full=withdraw_until_inv_full)
                )
            
            case Intention.DEPOSIT:
                items: List[ItemSelection] = intent.params.get("items")
                items_to_deposit = self._construct_item_list(items)
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_of=bank_locations),
                    bank_deposit_item(items=items_to_deposit)
                )
            
            case Intention.DEPOSIT_ALL:
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_of=bank_locations),
                    bank_deposit_item(preset="all")
                )
            
            # Complex Intentions
            case Intention.PREPARE_FOR_GATHERING:
                resource = intent.params.get("resource")
                skill = self.world_state.get_gather_skill_for_resource(resource)
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_of=bank_locations),
                    bank_all_items(),
                    action_group(
                        bank_withdraw_item(preset=f"gathering", sub_preset=skill),
                        equip(context="last_withdrawn")
                    ) 
                )

            case Intention.PREPARE_FOR_FIGHTING:
                monster = intent.params.get("monster")
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_of=bank_locations),
                    bank_all_items(),
                    action_group(
                        bank_withdraw_item(preset=f"fighting"),
                        equip(context="last_withdrawn")
                    ) 
                )

            case Intention.FIGHT_THEN_REST:
                if monster := intent.params.get("monster"):
                    monster_locations = self.world_state.get_locations_of_monster(monster)
                    return action_group(
                        move(closest_of=monster_locations),
                        action_group(
                            fight(),
                            rest(),
                            until=intent.until
                        )
                    )
                else:
                    return action_group(
                        fight(),
                        rest(),
                        until=intent.until
                    )

            case Intention.BANK_THEN_RETURN:
                if intent.params.get("preset") == "all":
                    bank_action = bank_all_items()
                else:
                    items: List[ItemSelection] = intent.params.get("items")
                    items_to_deposit = self._construct_item_list(items)
                    bank_action = bank_deposit_item(items=items_to_deposit)
        
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_of=bank_locations),
                    bank_action,
                    move(previous=True)
                )
            
            case Intention.COLLECT_THEN_CRAFT:
                craft_item = intent.params.get("item")
                craft_max = intent.params.get("as_many_as_possible", False)
                craft_qty = 1 if craft_max else intent.params.get("quantity", 0)

                required_materials = self.world_state.get_crafting_materials_for_item(craft_item, craft_qty)
                if craft_max:
                    item_selection = [
                        ItemSelection(m["item"], ItemQuantity(min=m["quantity"], multiple_of=m["quantity"]))
                        for m in required_materials
                    ]
                else:
                    item_selection = [
                        ItemSelection(m["item"], ItemQuantity(min=m["quantity"] * craft_qty, multiple_of=m["quantity"] * craft_qty))
                        for m in required_materials
                    ]

                # Get location of the banks
                bank_locations = self.world_state.get_bank_locations()

                # Get the location of the crafting stations
                skill_workshop = self.world_state.get_workshop_for_item(craft_item)
                workshop_locations = self.world_state.get_workshop_locations(skill_workshop)

                ## Construct main body conditions
                # First, check if we have the items available in our inventory alone
                cond_materials_in_inv = cond__items_in_inv(required_materials)

                # Second, check if combined in the inventory and bank we have the items
                cond_materials_in_inv_and_bank = cond__items_in_inv_and_bank(required_materials)

                # Third, check if we actually have enough space in the inventory to withdraw
                cond_has_space_for_items = cond__inv_has_space_for_items(required_materials)

                # Construct fallback for when we don't have enough inventory space
                act_bank_all_then_withdraw= action_group(
                    move(closest_of=bank_locations),
                    bank_deposit_item(preset='all'),
                    self.plan(ActionIntent(Intention.WITHDRAW, items=item_selection, needed_quantity_only=True, withdraw_until_inv_full=craft_max))
                )

                # Construct bank and withdraw action plan
                act_move_to_bank_and_withdraw = self.plan(ActionIntent(Intention.WITHDRAW, items=item_selection, needed_quantity_only=True, withdraw_until_inv_full=craft_max))

                # Construct move to workshop and craft action plan
                act_move_to_workshop_and_craft = self.plan(ActionIntent(Intention.CRAFT, item=craft_item, quantity=craft_qty, as_many_as_possible=craft_max))
                
                return IF(
                    (cond_materials_in_inv, act_move_to_workshop_and_craft),
                    (cond_materials_in_inv_and_bank, action_group(
                        IF(
                            (cond_has_space_for_items, action_group(
                                act_move_to_bank_and_withdraw,
                                act_move_to_workshop_and_craft
                            )),
                            fail_path=action_group(
                                act_bank_all_then_withdraw,
                                act_move_to_workshop_and_craft
                            )
                        )
                    )),
                    fail_path=do_nothing()
                )

            case Intention.CRAFT_OR_GATHER_INTERMEDIARIES:
                craft_item = intent.params.get("item")
                craft_max = intent.params.get("as_many_as_possible", False)
                craft_qty = 1 if craft_max else intent.params.get("quantity", 0)

                # Construct the list of gather fallback actions
                required_materials = self.world_state.get_crafting_materials_for_item(craft_item, craft_qty)
                act_gather_materials = action_group(*[
                    action_group(
                        self.plan(ActionIntent(Intention.PREPARE_FOR_GATHERING, resource=material["item"])),
                        self.plan(ActionIntent(Intention.GATHER, resource=material["item"], until=OR(cond(ActionCondition.INVENTORY_FULL), cond__item_qty_in_inv_and_bank(material["item"], material["quantity"])))),
                        self.plan(ActionIntent(Intention.DEPOSIT_ALL)),
                        until=cond__item_qty_in_inv_and_bank(material["item"], material["quantity"])
                    )
                    for material in required_materials
                ])
                
                # Generate a COLLECT_THEN_CRAFT, but override the failpath with the gathering
                act_collect_then_craft = self.plan(ActionIntent(Intention.COLLECT_THEN_CRAFT, item=craft_item, quantity=craft_qty, as_many_as_possible=craft_max))
                act_collect_then_craft.fail_path = act_gather_materials
                
                return act_collect_then_craft
                
            case _:
                raise Exception("Unknown action type.")