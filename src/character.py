from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
import time
import re
from typing import TYPE_CHECKING, Dict, List, Tuple, Any, Callable
from enum import Enum, auto
from math import floor, ceil

from src.action import Action, MetaAction, ActionOutcome, CharacterAction
from src.api import APIClient, RequestOutcome, RequestOutcomeDetail
from src.worldstate import WorldState
from src.helpers import SKILLS, ItemOrder, ItemType

if TYPE_CHECKING:
    from src.scheduler import ActionScheduler

class AgentMode(Enum):
    MANUAL = auto()
    AUTO_GOAL_LEADER = auto()
    AUTO_GOAL_SUPPORT = auto()

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
            "damage_taken_last_fight": self.char_data["max_hp"],
            "last_trade": {},
            "last_craft": {},
            "prepared_loadout": [],
            "bank_deposit_exclusions": []
        }
        self.world_state = world_state

        self.action_mode: AgentMode = AgentMode.MANUAL
        self.abort_actions: bool = False
        self.cooldown_expires_at: float = datetime.strptime(self.char_data.get("cooldown_expiration", "1970-01-01T00:00:00.000Z"), "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()

    ## Helper Functions
    def _get_closest_location(self, locations: List[Tuple[int, int]]) -> Tuple[int, int] | None:
        """Get the location which is the shortest distance from the agent."""
        if not locations:
            return None
        
        shortest_distance = 9999
        best_location = (0, 0)

        for location in locations:
            distance = pow(pow(self.char_data["x"] - location[0], 2) + pow(self.char_data["y"] - location[1], 2), 0.5)
            if distance < shortest_distance:
                shortest_distance = distance
                best_location = location

        return best_location
    
    def _get_best_food_in_inv(self) -> str | None:
        food = [
            (item["code"], self.world_state.get_heal_power_of_food(item["code"]))
            for item in self.char_data["inventory"]
            if self.world_state.is_food(item["code"]) 
            and self.world_state.character_meets_item_conditions(
                self.char_data, 
                self.world_state.get_item_info(item["code"])["conditions"]
            )
        ]

        if len(food) > 0:
            best_food = max(food, key=lambda f: f[1] if f[1] <= self.char_data["max_hp"] else -1 * f[1])
            return best_food[0]  
    
    # Item List Consturctor for Orders
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
                            item.item = best_food
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

    def get_number_of_items_in_inventory(self) -> int:
        """Get the total number of items in the agent's inventory"""
        return sum(item["quantity"] for item in self.char_data["inventory"])
    
    def get_inventory_size(self) -> int:
        """Get the maximum number of items the agent's inventory can store."""
        return self.char_data["inventory_max_items"]
    
    def get_free_inventory_spaces(self) -> int:
        return self.get_inventory_size() - self.get_number_of_items_in_inventory()

    def _get_quantity_of_item_in_inventory(self, item: str) -> int:
        """Get the quantity of an item in the agent's inventory."""
        for item_data in self.char_data["inventory"]:
            if item_data["code"] == item:
                return item_data["quantity"]

        return 0
    
    def get_max_batch_size_for_item(self, item: str) -> int:
        return self.world_state.get_max_batch_size_for_item(item, self.get_inventory_size())
    
    def get_task_target(self) -> str:
        return self.char_data["task"]
    
    def get_task_quantity_remaining(self) -> int:
        return self.char_data["task_total"] - self.char_data["task_progress"]
    
    def set_abort_actions(self):
        self.abort_actions = True

    def unset_abort_actions(self):
        self.abort_actions = False

    def set_mode_manual(self):
        self.action_mode = AgentMode.MANUAL

    def set_mode_leader(self):
        self.action_mode = AgentMode.AUTO_GOAL_LEADER

    def set_mode_support(self):
        self.action_mode = AgentMode.AUTO_GOAL_SUPPORT

    def get_quantity_of_item_available(self, item: str, in_inv=False, in_bank=False) -> bool:
        """Check if the agent's has an item of at least a specific quantity available via inv, bank, or both."""
        available_quantity = 0

        if in_inv:
            available_quantity += self._get_quantity_of_item_in_inventory(item)

        if in_bank:
            available_quantity += self.world_state.get_amount_of_item_in_bank(item)

        return available_quantity

    ## Condition Checkers
    def at_location(self, x: int, y: int) -> bool:
        return self.char_data["x"] == x and self.char_data["y"] == y

    def at_world_location(self, world_location: str) -> bool:
        locations = self.world_state.get_locations_of_world_location(world_location)
        for (x, y) in locations:
            if self.char_data["x"] == x and self.char_data["y"] == y:
                return True
        
        return False
    
    def at_monster_or_resource(self, monster_or_resource: str) -> bool:
        locations = self.world_state.get_locations_of_monster_or_resource(monster_or_resource)
        for (x, y) in locations:
            if self.char_data["x"] == x and self.char_data["y"] == y:
                return True
        
        return False
                    
    def at_workshop_for_item(self, workshop_for_item: str) -> bool:
        workshop = self.world_state.get_workshop_for_item(workshop_for_item)
        locations = self.world_state.get_workshop_locations(workshop)
        for (x, y) in locations:
            if self.char_data["x"] == x and self.char_data["y"] == y:
                return True
        
        return False

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
    
    def has_quantity_of_item_available(self, item: str, quantity: int, in_inv=False, in_bank=False) -> bool:
        """Check if the agent's has an item of at least a specific quantity available via inv, bank, or both."""
        available_quantity = self.get_quantity_of_item_available(item, in_inv=in_inv, in_bank=in_bank)
        return available_quantity >= quantity
    
    def crafting_materials_for_item_available(self, item: str, quantity: int, in_inv=False, in_bank=False) -> bool:
        materials = self.world_state.get_crafting_materials_for_item(item, quantity)
        for material in materials:
            quantity_available = self.has_quantity_of_item_available(material["code"], material["quantity"], in_inv, in_bank)
            if not quantity_available:
                return False
            
        return True
    
    def loadout_contains_items(self) -> bool:
        if "prepared_loadout" in self.context:
            return len(self.context["prepared_loadout"]) > 0
        else:
            return False 

    def loadout_differs_from_equipped(self) -> bool:
        loadout = self.context["prepared_loadout"]
        for item in loadout:
            if self.world_state.is_equipment(item["code"]):
                slot = self.world_state.get_equip_slot_for_item(item["code"])
                if slot == "ring" and (self.char_data["ring1_slot"] != item["code"] or self.char_data["ring2_slot"] != item["code"]):
                    return True
                elif self.char_data[f"{slot}_slot"] != item["code"]:
                    return True
                else:
                    raise Exception("We shouldn't get here.")
            else:
                if self._get_quantity_of_item_in_inventory(item["code"]) < item["quantity"]:
                    return True
                
        return False
    
    def items_in_equip_queue(self) -> bool:
        equip_queue = self.context.get("equip_queue", [])
        return len(equip_queue) > 0
    
    def inventory_contains_usable_food(self) -> bool:
        usable_food = [
            item for item in self.char_data["inventory"]
            if self.world_state.is_food(item["code"]) 
            and self.world_state.character_meets_item_conditions(
                self.char_data, 
                self.world_state.get_item_info(item["code"])["conditions"]
            )
        ]

        return len(usable_food) > 0
    
    def bank_contains_usable_food(self) -> bool:
        usable_food = [
            item for item, quantity in self.world_state.get_bank_items().items()
            if self.world_state.is_food(item)
            and self.world_state.character_meets_item_conditions(
                self.char_data, 
                self.world_state.get_item_info(item)["conditions"]
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
        if task_type == "fighting":
            return self.world_state.is_a_monster(self.char_data["task"])
        elif task_type == "gathering":
            return not self.world_state.item_is_craftable(self.char_data["task"])
        elif task_type == "crafting":
            return self.world_state.item_is_craftable(self.char_data["task"])
        else:
            raise Exception(f"Unknown task type: {task_type}.")
    
    def has_completed_task(self) -> bool:
        return self.char_data["task_progress"] == self.char_data["task_total"]
    
    def has_skill_level(self, skill: str, level: int) -> bool:
        if skill in SKILLS:
            return self.char_data[f"{skill}_level"] >= level
        elif skill == "character":
            return self.char_data["level"] >= level
        else:
            raise Exception(f"Unknown skill: {skill}.")
        
    def context_value_equals(self, key: str, value: Any) -> bool:
        return self.context[key] == value

    ## Action Performance        
    async def meta_perform(self, action: Action) -> ActionOutcome:
        log_msg = f"[{self.name}] Performing meta action: {action.type.value}"
        if action.params:
            log_msg += f" with params {action.params}"
        self.logger.debug(log_msg)

        match action.type:
            case MetaAction.FORCE_SUCCESS:
                return ActionOutcome.SUCCESS
            
            case MetaAction.FORCE_FAIL:
                return ActionOutcome.FAIL

            case MetaAction.SET_CONTEXT:
                key = action.params.get("key")
                value = action.params.get("value")
                self.context[key] = value
                return ActionOutcome.SUCCESS
            
            case MetaAction.UPDATE_CONTEXT:
                key = action.params.get("key")
                value = action.params.get("value")                    
                self.context[key] += value
                return ActionOutcome.SUCCESS
            
            case MetaAction.CLEAR_CONTEXT:
                key = action.params.get("key")
                del self.context[key]
                return ActionOutcome.SUCCESS
            
            case MetaAction.CREATE_ITEM_RESERVATION:
                items = action.params.get("items")

                for item in items:
                    self.world_state.set_bank_reservation(self.name, item["code"], item["quantity"])

                return ActionOutcome.SUCCESS

            case MetaAction.UPDATE_ITEM_RESERVATION:
                items = action.params.get("items")

                for item in items:
                    self.world_state.update_bank_reservation(self.name, item["code"], item["quantity"])

                return ActionOutcome.SUCCESS

            case MetaAction.CLEAR_ITEM_RESERVATION:
                items = action.params.get("items")

                for item in items:
                    if type(item) is dict:
                        item_to_clear = item["code"]
                    else:
                        item_to_clear = item

                    self.world_state.clear_bank_reservation(self.name, item_to_clear)

                return ActionOutcome.SUCCESS
            
            case MetaAction.PREPARE_LOADOUT:
                task = action.params.get("task")
                target = action.params.get("target")

                equipment, inventory, equip_queue = self.world_state.prepare_best_loadout_for_task(self.char_data, task, target)
                self.context["prepared_loadout"] = [*equipment, *inventory]
                self.context["prepared_loadout_inventory"] = [item["code"] for item in inventory]
                self.context["equip_queue"] = equip_queue

                return ActionOutcome.SUCCESS
            
            case MetaAction.CLEAR_PREPARED_LOADOUT:
                del self.context["prepared_loadout"]
                del self.context["prepared_loadout_inventory"]
                del self.context["equip_queue"]
                return ActionOutcome.SUCCESS

            case _:
                raise Exception(f"[{self.name}] Unknown meta action type: {action.type}")
            
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
                elif world_location := action.params.get("world_location"):
                    locations = self.world_state.get_locations_of_world_location(world_location)                        
                    loc = self._get_closest_location(locations)
                    if not loc:
                        return ActionOutcome.FAIL
                    
                    x, y = loc
                elif monster_or_resource := action.params.get("monster_or_resource"):
                    locations = self.world_state.get_locations_of_monster_or_resource(monster_or_resource)                        
                    loc = self._get_closest_location(locations)
                    if not loc:
                        return ActionOutcome.FAIL
                    
                    x, y = loc
                elif workshop_for_item := action.params.get("workshop_for_item"):
                    workshop = self.world_state.get_workshop_for_item(workshop_for_item)
                    locations = self.world_state.get_workshop_locations(workshop)
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

                if not resource:
                    self.logger.warning(f"[{self.name}] No resource at current location")
                    return ActionOutcome.FAIL

                for r in resource:
                    r_data = self.world_state.get_item_info(r)
                    
                    if not "skill" in r_data:
                        continue

                    r_skill = r_data["skill"]
                    r_level = r_data["level"]
                    character_skill_level = self.char_data[f"{r_skill}_level"]

                    if character_skill_level < r_level:
                        self.logger.warning(f"[{self.name}] Skill '{r_skill}' level {character_skill_level} insufficient to gather {resource} ({r_level}).")
                        return ActionOutcome.FAIL
                
                api_result = await self.api_client.gather(self.name)
        
            ## BANKING ##
            case CharacterAction.BANK_DEPOSIT_ITEM:
                if action.params.get("deposit_all", False):
                    exclusions = self.context.get("bank_deposit_exclusions", [])
                    items_to_deposit = [{ "code": item["code"], "quantity": item["quantity"] } for item in self.char_data["inventory"] if item["code"] != '' and item["code"] not in exclusions]
                    
                    if not items_to_deposit:
                        return ActionOutcome.CANCEL
                else:
                    items_to_deposit = []
                    for deposit in action.params.get("items", []):
                        items_to_deposit.append({ "code": deposit["item"], "quantity": int(deposit["quantity"]) })

                api_result = await self.api_client.bank_deposit_item(self.name, items_to_deposit)
                
            case CharacterAction.BANK_WITHDRAW_ITEM:
                items_to_withdraw = []

                if action.params.get("prepared_loadout", False):
                    items_to_withdraw = self.context["prepared_loadout"]
                elif items := action.params.get("items", []):
                    items_to_withdraw = items
                elif order := action.params.get("order", None):
                    items_to_withdraw = self._construct_item_list(order)

                # Clean up item withdrawals
                items_to_withdraw = [item for item in items_to_withdraw if item["quantity"] > 0]

                if not items_to_withdraw:
                    return ActionOutcome.CANCEL
                
                api_result = await self.api_client.bank_withdraw_item(self.name, items_to_withdraw)
            
            case CharacterAction.BANK_DEPOSIT_GOLD:
                quantity = action.params.get("quantity")

                if quantity == 0:
                    self.logger.warning(f"[{self.name}] Cannot deposit zero gold")
                    return ActionOutcome.CANCEL
                
                api_result = await self.api_client.bank_deposit_gold(self.name, quantity)
                
            case CharacterAction.BANK_WITHDRAW_GOLD:
                quantity = action.params.get("quantity")
                
                if quantity == 0:
                    self.logger.warning(f"[{self.name}] Cannot withdraw zero gold")
                    return ActionOutcome.CANCEL
                
                api_result = await self.api_client.bank_withdraw_gold(self.name, quantity)

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
                        item = self._get_best_food_in_inv()
                        quantity = 1

                        if not item:
                            return ActionOutcome.CANCEL

                    case _:
                        item = action.params.get("item")
                        quantity = action.params.get("quantity", 1)
                    
                api_result = await self.api_client.use(self.name, item, quantity)

            ## CRAFTING ##
            case CharacterAction.CRAFT:
                item = action.params.get("item")
                quantity = action.params.get("quantity")
                
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
            if fight_result_info := api_result.response.get("data", {}).get("fight", {}).get("characters", []):
                old_hp = self.char_data["hp"]

                # Each character in the fight is given a dict in he reponse list
                for i, result_info in enumerate(fight_result_info):
                    new_hp = result_info["final_hp"]
                    self.context["damage_taken_last_fight"] = old_hp - new_hp
                    self.char_data = api_result.response.get("data", {}).get("characters")[i]

                    # Need to add extra handling here for when we implement multi-char fights
                    break

            # Check for trade data
            if trade_data := api_result.response.get("data", {}).get("trade"):
                self.context["last_trade_quantity"] = trade_data.get("quantity")

            # Check for craft data
            if craft_data := api_result.response.get("data", {}).get("details", {}).get("items"):
                self.context["last_craft_quantity"] = craft_data[0].get("quantity")

            # Update character state
            if new_char_data := api_result.response.get("data", {}).get("character"):
                self.char_data = new_char_data

            # Update the agent's cooldown
            new_cooldown = api_result.response.get("data").get("cooldown").get("remaining_seconds")
            self.cooldown_expires_at = datetime.now().timestamp() + new_cooldown
            
            # Update bank
            if bank_data := api_result.response.get("data").get("bank", []):
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
