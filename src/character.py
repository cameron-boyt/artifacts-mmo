from typing import TYPE_CHECKING, Dict, Any
from action import Action, ActionGroup, ActionCondition, CharacterAction
from api import APIClient
import logging

if TYPE_CHECKING:
    from src.scheduler import ActionScheduler

class CharacterAgent:
    """Represents a single character, holding its state and execution logic."""
    def __init__(self, character_data: Dict[str, Any], bank_data: Dict[str, Any], map_data: Dict[str, Any], api_client: APIClient, scheduler: ActionScheduler):
        self.logger = logging.getLogger(__name__)
        
        self.api_client: APIClient = api_client
        self.scheduler: ActionScheduler = scheduler

        self.name = character_data["name"]
        self.char_data: Dict[str, Any] = character_data
        self.bank_data = bank_data
        self.map_data = map_data

        self.is_autonomous: bool = False
        self.cooldown_expires_at: float = 0.0

        self.prev_location = (0, 0)


    ## CONDITION CHECKERS
    def is_inventory_full(self) -> bool:
        item_count = sum(item["quantity"] for item in self.char_data["inventory"])
        return item_count >= self.char_data["inventory_max_items"]
    
    def bank_has_item_of_quantity(self, item_code: str, quantity: int) -> bool:
        for item in self.bank_data:
            if item["code"] == item_code:
                if item["quantity"] >= quantity:
                    return True

        return False

    def repeat_condition_met(self, condition: ActionCondition) -> bool:
        match condition:
            case ActionCondition.NONE:
                return True
            
            case ActionCondition.FOREVER:
                return False
            
            case ActionCondition.INVENTORY_FULL:
                return self.is_inventory_full()
            
            case _:
                raise Exception("Unknown condition")
            
        return True
    

    async def perform(self, action: Action) -> float:
        log_msg = f"[{self.name}] Performing action: {action.type.value}"
        if action.params:
            log_msg += f" with params {action.params}"
        self.logger.info(log_msg)

        match action.type:
            ## MOVING ##
            case CharacterAction.MOVE:
                if "prev_location" in action.params:
                    x = self.prev_location[0]
                    y = self.prev_location[1]
                else:
                    x = action.params["x"]
                    y = action.params["y"]

                self.prev_location = (self.char_data["x"],  self.char_data["y"])
                response: dict = await self.api_client.move(self.name, x, y)

            ## FIGHTING ##
            case CharacterAction.FIGHT:
                response: dict = await self.api_client.fight(self.name)
        
            case CharacterAction.REST:
                response: dict = await self.api_client.rest(self.name)
        
            ## GATHERING ##
            case CharacterAction.GATHER:
                response: dict = await self.api_client.gather(self.name)
        
            ## BANKING ##
            case CharacterAction.BANK_DEPOSIT_ITEM:
                match action.params.get("preset", "none"):
                    case "all":
                        items_to_deposit = [{ "code": item["code"], "quantity": item["quantity"] } for item in self.char_data["inventory"] if item["code"] != '']
                    case _:
                        items_to_deposit = []
                        for deposit in action.params.get("items", []):
                            items_to_deposit.append({ "code": deposit["code"], "quantity": int(deposit["quantity"]) })

                response: dict = await self.api_client.bank_deposit_item(self.name, items_to_deposit)
                
            case CharacterAction.BANK_WITHDRAW_ITEM:
                match action.params.get("preset", "none"):
                    case "all":
                        items_to_withdraw = [{ "code": item["code"], "quantity": item["quantity"] } for item in self.char_data["inventory"] if item["code"] != '']
                    case _:
                        items_to_deposit = []
                        for deposit in action.params.get("items", []):
                            items_to_deposit.append({ "code": deposit["code"], "quantity": int(deposit["quantity"]) })

                response: dict = await self.api_client.bank_withdraw_item(self.name, items_to_withdraw)
            
            case CharacterAction.BANK_DEPOSIT_GOLD:
                quantity_to_deposit = action.params.get("quantity", 0)
                response: dict = await self.api_client.bank_deposit_gold(self.name, quantity_to_deposit)
                
            case CharacterAction.BANK_WITHDRAW_GOLD:
                quantity_to_withdraw = action.params.get("quantity", 0)
                response: dict = await self.api_client.bank_withdraw_gold(self.name, quantity_to_withdraw)

            ## EQUIPMENT ##
            case CharacterAction.EQUIP:
                item_code = action.params.get("item_code")
                item_slot = action.params.get("item_slot")
                response: dict = await self.api_client.equip(self.name, item_code, item_slot)

            case CharacterAction.UNEQUIP:
                item_slot = action.params.get("item_slot")
                response: dict = await self.api_client.unequip(self.name, item_slot)

            ## CRAFTING ##
            case CharacterAction.CRAFT:
                item_code = action.params.get("item_code")
                response: dict = await self.api_client.craft(self.name, item_code)
        
            case _:
                raise Exception(f"[{self.name}] Unknown action type: {action.type}")
            
        
        if response:
            self.char_data = response.get("data").get("character")
            cooldown = response.get("data").get("cooldown").get("remaining_seconds")
            return cooldown
        else:
            return -1

