from __future__ import annotations

import logging
import uuid
import re
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Any
from math import floor, ceil
from itertools import product
from datetime import datetime
from src.action import *
from src.helpers import *

type LocationSet = Set[Tuple[int, int]]
type DataMapping = Dict[str, Set[str]]

@dataclass
class WorldInteractions:
    resources: Dict[str, LocationSet]
    monsters: Dict[str, LocationSet]
    workshops: Dict[str, LocationSet]
    banks: Dict[str, LocationSet]
    grand_exchanges: Dict[str, LocationSet]
    tasks_masters: Dict[str, LocationSet]
    npcs: Dict[str, LocationSet]

class WorldState:
    def __init__(self, bank_data: Dict, map_data: Dict, item_data: Dict, resource_data: Dict, monster_data: Dict):
        self.logger = logging.getLogger(__name__)

        self._bank_data: Dict[str, int] = {b["code"]: b["quantity"] for b in bank_data}
        self._map_data = map_data
        self._item_data: Dict[str, Dict] = {i["code"]: i for i in item_data}
        self._resource_data = resource_data
        self._monster_data = {m["code"]: m for m in monster_data}

        self._interactions: WorldInteractions = None
        self._resource_to_tile = {}
        self._tile_to_resource = {}
        self._drop_sources = {}
        self._item_stat_vectors = {}

        self.bank_reservations = {}

        self.__post_init__()

    def __post_init__(self):
        self._interactions = self._generate_interactions()
        self._resource_to_tile, self._tile_to_resource = self._generate_resource_sources()
        self._drop_sources = self._generate_monster_drop_sources()
        self._item_stat_vectors = self._generate_item_stat_vectors()

    ## Post-Init Generation
    def _generate_interactions(self) -> WorldInteractions:
        interactions = {}

        for map_tile in self._map_data:
            content_data = map_tile.get("interactions", {}).get("content", None)

            if content_data:
                content_type = content_data["type"]
                content_code = content_data["code"]
                x, y = map_tile["x"], map_tile["y"]
                interactions.setdefault(content_type, {}).setdefault(content_code, set()).add((x, y))

        return WorldInteractions(
            interactions["resource"],
            interactions["monster"],
            interactions["workshop"],
            interactions["bank"]["bank"],
            interactions["grand_exchange"],
            interactions["tasks_master"],
            interactions["npc"]
        )

    def _generate_resource_sources(self) -> Tuple[DataMapping, DataMapping]:
        resource_to_tile = {}
        tile_to_resource = {}
        for resource in self._resource_data:
            for drop in resource["drops"]:
                resource_to_tile.setdefault(drop["code"], set()).add(resource["code"])
                tile_to_resource.setdefault(resource["code"], set()).add(drop["code"])

        return resource_to_tile, tile_to_resource
    
    def _generate_monster_drop_sources(self) -> DataMapping:
        monster_sources = {}
        for monster, data in self._monster_data.items():
            for drop in data["drops"]:
                monster_sources.setdefault(drop["code"], set()).add(monster)

        return monster_sources 
    
    def _generate_item_stat_vectors(self) -> DataMapping:
        item_stat_vectors = {}
        
        for item, data in self._item_data.items():
            check_item = False

            if self.is_weapon(item):
                check_item = True
                relevant_stats = WEAPON_EFFECT_CODES
            elif self.is_armour(item):
                check_item = True
                relevant_stats = ARMOUR_EFFECT_CODES

            if check_item:
                stats = { "code": item }
                for stat in relevant_stats:
                    matching_stats = [effect for effect in data["effects"] if effect["code"] == stat]
                    if len(matching_stats) == 1:
                        stats[stat] = matching_stats[0]["value"]
                    else:
                        stats[stat] = 0

                item_stat_vectors[item] = stats

        return item_stat_vectors
    
    # Bank Stuff
    def get_bank_items(self) -> Dict[str, int]:
        return self._bank_data
    
    # Item Checkers
    def is_an_item(self, item: str) -> bool:
        return item in self._item_data
            
    def get_item_info(self, item: str) -> Dict:
        if not self.is_an_item(item):
            raise KeyError(f"{item} is not an item.")
        
        return self._item_data[item]
    
    def item_is_craftable(self, item: str) -> bool:
        if not self.is_an_item(item):
            raise KeyError(f"{item} is not an item.")
        
        return self._item_data[item].get("craft") is not None
    
    def item_from_fighting(self, item: str) -> bool:
        return item in self._drop_sources
    
    def item_from_gathering(self, item: str) -> bool:
        return item in self._resource_to_tile
    
    def item_from_crafting(self, item: str) -> bool:
        return self.item_is_craftable(item)
    
    def get_crafting_materials_for_item(self, item: str) -> List[Dict[str, Any]] | None:
        if not self.item_is_craftable(item):
            raise KeyError(f"{item} is not craftable.")
        
        materials = self._item_data[item]["craft"]["items"]
        return [{"code": m["code"], "quantity": m["quantity"]} for m in materials]
    
    def get_workshop_for_item(self, item: str) -> str:
        if not self.item_is_craftable(item):
            raise KeyError(f"{item} is not craftable.")
        
        return self._item_data[item]["craft"]["skill"]
    
    def get_workshop_locations(self, skill: str) -> LocationSet:
        if skill in self._interactions.workshops:
            return self._interactions.workshops[skill]
        
        raise KeyError(f"{skill} is not a skill.")
    
    def character_meets_item_conditions(self, character: dict, conditions: list) -> bool:
        for condition in conditions:
            match condition["code"]:
                case "level" | "mining_level" | "woodcutting_level" | "fishing_level" | "weaponcrafting_level" | \
                     "gearcrafting_level" | "jewelrycrafting_level" | "cooking_level" | "alchemy_level":
                    compare_value = character[condition["code"]]
                    
                case _:
                    raise Exception(f"Unknown condition code: {condition['code']}.")
            
            match condition["operator"]:
                case "gt":
                    condition_met = compare_value > condition["value"]

                case "eq":
                    condition_met = compare_value == condition["value"]

                case "lt":
                    condition_met = compare_value < condition["value"]
                    
                case _:
                    raise Exception(f"Unknown condition operator: {condition['operator']}.")
                
            if not condition_met:
                return False
            
        return True
    
    def character_meets_crafting_conditions(self, character: dict, item: str) -> bool:
        item_info = self.get_item_info(item)
        if self.item_is_craftable(item):
            craft_skill = item_info.get("craft").get("skill")
            craft_level = item_info.get("craft").get("level")
            return character.get(f"{craft_skill}_level") >= craft_level
        else:
            raise Exception(f"Item {item} is not craftable")

    
    # Equipment Checkers
    def is_equipment(self, item: str) -> bool:
        return self.is_an_item(item) and not self.get_item_info(item)["type"] == "resource"
    
    def get_equip_slot_for_item(self, item: str) -> str:
        if not self.is_equipment(item):
            raise KeyError(f"{item} is not equipment.")
        
        return self._item_data[item]["type"]
    
    def is_tool(self, item: str) -> bool:
        return self.is_an_item(item) and self._item_data[item]["subtype"] == "tool"
        
    def is_weapon(self, item: str) -> bool:
        return self.is_an_item(item) and self._item_data[item]["type"] == "weapon"
        
    def is_armour(self, item: str) -> bool:
        return self.is_an_item(item) and self._item_data[item]["type"] in ARMOUR_SLOTS
    
    def prepare_best_loadout_for_task(self, character: Dict[str, Any], task: str, target: str) -> Tuple[Dict[str, int], List[Dict[str, str]]]:
        loadout = self.get_best_loadout_for_task(character, task, target)

        final_loadout = []
        equip_queue = []

        for item in loadout:
            # If the item is already equipped, skip.
            # Only actual equipment slots are called *_slot, so the broad check is ok.
            if any([equipped == item for slot, equipped in character.items() if re.search(r'_slot$', slot)]):
                continue

            final_loadout.append({ "code": item, "quantity": 1 })

            # Prepare the equip queue
            item_slot = self.get_equip_slot_for_item(item)
            equip_queue.append({ "code": item, "slot": item_slot })

        # For fighting tasks, also withdraw some food
        if task == "fighting":
            best_food = self.get_best_food_for_character_in_bank(character)
            if best_food:
                food_amount = self.get_amount_of_item_in_bank(best_food)
                final_loadout.append({ "code": best_food, "quantity": min(50, food_amount) })

        return final_loadout, equip_queue
    
    def get_best_loadout_for_task(self, character: dict, task: str, target: str) -> List[str]:
        if task == "fighting":
            relevant_weapon_stats = ["attack_air", "attack_water", "attack_earth", "attack_fire", "critical_strike"]
            relevant_armour_stats = [
                "hp", "res_air", "res_water", "res_earth", "res_fire",
                "dmg", "dmg_air", "dmg_water", "dmg_earth", "dmg_fire", "critical_strike",
                "initiative", "haste", "wisdom", "prospecting"
            ]
            evaluation_function = self._evaluate_loadout_for_fighting
        elif task == "gathering":
            skill = self.get_gather_skill_for_resource(target)
            relevant_weapon_stats = [skill]
            relevant_armour_stats = ["wisdom", "prospecting"]
            evaluation_function = self._evaluate_loadout_for_gathering
        else:
            raise Exception(f"Unknown loadout task type: {task}.")

        loadouts = self._generate_equipment_loadouts(character, relevant_weapon_stats, relevant_armour_stats)
        dummy_char = self._generate_dummy_char(character)

        # For each loadout, apply the stats and then simulate a fight.
        loadout_ratings = {}
        for i, loadout in enumerate(loadouts):
            geared_char = self._generate_geared_char(dummy_char, loadout)

            # Simulate fight and rate the loadout:
            loadout_ratings[i] = evaluation_function(geared_char, target)

        # Sort loadouts
        sorted_loadouts = sorted(loadout_ratings.items(), key=lambda i: i[1], reverse=True)
        best_loadout = loadouts[sorted_loadouts[0][0]]

        # Convert the loadout into a listof items
        gear_list = [item["code"] for item in best_loadout if item is not None]
        return gear_list
        
    def _generate_dummy_char(self, character: dict) -> dict:
        """Create a dummy character from the provided character stats as if it had nothing equipped."""
        dummy_char = dict(character)

        # Reset stats, there is no other source to these stats other than this equipment, so this assumption is safe
        for stat in ALL_EFFECT_CODES:
            dummy_char[stat] = 0

        # Rewind hp
        dummy_char["max_hp"] = 120 + (dummy_char["level"] - 1) * 5

        # Remove active effects (we'll actually be treating these as normal stats instead for ease of computation)
        dummy_char["effects"] = []

        return dummy_char
    
    def _generate_geared_char(self, character: dict, loadout: dict) -> dict:
        """Given a loadout of gear, apply their stats to a char and generate a geared mock."""
        geared_char = dict(character)
        for item in loadout:
            if item is None:
                continue

            for stat, value in item.items():
                if stat == "code":
                    continue

                # max_hp additions are called "hp"
                if stat == "hp":
                    geared_char["max_hp"] += value
                else:
                    geared_char[stat] += value

        # Set hp to max
        geared_char["hp"] = geared_char["max_hp"]
        return geared_char
    
    def _generate_equipment_loadouts(self, character: Dict, relevant_weapon_stats: List[str], relevant_armour_stats: List[str]) -> List[Dict]:
        equipment = {
            "weapon": [],
            "helmet": [],
            "shield": [],
            "body_armor": [],
            "leg_armor": [],
            "boots": [],
            "amulet": [],
            "ring": []
        }

        # Take into account items already equipped
        items_to_check = set()
        for slot_key in [key for key in character.keys() if re.search(r'_slot$', key)]:
            if character[slot_key] != "":
                items_to_check.add(character[slot_key])

        # Also check items within the inventory
        for item in character["inventory"]:
            if item["code"] != "":
                items_to_check.add(item["code"])

        # Review available items in bank
        for item in self._bank_data:
            items_to_check.add(item)

        # Determine which items can be equipped and have relevant stats for consideration
        for item in items_to_check:
            item_data = self._item_data[item]

            if not self.character_meets_item_conditions(character, item_data["conditions"]):
                continue

            if self.is_weapon(item):
                weapon_stats = self._item_stat_vectors[item]
                has_relevant_stats = any(weapon_stats[stat] != 0 for stat in relevant_weapon_stats)
                if has_relevant_stats:
                    equipment["weapon"].append(self._item_stat_vectors[item])

            if self.is_armour(item):
                armour_stats = self._item_stat_vectors[item]
                has_relevant_stats = any(armour_stats[stat] != 0 for stat in relevant_armour_stats)

                if has_relevant_stats:
                    equip_slot = self.get_equip_slot_for_item(item)
                    equipment[equip_slot].append(armour_stats)

        # Prune equipment sets
        # for slot, items in equipment.items():
        #     print(slot, item)

        # Prepare equipment lists for cartesean product generation
        slot_item_lists = [(items if items else [None]) for items in equipment.values()]

        # Add another set of rings since we can equip two of them!
        slot_item_lists.append([*equipment["ring"], None] if equipment["ring"] else [None])

        # Create all equipment combinations
        loadouts = list(product(*slot_item_lists))

        # Check we have enough equipment quantity for both rings (lists 7 and 8)
        valid_loadouts = []

        for loadout in loadouts:
            if (
                loadout[7] and loadout[8] and
                loadout[7]["code"] == loadout[8]["code"]
            ):
                item = loadout[7]["code"]
                bank_amt = self.get_amount_of_item_in_bank(item)
                inv_amt = sum(i["quantity"] for i in character["inventory"] if i["code"] == item)
                equip_amt = 1 if (character["ring1_slot"] == item or character["ring2_slot"] == item) else 0

                if bank_amt + inv_amt + equip_amt < 2:
                    continue
                
            valid_loadouts.append(loadout)

        return valid_loadouts
    
    def _evaluate_loadout_for_gathering(self, character: dict, resource: str) -> Tuple[int]:
        skill = self.get_gather_skill_for_resource(resource)

        skill_cooldown_reduction = character[skill]
        droprate_bonus = character["prospecting"]
        xp_bonus = character["wisdom"]

        return -skill_cooldown_reduction, droprate_bonus, xp_bonus
    
    def is_food(self, item: str) -> bool:
        # Forbid eating apples :)
        return self.is_an_item(item) and self._item_data[item]["subtype"] == "food" and item != "apple"
    
    def get_best_food_for_character_in_bank(self, character: dict) -> str | None:
        foods = [
            item for item in self._bank_data 
            if self.is_food(item)
            and self.character_meets_item_conditions(character, self._item_data[item]["conditions"])
        ]

        if len(foods) > 0:
            food_power = []
            for food in foods:
                heal_power = self.get_heal_power_of_food(food)
                food_power.append((food, heal_power))

            # Preference for food: heal <= max_hp sort in descending order, then, heal > max_hp in ascending order.
            best_food = max(food_power, key=lambda f: f[1] if f[1] <= character["max_hp"] else -1 * f[1])
            return best_food[0]
        else:
            return None
        
    def get_heal_power_of_food(self, food: str) -> int:
        if not self.is_food(food):
            raise KeyError(f"{food} is not equipment.")
        
        food_data = self.get_item_info(food)

        # There should always be a heal effect, so this is safe
        heal_amount = [effect for effect in food_data["effects"] if effect["code"] == "heal"][0]["value"]
        return heal_amount
    
    # Resource Checkers
    def is_a_resource(self, resource: str) -> bool:
        return self.is_an_item(resource) and self.get_item_info(resource)["type"] == "resource"
    
    def get_resource_at_location(self, x: int, y: int) -> str | None:
        for tile, locations in self._interactions.resources.items():
            if (x, y) in locations:
                return self._tile_to_resource[tile]
    
    def get_locations_of_resource(self, resource: str) -> LocationSet:
        if not self.is_a_resource(resource):
            raise KeyError(f"{resource} is not a resource.")
        
        if not resource in self._resource_to_tile:
            return []
        
        resource_tile = self._resource_to_tile[resource]

        locations = set()
        for tile in resource_tile:
            locations.update(self._interactions.resources[tile])

        return locations
    
    def get_gather_skill_for_resource(self, resource: str) -> str:
        if not self.is_a_resource(resource):
            raise KeyError(f"{resource} is not a resource.")
        
        return self.get_item_info(resource)["subtype"]
    
    # Monster Checkers
    def is_a_monster(self, monster: str) -> bool:
        return monster in self._interactions.monsters
            
    def get_monster_info(self, monster: str) -> Dict:
        if not self.is_a_monster(monster):
            raise KeyError(f"{monster} is not a monster.")
        
        return self._monster_data[monster]
    
    def get_monster_at_location(self, x: int, y: int) -> str | None:
        for monster, locations in self._interactions.monsters.items():
            if (x, y) in locations:
                return monster

    def get_locations_of_monster(self, monster: str) -> LocationSet:
        if not self.is_a_monster(monster):
            raise KeyError(f"{monster} is not a monster.")
        
        locations = self._interactions.monsters[monster]
        return locations
    
    def get_monster_for_item(self, resource: str) -> str:
        sources = self._drop_sources[resource]

        if len(sources) == 1:
            return sources[0]
        else:
            # Eventually implement some logic to determine the best sources
            # Calculate kills times / drop rate etc.
            return sources[0]

    def _evaluate_loadout_for_fighting(self, character: dict, monster: str) -> Tuple[bool, int, int]:
        if not self.is_a_monster(monster):
            raise KeyError(f"{monster} is not a monster.")
        
        monster_data = self.get_monster_info(monster)

        damage_dealt, damage_taken = self.calculate_damage_against_character_and_monster(character, monster_data)
        turns_to_kill = ceil(monster_data["hp"] / damage_dealt)

        # If the monster goes first, the character gets hits one additional time
        monster_first = character.get("initiative", 0) < monster_data.get("initiative", 0) 
        if monster_first:
            turns_to_kill += 1

        char_damage_taken = turns_to_kill * damage_taken
        fight_win = char_damage_taken < character["hp"]

        return fight_win, -turns_to_kill, -char_damage_taken

    def calculate_damage_against_character_and_monster(self, character: dict, monster: dict) -> Tuple[int, int]:
        # critical_strike is an int between 0-100.
        crit_dmg_mult = 1.5

        character_damage = round((
            round((character["attack_air"] * (1 + character["dmg_air"] / 100)) / (1 + monster["res_air"] / 100)) + 
            round((character["attack_water"] * (1 + character["dmg_water"] / 100)) / (1 + monster["res_water"] / 100)) + 
            round((character["attack_earth"] * (1 + character["dmg_earth"] / 100)) / (1 + monster["res_earth"] / 100)) + 
            round((character["attack_fire"] * (1 + character["dmg_fire"] / 100)) / (1 + monster["res_fire"] / 100))
        ) * (1 + character["dmg"] / 100) * (1 + ((character["critical_strike"] / 100) * (crit_dmg_mult - 1))))

        monster_damage = round((
            round(monster["attack_air"] / (1 + character["res_air"] / 100)) + 
            round(monster["attack_water"] / (1 + character["res_water"] / 100)) + 
            round(monster["attack_earth"] / (1 + character["res_earth"] / 100)) + 
            round(monster["attack_fire"]  / (1 + character["res_fire"] / 100))
        ) * (1 + ((monster["critical_strike"] / 100) * (crit_dmg_mult - 1))))

        return character_damage, monster_damage
    
    # Bank Checkers
    def get_bank_locations(self) -> LocationSet:
        return self._interactions.banks

    def get_amount_of_item_in_bank(self, item: str) -> int:
        if item in self._bank_data:
            amount_in_bank = self._bank_data[item]
            amount_reserved = self.get_amount_of_item_reserved_in_bank(item)
            return amount_in_bank - amount_reserved
        else:
            return 0
    
    def update_bank_data(self, bank_data: List[Dict[str, Any]]):
        self._bank_data = {}
        for item in bank_data:
            self._bank_data[item["code"]] = item["quantity"]
        
    def set_bank_reservation(self, character: str, item: str, quantity: int):
        self.bank_reservations.setdefault(character, {})[item] = { 
            "quantity": quantity,
            "reserved_at": datetime.now()
        }

    def update_bank_reservation(self, character: str, item: str, qty_delta: int):
        char_reservations = self.bank_reservations.get(character, {})
        item_reservation = char_reservations.get(item, {})

        if not item_reservation:
            raise Exception(f"Could not find reservation of {item} for {character}") 
        
        item_reservation["quantity"] += qty_delta

        if item_reservation["quantity"] == 0:
            del self.bank_reservations[character][item]

    def clear_bank_reservation(self, character, item: str | None = None):
        if char_reservations := self.bank_reservations.get(character, {}):
            if not item:
                del self.bank_reservations[character]
            elif item in char_reservations:
                del self.bank_reservations[character][item]
            else:
                raise Exception(f"Could not find reservation of {item} for {character}") 
        
    def get_amount_of_item_reserved_in_bank(self, item: str) -> int:
        amount_reserved = 0
        for character, reservations in self.bank_reservations.items():
            for r_item, r_info in reservations.items():
                amount_reserved += r_info["quantity"] if r_item == item else 0

        return amount_reserved
    
    # Other Checkers
    def get_task_master_locations(self) -> LocationSet:
        return self._interactions.tasks_masters

   ## Action Performance
    async def perform(self, action: Action) -> Tuple[Dict[str, Any] | None, ActionOutcome]:
        match action.type:
            case MetaAction.CREATE_ITEM_RESERVATION:
                name = action.params.get("name")
                items = action.params.get("items")

                for item in items:
                    self.set_bank_reservation(name, item["code"], item["quantity"])

                return None, ActionOutcome.SUCCESS

            case MetaAction.UPDATE_ITEM_RESERVATION:
                name = action.params.get("name")
                items = action.params.get("items")

                for item in items:
                    self.update_bank_reservation(name, item["code"], item["quantity"])

                return None, ActionOutcome.SUCCESS

            case MetaAction.CLEAR_ITEM_RESERVATION:
                name = action.params.get("name")
                items = action.params.get("items")

                for item in items:
                    self.clear_bank_reservation(name, item)

                return None, ActionOutcome.SUCCESS
            
            case MetaAction.PREPARE_LOADOUT:
                character = action.params.get("character")
                task = action.params.get("task")
                target = action.params.get("target")

                loadout, equip_queue = self.prepare_best_loadout_for_task(character, task, target)
                context_update = {
                    "prepared_loadout": loadout,
                    "equip_queue": equip_queue
                }

                return context_update, ActionOutcome.SUCCESS
            
            case MetaAction.CLEAR_PREPARED_LOADOUT:
                context_update = { "prepared_loadout": [] }
                return context_update, ActionOutcome.SUCCESS

            case MetaAction.RESET_CONTEXT_COUNTER:
                counter_name = action.params.get("name")
                context_update = { counter_name: 0 }
                return context_update, ActionOutcome.SUCCESS
            
            case MetaAction.INCREMENT_CONTEXT_COUNTER:
                counter_name = action.params.get("name")
                counter_value = action.params.get("value", 0)
                counter_value_keys = action.params.get("value_keys", [])
                
                if counter_value_keys:
                    context_update = { counter_name: counter_value_keys }
                else:
                    context_update = { counter_name: counter_value }

                return context_update, ActionOutcome.SUCCESS
            
            case MetaAction.CLEAR_CONTEXT_COUNTER:
                counter_name = action.params.get("name")
                context_update = { counter_name: None }
                return context_update, ActionOutcome.SUCCESS
            
            case MetaAction.FAIL_OUT:
                return None, ActionOutcome.FAIL

            case _:
                raise Exception(f"[World] Unknown action type: {action.type}")
            