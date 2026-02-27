from __future__ import annotations

import asyncio
import datetime
import time
import logging
from collections import deque
from typing import TYPE_CHECKING, Any, Dict
from math import ceil

from src.action import *
from src.character import AgentMode
from src.planner import ContextValue, DeferredExpr

if TYPE_CHECKING:
    from src.character import CharacterAgent
    from src.goalcoordinator import GoalCoordinator

class ActionScheduler:
    """Manages action queues and worker tasks for all characters."""
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.coordinator: GoalCoordinator

        self.agents: dict[str, CharacterAgent] = {}
        self.queues: dict[str, deque[ActionExecutable]] = {}
        self.worker_tasks: dict[str, asyncio.Task] = {}

    def get_status(self):
        print(self.queues)

    def register_coordinator(self, coordinator: GoalCoordinator):
        self.coordinator = coordinator

    def add_character(self, agent: CharacterAgent):
        """Add a new charcter to be handled by the scheduler."""
        name = agent.name
        if name in self.agents: 
            return
        
        self.logger.info(f"Adding character: {name}")
        
        self.agents[name] = agent
        self.queues[name] = deque()
        task = asyncio.create_task(self._worker(name))
        task.add_done_callback(self._task_done_callback)
        self.worker_tasks[name] = task

    def _task_done_callback(self, task: asyncio.Task):
        try:
            result = task.result()  # This will re-raise any exception
        except Exception as e:
            self.logger.error(f"Task raised exception: {e}", exc_info=True)

    def queue_action_node(self, character_name: str, node: ActionExecutable):
        """Queue an `node` for evaluation and execution by the character's worker."""
        # Check the character exists (i.e. has a defined queue)
        if character_name in self.queues:
            if isinstance(node, Action):
                self.logger.debug(f"[{character_name}] Action '{node.type}' queued.")
            elif isinstance(node, ActionGroup):
                self.logger.debug(f"[{character_name}] Action Group queued.")
            elif isinstance(node, ActionControlNode):
                self.logger.debug(f"[{character_name}] Action Control Node queued.")

            # Queue up the action node for the chosen character
            self.queues[character_name].append(node)


    async def _worker(self, character_name: str):
        """Worker process for character `character_name`"""
        self.logger.info(f"Worker started for {character_name}.")
        agent = self.agents[character_name]
        queue = self.queues[character_name]

        while True:            
            if not queue:
                match agent.action_mode:
                    case AgentMode.MANUAL:
                        await asyncio.sleep(0.5)
                        continue
                   
                    case AgentMode.AUTO_GOAL_LEADER:
                        self.coordinator.get_next_goal(agent.char_data, "progression")
                   
                    case AgentMode.AUTO_GOAL_SUPPORT:
                        self.coordinator.get_next_goal(agent.char_data, "pantry")
                
                    case _:
                        raise Exception(f"Unknown Agent Mode: {agent.action_mode}")

            # Pop the next node and process
            node = queue.popleft()
            await self._process_node(agent, node)
            
            # If the chain was aborted upwards, unset the flag so the agent can act again
            if agent.abort_actions:
                # Clear out any lingering bank reservations
                agent.world_state.clear_bank_reservation(agent.name)
                self.logger.warning(f"[{character_name}] Active node successfully aborted.")
                agent.unset_abort_actions()
            else:
                self.logger.info(f"[{character_name}] Finished queued node.")

    async def _process_node(self, agent: CharacterAgent, node: ActionExecutable) -> bool:
        # Check for abort
        if agent.abort_actions:
            return False
        
        if isinstance(node, Action):
            success = await self._process_single_action(agent, node)
            # After every action, check in with the coordinator to update global knowledge
            self.coordinator.check_in_character(agent.char_data)
        elif isinstance(node, ActionGroup):
            success = await self._process_group(agent, node)
        elif isinstance(node, ActionControlNode):
            success = await self._process_control_node(agent, node)
        elif isinstance(node, DeferredPlanNode):
            resolved_node = node.resolver(agent)
            success = await self._process_node(agent, resolved_node)
        else:
            raise Exception("Unrecognised node typing.")

        return success

    async def _process_single_action(self, agent: CharacterAgent, action: Action) -> bool:
        """Process a single action to be made by an agent, repeating as defined."""

        # Resolve params
        for parameter, value in action.params.items():
            if isinstance(value, (ContextValue, DeferredExpr)):
                action.params[parameter] = value.resolve(agent)

        if type(action.type) is CharacterAction:
            return await self._process_single_character_action(agent, action)
        elif type(action.type) is MetaAction:
            return await self._process_single_meta_action(agent, action)  
        else:
            raise Exception(f"Unknown instance type of action: {type(action.type)}")     
    
    async def _process_single_character_action(self, agent: CharacterAgent, action: Action) -> bool:
        retry_count = 0
        retry_max = 3

        while True:
            # Wait for the remaining cooldown for the worker
            remaining_cooldown = max(0, agent.cooldown_expires_at - time.time())
            if remaining_cooldown > 0:
                self.logger.debug(f"[{agent.name}] Waiting for cooldown: {ceil(remaining_cooldown)}s.")
                await asyncio.sleep(remaining_cooldown)

            # Check for abort
            if agent.abort_actions:
                return False
                                    
            # Execute the action
            outcome = await agent.perform(action)

            # Check action result
            match outcome:
                case ActionOutcome.SUCCESS:
                    return True
                
                case ActionOutcome.FAIL:
                    self.logger.error(f"[{agent.name}] Action {action.type} failed.")
                    return False
                
                case ActionOutcome.FAIL_RETRY:
                    retry_count += 1
                    if retry_count >= retry_max:
                        self.logger.error(f"[{agent.name}] Action {action.type} failed.")
                        return False
                    else:
                        self.logger.warning(f"[{agent.name}] Action {action.type} failed, but will be retried.")
                        await asyncio.sleep(1)
                        continue

                case ActionOutcome.FAIL_CONTINUE:
                    # The action failed, but we can safely continue the action sequence
                    self.logger.warning(f"[{agent.name}] Action {action.type} failed, but continuing action sequence anyway...")
                    return True
                
                case ActionOutcome.CANCEL:
                    # A cancelled action can be treated as a success with no state updates
                    self.logger.debug(f"[{agent.name}] Action {action.type} was cancelled.")
                    return True
                
                case _:
                    raise Exception(f"Unknown action outcome for CharacterAction: {outcome}")
                

    async def _process_single_meta_action(self, agent: CharacterAgent, action: Action) -> bool:
        # Check for abort
        if agent.abort_actions:
            return False
        
        # Execute the action
        outcome = await agent.meta_perform(action)

        # Check action result
        match outcome:
            case ActionOutcome.SUCCESS:                    
                return True
            
            case ActionOutcome.FAIL:
                return False
                
            case _:
                raise Exception(f"Unknown action outcome for MetaAction: {outcome}")

    async def _process_group(self, agent: CharacterAgent, action_group: ActionGroup) -> bool:
        """Process an action group, sequencing through all child actions, repeating as defined."""                    
        # Traverse through the grouped actions and execute them in sequence
        for sub_action in action_group.actions:
            sub_action_successful = await self._process_node(agent, sub_action)

            # If a sub_action was unsuccessful, discard the rest of the group
            if not sub_action_successful:
                return False

        return True

    async def _process_control_node(self, agent: CharacterAgent, control_node: ActionControlNode) -> bool:
        """Process a control node, deciding on branching or control-specific looping behaviours."""
        match control_node.control_operator:
            case ControlOperator.IF:
                branch = self._evaluate_control_branches(agent, control_node)
                if branch:
                    return await self._process_node(agent, branch)
                else:
                    # No fail_path branch, therefore continue following the action sequence
                    return True
            
            case ControlOperator.WHILE:
                # No executions should result in a successful node
                result = True

                # Check the repeat condition first, since it's a prerequisite for performing the child nodes
                while self._evaluate_condition(agent, control_node.condition):
                    result = await self._process_node(agent, control_node.node)

                    # Break out if the sub node has failed
                    if not result:
                        return result

                return result

            case ControlOperator.DO_WHILE:
                while True:
                    result = await self._process_node(agent, control_node.node)

                    # Break out if the sub node has failed
                    if not result:
                        return result
                    
                    # Check the repeat condition last to see if we should repeat
                    if not self._evaluate_condition(agent, control_node.condition):
                        break
                
                return result
            
            case ControlOperator.TRY:
                result = await self._process_node(agent, control_node.node)

                # If the try group succeeded, execeute the success path, should one exist
                if result and control_node.success_path:
                    result = await self._process_node(agent, control_node.success_path)

                # If the try group failed, execute the error path, should one exist
                if not result and control_node.error_path:
                    result = await self._process_node(agent, control_node.error_path)

                # If a finally path exists, always execute
                if control_node.finally_path:
                    result = await self._process_node(agent, control_node.finally_path)
                
                return result

    def _evaluate_control_branches(self, agent: CharacterAgent, control_node: ActionControlNode) -> Action | ActionGroup | ActionControlNode | None:
        for branch in control_node.branches:
            if self._evaluate_condition(agent, branch[0]):
                return branch[1]
            
        return control_node.fail_path

    def _evaluate_condition(self, agent: CharacterAgent, expression: ActionConditionExpression) -> bool:
        """Evaluate a condition expression path."""
        if not expression:
            return True
           
        if expression.is_leaf():
            # If at a leaf node, evaluate the condition
            self.logger.debug(f"[{agent.name}] Evaluating condition {expression.condition}")

            # Resolve params
            for parameter, value in expression.params.items():
                if isinstance(value, (ContextValue, DeferredExpr)):
                    expression.params[parameter] = value.resolve(agent)

            condition_met = False
            match expression.condition:                
                case ActionCondition.FOREVER:
                    # Forever meaning the condition will always me bet, therefore TRUE.
                    condition_met = True

                case ActionCondition.AT_LOCATION:
                    if (x := expression.params.get("x")) and (y := expression.params.get("y")):
                        condition_met = agent.at_location(x, y)
                    elif world_location := expression.params.get("world_location"):
                        condition_met = agent.at_world_location(world_location)
                    elif monster_or_resource := expression.params.get("monster_or_resource"):
                        condition_met = agent.at_monster_or_resource(monster_or_resource)
                    elif workshop_for_item := expression.params.get("workshop_for_item"):
                        condition_met = agent.at_workshop_for_item(workshop_for_item)
                
                case ActionCondition.INVENTORY_FULL:
                    condition_met = agent.inventory_full()
                
                case ActionCondition.INVENTORY_EMPTY:
                    condition_met = agent.inventory_empty()

                case ActionCondition.INVENTORY_HAS_AVAILABLE_SPACE:
                    free_spaces = expression.params["spaces"]
                    condition_met = agent.inventory_has_available_space(free_spaces)

                case ActionCondition.INVENTORY_HAS_AVAILABLE_SPACE_FOR_ITEMS:
                    items = expression.params["items"]
                    needed_space = 0
                    for item in items:
                        needed_quantity = item["quantity"]
                        current_quantity = agent.get_quantity_of_item_available(item["code"], in_inv=True)
                        needed_space += needed_quantity - current_quantity

                    condition_met = agent.inventory_has_available_space(needed_space)
                
                case ActionCondition.INVENTORY_HAS_ITEM_OF_QUANTITY:
                    item = expression.params["item"]
                    quantity = expression.params["quantity"]
                    condition_met = agent.has_quantity_of_item_available(item, quantity, in_inv=True)
                
                case ActionCondition.BANK_HAS_ITEM_OF_QUANTITY:
                    item = expression.params["item"]
                    quantity = expression.params["quantity"]
                    condition_met = agent.has_quantity_of_item_available(item, quantity, in_bank=True)

                case ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY:
                    item = expression.params["item"]
                    quantity = expression.params["quantity"]
                    condition_met = agent.has_quantity_of_item_available(item, quantity, in_inv=True, in_bank=True)
                
                case ActionCondition.GLOBAL_AVAILABLE_QUANTIY_OF_ITEM:
                    item = expression.params["item"]
                    quantity = expression.params["quantity"]
                    condition_met = self.coordinator.get_amount_of_item_in_world(item) >= quantity

                case ActionCondition.CRAFT_INGREDIENTS_IN_INV:
                    item = expression.params["item"]
                    quantity = expression.params["quantity"]
                    condition_met = agent.crafting_materials_for_item_available(item, quantity, in_inv=True)

                case ActionCondition.CRAFT_INGREDIENTS_IN_BANK:
                    item = expression.params["item"]
                    quantity = expression.params["quantity"]
                    condition_met = agent.crafting_materials_for_item_available(item, quantity, in_bank=True)

                case ActionCondition.CRAFT_INGREDIENTS_IN_BANK_OR_INV:
                    item = expression.params["item"]
                    quantity = expression.params["quantity"]
                    condition_met = agent.crafting_materials_for_item_available(item, quantity, in_inv=True, in_bank=True)

                case ActionCondition.PREPARED_LOADOUT_HAS_ITEMS:
                    condition_met = agent.loadout_contains_items()

                case ActionCondition.PREPARED_LOADOUT_DIFFERS_FROM_EQUIPPED:
                    condition_met = agent.loadout_differs_from_equipped()

                case ActionCondition.ITEMS_IN_EQUIP_QUEUE:
                    condition_met = agent.items_in_equip_queue()
                    
                case ActionCondition.INVENTORY_CONTAINS_USABLE_FOOD:
                    condition_met = agent.inventory_contains_usable_food()
                    
                case ActionCondition.BANK_CONTAINS_USABLE_FOOD:
                    condition_met = agent.bank_contains_usable_food()
                
                case ActionCondition.HEALTH_LOW_ENOUGH_TO_EAT:
                    condition_met = agent.health_sufficiently_low_to_heal()

                case ActionCondition.HAS_TASK:
                    condition_met = agent.has_task()

                case ActionCondition.HAS_TASK_OF_TYPE:
                    task_type = expression.params["task_type"]
                    condition_met = agent.has_task_of_type(task_type)

                case ActionCondition.TASK_COMPLETE:
                    condition_met = agent.has_completed_task()

                case ActionCondition.HAS_SKILL_LEVEL:
                    skill = expression.params["skill"]
                    level = expression.params["level"]
                    condition_met = agent.has_skill_level(skill, level)

                case ActionCondition.RESOURCE_FROM_FIGHTING:
                    resource = expression.params["resource"]
                    condition_met = agent.world_state.item_from_fighting(resource)

                case ActionCondition.RESOURCE_FROM_GATHERING:
                    resource = expression.params["resource"]
                    condition_met = agent.world_state.item_from_gathering(resource)

                case ActionCondition.RESOURCE_FROM_CRAFTING:
                    resource = expression.params["resource"]
                    condition_met = agent.world_state.item_from_crafting(resource)

                case ActionCondition.CONTEXT_VALUE_EQUALS:
                    key = expression.params["key"]
                    value = expression.params["value"]
                    condition_met = agent.context_value_equals(key, value)

                case _:
                    raise NotImplementedError()
                
            if condition_met:
                self.logger.debug(f"[{agent.name}] Passed {expression.condition} with params {expression.params}.")
            else:
                # Exception case where a 'failure' is due to a FOREVER condition
                if expression.condition != ActionCondition.FOREVER:
                    self.logger.debug(f"[{agent.name}] Failed {expression.condition} with params {expression.params}.")

            return condition_met
        else:
            # Else, apply the node's operator and evaluate the child nodes
            self.logger.debug(f"[{agent.name}] - Applying operator {expression.operator} to next expression")
            match expression.operator:
                case LogicalOperator.AND:
                    return all(self._evaluate_condition(agent, child) for child in expression.children)
        
                case LogicalOperator.OR:
                    return any(self._evaluate_condition(agent, child) for child in expression.children)
                
                case LogicalOperator.NOT:
                    return not self._evaluate_condition(agent, expression.children[0])
                
                case _:
                    raise Exception(f"Unknown logical operator: {expression.operator}")
                