from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Any, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum, auto
import json
import re

from src.worldstate import WorldState
from src.planner import ActionPlanner, ActionIntent, Intention

if TYPE_CHECKING:
    from src.character import CharacterAgent
    from src.scheduler import ActionScheduler

@dataclass
class ProgressionGoal():
    item: str
    quantity: int
    goal_met_flag: bool = False

@dataclass
class PantryGoal():
    item: str
    desired_quantity: int
    replenish_threshold: int
    use_replenish_threshold: bool = False

@dataclass
class CharacterTracker():
    character: str
    inventory: Dict[str, int] = field(default_factory=dict)

    def get_quantity_of_item(self, item: str):
        return self.inventory.get(item, 0)
    
    def update_inventory(self, inventory: Dict[str, int]):
        self.inventory = inventory

class GoalCoordinator():
    def __init__(self, world_state: WorldState, planner: ActionPlanner, scheduler: ActionScheduler):
        self.world_state = world_state
        self.planner = planner
        self.scheduler = scheduler

        self._tracked_characters: List[CharacterTracker] = []

        self._progression_goals: List[ProgressionGoal] = []
        self._pantry_goals: List[PantryGoal] = []
        
        self.__post_init__()

    def __post_init__(self):
        self._progression_goals, self._pantry_goals = self._load_goals("data/shopping_list.json")

    def _load_goals(self, goal_file) -> Tuple[List[ProgressionGoal], List[PantryGoal]]:
        with open(goal_file, 'r') as f:
            goals = json.loads(f.read())
        
        progression_goals = []
        for goal in goals.get("progression"):
            progression_goals.append(ProgressionGoal(
                goal["code"],
                goal["quantity"]
            ))
        
        pantry_goals = []
        for goal in goals.get("pantry"):
            pantry_goals.append(PantryGoal(
                goal["code"],
                goal["desired_quantity"],
                goal["replenish_threshold"]
            ))

        return progression_goals, pantry_goals

    def _get_amount_of_item_in_world(self, item: str) -> int:
        amount_in_bank = self.world_state.get_amount_of_item_in_bank(item)
        amount_in_inventories = 0
        for t in self._tracked_characters:
            amount_in_inventories += sum(v for (i, v) in t.inventory.items() if i == item)

        return amount_in_bank + amount_in_inventories
    
    def check_in_character(self, character: dict):
        # Get Tracker
        trackers = [tracker for tracker in self._tracked_characters if tracker.character == character["name"]]
        if not trackers:
            character_tracker = CharacterTracker(character["name"])
            self._tracked_characters.append(character_tracker)#
        else:
            character_tracker = trackers[0]

        # Extract items in inventory
        inventory = {}
        for item in character["inventory"]:
            if item["code"] != "":
                inventory[item["code"]] = item["quantity"] 

        # Extract equipped items
        for slot in [slot for slot in character.keys() if re.search(r'_slot$', slot)]:
            equipped_item = character[slot]
            if equipped_item == "":
                continue

            if equipped_item in inventory:
                inventory[equipped_item] += 1
            else:
                inventory[equipped_item] = 1

        # Update Tracker
        character_tracker.update_inventory(inventory)
    
    def get_next_goal(self, character: dict, goal_type: str):
        if goal_type == "progression":
            self._get_next_progression_goal(character, primary_worker=True)
        elif goal_type == "pantry":
            self._get_next_pantry_goal(character)
        else:
            raise Exception(f"Unknown goal type: {goal_type}")
        
    def _get_next_progression_goal(self, character: dict, primary_worker: bool = False):
        for goal in self._progression_goals:
            if self._get_amount_of_item_in_world(goal.item) >= goal.quantity:
                continue

            # Check the agent meets the conditions to attempt this goal
            if self.world_state.character_meets_crafting_conditions(character, goal.item):
                current_quantity = self._get_amount_of_item_in_world(goal.item)

                if primary_worker:
                    node = self.planner.plan(ActionIntent(Intention.CRAFT_OR_GATHER_INTERMEDIARIES, item=goal.item, quantity=goal.quantity - current_quantity, gather_intermediaries=True))
                else:
                    node = self.planner.plan(ActionIntent(Intention.GATHER_MATERIALS_FOR_CRAFT, item=goal.item, quantity=goal.quantity - current_quantity))
                self.scheduler.queue_action_node(character["name"], node)
                return
            else:
                break

        # No valid goals are left in the queue, should use this time to progress levels for the next items
        self._get_next_backup_goal(character)

    def _get_next_pantry_goal(self, character: dict):
        for goal in self._pantry_goals:
            if self._get_amount_of_item_in_world(goal.item) >= goal.desired_quantity:
                goal.use_replenish_threshold = True
                continue
            elif goal.use_replenish_threshold and self._get_amount_of_item_in_world(goal.item) >= goal.replenish_threshold:
                continue

            goal.use_replenish_threshold = False

            current_quantity = self._get_amount_of_item_in_world(goal.item)
            node = self.planner.plan(ActionIntent(Intention.CRAFT_OR_GATHER_INTERMEDIARIES, item=goal.item, quantity=goal.desired_quantity - current_quantity, gather_intermediaries=True))
            self.scheduler.queue_action_node(character["name"], node)
            return
        
        # No goals are left in the queue, should start offering help to the progression items as a support
        self._get_next_progression_goal(character, primary_worker=False)
        
    def _get_next_backup_goal(self, character: dict):
        node = self.planner.plan(ActionIntent(Intention.GATHER_RESOURCES, resource="copper_ore"))
        self.scheduler.queue_action_node(character["name"], node)
