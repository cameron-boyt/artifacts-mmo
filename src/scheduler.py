import asyncio
import datetime
import time
from collections import deque
from action import Action, ActionGroup, ActionCondition
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

    def add_character(self, data: Dict[str, Any]):
        name = data["name"]
        if name in self.agents: 
            return
        
        self.logger.info(f"Adding character: {name}")
        agent = CharacterAgent(data, self.api_client, self)
        self.agents[name] = agent
        self.queues[name] = deque()
        self.worker_tasks[name] = asyncio.create_task(self._worker(name))

    def queue_action(self, character_name: str, action: Action | ActionGroup):
        if character_name in self.queues:
            if isinstance(action, Action):
                self.logger.info(f"Action '{action.type}' queued for {character_name}.")
            elif isinstance(action, ActionGroup):
                self.logger.info(f"Action Group '???' queued for {character_name}.")

            self.queues[character_name].append(action)
    

    async def _worker(self, character_name: str):
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
            action = queue.popleft()
            await self._process_action(agent, action)
            self.logger.info(f"Finished queued action grouping for {character_name}.")


    async def _process_action(self, agent: CharacterAgent, action: Action | ActionGroup) -> bool:
        while True:
            if isinstance(action, Action):
                # Wait for the remaining cooldown for the worker
                remaining_cooldown = agent.cooldown_expires_at - time.time()
                if remaining_cooldown > 0:
                    await asyncio.sleep(remaining_cooldown)
                                        
                # Execute the action
                new_cooldown = await agent.perform(action)

                if new_cooldown == 0.0:
                    # Action failed if cooldown is zero
                    self.logger.warning(f"Action {action.type} failed for {agent.name}.")
                    return False

                agent.cooldown_expires_at = time.time() + new_cooldown
            elif isinstance(action, ActionGroup):
                for sub_action in action.actions:
                    sub_action_succesful = await self._process_action(agent, sub_action)
                    if not sub_action_succesful:
                        return False

            if (
                not action.repeat or
                action.repeat and agent.repeat_condition_met(action.repeat_until)
            ):
                break

        return True