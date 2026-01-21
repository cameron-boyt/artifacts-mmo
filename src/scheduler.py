import asyncio
import datetime
import time
from collections import deque
from action import Action, ActionGroup, ActionCondition, ActionConditionExpression, LogicalOperator, ActionControlNode
from character import CharacterAgent
from api import APIClient
import logging
from typing import Any, Dict

class ActionScheduler:
    """Manages action queues and worker tasks for all characters."""
    def __init__(self, api_client: APIClient):
        self.logger = logging.getLogger(__name__)

        self.api_client = api_client
        self.agents: dict[str, CharacterAgent] = {}
        self.queues: dict[str, deque[Action | ActionGroup]] = {}
        self.worker_tasks: dict[str, asyncio.Task] = {}


    def get_status(self):
        print(self.queues)


    def add_character(self, character_data: Dict[str, Any], bank_data: Dict[str, Any], map_data: Dict[str, Any]):
        """Add a new charcter to be handled by the scheduler."""
        name = character_data["name"]
        if name in self.agents: 
            return
        
        self.logger.info(f"Adding character: {name}")
        agent = CharacterAgent(character_data, bank_data, map_data, self.api_client, self)
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

            # Pop the next action and process
            node = queue.popleft()
            await self._process_action(agent, node)
            self.logger.info(f"[{character_name}] Finished queued node.")

    async def _process_action(self, agent: CharacterAgent, node: Action | ActionGroup | ActionControlNode) -> bool:
        # If the node is a control node, derive the correct branch to take

        ##TODO:
        # REPEAT CONTROL BRANCH
        
        if isinstance(node, ActionControlNode):
            action = self._evaluate_control_branches(agent, node)
        else:
            action = node

        while True:
            if isinstance(action, Action):
                # Wait for the remaining cooldown for the worker
                remaining_cooldown = max(0, agent.cooldown_expires_at - time.time())
                if remaining_cooldown > 0:
                    self.logger.debug(f"[{agent.name}] Waiting for cooldown: {round(remaining_cooldown)}s.")
                    await asyncio.sleep(remaining_cooldown)
                                        
                # Execute the action
                new_cooldown = await agent.perform(action)

                # Action failed if cooldown is negative
                if new_cooldown < 0:
                    self.logger.warning(f"Action {action.type} failed for {agent.name}.")
                    return False

                agent.cooldown_expires_at = time.time() + new_cooldown
            elif isinstance(action, ActionGroup):
                # Traverse through the grouped actions and execute them in sequence
                for sub_action in action.actions:
                    sub_action_succesful = await self._process_action(agent, sub_action)

                    # If a sub_action was unsuccessful, discard the rest of the group
                    if not sub_action_succesful:
                        return False

            # Check if a repeat condition has been defined for this action
            if not action.until:
                break
            
            # If so, try evaluate
            if self._evaluate_condition(agent, action.until):
                break

        return True


    def _evaluate_control_branches(self, agent: CharacterAgent, control_node: ActionControlNode) -> Action | ActionGroup:
        for branch in control_node.branches:
            if self._evaluate_condition(agent, branch[0]):
                return branch[1]
            
        return control_node.fail_path


    def _evaluate_condition(self, agent: CharacterAgent, expression: ActionConditionExpression) -> bool:
        """Evaluate a condition expression path."""        
        if expression.is_leaf():
            # If at a leaf node, evaluate the condition
            self.logger.debug(f"[{agent.name}] Evaluating condition {expression.condition}")

            condition_met = False
            match expression.condition:
                case ActionCondition.FOREVER:
                    condition_met =  True
                
                case ActionCondition.INVENTORY_FULL:
                    condition_met = agent.is_inventory_full()
                
                case ActionCondition.BANK_HAS_ITEM_OF_QUANTITY:
                    item_code = expression.parameters.get("item_code", "")
                    quantity = expression.parameters.get("quantity", 0)
                    condition_met = agent.bank_has_item_of_quantity(item_code, quantity)

                case _:
                    raise NotImplementedError()
                
            if condition_met:
                self.logger.debug(f"[{agent.name}] Successfully met condition.")
            else:
                self.logger.debug(f"[{agent.name}] Failed to meet condition.")

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