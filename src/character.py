from typing import TYPE_CHECKING, Dict, Any
from action import Action, ActionGroup, ActionCondition, CharacterAction
from api import APIClient
import logging

if TYPE_CHECKING:
    from src.scheduler import ActionScheduler

class CharacterAgent:
    """Represents a single character, holding its state and execution logic."""
    def __init__(self, data: Dict[str, Any], api_client: APIClient, scheduler: ActionScheduler):
        self.logger = logging.getLogger(__name__)

        self.name = data["name"]
        self.api_client: APIClient = api_client
        self.scheduler: ActionScheduler = scheduler
        self.is_autonomous: bool = False
        self.char_data: Dict[str, Any] = data
        self.cooldown_expires_at: float = 0.0

    def is_inventory_full(self) -> bool:
        item_count = sum(item["quantity"] for item in self.char_data["inventory"])
        return item_count >= self.char_data["inventory_max_items"]
    

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
        self.logger.info(f"[{self.name}] Performing action: {action.type} with params {action.params}")

        match action.type:
            case CharacterAction.MOVE:
                x = action.params["x"]
                y = action.params["y"]
                response: dict = await self.api_client.move(self.name, x, y)
        
            case CharacterAction.FIGHT:
                response: dict = await self.api_client.fight(self.name)
        
            case CharacterAction.REST:
                response: dict = await self.api_client.rest(self.name)
        
            case CharacterAction.GATHER:
                response: dict = await self.api_client.gather(self.name)
        
            case CharacterAction.BANK:
                match action.params.get("bank_preset", "all"):
                    case "all":
                        items_to_bank = [{ "code": item["code"], "quantity": item["quantity"] } for item in self.char_data["inventory"] if item["code"] != '']
                    case _:
                        raise Exception("Unknown bank preset")
                    
                response: dict = await self.api_client.bank(self.name, items_to_bank)
        
            case _:
                raise Exception(f"[{self.name}] Unknown action type: {action.type}")
            
        
        if response:
            self.char_data = response.get("data").get("character")
            cooldown = response.get("data").get("cooldown").get("remaining_seconds")

        return cooldown

