from __future__ import annotations

import asyncio
import datetime
import time
import logging
from collections import deque
from typing import TYPE_CHECKING, Any, Dict

from src.action import Action, ActionGroup, ActionCondition, ActionConditionExpression, ActionOutcome, LogicalOperator, ControlOperator, ActionControlNode
from src.character import CharacterAgent
from src.api import APIClient
from src.worldstate import WorldState

if TYPE_CHECKING:
    from src.character import CharacterAgent

class ActionScheduler:
    """Manages action queues and worker tasks for all characters."""
    def __init__(self, api_client: APIClient):
        self.logger = logging.getLogger(__name__)

        self.api_client = api_client
        self.agents: dict[str, CharacterAgent] = {}
        self.queues: dict[str, deque[Action | ActionGroup | ActionControlNode]] = {}
        self.worker_tasks: dict[str, asyncio.Task] = {}


    def get_status(self):
        print(self.queues)


    def add_character(self, character_data: Dict[str, Any], world_state: WorldState):
        """Add a new charcter to be handled by the scheduler."""
        name = character_data["name"]
        if name in self.agents: 
            return
        
        self.logger.info(f"Adding character: {name}")
        agent = CharacterAgent(character_data, world_state, self.api_client, self)
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


    def queue_action_node(self, character_name: str, node: Action | ActionGroup | ActionControlNode):
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
        
        # If the agent has any residual cooldown, let it expire first
        if agent.cooldown_expires_at == 0.0:
            agent.cooldown_expires_at = datetime.datetime.strptime(agent.char_data.get("cooldown_expiration"), "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()

        while True:
            if not queue:
                await asyncio.sleep(0.5)
                continue

            # Pop the next node and process
            node = queue.popleft()
            await self._process_node(agent, node)
            
            # If the chain was aborted upwards, unset the flag so the agent can act again
            if agent.abort_actions:
                self.logger.warning(f"[{character_name}] Active node successfully aborted.")
                agent.unset_abort_actions()
            else:
                self.logger.info(f"[{character_name}] Finished queued node.")

    async def _process_node(self, agent: CharacterAgent, node: Action | ActionGroup | ActionControlNode) -> bool:
        # Check for abort
        if agent.abort_actions:
            return False
        
        if isinstance(node, Action):
            success = await self._process_single_action(agent, node)
        elif isinstance(node, ActionGroup):
            success = await self._process_action_group(agent, node)
        elif isinstance(node, ActionControlNode):
            success = await self._process_control_node(agent, node)
        else:
            raise Exception("Unrecognised node typing.")

        return success

    async def _process_single_action(self, agent: CharacterAgent, action: Action) -> bool:
        """Process a single action to be made by an agent, repeating as defined."""        
        retry_count = 0
        retry_max = 3

        while True:
            # Wait for the remaining cooldown for the worker
            remaining_cooldown = max(0, agent.cooldown_expires_at - time.time())
            if remaining_cooldown > 0:
                self.logger.debug(f"[{agent.name}] Waiting for cooldown: {round(remaining_cooldown)}s.")
                await asyncio.sleep(remaining_cooldown)

            # Check for abort
            if agent.abort_actions:
                return False
                                    
            # Execute the action
            outcome = await agent.perform(action)

            # Check action result
            match outcome:
                case ActionOutcome.SUCCESS:
                    # Check if the repeat until condition has been met for this action
                    if self._evaluate_condition(agent, action.until):
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
                
            # Check if the repeat until condition has been met for this action
            if self._evaluate_condition(agent, action.until):
                break

    async def _process_action_group(self, agent: CharacterAgent, action_group: ActionGroup) -> bool:
        """Process an action group, sequencing through all child actions, repeating as defined."""
        while True:   
            # Check for abort
            if agent.abort_actions:
                return False
                     
            # Traverse through the grouped actions and execute them in sequence
            for sub_action in action_group.actions:
                sub_action_successful = await self._process_node(agent, sub_action)

                # If a sub_action was unsuccessful, discard the rest of the group
                if not sub_action_successful:
                    return False
                
            # Check if the repeat until condition has been met for this action
            if self._evaluate_condition(agent, action_group.until):
                break

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
            
            case ControlOperator.REPEAT:
                while True:
                    # Check for abort
                    if agent.abort_actions:
                        return False
                        
                    result = await self._process_node(agent, control_node.control_node)

                    # Break out if the sub node has failed
                    if not result:
                        return result

                    # Check if the repeat until condition has been met for this action
                    if self._evaluate_condition(agent, control_node.until):
                        break

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

            condition_met = False
            match expression.condition:
                case ActionCondition.FOREVER:
                    # Forever meaning the condition will never be met, therefore FALSE.
                    condition_met = False
                
                case ActionCondition.INVENTORY_FULL:
                    condition_met = agent.inventory_full()
                
                case ActionCondition.INVENTORY_EMPTY:
                    condition_met = agent.inventory_empty()

                case ActionCondition.INVENTORY_HAS_AVAILABLE_SPACE:
                    free_spaces = expression.parameters["spaces"]
                    condition_met = agent.inventory_has_available_space(free_spaces)

                case ActionCondition.INVENTORY_HAS_AVAILABLE_SPACE_FOR_ITEMS:
                    items = expression.parameters["items"]
                    needed_space = 0
                    for item in items:
                        needed_quantity = item["quantity"]
                        current_quantity = agent.get_quantity_of_item_in_inventory(item["code"])
                        needed_space += needed_quantity - current_quantity

                    condition_met = agent.inventory_has_available_space(needed_space)
                
                case ActionCondition.INVENTORY_HAS_ITEM_OF_QUANTITY:
                    item = expression.parameters["item"]
                    quantity = expression.parameters["quantity"]
                    condition_met = agent.inventory_has_item_of_quantity(item, quantity)
                
                case ActionCondition.BANK_HAS_ITEM_OF_QUANTITY:
                    item = expression.parameters["item"]
                    quantity = expression.parameters["quantity"]
                    condition_met = agent.bank_has_item_of_quantity(item, quantity)

                case ActionCondition.BANK_AND_INVENTORY_HAVE_ITEM_OF_QUANTITY:
                    item = expression.parameters["item"]
                    quantity = expression.parameters["quantity"]
                    condition_met = agent.bank_and_inventory_have_item_of_quantity(item, quantity)

                case ActionCondition.ITEMS_IN_LAST_WITHDRAW_CONTEXT:
                    condition_met = agent.items_in_last_withdraw_context()

                case ActionCondition.HAS_TASK:
                    condition_met = agent.has_task()

                case ActionCondition.HAS_TASK_OF_TYPE:
                    task_type = expression.parameters["type"]
                    condition_met = agent.char_data["task_type"] == task_type

                case ActionCondition.TASK_COMPLETE:
                    condition_met = agent.char_data["task_total"] == agent.char_data["task_progress"]

                case ActionCondition.HAS_SKILL_LEVEL:
                    skill = expression.parameters["skill"]
                    level = expression.parameters["level"]
                    condition_met = agent.has_skill_level(skill, level)

                case _:
                    raise NotImplementedError()
                
            if condition_met:
                self.logger.debug(f"[{agent.name}] Passed {expression.condition} with parameters {expression.parameters}.")
            else:
                # Exception case where a 'failure' is due to a FOREVER condition
                if expression.condition != ActionCondition.FOREVER:
                    self.logger.debug(f"[{agent.name}] Failed {expression.condition} with parameters {expression.parameters}.")

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