from dataclasses import dataclass
from enum import Enum, auto
from typing import List
import math

@dataclass
class ItemOrder:
    items: List[ItemSelection]
    greedy_order: bool
    check_inv: bool

@dataclass
class ItemSelection:
    item: str
    quantity: ItemQuantity

@dataclass
class ItemQuantity:
    min: int | None = None
    max: int | None = None
    multiple_of: int | None = None
    all: bool | None = None

    def __post_init__(self):
        if self.all:
            # If requesting all of an item, forbid a min/max selection
            assert(not self.max)
            assert(not self.min)

        if not self.all:
            # If not requesting all of an item, require a min or max selection
            assert((self.max is not None and self.max > 0) or (self.min is not None and self.min > 0))

            # If not defined, set min to -INF and max to +INF
            if not self.max:
                self.max = math.inf

            if not self.min:
                self.min = -math.inf

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