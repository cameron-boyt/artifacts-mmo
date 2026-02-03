from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Dict, List, Tuple, Any
from math import floor, ceil

from src.action import Action, ActionGroup, ActionCondition, ActionOutcome, CharacterAction
from src.api import APIClient, RequestOutcome, RequestOutcomeDetail
from src.worldstate import WorldState
from src.helpers import *

if TYPE_CHECKING:
    from src.scheduler import ActionScheduler

class CharacterAgent:
    """Represents a single character, holding its state and execution logic."""
    def __init__(self, character_data: Dict[str, Any], world_state: WorldState, api_client: APIClient, scheduler: ActionScheduler):
        self.logger = logging.getLogger(__name__)
        
        self.api_client: APIClient = api_client
        self.scheduler: ActionScheduler = scheduler

        self.name = character_data["name"]
        self.char_data: Dict[str, Any] = character_data
        self.context = {
            "previous_location": (self.char_data["x"],  self.char_data["y"])
        }
        self.world_state = world_state

        self.is_autonomous: bool = False
        self.cooldown_expires_at: float = 0.0

    ## Helper Functions
    def _get_closest_location(self, locations: List[Tuple[int, int]]) -> Tuple[int, int]:
        """Get the location which is the shortest distance from the agent."""
        if not locations:
            return ()
        
        shortest_distance = 9999
        best_location = (0, 0)

        for location in locations:
            distance = pow(pow(self.char_data["x"] - location[0], 2) + pow(self.char_data["y"] - location[1], 2), 0.5)
            if distance < shortest_distance:
                shortest_distance = distance
                best_location = location

        return best_location

    def _construct_item_list(self, order: ItemOrder) -> List[Dict]:
        items = []
        for item in order.items:
            quantity = self._get_desired_item_quantity(item)
            if quantity == 0:
                # Failed to meet one of the item requests
                return []

            items.append({
                "code": item.item,
                "quantity": quantity
            })

        # If we only want to withdraw the needed amount, check how much we have in the inventory
        if order.check_inv and not order.greedy_order:
            for item in items:
                quantity_in_inv = self.get_quantity_of_item_in_inventory(item["code"])
                item["quantity"] -= quantity_in_inv

        # Withdraw multiple sets of the desired items until the inventory is full
        if order.greedy_order:
            per_set = {}
            inv = {}
            bank = {}
            for item in items:
                i = item["code"]
                per_set[i] = item["quantity"]
                inv[i] = self.get_quantity_of_item_in_inventory(i)
                bank[i] = self.world_state.get_amount_of_item_in_bank(i)

            items_per_set = sum(item["quantity"] for item in items)
            
            if order.check_inv:
                sets_from_inv = min(floor(inv[item["code"]] / per_set[item["code"]]) for item in items)
            else:
                sets_from_inv = 0
                
            sets_from_total = min(floor((inv[item["code"]] + bank[item["code"]]) / per_set[item["code"]]) for item in items)
            sets_target = min(sets_from_total, floor(self.get_free_inventory_spaces() / items_per_set))

            additional_sets_needed = max(0, sets_target - sets_from_inv)

            need = [{"code": item["code"], "quantity": max(0, additional_sets_needed * per_set[item["code"]])} for item in items]

            if order.check_inv:
                need = [{"code": item["code"], "quantity": item["quantity"] - inv[item["code"]]} for item in need]

            items = need

        return items
    
    def _get_desired_item_quantity(self, item: ItemSelection) -> int:
        available_quantity = self.world_state.get_amount_of_item_in_bank(item.item)

        # Get all available quantity, or clamp the quantity within the bound min/max attributes
        if item.quantity.all:
            quantity = available_quantity
        else:
            # Check we're not trying to take more than we have
            if available_quantity < item.quantity.min:
                return 0
            else:
                quantity = min(item.quantity.max, available_quantity)
            
        # If set, apply a 'mutiple of' rounding; i.e. get quantity in multiples of 5, 10 etc.
        if item.quantity.multiple_of:
            quantity = (quantity // item.quantity.multiple_of) * item.quantity.multiple_of

        return quantity
    
    def get_number_of_items_in_inventory(self) -> int:
        """Get the total number of items in the agent's inventory"""
        return sum(item["quantity"] for item in self.char_data["inventory"])
    
    def get_inventory_size(self) -> int:
        """Get the maximum number of items the agent's inventory can store."""
        return self.char_data["inventory_max_items"]
    
    def get_free_inventory_spaces(self) -> int:
        return self.get_inventory_size() - self.get_number_of_items_in_inventory()

    def get_quantity_of_item_in_inventory(self, item: str) -> int:
        """Get the quantity of an item in the agent's inventory."""
        for item_data in self.char_data["inventory"]:
            if item_data["code"] == item:
                return item_data["quantity"]

        return 0

    ## Condition Checkers
    def inventory_full(self) -> bool:
        """Check if the agent's inventory is full."""
        item_count = self.get_number_of_items_in_inventory()
        inv_size = self.get_inventory_size()
        return item_count >= inv_size
    
    def inventory_empty(self) -> bool:
        """Check if the agent's inventory is empty."""
        item_count = self.get_number_of_items_in_inventory()
        return item_count == 0
    
    def inventory_has_available_space(self, spaces: int) -> bool:
        """Check if the agent's inventory has a number of space available."""
        item_count = self.get_number_of_items_in_inventory()
        inv_size = self.get_inventory_size()
        return inv_size - item_count >= spaces
    
    def inventory_has_item_of_quantity(self, item: str, quantity: int) -> bool:
        """Check if the agent's inventory has an item of at least a specific quantity."""
        inv_quantity = self.get_quantity_of_item_in_inventory(item)
        return inv_quantity >= quantity

    def bank_has_item_of_quantity(self, item: str, quantity: int) -> bool:
        """Check if the agent's bank has an item of at least a specific quantity."""
        bank_quantity = self.world_state.get_amount_of_item_in_bank(item)
        return bank_quantity >= quantity
    
    def bank_and_inventory_have_item_of_quantity(self, item: str, quantity: int) -> bool:
        """Check if the agent's bank and inventory have a combined amount of an item of at least a specific quantity."""
        inv_quantity = self.get_quantity_of_item_in_inventory(item)
        bank_quantity = self.world_state.get_amount_of_item_in_bank(item)
        return inv_quantity + bank_quantity >= quantity
    

    ## Action Performance
    async def perform(self, action: Action) -> ActionOutcome:
        log_msg = f"[{self.name}] Performing action: {action.type.value}"
        if action.params:
            log_msg += f" with params {action.params}"
        self.logger.info(log_msg)

        match action.type:
            ## MOVING ##
            case CharacterAction.MOVE:
                if action.params.get("previous", False):
                    x, y = self.context.get("previous_location")
                elif locations := action.params.get("closest_of", []):
                    loc = self._get_closest_location(locations)
                    if not loc:
                        return ActionOutcome.FAIL
                    
                    x, y = loc
                else:
                    x = action.params["x"]
                    y = action.params["y"]

                # If we're already there, don't move
                if (x, y) == (self.char_data["x"],  self.char_data["y"]):
                    return ActionOutcome.CANCEL

                self.context["previous_location"] = (self.char_data["x"],  self.char_data["y"])
                api_result = await self.api_client.move(self.name, x, y)

            ## FIGHTING ##
            case CharacterAction.FIGHT:
                api_result = await self.api_client.fight(self.name)
        
            case CharacterAction.REST:
                api_result = await self.api_client.rest(self.name)
        
            ## GATHERING ##
            case CharacterAction.GATHER:
                resource = self.world_state.get_resource_at_location(self.char_data["x"], self.char_data["y"])
                resource_data = self.world_state.get_data_for_resource(resource)
                resource_skill = resource_data["skill"]
                resource_level = resource_data["level"]
                charcter_skill_level = self.char_data[f"{resource_skill}_level"]
                if charcter_skill_level < resource_level:
                    self.logger.warning(f"[{self.name}] Skill '{resource_skill}' level (charcter_skill_level) insufficient to gather {resource} ({resource_level}).")
                    return ActionOutcome.FAIL
                
                api_result = await self.api_client.gather(self.name)
        
            ## BANKING ##
            case CharacterAction.BANK_DEPOSIT_ITEM:
                match action.params.get("preset", "none"):
                    case "all":
                        items_to_deposit = [{ "code": item["code"], "quantity": item["quantity"] } for item in self.char_data["inventory"] if item["code"] != '']
                        if not items_to_deposit:
                            return ActionOutcome.CANCEL
                    case _:
                        items_to_deposit = []
                        for deposit in action.params.get("items", []):
                            items_to_deposit.append({ "code": deposit["item"], "quantity": int(deposit["quantity"]) })

                api_result = await self.api_client.bank_deposit_item(self.name, items_to_deposit)
                
            case CharacterAction.BANK_WITHDRAW_ITEM:
                items_to_withdraw = []

                match action.params.get("preset", "none"):
                    case "gathering":
                        if skill := action.params.get("sub_preset"):
                            if best_tool := self.world_state.get_best_tool_for_skill_in_bank(skill):
                                # If current tool is same or better, don't bother withdrawing
                                equipped_item = self.char_data["weapon_slot"]
                                if self.world_state.get_gathering_skill_of_item(equipped_item, skill) <= best_tool[1]:
                                    self.context["last_withdrawn"] = []
                                    return ActionOutcome.CANCEL

                                items_to_withdraw = [{ "code": best_tool[0], "quantity": 1 }]
                                self.context["last_withdrawn"] = items_to_withdraw
                        
                        if not items_to_withdraw:
                            self.context["last_withdrawn"] = []
                            return ActionOutcome.CANCEL
                            
                    case "fighting":
                        monster = action.params.get("sub_preset", "generic")
                        if best_weapon := self.world_state.get_best_weapon_for_monster_in_bank(monster):
                            items_to_withdraw = [{ "code": best_weapon, "quantity": 1 }]
                            self.context["last_withdrawn"] = items_to_withdraw
                        
                        if not items_to_withdraw:
                            self.context["last_withdrawn"] = []
                            return ActionOutcome.CANCEL
                    case _:
                        # Construct a list of items that need to be withdrawn
                        item_order = action.params.get("items")

                        items_to_withdraw = self._construct_item_list(item_order)

                        if not items_to_withdraw:
                            return ActionOutcome.FAIL

                # Clean up item withdrawals
                items_to_withdraw = [item for item in items_to_withdraw if item["quantity"] > 0]

                if not items_to_withdraw:
                    return ActionOutcome.CANCEL

                # Reserve the chosen items
                reservation_id = self.world_state.reserve_bank_items(items_to_withdraw)
                
                api_result = await self.api_client.bank_withdraw_item(self.name, items_to_withdraw)

                # Clear the item reservation now we've attempted the transaction
                self.world_state.clear_bank_reservation(reservation_id)
            
            case CharacterAction.BANK_DEPOSIT_GOLD:
                quantity_to_deposit = action.params.get("quantity", 0)
                api_result = await self.api_client.bank_deposit_gold(self.name, quantity_to_deposit)
                
            case CharacterAction.BANK_WITHDRAW_GOLD:
                quantity_to_withdraw = action.params.get("quantity", 0)
                api_result = await self.api_client.bank_withdraw_gold(self.name, quantity_to_withdraw)

            ## EQUIPMENT ##
            case CharacterAction.EQUIP:
                match action.params.get("context", "none"):
                    case "last_withdrawn":
                        last_withdraw = self.context.get("last_withdrawn", [])

                        # If nothing was withdrawn previously, cancel out
                        if not last_withdraw:
                            return ActionOutcome.CANCEL
                        
                        item_code = last_withdraw[0]["code"]
                        item_slot = self.world_state.get_equip_slot_for_item(item_code)

                    case _:
                        item_code = action.params.get("item")
                        item_slot = action.params.get("slot")

                api_result = await self.api_client.equip(self.name, item_code, item_slot)

            case CharacterAction.UNEQUIP:
                item_slot = action.params.get("slot")
                api_result = await self.api_client.unequip(self.name, item_slot)

            ## CRAFTING ##
            case CharacterAction.CRAFT:
                item = action.params.get("item")
                quantity = action.params.get("quantity", 1)
                as_many_as_possible = action.params.get("as_many_as_possible", False)

                if as_many_as_possible:
                    # Maximise the number of items we craft
                    lowest_multiple = 999
                    required_materials = self.world_state.get_crafting_materials_for_item(item)
                    for inv_item in self.char_data["inventory"]:
                        for req_item in required_materials:
                            if inv_item["code"] == req_item["item"]:
                                lowest_multiple = min(lowest_multiple, inv_item["quantity"] // req_item["quantity"])

                    quantity = lowest_multiple
                        
                api_result = await self.api_client.craft(self.name, item, quantity)
        
            case _:
                raise Exception(f"[{self.name}] Unknown action type: {action.type}")
            
        
        if api_result.outcome == RequestOutcome.SUCCESS:
            # Update character state
            self.char_data = api_result.response.get("data").get("character")

            # Update the agent's cooldown
            new_cooldown = api_result.response.get("data").get("cooldown").get("remaining_seconds")
            self.cooldown_expires_at = time.time() + new_cooldown
            
            # Update bank
            if bank_data := api_result.response.get("data").get("bank"):
                self.world_state.update_bank_data(bank_data)

            return ActionOutcome.SUCCESS
        else:
            match api_result.detail:
                case RequestOutcomeDetail.NOT_FOUND:
                    return ActionOutcome.FAIL
                
                case RequestOutcomeDetail.INVALID_PAYLOAD:
                    return ActionOutcome.FAIL
                
                case RequestOutcomeDetail.MISSING_REQUIRED_ITEMS:
                    return ActionOutcome.FAIL
                
                case RequestOutcomeDetail.ALREADY_AT_DESTINATION:
                    return ActionOutcome.FAIL_CONTINUE
                
                case RequestOutcomeDetail.LEVEL_TOO_LOW:
                    return ActionOutcome.FAIL
                
                case RequestOutcomeDetail.INVENTORY_FULL:
                    return ActionOutcome.FAIL
                
                case RequestOutcomeDetail.ON_COOLDOWN:
                    return ActionOutcome.FAIL_RETRY
                
                case RequestOutcomeDetail.NO_INTERACTION:
                    return ActionOutcome.FAIL
                
                case _:
                    raise NotImplementedError(f"Unknown detail {api_result.detail}.")

