from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import List

@dataclass
class ItemOrder:
    items: List[ItemSelection]
    greedy_order: bool = False
    check_inv: bool = False

class ItemType(Enum):
    FOOD = auto()

@dataclass
class ItemSelection:
    quantity: ItemQuantity
    item: str | None = None
    item_type: ItemType | None = None

    def __post_init__(self):
        # Only allow item xor item_type
        assert(self.item or self.item_type)

        if self.item:
            assert(not self.item_type)

        if self.item_type:
            assert(not self.item)

@dataclass
class ItemQuantity:
    min: int | None = None
    max: int | None = None
    multiple_of: int | None = None

    def __post_init__(self):
        # Require a min or max selection OR multiple of
        assert((self.max is not None and self.max > 0) or (self.min is not None and self.min > 0) or self.multiple_of)

        # If both min and max are assigned, min must be no larger than max
        if self.min and self.max:
            assert(self.min <= self.max)

        # If not defined, set min to -INF and max to +INF
        if not self.max:
            self.max = math.inf

        if not self.min:
            self.min = -math.inf
        
ARMOUR_SLOTS = ["shield", "helmet", "body_armor", "leg_armor", "boots", "ring", "amulet"]
SKILLS = ["mining", "woodcutting", "fishing", "weaponcrafting", "gearcrafting", "jewelrycrafting", "cooking", "alchemy"]
WEAPON_EFFECT_CODES = [
    "alchemy",
    "attack_air",
    "attack_earth",
    "attack_fire",
    "attack_water",
    "critical_strike",
    "fishing",
    "inventory_space",
    "mining",
    "woodcutting",
]
ARMOUR_EFFECT_CODES = [
    "critical_strike",
    "dmg",
    "dmg_air",
    "dmg_earth",
    "dmg_fire",
    "dmg_water",
    "haste",
    "hp",
    "initiative",
    "inventory_space",
    "prospecting",
    "res_air",
    "res_earth",
    "res_fire",
    "res_water",
    "threat",
    "wisdom",
]
ALL_EFFECT_CODES = [*WEAPON_EFFECT_CODES, *ARMOUR_EFFECT_CODES]

class ItemSlot(Enum):
    WEAPON = "weapon"
    SHIELD = "shield"
    HELMET = "helmet"
    BODY_ARMOUR = "body_armor"
    LEG_ARMOUR = "leg_armor"
    BOOTS = "boots"
    RING1 = "ring1"
    RING2 = "ring2"
    AMULET = "amulet"
    ARTIFACT1 = "artifact1"
    ARTIFACT2 = "artifact2"
    ARTIFACT3 = "artifact3"
    UTILITY1 = "utility1"
    UILTITY2 = "utility2"
    BAG = "bag"
    RUNE = "rune"