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
    # Basic Intention
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

    # General Worker Intentions
    PREPARE_FOR_TASK =  auto()
    FIGHT_MONSTERS = auto()
    GATHER_RESOURCES = auto()

    # Task Intentions
    MOVE_TO_TASK_MASTER = auto()
    COMPLETE_TASKS = auto()
    PLAN_TASK_COMPLETION = auto()
    COMPLETE_MONSTER_TASK = auto()
    COMPLETE_ITEM_TASK_GATHERING = auto()
    COMPLETE_ITEM_TASK_CRAFTING = auto()
    TURN_IN_ITEM_TASK_ITEMS = auto()

    # Complex Intentions
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
                return group(
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
                    fight()
                )

            case Intention.REST:
                return rest()
            
            case Intention.GATHER:
                return gather()
            
            case Intention.CRAFT:
                item: str = intent.params.get("item")
                quantity: int = intent.params.get("quantity")
                skill_workshop = self.world_state.get_workshop_for_item(item)
                workshop_locations = self.world_state.get_workshop_locations(skill_workshop)

                return group(
                    move(closest_of=workshop_locations),
                    craft(item=item, quantity=quantity)
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

                return group(
                    move(closest_of=bank_locations),
                    bank_withdraw_item(items=items)
                )
            
            case Intention.DEPOSIT_ITEMS:
                bank_locations = self.world_state.get_bank_locations()
                match intent.params.get("preset", "none"):
                    case "all":
                        return group(
                            move(closest_of=bank_locations),
                            bank_deposit_item(preset="all")
                        )
                    
                    case _:
                        items: List[ItemSelection] = intent.params.get("items")
                        return group(
                            move(closest_of=bank_locations),
                            bank_deposit_item(items=items)
                        )
                    
            case Intention.DEPOSIT_ALL_AT_BANK:
                bank_locations = self.world_state.get_bank_locations()
                return group(
                    move(closest_of=bank_locations),
                    bank_all_items()
                )
            
            case Intention.WITHDRAW_GOLD:
                bank_locations = self.world_state.get_bank_locations()
                quantity: int = intent.params.get("quantity")
                return group(
                    move(closest_of=bank_locations),
                    bank_withdraw_gold(quantity=quantity)
                )
            
            case Intention.DEPOSIT_GOLD:
                bank_locations = self.world_state.get_bank_locations()
                quantity: int = intent.params.get("quantity")
                return group(
                    move(closest_of=bank_locations),
                    bank_deposit_gold(quantity=quantity)
                )
            
            # General Worker Intentions
            case Intention.PREPARE_FOR_TASK:
                task_type = intent.params.get("task_type")
                target = intent.params.get("target")

                if task_type == "fighting":
                    locations = self.world_state.get_locations_of_monster(target)
                elif task_type == "gathering":
                    locations = self.world_state.get_locations_of_resource(target)
                else:
                    raise Exception(f"Unknown task type for prepare for: {task_type}")

                return group(
                    self.plan(ActionIntent(Intention.DEPOSIT_ALL_AT_BANK)),
                    DeferredAction(lambda agent: prepare_best_loadout(character=agent.char_data, task=task_type, target=target)),
                    DeferredAction(lambda agent: add_item_reservations(name=agent.name, items=agent.context["prepared_loadout"])),
                    TRY(
                        group(
                            DeferredAction(lambda agent: bank_withdraw_item(items=agent.context["prepared_loadout"])),
                            WHILE(
                                equip(use_queue=True),
                                condition=cond(ActionCondition.ITEMS_IN_EQUIP_QUEUE)
                            ),
                            bank_all_items(),
                            move(closest_of=locations)
                        ),
                        error_path=clear_prepared_loadout(),
                        finally_path=DeferredAction(lambda agent: clear_item_reservations(name=agent.name, items=agent.context["prepared_loadout"]))
                    )
                )
            
            case Intention.FIGHT_MONSTERS:
                monster = intent.params.get("monster")
                condition = intent.params.get("condition")
                prepare_action = self.plan(ActionIntent(Intention.PREPARE_FOR_TASK, task_type="fighting", target=monster))

                return group(
                    prepare_action,
                    WHILE(
                        group(
                            IF(
                                (
                                    OR(
                                        cond(ActionCondition.INVENTORY_FULL), 
                                        AND(
                                            NOT(cond(ActionCondition.INVENTORY_CONTAINS_USABLE_FOOD)),
                                            cond(ActionCondition.BANK_CONTAINS_USABLE_FOOD)
                                        )
                                    ), 
                                    prepare_action
                                )
                            ),
                            self.plan(ActionIntent(Intention.FIGHT))
                        ),
                        condition=condition
                    )
                )
            
            case Intention.GATHER_RESOURCES:
                resource = intent.params.get("resource")
                condition = intent.params.get("condition")
                prepare_action = self.plan(ActionIntent(Intention.PREPARE_FOR_TASK, task_type="gathering", target=resource))

                return group(
                    prepare_action,
                    WHILE(
                        group(
                            IF(
                                (
                                    cond(ActionCondition.INVENTORY_FULL),
                                    prepare_action
                                )
                            ),
                            self.plan(ActionIntent(Intention.GATHER))
                        ),
                        condition=condition
                    )
                )
            
            # Task Execution
            case Intention.MOVE_TO_TASK_MASTER:
                task_type = intent.params.get("task_type")
                task_master_locations = self.world_state.get_task_master_locations().get(task_type)
                return move(closest_of=task_master_locations)

            case Intention.COMPLETE_TASKS:
                task_type = intent.params.get("type")
                move_to_task_master = self.plan(ActionIntent(Intention.MOVE_TO_TASK_MASTER, task_type=task_type))
                
                return DO_WHILE(
                    group(
                        IF(
                            (
                                NOT(cond(ActionCondition.HAS_TASK)), 
                                group(
                                    move_to_task_master,
                                    get_task()
                                )
                            ),
                            (
                                cond(ActionCondition.TASK_COMPLETE), 
                                group(
                                    move_to_task_master,
                                    complete_task(),
                                    get_task()
                                )
                            )
                        ),
                        self.plan(ActionIntent(Intention.PLAN_TASK_COMPLETION))
                    ),
                    condition=cond(ActionCondition.FOREVER)
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

            case Intention.COMPLETE_MONSTER_TASK:
                fight_action = DeferredAction(lambda agent:
                    self.plan(ActionIntent(
                        Intention.FIGHT_MONSTERS,
                        monster=agent.get_task_target(),
                        condition=NOT(cond(ActionCondition.TASK_COMPLETE))
                    ))
                )

                return fight_action
            
            case Intention.COMPLETE_ITEM_TASK_GATHERING:
                gather_action = DeferredAction(lambda agent:
                    self.plan(ActionIntent(
                        Intention.GATHER_RESOURCES,
                        resource=agent.get_task_target(),
                        condition=DeferredCondition(lambda agent:
                            NOT(cond(
                                ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY,
                                item=agent.get_task_target(),
                                quantity=agent.get_task_quantity_remaining()
                            ))
                        ))
                    )
                )

                return group(
                    gather_action,
                    self.plan(ActionIntent(Intention.TURN_IN_ITEM_TASK_ITEMS))
                )
            
            case Intention.COMPLETE_ITEM_TASK_CRAFTING:
                return group(
                    DeferredAction(lambda agent:
                        IF(
                            (
                                NOT(cond(ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY, item=agent.get_task_target(), quantity=agent.get_task_quantity_remaining())),
                                self.plan(ActionIntent(
                                    Intention.CRAFT_OR_GATHER_INTERMEDIARIES,
                                    item=agent.get_task_target(),
                                    quantity=agent.get_task_quantity_remaining() - agent.world_state.get_amount_of_item_in_bank(agent.get_task_target())
                                ))
                            )
                        )
                    ),
                    self.plan(ActionIntent(Intention.TURN_IN_ITEM_TASK_ITEMS))
                )
            
            case Intention.TURN_IN_ITEM_TASK_ITEMS:
                return group(
                    DeferredAction(lambda agent: add_item_reservations(
                        name=agent.name, 
                        items=[{ "code": agent.get_task_target(), "quantity": agent.get_task_quantity_remaining() }]
                    )),
                    WHILE(
                        group(
                            self.plan(ActionIntent(Intention.DEPOSIT_ALL_AT_BANK)),   
                            DeferredAction(lambda agent: bank_withdraw_item(items=ItemOrder(items=[ItemSelection(item=agent.get_task_target(), quantity=ItemQuantity(max=min(agent.get_task_quantity_remaining(), agent.get_free_inventory_spaces())))]), reserve=False)),
                            self.plan(ActionIntent(Intention.MOVE_TO_TASK_MASTER, task_type="items")),
                            DeferredAction(lambda agent: task_trade(item=agent.get_task_target(), quantity=agent.get_quantity_of_item_in_inventory(agent.get_task_target()))),
                            DeferredAction(lambda agent: update_item_reservations(
                                name=agent.name,
                                items=[{ "code": agent.get_task_target(), "quantity": -agent.context["last_trade"]["quantity"] }]
                            )),
                        ),
                        condition=NOT(cond(ActionCondition.TASK_COMPLETE))
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
                return group(
                    move(closest_of=bank_locations),
                    bank_action,
                    move(previous=True)
                )
            
            case Intention.COLLECT_THEN_CRAFT:
                craft_item = intent.params.get("item")
                craft_qty = intent.params.get("quantity", 1)
                craft_max = intent.params.get("craft_max", False)
                gather_intermediaries = intent.params.get("gather_intermediaries", False)

                required_materials = self.world_state.get_crafting_materials_for_item(craft_item)
                total_materials = sum(i["quantity"] for i in required_materials)

                context_counter = f"counter_craft_{craft_item}"

                augment_req_mats = lambda inv_size: [
                    { "code": m["code"], "quantity": m["quantity"] * (min(craft_qty, inv_size // total_materials) if not craft_max else inv_size // total_materials) } 
                    for m in required_materials
                ]

                if gather_intermediaries:
                    insufficient_mats_action = DeferredAction(lambda agent: group(*[
                        IF(
                            (
                                cond(ActionCondition.RESOURCE_FROM_FIGHTING, resource=material["code"]),
                                DeferredAction(lambda agent: self.plan(ActionIntent(
                                    Intention.FIGHT_MONSTERS, 
                                    monster=agent.world_state._drop_sources[material["code"]][0],
                                    condition=cond__item_qty_in_inv_and_bank(material["code"], material["quantity"])
                                )))
                            ),
                            (
                                cond(ActionCondition.RESOURCE_FROM_GATHERING, resource=material["code"]),
                                self.plan(ActionIntent(
                                    Intention.GATHER_RESOURCES,
                                    resource=material["code"],
                                    condition=cond__item_qty_in_inv_and_bank(material["code"], material["quantity"])
                                ))
                            )
                        )
                        for material in augment_req_mats(agent.get_inventory_size())
                    ]))
                else:
                    insufficient_mats_action = fail_action()
                
                return group(
                    reset_context_counter(name=context_counter),
                    DeferredAction(lambda agent:
                        WHILE(
                            group(
                                IF(
                                    (
                                        NOT(cond__items_in_inv_and_bank(augment_req_mats(agent.get_inventory_size()))),
                                        insufficient_mats_action
                                    ),
                                    (
                                        NOT(cond__items_in_inv(augment_req_mats(agent.get_inventory_size()))),
                                        group(
                                            add_item_reservations(name=agent.name, items=augment_req_mats(agent.get_inventory_size())),
                                            IF(
                                                (
                                                    NOT(cond__inv_has_space_for_items(augment_req_mats(agent.get_inventory_size()))),
                                                    self.plan(ActionIntent(Intention.DEPOSIT_ALL_AT_BANK))
                                                )
                                            ),
                                            TRY(
                                                self.plan(ActionIntent(Intention.WITHDRAW_ITEMS, items=augment_req_mats(agent.get_inventory_size()))),
                                                finally_path=clear_item_reservations(
                                                    name=agent.name, 
                                                    items=[{ "code": i["code"], "quantity": -i["quantity"] } for i in augment_req_mats(agent.get_inventory_size())]
                                                )
                                            )
                                        )
                                    )
                                ),
                                TRY(
                                    self.plan(ActionIntent(Intention.CRAFT, item=craft_item, quantity=craft_qty if not craft_max else agent.get_inventory_size() // total_materials)),
                                    success_path=DeferredAction(lambda agent: increment_context_counter(name=context_counter, value=agent.context["last_craft"]["value"])),
                                    error_path=group(
                                        clear_context_counter(name=context_counter),
                                        fail_action()
                                    )
                                )
                            ),
                            condition=NOT(cond(
                                ActionCondition.CONTEXT_COUNTER_AT_VALUE, 
                                name=context_counter, 
                                value=craft_qty if not craft_max else agent.get_inventory_size() // total_materials
                            ))
                        )
                    )
                )
            
            case _:
                raise Exception("Unknown action type.")
