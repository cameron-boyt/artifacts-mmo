from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Any
from math import floor, ceil

from src.helpers import *

type LocationSet = Set[Tuple[int, int]]

@dataclass
class WorldInteractions:
    resources: Dict[str, LocationSet]
    monsters: Dict[str, LocationSet]
    workshops: Dict[str, LocationSet]
    banks: Dict[str, LocationSet]
    grand_exchanges: Dict[str, LocationSet]
    tasks_masters: Dict[str, LocationSet]
    npcs: Dict[str, LocationSet]

@dataclass
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

        self.bank_reservations = {}

        self.__post_init__()

    def __post_init__(self):
        self._interactions = self._generate_interations()
        self._resource_to_tile, self._tile_to_resource = self._generate_resource_sources()
        self._drop_sources = self._generate_monster_drop_sources()

    ## Post-Init Generation
    def _generate_interations(self):
        interactions = {}

        for map_tile in self._map_data:
            content_data = map_tile.get("interactions", {}).get("content", None)

            if content_data:
                content_type = content_data["type"]
                content_code = content_data["code"]
                x, y = map_tile["x"], map_tile["y"]
                interactions.setdefault(content_type, {}).setdefault(content_code, set()).add((x, y))

        return WorldInteractions(
            interactions.get("resource", {}),
            interactions.get("monster", {}),
            interactions.get("workshop", {}),
            interactions.get("bank", {}).get("bank", {}),
            interactions.get("grand_exchange", {}),
            interactions.get("tasks_master", {}),
            interactions.get("npc", {})
        ) 
    
    def _generate_resource_sources(self):
        resource_to_tile = {}
        tile_to_resource = {}
        for resource in self._resource_data:
            for drop in resource["drops"]:
                resource_to_tile.setdefault(drop["code"], set()).add(resource["code"])
                tile_to_resource.setdefault(resource["code"], set()).add(drop["code"])

        return resource_to_tile, tile_to_resource
    
    def _generate_monster_drop_sources(self):
        monster_sources = {}
        for monster, data in self._monster_data.items():
            for drop in data["drops"]:
                monster_sources.setdefault(drop["code"], set()).add(monster)

        return monster_sources 
    
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
    
    def get_crafting_materials_for_item(self, item: str, qty=1) -> List[Tuple[str, int]] | None:
        if not self.item_is_craftable(item):
            raise KeyError(f"{item} is not craftable.")
        
        materials = self._item_data[item]["craft"]["items"]
        return [{"code": m["code"], "quantity": m["quantity"] * qty} for m in materials]
    
    def get_workshop_for_item(self, item: str) -> str:
        if not self.item_is_craftable(item):
            raise KeyError(f"{item} is not craftable.")
        
        return self._item_data[item]["craft"]["skill"]
    
    def get_workshop_locations(self, skill: str) -> List[Tuple[int, int]]:
        if skill in self._interactions.workshops:
            return self._interactions.workshops[skill]
        
        raise KeyError(f"{skill} is not a skill.")
    
    # Equipment Checkers
    def is_equipment(self, item: str) -> bool:
        return self.is_an_item(item) and not self.get_item_info(item)["type"] == "resource"
    
    def get_equip_slot_for_item(self, item: str) -> str:
        if not self.is_equipment(item):
            raise KeyError(f"{item} is not equipment.")
        
        return self._item_data[item]["type"]
    
    def is_tool(self, item: str) -> bool:
        return self.is_an_item(item) and self._item_data[item]["subtype"] == "tool"
    
    def get_best_tool_for_skill_in_bank(self, skill: str) -> Tuple[str, int] | None:
        tools = [
            item for item in self._bank_data 
            if self.is_tool(item)
            and any(effect["code"] == skill for effect in self._item_data[item]["effects"])
        ]

        if len(tools) > 0:
            best_tool = min([
                (tool, [effect["value"] for effect in self._item_data[tool]["effects"] if effect["code"] == skill][0])
                for tool in tools
            ], key=lambda t: t[1])

            return best_tool
        else:
            return None
        
    def get_gather_power_of_tool(self, tool: str, skill: str) -> int:
        if not self.is_equipment(tool):
            raise KeyError(f"{tool} is not equipment.")

        power = [effect["value"] for effect in self._item_data[tool]["effects"] if effect["code"] == skill]
        if len(power) > 0:
            return power[0]
        else:
            return 0
        
    def is_weapon(self, item: str) -> bool:
        return self.is_an_item(item) and self._item_data[item]["type"] == "weapon"
        
    def get_best_weapon_for_monster_in_bank(self, monster: str) -> Tuple[str, int] | None:
        weapons = [
            item for item in self._bank_data 
            if self.is_weapon(item)
        ]

        if len(weapons) > 0:
            weapon_damage = [(weapon, self.get_attack_power_of_weapon(weapon, monster)) for weapon in weapons]
            best_weapon = max(weapon_damage, key=lambda w: w[1])
            return best_weapon
        else:
            return (None, 0)
        
    def get_attack_power_of_weapon(self, weapon: str, monster: str) -> int:
        if not self.is_equipment(weapon):
            raise KeyError(f"{weapon} is not equipment.")
        
        monster_data = self._monster_data[monster]
        weapon_data = self.get_item_info(weapon)

        power = 0
        crit_chance = 0
        crit_damage_mult = 1.5

        for effect in weapon_data["effects"]:
            match effect["code"]:
                case "attack_air":
                    power += floor(effect["value"] / (1 + int(monster_data["res_air"]) / 100))

                case "attack_water":
                    power += floor(effect["value"] / (1 + int(monster_data["res_water"]) / 100))

                case "attack_earth":
                    power += floor(effect["value"] / (1 + int(monster_data["res_earth"]) / 100))

                case "attack_fire":
                    power += floor(effect["value"] / (1 + int(monster_data["res_fire"]) / 100))

                case "critical_strike":
                    crit_chance = effect["value"] / 100

        power += (power * crit_damage_mult * crit_chance)
        return power
        
    def is_armour(self, item: str) -> bool:
        return self.is_an_item(item) and self._item_data[item]["type"] in ARMOUR_SLOTS
        
    def get_best_armour_for_monster_in_bank(self, monster: str) -> Dict[str, Tuple[str, int]] | None:
        armours = [
            item for item in self._bank_data 
            if self.is_armour(item)
        ]

        if len(armours) > 0:
            armour_choices = {
                "helmet": [],
                "shield": [],
                "body_armour": [],
                "leg_armour": [],
                "boots": []
            }
            
            for armour in armours:
                armour_data = self.get_item_info(armour)
                armour_type = armour_data["type"]
                def_power = self.get_defence_power_of_armour(armour, monster)
                armour_choices[armour_type].append((armour, def_power))

            for k, v in armour_choices.items():
                if len(v) > 0:
                    armour_choices[k] = max(v, key=lambda a: a[1])

            return armour_choices
        else:
            return None
        
    def get_defence_power_of_armour(self, armour: str, monster: str) -> int:
        if not self.is_equipment(armour):
            raise KeyError(f"{armour} is not equipment.")
        
        monster_data = self._monster_data[monster]
        armour_data = self.get_item_info(armour)

        def_power = 0
        dmg_bonus = 1
        wisdom = 0

        for effect in armour_data["effects"]:
            match effect["code"]:
                case "hp":
                    def_power += effect["value"]

                case "dmg":
                    dmg_bonus += effect["value"]
                    
                case "res_air":
                    def_power += (1 + effect["value"] / 100) * int(monster_data["attack_air"])

                case "res_water":
                    def_power += (1 + effect["value"] / 100) * int(monster_data["attack_water"])

                case "res_earth":
                    def_power += (1 + effect["value"] / 100) * int(monster_data["attack_earth"])

                case "res_fire":
                    def_power += (1 + effect["value"] / 100) * int(monster_data["attack_fire"])

                case "attack_air":
                    def_power += effect["value"] / 100

                case "attack_water":
                    dmg_bonus += floor(effect["value"] / (1 + int(monster_data["res_water"]) / 100))

                case "attack_earth":
                    dmg_bonus += floor(effect["value"] / (1 + int(monster_data["res_earth"]) / 100))

                case "attack_fire":
                    dmg_bonus += floor(effect["value"] / (1 + int(monster_data["res_fire"]) / 100))

                case "wisdom":
                    wisdom = floor(effect["value"] / (1 + int(monster_data["res_fire"]) / 100))

                case _:
                    raise Exception("wtf is this")

        return def_power
    
    # Resource Checkers
    def is_a_resource(self, resource: str) -> bool:
        return self.is_an_item(resource) and self.get_item_info(resource)["type"] == "resource"
    
    def get_resource_at_location(self, x: int, y: int) -> str | None:
        for tile, locations in self._interactions.resources.items():
            if (x, y) in locations:
                return self._tile_to_resource[tile]
    
    def get_locations_of_resource(self, resource: str) -> List[Tuple[int, int]]:
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

    def get_locations_of_monster(self, monster: str) -> List[Tuple[int, int]]:
        if not self.is_a_monster(monster):
            raise KeyError(f"{monster} is not a monster.")
        
        locations = self._interactions.monsters[monster]
        return locations
    
    # Bank Checkers
    def get_bank_locations(self) -> List[Tuple[int, int]]:
        return self._interactions.banks

    def get_amount_of_item_in_bank(self, item: str) -> int:
        if item in self._bank_data:
            amount_in_bank = self._bank_data[item]
            amount_reserved = self.get_amount_of_item_reserved_in_bank(item)
            return amount_in_bank - amount_reserved
        else:
            return 0
    
    def update_bank_data(self, bank_data: Dict[str, Any]):
        self._bank_data = {}
        for item in bank_data:
            self._bank_data[item["code"]] = item["quantity"]
        
    def reserve_bank_items(self, items: List[Dict]) -> str:
        id = str(uuid.uuid4())
        self.bank_reservations[id] = items
        return id

    def clear_bank_reservation(self, id: str):
        del self.bank_reservations[id]      
        
    def get_amount_of_item_reserved_in_bank(self, item: str) -> int:
        amount_reserved = 0
        for id, reservation in self.bank_reservations.items():
            for r in reservation:
                amount_reserved += r["quantity"] if r["code"] == item else 0

        return amount_reserved
    
    # Other Checkers
    def get_task_master_locations(self) -> List[Tuple[int, int]]:
        return self._interactions.tasks_masters
