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
            "previous_location": (self.char_data["x"],  self.char_data["y"]),
            "equip_queue": [],
            "damage_taken_last_fight": self.char_data["max_hp"] -self.char_data["hp"]
        }
        self.world_state = world_state

        self.is_autonomous: bool = False
        self.abort_actions: bool = False
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
        
        per_set = {}
        inv = {}
        bank = {}

        free_inv_spaces = self.get_free_inventory_spaces()

        # Resolve any ItemType items
        true_order = []
        for item in order.items:
            if item.item_type:
                match item.item_type:
                    case ItemType.FOOD:
                        best_food = self.world_state.get_best_food_for_character_in_bank(self.char_data)
                        if best_food:
                            item.item = best_food[0]
                        else:
                            return []

        for item in order.items:
            i = item.item
            inv[i] = self.get_quantity_of_item_in_inventory(i)
            bank[i] = self.world_state.get_amount_of_item_in_bank(i)

            # Determine how many of the item we have available
            if order.check_inv:
                available_quantity = inv[i] + bank[i]
            else:
                available_quantity = bank[i]

            # Clamp the quantity within the avilability count and the min/max bounds
            if available_quantity < item.quantity.min:
                return []
            elif item.quantity.min <= free_inv_spaces <= item.quantity.max:
                quantity = min(item.quantity.max, bank[i], free_inv_spaces)
            elif (
                (order.check_inv and inv[i] + free_inv_spaces < item.quantity.min) or
                (not order.check_inv and free_inv_spaces < item.quantity.min)
            ):
                return []
            else:
                quantity = min(item.quantity.max, bank[i])
        
            # If we only want to withdraw the needed amount, check how much we have in the inventory
            if order.check_inv and not order.greedy_order:
                if item.quantity.multiple_of:
                    # If we're working with multiples, we can always safely remove all inventory quantities
                    quantity = ((quantity + inv[i]) // item.quantity.multiple_of) * item.quantity.multiple_of
                    quantity = max(0, quantity - inv[i])
                    
                    # if quantity <= 0:
                    #     return []
                else:
                    # Otherwise, only subtract if the chosen quantity + count in inventory surpass the range max
                    quantity = min(free_inv_spaces, max(0, quantity - max(0, (quantity + inv[i]) - item.quantity.max)))
            elif item.quantity.multiple_of:
                # Apply a 'multiple of' rounding; i.e. get quantity in multiples of 5, 10 etc.
                quantity = (quantity // item.quantity.multiple_of) * item.quantity.multiple_of

                if quantity <= 0:
                    return []
            
            items.append({ "code": i, "quantity": quantity })
            per_set[i] = quantity
            free_inv_spaces -= quantity

        # Check the we have sufficient inventory space
        items_per_set = sum(per_set.values())
        if self.get_free_inventory_spaces() < items_per_set:
            return []

        # Withdraw multiple sets of the desired items until the inventory is full
        if order.greedy_order:
            if order.check_inv:
                sets_from_inv = min(floor(inv[item["code"]] / per_set[item["code"]]) for item in items)
            else:
                sets_from_inv = 0
                
            sets_from_total = min(floor((inv[item["code"]] + bank[item["code"]]) / per_set[item["code"]]) for item in items)
            sets_target = min(sets_from_total, floor(self.get_free_inventory_spaces() / items_per_set))

            additional_sets_needed = max(0, sets_target - sets_from_inv)

            if order.check_inv:
                need = [
                    {
                        "code": item["code"], 
                        "quantity": max(0, additional_sets_needed * per_set[item["code"]]) - (inv[item["code"]] - (sets_from_inv * per_set[item["code"]]))
                    } 
                    for item in items
                ]
            else:
                need = [{"code": item["code"], "quantity": max(0, additional_sets_needed * per_set[item["code"]])} for item in items]

            items = need

        return items
    
    def _get_best_food_in_inv(self) -> str | None:
        food = [
            (item, self.world_state.get_heal_power_of_food(item["code"]))
            for item in self.char_data["inventory"]
            if self.world_state.is_food(item["code"]) 
            and self.world_state.character_meets_conditions(
                self.char_data, 
                self.world_state.get_item_info(item["code"])["conditions"]
            )
        ]

        if len(food) > 0:
            best_food = max(food, key=lambda f: f[1] if f[1] <= self.char_data["max_hp"] else -1 * f[1])
            return best_food[0]  

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
    
    def set_abort_actions(self):
        self.abort_actions = True

    def unset_abort_actions(self):
        self.abort_actions = False

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
    
    def inventory_contains_usable_food(self) -> bool:
        usable_food = [
            item for item in self.char_data["inventory"]
            if self.world_state.is_food(item["code"]) 
            and self.world_state.character_meets_conditions(
                self.char_data, 
                self.world_state.get_item_info(item["code"])["conditions"]
            )
        ]

        return len(usable_food) > 0
    
    def health_sufficiently_low_to_heal(self) -> bool:
        taken_sufficient_damage = self.char_data["hp"] < self.context["damage_taken_last_fight"] * 1.5
        at_max_health = self.char_data["hp"] == self.char_data["max_hp"]
        return taken_sufficient_damage and not at_max_health
        
    def has_task(self) -> bool:
        return self.char_data["task"] != ""
    
    def has_task_of_type(self, task_type: str) -> bool:
        if task_type == "gathering":
            return self.world_state.is_a_resource(self.char_data["task"])
        elif task_type == "crafting":
            return self.world_state.item_is_craftable(self.char_data["task"])
        else:
            raise Exception(f"Unknown task type: {task_type}.")
    
    def has_completed_task(self) -> bool:
        return self.char_data["task_progress"] == self.char_data["task_total"]
    
    def items_in_equip_queue(self) -> bool:
        equip_queue = self.context.get("equip_queue", [])
        return len(equip_queue) > 0
    
    def has_skill_level(self, skill, level) -> bool:
        if skill in SKILLS:
            return self.char_data[f"{skill}_level"] >= level
        elif skill == "character":
            return self.char_data["level"] >= level
        else:
            raise Exception(f"Unknown skill: {skill}.")

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
                elif action.params.get("on_task", False):
                    task = self.char_data["task"]
                    if self.char_data["task_type"] == "monsters":
                        locations = self.world_state.get_locations_of_monster(task)
                    elif self.char_data["task_type"] == "resources":
                        locations = self.world_state.get_locations_of_resource(task)
                
                    loc = self._get_closest_location(locations)
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

                for r in resource:
                    r_data = self.world_state.get_item_info(r)
                    
                    if not "skill" in r_data:
                        continue

                    r_skill = r_data["skill"]
                    r_level = r_data["level"]
                    charcter_skill_level = self.char_data[f"{r_skill}_level"]
                    if charcter_skill_level < r_level:
                        self.logger.warning(f"[{self.name}] Skill '{r_skill}' level (charcter_skill_level) insufficient to gather {resource} ({r_level}).")
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

                match preset := action.params.get("preset", "none"):
                    case "gathering" | "fighting":
                        if on_task := action.params.get("on_task", False): 
                            target = self.char_data["task"]
                        else:
                            target = action.params.get("sub_preset")

                        if loadout := self.world_state.get_best_loadout_for_task(self.char_data, preset, target):
                            for item in loadout:
                                # If the item is already equipped, skip
                                if any([equipped == item for slot, equipped in self.char_data.items() if "slot" in slot]):
                                    continue

                                items_to_withdraw.extend([{ "code": item, "quantity": 1 }])
                                item_slot = self.world_state.get_equip_slot_for_item(item)
                                self.context["equip_queue"].append({ "code": item, "slot": item_slot })
                        
                    case "on_task":
                        task_item = self.char_data["task"]
                        item_order = ItemOrder([ItemSelection(item=task_item, quantity=ItemQuantity(min=1))])
                        items_to_withdraw = self._construct_item_list(item_order)

                    case _:
                        # Construct a list of items that need to be withdrawn
                        item_order = action.params.get("items")
                        items_to_withdraw = self._construct_item_list(item_order)

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
                if action.params.get("use_queue", False):
                    equip_queue = self.context.get("equip_queue", [])

                    # If nothing is in the queue, cancel out
                    if len(equip_queue) == 0:
                        return ActionOutcome.CANCEL
                    
                    item = equip_queue.pop()
                    item_code = item["code"]
                    item_slot = item["slot"]

                else:
                    item_code = action.params.get("item")
                    item_slot = action.params.get("slot")
                        
                api_result = await self.api_client.equip(self.name, item_code, item_slot)

            case CharacterAction.UNEQUIP:
                item_slot = action.params.get("slot")
                api_result = await self.api_client.unequip(self.name, item_slot)

            case CharacterAction.USE:
                match action.params.get("item_type"):
                    case "food":
                        item_to_use = self._get_best_food_in_inv()
                        if not item_to_use:
                            return ActionOutcome.CANCEL

                    case _:
                        raise Exception("idk what to use")
                    
                api_result = await self.api_client.use(self.name, item_to_use["code"])

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
                            if inv_item["code"] == req_item["code"]:
                                lowest_multiple = min(lowest_multiple, inv_item["quantity"] // req_item["quantity"])

                    quantity = lowest_multiple
                
                if quantity == 0:
                    self.logger.warning(f"[{self.name}] Cannot craft zero of an item.")
                    return ActionOutcome.CANCEL
                
                api_result = await self.api_client.craft(self.name, item, quantity)

            case CharacterAction.GET_TASK:
                api_result = await self.api_client.accept_new_task(self.name)

            case CharacterAction.TASK_TRADE:
                item = action.params.get("item")
                quantity = action.params.get("quantity")
                api_result = await self.api_client.task_trade(self.name, item, quantity)

            case CharacterAction.COMPLETE_TASK:
                api_result = await self.api_client.complete_task(self.name)
        
            case _:
                raise Exception(f"[{self.name}] Unknown action type: {action.type}")
            
        
        if api_result.outcome == RequestOutcome.SUCCESS:
            # If a fight occurred, get some data for future context
            if fight_result_info := api_result.response.get("data", {}).get("fight", {}).get("characters", {}):
                old_hp = self.char_data["hp"]
                new_hp = fight_result_info[0]["final_hp"]
                self.context["damage_taken_last_fight"] = old_hp - new_hp
                self.char_data = api_result.response.get("data", {}).get("characters")[0]

            # Update character state
            if new_char_data := api_result.response.get("data", {}).get("character"):
                self.char_data = new_char_data

            # Update the agent's cooldown
            new_cooldown = api_result.response.get("data").get("cooldown").get("remaining_seconds")
            self.cooldown_expires_at = time.time() + new_cooldown
            
            # Update bank
            if bank_data := api_result.response.get("data").get("bank", {}):
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
