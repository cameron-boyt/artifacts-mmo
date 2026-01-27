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

    # Complex Intentions
    PREPARE_FOR_GATHERING =  auto()
    PREPARE_FOR_FIGHTING = auto()

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

    def _construct_item_list(self, selection: List[ItemSelection]) -> List[Dict]:
        items = []
        for item in selection:
            quantity = self._get_desired_item_quantity(item)
            if quantity == 0:
                continue

            items.append({
                "item": item.item,
                "quantity": quantity
            })

        return items
    
    def _get_desired_item_quantity(self, item: ItemSelection) -> int:
        available_quantity = self.world_state.get_amount_of_item_in_bank(item.item)

        # Get all available quantity, or clamp the quantity within the bound min/max attributes
        if item.quantity.all:
            quantity = available_quantity
        else:
            quantity = min(item.quantity.max, max(item.quantity.min, available_quantity))

            # Check we're not trying to take more than we have
            if quantity > available_quantity:
                return 0
            
        # If set, apply a 'mutiple of' rounding; i.e. get quantity in multiples of 5, 10 etc.
        if item.quantity.multiple_of:
            quantity = (quantity // item.quantity.multiple_of) * item.quantity.multiple_of

        return quantity

    def plan(self, agent: CharacterAgent, intent: ActionIntent) -> Action | ActionGroup | ActionControlNode:
        match intent.intention:
            # Basic Intentions
            case Intention.MOVE:
                return move(params=intent.params)
            
            case Intention.TRANSITION:
                raise NotImplementedError()
            
            case Intention.FIGHT:
                if monster := intent.params.get("monster"):
                    monster_locations = self.world_state.get_locations_of_monster(monster)
                    return action_group(
                        move(closest_location_of=monster_locations),
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
                        move(closest_location_of=resource_locations),
                        gather(until=intent.until)
                    )
                else:
                    return gather(until=intent.until)
            
            case Intention.CRAFT:
                item = intent.params.get("item")
                quantity = intent.params.get("quantity")
                skill_workshop = self.world_state.get_workshop_for_item(item)
                workshop_locations = self.world_state.get_workshop_locations(skill_workshop)
                return action_group(
                    move(closet_location_of=workshop_locations),
                    craft(item_code=item, quantity=quantity)
                )
            
            case Intention.EQUIP:
                return equip()
            
            case Intention.UNEQUIP:
                return unequip()
            
            case Intention.USE:
                raise NotImplementedError()
            
            case Intention.WITHDRAW:
                items: List[ItemSelection] = intent.params.get("items")
                items_to_withdraw = self._construct_item_list(items)
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_location_of=bank_locations),
                    bank_withdraw_item(items=items_to_withdraw)
                )
            
            case Intention.DEPOSIT:
                items: List[ItemSelection] = intent.params.get("items")
                items_to_deposit = self._construct_item_list(items)
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_location_of=bank_locations),
                    bank_deposit_item(items=items_to_deposit)
                )
            
            # Complex Intentions
            case Intention.PREPARE_FOR_GATHERING:
                move_prev = intent.params.get("move_prev", False)
                bank_locations = self.world_state.get_bank_locations()

                if move_prev:
                    return action_group(
                        move(closest_location_of=bank_locations),
                        bank_all_items(),
                        move(prev_location=True)
                    )
                else:
                    return action_group(
                        move(closest_location_of=bank_locations),
                        bank_all_items()
                    )

            case Intention.PREPARE_FOR_FIGHTING:
                move_prev = intent.params.get("move_prev", False)
                bank_locations = self.world_state.get_bank_locations()

                if move_prev:
                    return action_group(
                        move(closest_location_of=bank_locations),
                        bank_all_items(),
                        move(prev_location=True)
                    )
                else:
                    return action_group(
                        move(closest_location_of=bank_locations),
                        bank_all_items()
                    )

            case Intention.FIGHT_THEN_REST:
                if monster := intent.params.get("monster"):
                    monster_locations = self.world_state.get_locations_of_monster(monster)
                    return action_group(
                        move(closest_location_of=monster_locations),
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
                    move(closest_location_of=bank_locations),
                    bank_action,
                    move(prev=True)
                )

            case Intention.CRAFT_OR_GATHER_INTERMEDIARIES:
                """
                If we have enough items in the inv, 
                    Go to the crafting station
                    Craft
                Elseif we have enough including bank items,
                    Go to the bank
                    If don't have enough space,
                        Deposit some items we don't need
                    Withdraw the items from the bank
                    Go to the crafting station
                    Craft
                Else (we don't have enough items at all),
                    For each item,
                        Go to the gathering location
                        Gather
                        Go to the bank
                        Bank all items
                    END for
                END

                """
                craft_item = intent.params.get("item")
                craft_max = intent.params.get("as_many_as_possible", False)
                craft_qty = 1 if craft_max else intent.params.get("quantity", 0)

                required_materials = self.world_state.get_crafting_materials_for_item(craft_item)
                item_selection = [
                    ItemSelection(m["item"], ItemQuantity(min=m["quantity"], max=m["quantity"])) 
                    for m in required_materials
                ]
                
                # Constuct list of items to withdraw from the bank
                items_to_withdraw = self._construct_item_list(item_selection)

                # Get location of the banks
                bank_locations = self.world_state.get_bank_locations()

                # Get the location of the crafting stations
                skill_workshop = self.world_state.get_workshop_for_item(item)
                workshop_locations = self.world_state.get_workshop_locations(skill_workshop)

                # Get the locations of items to gather incase of fallback
                fallback_actions = []
                for material in required_materials:
                    gather_item = material["item"]
                    gather_qty = material["quantity"]

                    # Get the location of the closest source of this item
                    resource_locations = self.world_state.get_locations_of_resource(gather_item)

                    bank_or_inv_has_quantity_cond = cond__item_qty_in_bank_and_inv(gather_item, gather_qty)
                    fallback_actions.extend([
                        action_group(
                            move(closest_location_of=resource_locations),
                            gather(until=OR(
                                cond(ActionCondition.INVENTORY_FULL),
                                bank_or_inv_has_quantity_cond
                            )),
                            move(closest_location_of=bank_locations),
                            bank_all_items(),
                            until=bank_or_inv_has_quantity_cond 
                        )
                    ])

                act_gather_materials = action_group(
                    *fallback_actions
                )

                ## Construct main body conditions
                # First, check if we have the items available in our inventory alone
                if len(required_materials) == 1:
                    item = required_materials[0]["item"]
                    qty = required_materials[0]["quantity"]
                    cond_materials_in_inv = cond__item_qty_in_inv(item, qty * craft_qty)
                else:
                    cond_materials_in_inv = AND(*[
                        cond__item_qty_in_inv(m["item"], m["qty"] * craft_qty)
                        for m in required_materials
                    ])

                # Second, check if combined in the inventory and bank we have the items
                if len(required_materials) == 1:
                    item = required_materials[0]["item"]
                    qty = required_materials[0]["quantity"]
                    cond_materials_in_inv_and_bank = cond__item_qty_in_bank_and_inv(item, qty * craft_qty)
                else:
                    cond_materials_in_inv_and_bank = AND(*[
                        cond__item_qty_in_bank_and_inv(m["item"], m["qty"] * craft_qty)
                        for m in required_materials
                    ])

                # Third, check if we actually have enough space in the inventory to withdraw
                cond_has_space_for_items = cond__inv_has_space_for_items(required_materials)

                # Construct fallback for when we don't have enough inventory space
                act_bank_all_then_withdraw= action_group(
                    move(closest_location_of=bank_locations),
                    bank_deposit_item(preset='all'),
                    bank_withdraw_item(items=items_to_withdraw, withdraw_until_inv_full=craft_max, needed_quantity_only=True)
                )

                # Construct bank and withdraw action plan
                act_move_to_bank_and_withdraw = action_group(
                    move(closest_location_of=bank_locations),
                    bank_withdraw_item(items=items_to_withdraw, withdraw_until_inv_full=craft_max, needed_quantity_only=True)
                )

                # Construct move to workshop and craft action plan
                act_move_to_workshop_and_craft = action_group(
                    move(closest_location_of=workshop_locations),
                    craft(item=item, as_many_as_possible=craft_max, quantity=quantity)
                )
                
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
                    fail_path=act_gather_materials
                )
                
            case _:
                raise Exception("Unknown action type.")