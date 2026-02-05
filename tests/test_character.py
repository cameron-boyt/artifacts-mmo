import pytest
from unittest.mock import MagicMock

from src.character import CharacterAgent
from src.helpers import ItemOrder, ItemSelection, ItemQuantity

def inv_map_to_list(inv: dict[str, int]) -> list[dict[str, int]]:
    return [{"code": code, "quantity": qty} for code, qty in inv.items()]

def set_bank(agent: CharacterAgent, bank: dict[str, int]) -> None:
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: bank.get(code, 0)

def set_inv(agent: CharacterAgent, inv: dict[str, int]) -> None:
    agent.char_data["inventory"] = inv_map_to_list(inv)

@pytest.fixture
def agent() -> CharacterAgent:
    character_data = {
        "name": "Test Agent",
        "x": 0,
        "y": 0,
        "inventory": {},
        "inventory_max_items": 100,
    }

    world_state = MagicMock()
    api_client = MagicMock()
    scheduler = MagicMock()

    agent = CharacterAgent(character_data, world_state, api_client, scheduler)
    set_bank(agent, {"copper_ore": 15, "iron_ore": 5})

    return agent


## Helper Functions
#_get_closest_location
@pytest.mark.parametrize(
    "start,locations,expected",
    [
        pytest.param((0, 0), [], (), id="no_location"),
        pytest.param((0, 0), [(1, 0)], (1, 0), id="one_location"),
        pytest.param((0, 0), [(4, -2), (1, 0), (5, 5)], (1, 0), id="many_locations_0_0_start"),
        pytest.param((4, 3), [(4, -2), (1, 0), (5, 5)], (5, 5), id="many_locations_4_3_start")
    ]
)

def test__get_closest_location__cases(agent: CharacterAgent, start, locations, expected):
    agent.char_data["x"], agent.char_data["y"] = start
    result = agent._get_closest_location(locations)
    assert result == expected
   
#_construct_item_list

def order_single_exact(code: str, qty: int, greedy=False, check_inv=False):
    return ItemOrder(
        items=[ItemSelection(code, ItemQuantity(min=qty, max=qty))],
        greedy_order=greedy,
        check_inv=check_inv,
    )

def order_single_range(code: str, min_q: int | None, max_q: int | None, check_inv=False):
    return ItemOrder(
        items=[ItemSelection(code, ItemQuantity(min=min_q, max=max_q))],
        check_inv=check_inv,
    )

def order_single_multiple_of(code: str, min_q: int | None, max_q: int | None, multiple_of: int, check_inv=False):
    return ItemOrder(
        items=[ItemSelection(code, ItemQuantity(min=min_q, max=max_q, multiple_of=multiple_of))],
        check_inv=check_inv,
    )

def order_multi(items: list[tuple[str, ItemQuantity]], greedy=False, check_inv=False) -> ItemOrder:
    """Helper to define multi-item orders compactly in test cases."""
    return ItemOrder(
        items=[ItemSelection(code, qty) for code, qty in items],
        greedy_order=greedy,
        check_inv=check_inv,
    )

