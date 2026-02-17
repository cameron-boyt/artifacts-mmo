from __future__ import annotations

import logging
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum, auto

from src.action import *
from src.condition_factories import *
from src.control_factories import *
from src.action_factories import *
from src.worldstate import WorldState
from src.helpers import *

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

    WITHDRAW_ITEMS = auto()
    DEPOSIT_ITEMS = auto()

    WITHDRAW_GOLD = auto()
    DEPOSIT_GOLD = auto()

    # Tasks
    MOVE_TO_TASK_MASTER = auto()
    COMPLETE_TASKS = auto()
    PLAN_TASK_COMPLETION = auto()
    COMPLETE_MONSTER_TASK = auto()
    COMPLETE_ITEM_TASK_GATHERING = auto()
    COMPLETE_ITEM_TASK_CRAFTING = auto()
    TURN_IN_ITEM_TASK_ITEMS = auto()

    # Complex Intentions
    PREPARE_FOR_TASK =  auto()
    COLLECT_THEN_CRAFT = auto()

    DEPOSIT_ALL_AT_BANK = auto()
    BANK_THEN_RETURN = auto()
    CRAFT_OR_GATHER_INTERMEDIARIES = auto()

    CRAFT_UNTIL_LEVEL = auto()

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

    def plan(self, intent: ActionIntent) -> ActionExecutable:
        match intent.intention:
            # Basic Intentions
            case Intention.MOVE:
                return move(**intent.params)
            
            case Intention.TRANSITION:
                raise NotImplementedError()
            
            case Intention.FIGHT:
                monster = intent.params.get("monster")
                monster_locations = self.world_state.get_locations_of_monster(monster)

                prepare_and_move_action = action_group(
                    self.plan(ActionIntent(Intention.PREPARE_FOR_TASK, task_type="fighting", target=monster)),
                    move(closest_of=monster_locations)
                )
                
                return action_group(
                    prepare_and_move_action,
                    action_group(
                        IF(
                            (
                                OR(
                                    cond(ActionCondition.INVENTORY_FULL), 
                                    NOT(cond(ActionCondition.INVENTORY_CONTAINS_USABLE_FOOD))
                                ), 
                                prepare_and_move_action
                            )
                        ),
                        DO_WHILE(
                            IF(
                                (
                                    cond(ActionCondition.INVENTORY_CONTAINS_USABLE_FOOD),
                                    use(item_type="food")
                                ),
                                fail_path=rest()
                            ),
                            condition=cond(ActionCondition.HEALTH_LOW_ENOUGH_TO_EAT)
                        ),
                        fight(),                            
                        until=intent.until
                    )
                )

            case Intention.REST:
                return rest()
            
            case Intention.GATHER:
                resource = intent.params.get("resource")
                resource_locations = self.world_state.get_locations_of_resource(resource)

                prepare_and_move_action = action_group(
                    self.plan(ActionIntent(Intention.PREPARE_FOR_TASK, task_type="gathering", target=resource)),
                    move(closest_of=resource_locations)
                )

                return action_group(
                    prepare_and_move_action,
                    action_group(
                        IF(
                            (
                                cond(ActionCondition.INVENTORY_FULL), 
                                prepare_and_move_action
                            )
                        ),
                        gather(),
                        until=intent.until
                    )
                )
            
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
            
            case Intention.WITHDRAW_ITEMS:
                items: ItemOrder = intent.params.get("items")
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_of=bank_locations),
                    bank_withdraw_item(items=items)
                )
            
            case Intention.DEPOSIT_ITEMS:
                bank_locations = self.world_state.get_bank_locations()
                match intent.params.get("preset", "none"):
                    case "all":
                        return action_group(
                            move(closest_of=bank_locations),
                            bank_deposit_item(preset="all")
                        )
                    
                    case _:
                        items: List[ItemSelection] = intent.params.get("items")
                        return action_group(
                            move(closest_of=bank_locations),
                            bank_deposit_item(items=items)
                        )
                    
            case Intention.DEPOSIT_ALL_AT_BANK:
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_of=bank_locations),
                    bank_deposit_item(preset="all")
                )
            
            case Intention.WITHDRAW_GOLD:
                bank_locations = self.world_state.get_bank_locations()
                quantity: int = intent.params.get("quantity")
                return action_group(
                    move(closest_of=bank_locations),
                    bank_withdraw_gold(quantity=quantity)
                )
            
            case Intention.DEPOSIT_GOLD:
                bank_locations = self.world_state.get_bank_locations()
                quantity: int = intent.params.get("quantity")
                return action_group(
                    move(closest_of=bank_locations),
                    bank_deposit_gold(quantity=quantity)
                )
            
            # Task Execution
            case Intention.MOVE_TO_TASK_MASTER:
                task_type = intent.params.get("task_type")
                task_master_locations = self.world_state.get_task_master_locations().get(task_type)
                return move(closest_of=task_master_locations)

            case Intention.COMPLETE_TASKS:
                task_type = intent.params.get("type")
                move_to_task_master = self.plan(ActionIntent(Intention.MOVE_TO_TASK_MASTER, task_type=task_type))
                
                return action_group(
                        IF(
                            (
                                NOT(cond(ActionCondition.HAS_TASK)), 
                                action_group(
                                    move_to_task_master,
                                    get_task()
                                )
                            ),
                            (
                                cond(ActionCondition.TASK_COMPLETE), 
                                action_group(
                                    move_to_task_master,
                                    complete_task(),
                                    get_task()
                                )
                            )
                        ),
                        self.plan(ActionIntent(Intention.PLAN_TASK_COMPLETION)),
                        until=cond(ActionCondition.FOREVER)
                    )
                
            case Intention.PLAN_TASK_COMPLETION:
                return IF(
                    (
                        cond(ActionCondition.HAS_TASK_OF_TYPE, task_type="fighting"),
                        self.plan(ActionIntent(Intention.COMPLETE_MONSTER_TASK))
                    ),
                    (
                        cond(ActionCondition.HAS_TASK_OF_TYPE, task_type="gathering"),
                        self.plan(ActionIntent(Intention.COMPLETE_ITEM_TASK_GATHERING))
                    ),
                    (
                        cond(ActionCondition.HAS_TASK_OF_TYPE, task_type="crafting"),
                        self.plan(ActionIntent(Intention.COMPLETE_ITEM_TASK_CRAFTING))
                    )
                )
            
            case Intention.PREPARE_FOR_TASK:
                task_type = intent.params.get("task_type")
                target = intent.params.get("target")

                return action_group(
                    self.plan(ActionIntent(Intention.DEPOSIT_ALL_AT_BANK)),
                    action_group(
                        bank_withdraw_item(preset=task_type, sub_preset=target),
                        REPEAT(
                            IF((cond(ActionCondition.ITEMS_IN_EQUIP_QUEUE), equip(use_queue=True))),
                            until=NOT(cond(ActionCondition.ITEMS_IN_EQUIP_QUEUE))
                        ),
                        DeferredAction(lambda agent: bank_all_items(exclude=[agent.context["withdrawn_food"]]))
                    ) 
                )

            case Intention.COMPLETE_MONSTER_TASK:
                return DeferredAction(lambda agent: 
                    self.plan(
                        ActionIntent(Intention.FIGHT, monster=agent.get_task_target(), until=cond(ActionCondition.TASK_COMPLETE))
                    )
                )
            
            case Intention.COMPLETE_ITEM_TASK_GATHERING:
                return DeferredAction(lambda agent:
                    action_group(
                        IF(
                            (
                                NOT(cond(ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY, item=agent.get_task_target(), quantity=agent.get_task_quantity_remaining())),
                                self.plan(ActionIntent(Intention.GATHER, resource=agent.get_task_target(),
                                    until=cond(ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY, item=agent.get_task_target(), quantity=agent.get_task_quantity_remaining())
                                ))
                            )
                        ),
                        self.plan(ActionIntent(Intention.TURN_IN_ITEM_TASK_ITEMS))
                    )
                )
            
            case Intention.COMPLETE_ITEM_TASK_CRAFTING:
                return DeferredAction(lambda agent:
                    action_group(
                        IF(
                            (
                                NOT(cond(ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY, item=agent.get_task_target(), quantity=agent.get_task_quantity_remaining())),
                                self.plan(ActionIntent(Intention.CRAFT_OR_GATHER_INTERMEDIARIES, item=agent.get_task_target(), quantity=agent.get_task_quantity_remaining()))
                            )
                        ),
                        self.plan(ActionIntent(Intention.TURN_IN_ITEM_TASK_ITEMS))
                    )
                )
            
            case Intention.TURN_IN_ITEM_TASK_ITEMS:
                return DeferredAction(lambda agent:
                    action_group(
                        reserve_item_in_bank(name=agent.name, item=agent.get_task_target(), quantity=agent.get_task_quantity_remaining()),
                        action_group(
                            self.plan(ActionIntent(Intention.DEPOSIT_ALL_AT_BANK)),   
                            DeferredAction(lambda agent: bank_withdraw_item(items=ItemOrder(items=[ItemSelection(item=agent.get_task_target(), quantity=ItemQuantity(max=min(agent.get_task_quantity_remaining(), agent.get_free_inventory_spaces())))]), reserve=False)),
                            self.plan(ActionIntent(Intention.MOVE_TO_TASK_MASTER, task_type="items")),
                            DeferredAction(lambda agent: task_trade(item=agent.get_task_target(), quantity=agent.get_quantity_of_item_in_inventory(agent.get_task_target()))),
                            DeferredAction(lambda agent: update_item_reservation(name=agent.name, item=agent.get_task_target(), quantity=-agent.context["last_trade"]["quantity"])),
                            until=cond(ActionCondition.TASK_COMPLETE)
                        )
                    )
                )
            
            # Complex Intentions             
            case Intention.BANK_THEN_RETURN:
                if intent.params.get("preset") == "all":
                    bank_action = bank_all_items()
                else:
                    items: List[ItemSelection] = intent.params.get("items")
                    bank_action = bank_deposit_item(items=items)
        
                bank_locations = self.world_state.get_bank_locations()
                return action_group(
                    move(closest_of=bank_locations),
                    bank_action,
                    move(previous=True)
                )
            
            case Intention.COLLECT_THEN_CRAFT:
                craft_item = intent.params.get("item")
                craft_max = intent.params.get("as_many_as_possible", False)
                craft_qty = intent.params.get("quantity", 1)

                required_materials = self.world_state.get_crafting_materials_for_item(craft_item, craft_qty)
                items=[
                    ItemSelection(item=m["code"], quantity=ItemQuantity(min=m["quantity"], max=m["quantity"]))
                    for m in required_materials
                ]
                
                item_order = ItemOrder(items, greedy_order=craft_max, check_inv=True)

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
                    self.plan(ActionIntent(Intention.WITHDRAW_ITEMS, items=item_order, needed_quantity_only=True, withdraw_until_inv_full=craft_max))
                )

                # Construct bank and withdraw action plan
                act_move_to_bank_and_withdraw = self.plan(ActionIntent(Intention.WITHDRAW_ITEMS, items=item_order, needed_quantity_only=True, withdraw_until_inv_full=craft_max))

                # Construct move to workshop and craft action plan
                act_move_to_workshop_and_craft = self.plan(ActionIntent(Intention.CRAFT, item=craft_item, quantity=craft_qty, as_many_as_possible=craft_max))
                
                return IF(
                    (cond_materials_in_inv, act_move_to_workshop_and_craft),
                    (cond_materials_in_inv_and_bank, IF(
                        (cond_has_space_for_items, action_group(
                            act_move_to_bank_and_withdraw,
                            act_move_to_workshop_and_craft
                        )),
                        fail_path=action_group(
                            act_bank_all_then_withdraw,
                            act_move_to_workshop_and_craft
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
                        IF(
                            (
                                cond(ActionCondition.RESOURCE_FROM_GATHERING, resource=material["code"]),
                                action_group(
                                    self.plan(ActionIntent(Intention.PREPARE_FOR_TASK, task_type="gathering", target=material["code"])),
                                    self.plan(ActionIntent(Intention.GATHER, resource=material["code"], until=cond(ActionCondition.INVENTORY_FULL)))
                                )
                            ),
                            (
                                cond(ActionCondition.RESOURCE_FROM_FIGHTING, resource=material["code"]),
                                action_group(
                                    self.plan(ActionIntent(Intention.PREPARE_FOR_TASK, task_type="fighting", target=material["code"])),
                                    self.plan(ActionIntent(Intention.FIGHT, until=cond(ActionCondition.INVENTORY_FULL)))
                                )
                            )
                        ),
                        
                        self.plan(ActionIntent(Intention.DEPOSIT_ITEMS, preset="all")),
                        until=cond__item_qty_in_inv_and_bank(material["code"], material["quantity"])
                    )
                    for material in required_materials
                ])
                
                # Generate a COLLECT_THEN_CRAFT, but override the failpath with the gathering
                act_collect_then_craft = self.plan(ActionIntent(Intention.COLLECT_THEN_CRAFT, item=craft_item, quantity=craft_qty, as_many_as_possible=craft_max))
                assert isinstance(act_collect_then_craft, ActionControlNode)
                act_collect_then_craft.fail_path = act_gather_materials
                
                return act_collect_then_craft
            
            case Intention.CRAFT_UNTIL_LEVEL:
                craft_item = intent.params.get("item")
                level_goal = intent.params.get("level")

                skill = self.world_state.get_item_info(craft_item)["craft"]["skill"]
                craft_or_gather_plan = self.plan(ActionIntent(Intention.CRAFT_OR_GATHER_INTERMEDIARIES, item=craft_item, as_many_as_possible=True))

                return REPEAT(
                    craft_or_gather_plan,
                    until=cond(ActionCondition.HAS_SKILL_LEVEL, skill=skill, level=level_goal)
                )
            
            case _:
                raise Exception("Unknown action type.")
