from dataclasses import dataclass
import math

@dataclass
class ItemQuantity:
    max: int | None = None
    min: int | None = None
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

@dataclass
class ItemSelection:
    item: str
    quantity: ItemQuantity