@pytest.mark.parametrize(
    "order,inv,bank,expected",
    [
        ### SINGLE ITEM ; EXACT QUANTITY ###
        # Basic variations
        pytest.param(
            order_single_exact("copper_ore", 5), {}, {},
            [],
            id="single_item__not_in_bank"
        ),
        pytest.param(
            order_single_exact("copper_ore", 5), {}, { "copper_ore": 15 },
            [{ "code": "copper_ore", "quantity": 5 }],
            id="single_item__exact_quantity"
        ),
        pytest.param(
            order_single_exact("copper_ore", 5), {}, {"copper_ore": 3},
            [],
            id="single_item__exact_quantity__bank_insufficient"
        ),
        pytest.param(
            order_single_exact("copper_ore", 5), {"filler_item": 98}, {"copper_ore": 15},
            [],
            id="single_item__exact_quantity__low_inv_space"
        ),

        # +greedy flag variations
        pytest.param(
            order_single_exact("copper_ore", 5, greedy=True), {}, {"copper_ore": 8},
            [{ "code": "copper_ore", "quantity": 5 }],
            id="single_item__exact_quantity__greedy__one_set"
        ),
        pytest.param(
            order_single_exact("copper_ore", 5, greedy=True), {}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 15 }],
            id="single_item__exact_quantity__greedy__many_sets"
        ),

        # +check_inv flag variations
        pytest.param(
            order_single_exact("copper_ore", 5, check_inv=True), {"copper_ore": 3}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 2 }],
            id="single_item__exact_quantity__check_inv__inv_partial"
        ),
        pytest.param(
            order_single_exact("copper_ore", 5, check_inv=True), {"copper_ore": 7}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 0 }],
            id="single_item__exact_quantity__check_inv__inv_satisfies"
        ),

        # +greevy and +check_inv flag variations
        pytest.param(
            order_single_exact("copper_ore", 5, greedy=True, check_inv=True), {}, {"copper_ore": 8},
            [{ "code": "copper_ore", "quantity": 5 }],
            id="single_item__exact_quantity__greedy__check_inv__inv_empty"
        ),
        pytest.param(
            order_single_exact("copper_ore", 5, greedy=True, check_inv=True), {"copper_ore": 1}, {"copper_ore": 8},
            [{ "code": "copper_ore", "quantity": 4 }],
            id="single_item__exact_quantity__greedy__check_inv__inv_partial__no_overflow"
        ),
        pytest.param(
            order_single_exact("copper_ore", 5, greedy=True, check_inv=True), {"copper_ore": 3}, {"copper_ore": 8},
            [{ "code": "copper_ore", "quantity": 7 }],
            id="single_item__exact_quantity__greedy__one_set__check_inv__inv_partial__set_overflow"
        ),
        pytest.param(
            order_single_exact("copper_ore", 5, greedy=True, check_inv=True), {"copper_ore": 6}, {"copper_ore": 8},
            [{ "code": "copper_ore", "quantity": 4 }],
            id="single_item__exact_quantity__greedy__check_inv__inv_satisfies"
        ),

        
        ### SINGLE ITEM ; RANGE QUANTITY ###    
        # Basic variations
        pytest.param(
            order_single_range("copper_ore", 3, 10), {}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 10 }],
            id="single_item__range_quantity__bank_sufficient"
        ),
        pytest.param(
            order_single_range("copper_ore", 3, 10), {"filler_item": 95}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 5 }],
            id="single_item__range_quantity__bank_sufficient__low_inv_space__within_range"
        ),
        pytest.param(
            order_single_range("copper_ore", 3, 10), {"filler_item": 98}, {"copper_ore": 15},
            [],
            id="single_item__range_quantity__bank_sufficient__low_inv_space__outside_range"
        ),        
        pytest.param(
            order_single_range("copper_ore", 3, 10), {}, {"copper_ore": 2},
            [],
            id="single_item__range_quantity__bank_insufficient"
        ),

        # +check_inv flag variations

        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 2}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 8 }],
            id="single_item__range_quantity__bank_sufficient__check_inv__inv_partial"
        ),
        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 2, "filler_item": 95}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 3 }],
            id="single_item__range_quantity__bank_sufficient__check_inv__inv_partial__low_inv_space__within_range"
        ),
        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 2, "filler_item": 97}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 1}],
            id="single_item__range_quantity__bank_sufficient__check_inv__inv_partial__low_inv_space__outside_range__inv_satisfies"
        ),
        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 1, "filler_item": 98}, {"copper_ore": 15},
            [],
            id="single_item__range_quantity__bank_sufficient__check_inv__inv_partial__low_inv_space__outside_range__inv_not_satisfies"
        ),

        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 4}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 6 }],
            id="single_item__range_quantity__bank_sufficient__check_inv__inv_satisfies"
        ),
        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 4, "filler_item": 91}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 5 }],
            id="single_item__range_quantity__bank_sufficient__check_inv__inv_satisfies__low_inv_space__within_range"
        ),
        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 4, "filler_item": 94}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 2}],
            id="single_item__range_quantity__bank_sufficient__check_inv__inv_satisfies__low_inv_space__outside_range"
        ),
        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 4, "filler_item": 96}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 0}],
            id="single_item__range_quantity__bank_sufficient__check_inv__inv_satisfies__low_inv_space__inv_full"
        ),

        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 2}, {"copper_ore": 2},
            [{ "code": "copper_ore", "quantity": 2}],
            id="single_item__range_quantity__bank_insufficient__inv_satisfies"
        ),

        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 5}, {},
            [{ "code": "copper_ore", "quantity": 0}],
            id="single_item__range_quantity__bank_empty__inv_satisfies"
        ),

        pytest.param(
            order_single_range("copper_ore", 3, 10, check_inv=True), {"copper_ore": 2}, {},
            [],
            id="single_item__range_quantity__bank_empty__inv_not_satisfies"
        ),

        # No min or no max variations
        pytest.param(
            order_single_range("copper_ore", None, 10), {}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 10 }],
            id="single_item__range_quantity__no_min__bank_sufficient"
        ),
        pytest.param(
            order_single_range("copper_ore", None, 10), {}, {"copper_ore": 6},
            [{ "code": "copper_ore", "quantity": 6 }],
            id="single_item__range_quantity__no_min__bank_within_range"
        ),
         pytest.param(
            order_single_range("copper_ore", 5, None), {}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 15 }],
            id="single_item__range_quantity__no_max__bank_sufficient"
        ),
        pytest.param(
            order_single_range("copper_ore", 5, None), {}, {"copper_ore": 3},
            [],
            id="single_item__range_quantity__no_max__bank_insufficient"
        ),

        ### SINGLE ITEM ; MULTIPLE_OF SET ###
        # Basic variations
        pytest.param(
            order_single_multiple_of("copper_ore", None, None, 5), {}, {"copper_ore": 15},
            [{ "code": "copper_ore", "quantity": 15 }],
            id="single_item__multiple_of"
        ),

        # +check_inv variations
        pytest.param(
            order_single_multiple_of("copper_ore", None, None, 5, check_inv=True), {"copper_ore": 3}, {"copper_ore": 12},
            [{"code": "copper_ore", "quantity": 12}],
            id="single_item__multiple_of__check_inv__inv_partial"
        ),
        pytest.param(
            order_single_multiple_of("copper_ore", None, None, 5, check_inv=True), {"copper_ore": 7}, {"copper_ore": 3},
            [{"code": "copper_ore", "quantity": 3}],
            id="single_item__multiple_of__check_inv__inv_satisfies"
        ),
        pytest.param(
            order_single_multiple_of("copper_ore", None, None, 5, check_inv=True), {"copper_ore": 7}, {"copper_ore": 2},
            [{"code": "copper_ore", "quantity": 0}],
            id="single_item__multiple_of__check_inv__inv_satisfies__bank_insufficient"
        ),

        ### MULTI ITEM ; EXACT QUANTITY ###
        pytest.param(
            order_multi(
                [
                    ("copper_ore", ItemQuantity(min=7, max=7)),
                    ("iron_ore", ItemQuantity(min=3, max=3)),
                ]
            ),
            {},
            {"copper_ore": 15, "iron_ore": 5},
            [{"code": "copper_ore", "quantity": 7}, {"code": "iron_ore", "quantity": 3}],
            id="multi_item__exact__both_succeed"
        ),
        pytest.param(
            order_multi(
                [
                    ("copper_ore", ItemQuantity(min=7, max=7)),
                    ("iron_ore", ItemQuantity(min=3, max=3)),
                ]
            ),
            {"filler_item": 93},
            {"copper_ore": 15, "iron_ore": 5},
            [],
            id="multi_item__exact__second_fails_due_to_space"
        ),

        ### MULTI ITEM ; GREEDY ###
        pytest.param(
            order_multi(
                [
                    ("copper_ore", ItemQuantity(min=4, max=4)),
                    ("iron_ore", ItemQuantity(min=2, max=2)),
                ],
                greedy=True,
            ),
            {},
            {"copper_ore": 15, "iron_ore": 5},
            [{"code": "copper_ore", "quantity": 8}, {"code": "iron_ore", "quantity": 4}],
            id="multi_item__greedy__capped_by_scarce_item"
        ),
        pytest.param(
            order_multi(
                [
                    ("copper_ore", ItemQuantity(min=4, max=4)),
                    ("iron_ore", ItemQuantity(min=2, max=2)),
                ],
                greedy=True,
            ),
            {"filler_item": 91},
            {"copper_ore": 15, "iron_ore": 50},
            [{"code": "copper_ore", "quantity": 4}, {"code": "iron_ore", "quantity": 2}],
            id="multi_item__greedy__capped_by_free_space"
        ),
    ]
)

