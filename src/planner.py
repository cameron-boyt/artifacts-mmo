from __future__ import annotations

import logging
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum, auto

from src.action import *
from src.condition_factories import *
from src.control_factories import *
from src.action_factories import *
from src.helpers import *

@dataclass(frozen=True)
class ContextValue:
    key: str
    def resolve(self, agent: CharacterAgent):
        return agent.context[self.key]

@dataclass(frozen=True)
class DeferredExpr:
    expr: Callable[[CharacterAgent], Any]
    def resolve(self, agent: CharacterAgent):
        return self.expr(agent)

class Intention(Enum):
    # Basic Intention
    MOVE = auto()
    TRANSITION = auto()

    FIGHT_AND_HEAL = auto()
    CRAFT_AT_STATION = auto()

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

    # Crafting Intentions
    CRAFT_OR_GATHER_INTERMEDIARIES = auto()
    GATHER_MATERIALS_FOR_CRAFT = auto()

    CRAFT_UNTIL_LEVEL = auto()

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
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def plan(self, intent: ActionIntent) -> ActionExecutable:
        match intent.intention:
            # Basic Intentions
            case Intention.MOVE:
                return move(**intent.params)
            
            case Intention.TRANSITION:
                raise NotImplementedError()
            
            case Intention.FIGHT_AND_HEAL:                
                return group(
                    WHILE(
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
            
            case Intention.CRAFT_AT_STATION:
                item = intent.params.get("item")
                quantity = intent.params.get("quantity")

                return group(
                    IF(
                        (
                            NOT(cond(ActionCondition.AT_LOCATION, workshop_for_item=item)),
                            move(workshop_for_item=item)
                        )
                    ),
                    craft(item=item, quantity=quantity)
                )
            
            # General Worker Intentions
            case Intention.DEPOSIT_ALL_AT_BANK:
                return group(
                    IF(
                        (
                            NOT(cond(ActionCondition.AT_LOCATION, world_location="bank")),
                            move(world_location="bank")
                        )
                    ),
                    IF(
                        (
                            NOT(cond(ActionCondition.INVENTORY_EMPTY)),
                            bank_all_items()
                        )
                    )
                )

            case Intention.PREPARE_FOR_TASK:
                task_type = intent.params.get("task_type")
                target = intent.params.get("target")
                
                if task_type != "fighting" and task_type != "gathering":
                    raise Exception(f"Unknown task type for prepare for: {task_type}")

                return group(
                    prepare_best_loadout(task=task_type, target=target),
                    IF(
                        (
                            OR(
                                cond(ActionCondition.INVENTORY_FULL),
                                AND(
                                    cond(ActionCondition.PREPARED_LOADOUT_HAS_ITEMS),
                                    cond(ActionCondition.PREPARED_LOADOUT_DIFFERS_FROM_EQUIPPED)
                                )
                            ),
                            group(
                                self.plan(ActionIntent(Intention.DEPOSIT_ALL_AT_BANK)),
                                add_item_reservations(items=ContextValue("prepared_loadout")),
                                set_context(key="bank_deposit_exclusions", value=ContextValue("prepared_loadout_inventory")),
                                TRY(
                                    group(
                                        bank_withdraw_item(items=ContextValue("prepared_loadout")),
                                        WHILE(
                                            equip(use_queue=True),
                                            condition=cond(ActionCondition.ITEMS_IN_EQUIP_QUEUE)
                                        )
                                    ),
                                    finally_path=group(
                                        clear_item_reservations(items=ContextValue("prepared_loadout")),
                                        clear_prepared_loadout()
                                    )
                                ),
                                self.plan(ActionIntent(Intention.DEPOSIT_ALL_AT_BANK)),
                                clear_context(key="bank_deposit_exclusions"),
                            )
                        ),
                        fail_path=clear_prepared_loadout()
                    ),
                    IF(
                        (
                            NOT(cond(ActionCondition.AT_LOCATION, monster_or_resource=target)),
                            move(monster_or_resource=target)
                        )
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
                            self.plan(ActionIntent(Intention.FIGHT_AND_HEAL))
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
                            gather()
                        ),
                        condition=condition
                    )
                )
            
            # Task Execution
            case Intention.MOVE_TO_TASK_MASTER:
                task_type = intent.params.get("task_type")
                world_location = f"task_master_{task_type}"

                return IF(
                    (
                        NOT(cond(ActionCondition.AT_LOCATION, world_location=world_location)),
                        move(world_location=world_location)
                    )
                )

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
                return DeferredPlanNode(lambda agent: self.plan(ActionIntent(
                    Intention.FIGHT_MONSTERS,
                    monster=agent.get_task_target(),
                    condition=NOT(cond(ActionCondition.TASK_COMPLETE))
                )))
            
            case Intention.COMPLETE_ITEM_TASK_GATHERING:
                return DeferredPlanNode(lambda agent: group(
                    self.plan(ActionIntent(
                        Intention.GATHER_RESOURCES,
                        resource=agent.get_task_target(),
                        condition=NOT(cond(
                            ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY,
                            item=agent.get_task_target(),
                            quantity=agent.get_task_quantity_remaining()
                        ))
                    )),
                    self.plan(ActionIntent(Intention.TURN_IN_ITEM_TASK_ITEMS))
                ))
            
            case Intention.COMPLETE_ITEM_TASK_CRAFTING:
                return DeferredPlanNode(lambda agent: group(
                    IF(
                        (
                            NOT(cond(
                                ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY,
                                item=agent.get_task_target(),
                                quantity=agent.get_task_quantity_remaining()
                            )),
                            self.plan(ActionIntent(
                                Intention.CRAFT_OR_GATHER_INTERMEDIARIES,
                                item=agent.get_task_target(),
                                quantity=agent.get_task_quantity_remaining() - agent.world_state.get_amount_of_item_in_bank(agent.get_task_target())
                            ))
                        )
                    ),
                    self.plan(ActionIntent(Intention.TURN_IN_ITEM_TASK_ITEMS))
                ))
            
            case Intention.TURN_IN_ITEM_TASK_ITEMS:
                return group(
                    set_context(key="selected_items", value=DeferredExpr(lambda agent: [{ "code": agent.get_task_target(), "quantity": agent.get_task_quantity_remaining() }])),
                    add_item_reservations(items=ContextValue("selected_items")),
                    WHILE(
                        group(
                            self.plan(ActionIntent(Intention.DEPOSIT_ALL_AT_BANK)),
                            bank_withdraw_item(items=DeferredExpr(lambda agent: [{ "code": agent.get_task_target(), "quantity": min(agent.get_task_quantity_remaining(), agent.get_inventory_size()) }])),
                            self.plan(ActionIntent(Intention.MOVE_TO_TASK_MASTER, task_type="items")),
                            task_trade(item=DeferredExpr(lambda agent: agent.get_task_target()), quantity=DeferredExpr(lambda agent: agent.get_quantity_of_item_in_inventory(agent.get_task_target()))),
                            update_item_reservations(
                                item=DeferredExpr(lambda agent: agent.get_task_target()),
                                quantity=ContextValue("last_trade_quantity")
                            ),
                        ),
                        condition=NOT(cond(ActionCondition.TASK_COMPLETE))
                    )
                )
            
            # Complex Intentions            
            case Intention.GATHER_MATERIALS_FOR_CRAFT:
                item = intent.params.get("item")
                quantity_context_key = intent.params.get("quantity_context_key")

                return DeferredPlanNode(lambda agent: group(*[
                    IF(
                        (
                            cond(ActionCondition.RESOURCE_FROM_FIGHTING, resource=item["code"]),
                            DeferredPlanNode(lambda agent: self.plan(ActionIntent(
                                Intention.FIGHT_MONSTERS, 
                                monster=agent.world_state.get_monster_for_item(item["code"]),
                                condition=NOT(cond(ActionCondition.GLOBAL_AVAILABLE_QUANTIY_OF_ITEM, item=item["code"], quantity=item["quantity"] * agent.context[quantity_context_key]))
                            )))
                        ),
                        (
                            cond(ActionCondition.RESOURCE_FROM_GATHERING, resource=item["code"]),
                            DeferredPlanNode(lambda agent: self.plan(ActionIntent(
                                Intention.GATHER_RESOURCES,
                                resource=item["code"],
                                condition=NOT(cond(ActionCondition.GLOBAL_AVAILABLE_QUANTIY_OF_ITEM, item=item["code"], quantity=item["quantity"] * agent.context[quantity_context_key]))
                            )))
                        ),
                        (
                            cond(ActionCondition.RESOURCE_FROM_CRAFTING, resource=item["code"]),
                            DeferredPlanNode(lambda agent: self.plan(ActionIntent(
                                Intention.CRAFT_OR_GATHER_INTERMEDIARIES,
                                item=item["code"],
                                quantity=item["quantity"] * agent.context[quantity_context_key]
                            )))
                        ),
                        # (
                        #     cond(ActionCondition.RESOURCE_FROM_TASKS, resource=material["code"]),
                        #     self.plan(ActionIntent(
                        #         Intention.COMPLETE_TASKS,
                        #         condition=NOT(cond__item_qty_in_inv_and_bank(item["code"], item["quantity"] * agent.context[quantity_context_key]))
                        #     ))
                        # ),
                        fail_path=fail_action()
                    ) for item in agent.world_state.get_crafting_materials_for_item(item)]
                ))
            
            case Intention.CRAFT_OR_GATHER_INTERMEDIARIES:
                item = intent.params.get("item")
                quantity = intent.params.get("quantity")

                amount_crafted = f"{item}_amount_crafted"
                total_amount_to_craft = f"{item}_total_amount_to_craft"
                craft_batch_size = f"{item}_craft_batch_size"

                return group(
                    set_context(key=amount_crafted, value=0),
                    set_context(key=total_amount_to_craft, value=quantity),
                    WHILE(
                        group(
                            set_context(key=craft_batch_size, value=DeferredExpr(lambda agent: min(agent.context[total_amount_to_craft] - agent.context[amount_crafted], agent.get_max_batch_size_for_item(item)))),
                            IF(
                                (
                                    NOT(cond(ActionCondition.CRAFT_INGREDIENTS_IN_BANK_OR_INV, item=item, quantity=ContextValue(craft_batch_size))),
                                    self.plan(ActionIntent(Intention.GATHER_MATERIALS_FOR_CRAFT, item=item, quantity_context_key=craft_batch_size)),
                                )
                            ),
                            # After gathering and depositing, another agent could reserve and grab them first, so need to recheck the available batch size
                            set_context(key=craft_batch_size, value=DeferredExpr(lambda agent: min(agent.context[total_amount_to_craft] - agent.context[amount_crafted], agent.get_max_batch_size_for_item(item)))),
                            IF(
                                (
                                    NOT(cond(ActionCondition.CRAFT_INGREDIENTS_IN_INV, item=item, quantity=ContextValue(craft_batch_size))),
                                    group(
                                        set_context(key="selected_items", value=DeferredExpr(lambda agent: agent.world_state.get_crafting_materials_for_item(item, agent.context[craft_batch_size]))),
                                        add_item_reservations(items=ContextValue("selected_items")),
                                        self.plan(ActionIntent(Intention.DEPOSIT_ALL_AT_BANK)),
                                        TRY(
                                            bank_withdraw_item(items=ContextValue("selected_items")),
                                            finally_path=group(
                                                clear_item_reservations(items=ContextValue("selected_items")),
                                                clear_context(key="selected_items")
                                            )
                                        )
                                    )
                                )
                            ),
                            TRY(
                                self.plan(ActionIntent(Intention.CRAFT_AT_STATION, item=item, quantity=ContextValue(craft_batch_size))),
                                update_context(key=amount_crafted, value=ContextValue("last_craft_quantity")),
                                error_path=group(
                                    clear_context(key=amount_crafted),
                                    clear_context(key=total_amount_to_craft),
                                    fail_action()
                                ),
                                finally_path=clear_context(key=craft_batch_size)
                            )
                        ),
                        condition=NOT(cond(
                            ActionCondition.CONTEXT_VALUE_EQUALS, 
                            key=amount_crafted, 
                            value=ContextValue(total_amount_to_craft)
                        ))
                    ),
                    clear_context(key=amount_crafted),
                    clear_context(key=total_amount_to_craft)
                )
            
            case _:
                raise Exception("Unknown action type.")
            