import logging
from typing import Dict, List, Any
from character import CharacterAction, CharacterAgent
from action import ActionConditionExpression
from dataclasses import dataclass
from action_factories import *
from enum import Enum, auto

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
    def __init__(self, world_data: Dict):
        self.logger = logging.getLogger(__name__)

        self.world_data: Dict[str, Dict] = world_data

    def _get_locations_of_resource(self, resource: str) -> str:
        resource_tile = self.world_data["resources"][resource]

        locations = []
        for tile in resource_tile:
            locations.extend(self.world_data["interactions"]["resource"][tile])

        return locations

    def _get_locations_of_monster(self, monster: str) -> str:
        locations = self.world_data["interactions"]["monster"][monster]
        return locations

    def plan_intent(self, agent: CharacterAgent, intent: ActionIntent) -> Action | ActionGroup:
        match intent.intention:
            case Intention.MOVE:
                return move(params=intent.params)
            
            case Intention.TRANSITION:
                raise NotImplementedError()
            
            case Intention.FIGHT:
                if monster := intent.params.get("monster"):
                    resource_locations = self._get_locations_of_monster(monster)
                    x, y = agent.get_closest_location(resource_locations)
                    return group(
                        move(x=x, y=y),
                        fight(until=intent.until)
                    )
                else:
                    return fight(until=intent.until)

            case Intention.REST:
                return rest()
            
            case Intention.GATHER:
                if resource := intent.params.get("resource"):
                    resource_locations = self._get_locations_of_resource(resource)
                    x, y = agent.get_closest_location(resource_locations)
                    return group(
                        move(x=x, y=y),
                        gather(until=intent.until)
                    )
                else:
                    return gather(until=intent.until)
            
            case Intention.CRAFT:
                item = intent.params.get("item")
                quantity = intent.params.get("quantity")
                skill_workshop = self.world_data["items"][item]["craft"]["skill"]
                crafting_locations = self.world_data["interactions"]["workshop"][skill_workshop]
                x, y = agent.get_closest_location(crafting_locations)
                return group(
                    move(x=x, y=y),
                    craft(item_code=item, quantity=quantity)
                )
            
            case Intention.EQUIP:
                return equip()
            
            case Intention.UNEQUIP:
                return unequip()
            
            case Intention.USE:
                raise NotImplementedError()
            
            case Intention.WITHDRAW:
                item = intent.params.get("item")
                quantity = intent.params.get("quantity")
                resource_locations = self.world_data["interactions"]["bank"]["bank"]
                x, y = agent.get_closest_location(resource_locations)
                return group(
                    move(x=x, y=y),
                    bank_withdraw_item(items=[{ "item_code": item, "quantity": quantity}])
                )
            
            case Intention.DEPOSIT:
                item = intent.params.get("item")
                quantity = intent.params.get("quantity")
                resource_locations = self.world_data["bank"]["bank"]
                x, y = agent.get_closest_location(resource_locations)
                return group(
                    move(x=x, y=y),
                    bank_deposit_item(items=[{ "item_code": item, "quantity": quantity}])
                )
                
            case _:
                raise Exception("Unknown action type.")