def test__construct_item_list__cases(agent: CharacterAgent, order, inv, bank, expected):
    set_inv(agent, inv)
    set_bank(agent, bank)
    result = agent._construct_item_list(order)
    assert result == expected

#get_number_of_items_in_inventory
def test__get_number_of_items_in_inventory__inv_empty(agent: CharacterAgent):
    assert agent.get_number_of_items_in_inventory() == 0

def test__get_number_of_items_in_inventory__inv_filled(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15, "ash_wood": 3, "sunflower": 4})
    assert agent.get_number_of_items_in_inventory() == 27

#get_inventory_size
def test__get_inventory_size(agent: CharacterAgent):
    assert agent.get_inventory_size() == 100

#get_free_inventory_spaces
def test__get_free_inventory_spaces__empty_inv(agent: CharacterAgent):
    assert agent.get_free_inventory_spaces() == 100

def test__get_free_inventory_spaces__populated_inv(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert agent.get_free_inventory_spaces() == 80

#get_quantity_of_item_in_inventory
def test__get_quantity_of_item_in_inventory__no_item(agent: CharacterAgent):
    assert agent.get_quantity_of_item_in_inventory("copper_ore") == 0

def test__get_quantity_of_item_in__inventory_inv_full__no_item(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert agent.get_quantity_of_item_in_inventory("random_item") == 0

def test__get_quantity_of_item_in__inventory_inv_full__has_item(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert agent.get_quantity_of_item_in_inventory("copper_ore") == 5
    assert agent.get_quantity_of_item_in_inventory("iron_ore") == 15

## Condition Checkers
#inventory_full
def test__inventory_full__no_items(agent: CharacterAgent):
    assert not agent.inventory_full()

def test__inventory_full__no_items__zero_max_inv_space(agent: CharacterAgent):
    agent.char_data["inventory_max_items"] = 0
    assert agent.inventory_full()

def test__inventory_full__partial_fill(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert not agent.inventory_full()

def test__inventory_full__completed_filled(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15, "ash_wood": 80})
    assert agent.inventory_full()

#inventory_empty
def test__inventory_empty__no_items(agent: CharacterAgent):
    assert agent.inventory_empty()

def test__inventory_empty__partial_fill(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert not agent.inventory_empty()

def test__inventory_empty__no_items__no_max_space(agent: CharacterAgent):
    agent.char_data["inventory_max_items"] = 0
    assert agent.inventory_full()

#inventory_has_available_space
def test__inventory_has_available_space__empty_inv__low_request(agent: CharacterAgent):
    assert agent.inventory_has_available_space(10)

def test__inventory_has_available_space__empty_inv__request_above_inv_capacity(agent: CharacterAgent):
    assert not agent.inventory_has_available_space(110)

def test__inventory_has_available_space__partially_filled_inv__low_request(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert agent.inventory_has_available_space(10)

def test__inventory_has_available_space__partially_filled_inv__high_request(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert not agent.inventory_has_available_space(90)

#inventory_has_item_of_quantity
def test__inventory_has_item_of_quantity__empty_inv(agent: CharacterAgent):
    assert not agent.inventory_has_item_of_quantity("copper_ore", 10)

def test__inventory_has_item_of_quantity__partially_filled_inv__no_item(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert not agent.inventory_has_item_of_quantity("ash_wood", 5)

def test__inventory_has_item_of_quantity__has_item__exact_quantity(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert agent.inventory_has_item_of_quantity("copper_ore", 5)

def test__inventory_has_item_of_quantity__has_item__low_quantity(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert agent.inventory_has_item_of_quantity("copper_ore", 3)

def test__inventory_has_item_of_quantity__has_item__too_high_quantity(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5, "iron_ore": 15})
    assert not agent.inventory_has_item_of_quantity("copper_ore", 10)

#bank_has_item_of_quantity
def test__bank_has_item_of_quantity__bank_has_sufficent(agent: CharacterAgent):
    assert agent.bank_has_item_of_quantity("copper_ore", 5)

def test__bank_has_item_of_quantity__bank_has_exact(agent: CharacterAgent):
    assert agent.bank_has_item_of_quantity("copper_ore", 15)

def test__bank_has_item_of_quantity__bank_has_insufficent(agent: CharacterAgent):
    assert not agent.bank_has_item_of_quantity("copper_ore", 25)

#bank_and_inventory_have_item_of_quantity
def test__bank_and_inventory_have_item_of_quantity__both_sufficient(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 20})
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 10)

def test__bank_and_inventory_have_item_of_quantity__bank_insufficient__inv_sufficient(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 20})
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 18)

def test__bank_and_inventory_have_item_of_quantity__bank_sufficient__inv_insufficient(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 10})
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 12)


def test__bank_and_inventory_have_item_of_quantity__both_insufficient__total_sufficient(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5})
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 18)

def test__bank_and_inventory_have_item_of_quantity__both_insufficient__total_exact(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5})
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 20)

def test__bank_and_inventory_have_item_of_quantity__both_insufficient__total_insufficient(agent: CharacterAgent):
    set_inv(agent, {"copper_ore": 5})
    assert not agent.bank_and_inventory_have_item_of_quantity("copper_ore", 25)
