import logging
from typing import Dict, List, Any
from character import CharacterAction, CharacterAgent
from action import ActionConditionExpression
from condition_factories import *
from control_factories import *
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

    # Complex Intentions
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

@dataclass
class ItemQuantity:
    max: int | None = None
    min: int | None = None
    multiple_of: int | None = None
    all: bool | None = None

    def __post_init__(self):
        if self.all:
            # If requesting all of an item, forbid a min/max selection
            assert(not self.max)
            assert(not self.min)

        if not self.all:
            # If not requesting all of an item, require a min or max selection
            assert(self.max > 0 or self.min > 0)

@dataclass
class ItemSelection:
    item: str
    quantity: ItemQuantity

class ActionPlanner:
    """Interprets action intent and generates action plans."""
    def __init__(self, world_data: Dict, bank_data: Dict):
        self.logger = logging.getLogger(__name__)

        self.world_data: Dict[str, Dict] = world_data
        self.bank_data: Dict[str, Dict] = bank_data

    def _get_locations_of_resource(self, resource: str) -> str:
        resource_tile = self.world_data["resources"][resource]

        locations = []
        for tile in resource_tile:
            locations.extend(self.world_data["interactions"]["resource"][tile])

        return locations

    def _get_locations_of_monster(self, monster: str) -> str:
        locations = self.world_data["interactions"]["monster"][monster]
        return locations
    
    def _construct_item_list(self, selection: List[ItemSelection]) -> List[Dict]:
        items = []
        for item in selection:
            quantity = self._get_desired_item_quantity(item)
            if quantity == 0:
                continue

            items.append({
                "item_code": item.item,
                "quantity": quantity
            })

        return items
    
    def _bank_contains_items(self, items: List[ItemSelection]) -> bool:
        #TODO: Implement
        return True
    
    def _get_desired_item_quantity(self, item: ItemSelection) -> int:
        available_quantity = self.bank_data[item.item]["quantity"]

        # Get all available quantity, or clamp the quantity within the bound min/max attributes
        if item.quantity.all:
            quantity = available_quantity
        else:
            quantity = min(item.quantity.max, max(item.quantity.min, available_quantity))

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
                    resource_locations = self._get_locations_of_monster(monster)
                    x, y = agent.get_closest_location(resource_locations)
                    return action_group(
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
                    return action_group(
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
                return action_group(
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
                items: List[ItemSelection] = intent.params.get("items")
                items_to_withdraw = self._construct_item_list(items)

                resource_locations = self.world_data["interactions"]["bank"]["bank"]
                x, y = agent.get_closest_location(resource_locations)
                return action_group(
                    move(x=x, y=y),
                    bank_withdraw_item(items=items_to_withdraw)
                )
            
            case Intention.DEPOSIT:
                items: List[ItemSelection] = intent.params.get("items")
                items_to_deposit = self._construct_item_list(items)
        
                resource_locations = self.world_data["interactions"]["bank"]["bank"]
                x, y = agent.get_closest_location(resource_locations)
                return action_group(
                    move(x=x, y=y),
                    bank_deposit_item(items=items_to_deposit)
                )
            
            # Complex Intentions
            case Intention.FIGHT_THEN_REST:
                if monster := intent.params.get("monster"):
                    resource_locations = self._get_locations_of_monster(monster)
                    x, y = agent.get_closest_location(resource_locations)
                    return action_group(
                        move(x=x, y=y),
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
        
                resource_locations = self.world_data["interactions"]["bank"]["bank"]
                x, y = agent.get_closest_location(resource_locations)
                return action_group(
                    move(x=x, y=y),
                    bank_action,
                    move(prev=True)
                )

            case Intention.CRAFT_OR_GATHER_INTERMEDIARIES:
                item = intent.params.get("item")
                quantity = intent.params.get("quantity")

                required_materials = self.world_data["items"][item]["craft"]["materials"]
                item_selection = [ItemSelection(material["code"], ItemQuantity(min=material["quantity"])) for material in required_materials]
                
                # Constuct list of items to withdraw from the bank
                items_to_withdraw = self._construct_item_list(item_selection)

                # Get location of the closest bank
                bank_locations = self.world_data["interactions"]["bank"]["bank"]
                b_x, b_y = agent.get_closest_location(bank_locations)

                # Get the location of the closest crafting station
                skill_workshop = self.world_data["items"][item]["craft"]["skill"]
                crafting_locations = self.world_data["interactions"]["workshop"][skill_workshop]
                w_x, w_y = agent.get_closest_location(crafting_locations)

                # Get the items to gather in case of a fallback
                item_to_gather = required_materials[0]["code"]
                quantity_to_gather = required_materials[0]["quantity"]

                # Get the location of the closest source of this item
                resource_locations = self._get_locations_of_resource(item_to_gather)
                g_x, g_y = agent.get_closest_location(resource_locations)
                
                return IF(
                    (
                        AND(*[
                            cond(ActionCondition.BANK_HAS_ITEM_OF_QUANTITY, item=material["code"], quantity=material["quantity"])
                            for material in required_materials
                        ]),
                        action_group(
                            move(x=b_x, y=b_y),
                            bank_withdraw_item(items=items_to_withdraw),
                            move(x=w_x, y=w_y),
                            craft(item=item, quantity=quantity)
                        )
                    ), fail_path=action_group(
                            move(x=g_x, y=g_y),
                            gather(until=cond(ActionCondition.BANK_HAS_ITEM_OF_QUANTITY, item=item_to_gather, quantity=quantity_to_gather))
                    )
                )
                
            case _:
                raise Exception("Unknown action type.")