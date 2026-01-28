from typing import TYPE_CHECKING, Dict, List, Tuple, Any
from action import Action, ActionGroup, ActionCondition, CharacterAction
from api import APIClient, ActionResult
import logging
from worldstate import WorldState

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
        self.world_state = world_state

        self.is_autonomous: bool = False
        self.cooldown_expires_at: float = 0.0

        self.prev_location = (0, 0)

    ## Helper Functions
    def get_closest_location(self, locations: List[Tuple[int, int]]) -> Tuple[int, int]:
        """Get the location which is the shortest distance from the agent."""
        shortest_distance = 9999
        best_location = (0, 0)

        for location in locations:
            distance = pow(pow(self.char_data["x"] - location[0], 2) + pow(self.char_data["y"] - location[1], 2), 0.5)
            if distance < shortest_distance:
                shortest_distance = distance
                best_location = location

        return best_location
    
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
    
    def get_quantity_of_item_in_bank(self, item: str) -> int:
        """Get the quantity of an item in the agent's bank."""
        if item in self.world_state._bank_data:
            return self.world_state._bank_data[item]

        return 0


    ## Condition Checkers
    def is_inventory_full(self) -> bool:
        """Check if the agent's inventory is full."""
        item_count = self.get_number_of_items_in_inventory()
        inv_size = self.get_inventory_size()
        return item_count >= inv_size
    
    def is_inventory_empty(self) -> bool:
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
        bank_quantity = self.get_quantity_of_item_in_bank(item)
        return bank_quantity >= quantity
    
    def bank_and_inventory_have_item_of_quantity(self, item: str, quantity: int) -> bool:
        """Check if the agent's bank and inventory have a combined amount of an item of at least a specific quantity."""
        inv_quantity = self.get_quantity_of_item_in_inventory(item)
        bank_quantity = self.get_quantity_of_item_in_bank(item)
        return inv_quantity + bank_quantity >= quantity
    

    ## Action Performance
    async def perform(self, action: Action) -> ActionResult:
        log_msg = f"[{self.name}] Performing action: {action.type.value}"
        if action.params:
            log_msg += f" with params {action.params}"
        self.logger.info(log_msg)

        match action.type:
            ## MOVING ##
            case CharacterAction.MOVE:
                if action.params.get("prev_location", False):
                    x = self.prev_location[0]
                    y = self.prev_location[1]
                elif locations := action.params.get("closest_location_of", []):
                    x, y = self.get_closest_location(locations)
                else:
                    x = action.params["x"]
                    y = action.params["y"]

                self.prev_location = (self.char_data["x"],  self.char_data["y"])
                result = await self.api_client.move(self.name, x, y)

            ## FIGHTING ##
            case CharacterAction.FIGHT:
                result = await self.api_client.fight(self.name)
        
            case CharacterAction.REST:
                result = await self.api_client.rest(self.name)
        
            ## GATHERING ##
            case CharacterAction.GATHER:
                result = await self.api_client.gather(self.name)
        
            ## BANKING ##
            case CharacterAction.BANK_DEPOSIT_ITEM:
                match action.params.get("preset", "none"):
                    case "all":
                        items_to_deposit = [{ "code": item["code"], "quantity": item["quantity"] } for item in self.char_data["inventory"] if item["code"] != '']
                    case _:
                        items_to_deposit = []
                        for deposit in action.params.get("items", []):
                            items_to_deposit.append({ "code": deposit["item"], "quantity": int(deposit["quantity"]) })

                result = await self.api_client.bank_deposit_item(self.name, items_to_deposit)
                
            case CharacterAction.BANK_WITHDRAW_ITEM:
                match action.params.get("preset", "none"):
                    case _:
                        # Construct a list of items that need to be withdrawn
                        items_to_withdraw = []

                        # Also, heck how many items are needed to be withdrawn
                        total_items_needed = 0
                        items_already_in_inv = 0

                        for withdraw in action.params.get("items", []):
                            quantity_to_withdraw = int(withdraw["quantity"])
                            items_to_withdraw.append({ "code": withdraw["item"], "quantity": quantity_to_withdraw })

                            total_items_needed += int(withdraw["quantity"])
                            items_already_in_inv += self.get_quantity_of_item_in_inventory(withdraw["item"])

                        if total_items_needed == 0:
                            print("?")

                        if action.params.get("withdraw_until_inv_full", False):
                            # Maximise the number of item sets we can withdraw
                            available_inv_space = self.get_free_inventory_spaces()
                            sets_to_withdraw = (available_inv_space - items_already_in_inv) // total_items_needed

                            # Check we can actually withdraw this number of sets
                            all_good = False
                            for n in range(sets_to_withdraw, 0, -1):
                                for item in items_to_withdraw:
                                    if self.world_state.get_amount_of_item_in_bank(item["code"]) < item["quantity"] * n:
                                        break

                                    all_good = True

                                if all_good:
                                    break
                            
                            if n == 0:
                                return ActionResult(self.char_data, False, True)
                            
                            for item in items_to_withdraw:
                                item["quantity"] *= n

                        # If we only want to withdraw the needed amount, check how much we have in the inventory
                        if action.params.get("needed_quantity_only", False):
                            for item in items_to_withdraw:
                                quantity_in_inv = self.get_quantity_of_item_in_inventory(item["code"])
                                item["quantity"] -= quantity_in_inv

                result = await self.api_client.bank_withdraw_item(self.name, items_to_withdraw)
            
            case CharacterAction.BANK_DEPOSIT_GOLD:
                quantity_to_deposit = action.params.get("quantity", 0)
                result = await self.api_client.bank_deposit_gold(self.name, quantity_to_deposit)
                
            case CharacterAction.BANK_WITHDRAW_GOLD:
                quantity_to_withdraw = action.params.get("quantity", 0)
                result = await self.api_client.bank_withdraw_gold(self.name, quantity_to_withdraw)

            ## EQUIPMENT ##
            case CharacterAction.EQUIP:
                item_code = action.params.get("item")
                item_slot = action.params.get("slot")
                result = await self.api_client.equip(self.name, item_code, item_slot)

            case CharacterAction.UNEQUIP:
                item_slot = action.params.get("slot")
                result = await self.api_client.unequip(self.name, item_slot)

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
                        
                result = await self.api_client.craft(self.name, item, quantity)
        
            case _:
                raise Exception(f"[{self.name}] Unknown action type: {action.type}")
            
        
        if result.success:
            self.char_data = result.response.get("data").get("character")
            
            # Update bank
            if bank_data := result.response.get("data").get("bank"):
                for item in bank_data:
                    self.world_state._bank_data[item["code"]] = item["quantity"]
        

        return result

