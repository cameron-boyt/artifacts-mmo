import pytest
from unittest.mock import MagicMock

from src.character import CharacterAgent
from src.helpers import ItemOrder, ItemSelection, ItemQuantity

@pytest.fixture
def agent() -> CharacterAgent:
    character_data = {
        "name": "Test Agent",
        "x": 0,
        "y": 0,
        "inventory": [],
        "inventory_max_items": 100
    }

    world_state = MagicMock()
    api_client = MagicMock()
    scheduler = MagicMock()

    agent = CharacterAgent(character_data, world_state, api_client, scheduler)
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 15, "iron_ore": 5}.get(code, 0)

    return agent

## Helper Functions
#_get_closest_location
def test_get_closest_location_no_location(agent: CharacterAgent):
    locations = []
    assert agent._get_closest_location(locations) == ()

def test_get_closest_location_one_location(agent: CharacterAgent):
    locations = [(1, 0)]
    assert agent._get_closest_location(locations) == (1, 0)

def test_get_closest_location_many_location(agent: CharacterAgent):
    locations = [(0, 0), (1, 0), (5, 5)]
    assert agent._get_closest_location(locations) == (0, 0)

    agent.char_data["x"] = 4
    agent.char_data["y"] = 3
    assert agent._get_closest_location(locations) == (5, 5)

#_construct_item_list
def test__construct_item_list__single_item__exact_quantity(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=5, max=5))])
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 5 }]

def test__construct_item_list__single_item__exact_quantity_low_inv_space(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=5, max=5))])
    agent.char_data["inventory_max_items"] = 3
    assert agent._construct_item_list(order) == []

def test__construct_item_list__single_item__exact_quantity__greedy(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=5, max=5))], greedy_order=True)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 15 }]

def test__construct_item_list__single_item__exact_quantity__check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=5, max=5))], check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 2 }]

def test__construct_item_list__single_item__exact_quantity__check_inv__inv_is_sufficient(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=5, max=5))], check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 7 }]
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 0 }]

def test__construct_item_list__single_item__exact_quantity__greedy__check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=5, max=5))], greedy_order=True, check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 12 }]


def test__construct_item_list__single_item__range_quantity__bank_sufficient(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))])
    assert agent._construct_item_list(order) == [ { "code": "copper_ore", "quantity": 10 }]

def test__construct_item_list__single_item__range_quantity__bank_sufficient__low_inv_space_within_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))])
    agent.char_data["inventory_max_items"] = 4
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 4 }]

def test__construct_item_list__single_item__range_quantity__bank_sufficient__low_inv_space_outside_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))])
    agent.char_data["inventory_max_items"] = 2
    assert agent._construct_item_list(order) == []


def test__construct_item_list__single_item__range_quantity__bank_exact(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))])
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 10}.get(code, 0)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 10 }]

def test__construct_item_list__single_item__range_quantity__bank_exact__low_inv_space_within_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))])
    agent.char_data["inventory_max_items"] = 4
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 10}.get(code, 0)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 4 }]

def test__construct_item_list__single_item__range_quantity__bank_exact__low_inv_space_outside_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))])
    agent.char_data["inventory_max_items"] = 2
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 10}.get(code, 0)
    assert agent._construct_item_list(order) == []


def test__construct_item_list__single_item__range_quantity__bank_insufficient(agent: CharacterAgent):
    order = ItemOrder( items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))])
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 2}.get(code, 0)
    assert agent._construct_item_list(order) == []


def test__construct_item_list__single_item__range_quantity__bank_sufficient__check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 7 }]

def test__construct_item_list__single_item__range_quantity__bank_sufficient__check_inv__low_inv_space_within_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory_max_items"] = 7
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 4 }]

def test__construct_item_list__single_item__range_quantity__bank_sufficient__check_inv__low_inv_space_outside_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory_max_items"] = 2
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 1 }]
    assert agent._construct_item_list(order) == []

def test__construct_item_list__single_item__range_quantity__bank_sufficient_with_inv__check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 7}.get(code, 0)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 7 }]

def test__construct_item_list__single_item__range_quantity__bank_sufficient_with_inv__check_inv__low_inv_space_within_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory_max_items"] = 7
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 7}.get(code, 0)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 4 }]

def test__construct_item_list__single_item__range_quantity__bank_sufficient_with_inv__check_inv__low_inv_space_outside_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory_max_items"] = 2
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 7}.get(code, 0)
    assert agent._construct_item_list(order) == []


def test__construct_item_list__single_item__range_quantity__bank_exact__check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 10}.get(code, 0)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 7 }]

def test__construct_item_list__single_item__range_quantity__bank_exact__check_inv__low_inv_space_within_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory_max_items"] = 7
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 10}.get(code, 0)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 4 }]

def test__construct_item_list__single_item__range_quantity__bank_exact__check_inv__low_inv_space_outside_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory_max_items"] = 2
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 1 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 10}.get(code, 0)
    assert agent._construct_item_list(order) == []

def test__construct_item_list__single_item__range_quantity__bank_exact_with_inv__check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 7}.get(code, 0)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 7 }]

def test__construct_item_list__single_item__range_quantity__bank_exact_with_inv__check_inv__low_inv_space_within_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory_max_items"] = 7
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 7}.get(code, 0)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 4 }]

def test__construct_item_list__single_item__range_quantity__bank_exact_with_inv__check_inv__low_inv_space_outside_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory_max_items"] = 2
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 1 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 7}.get(code, 0)
    assert agent._construct_item_list(order) == []


def test__construct_item_list__single_item__range_quantity__bank_insufficient__check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 2}.get(code, 0)
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 2 }]

def test__construct_item_list__single_item__range_quantity__bank_insufficient__check_inv__still_insufficient(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(min=3, max=10))], check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 1 }]
    agent.world_state.get_amount_of_item_in_bank.side_effect = lambda code: {"copper_ore": 1}.get(code, 0)
    assert agent._construct_item_list(order) == []


def test__construct_item_list__single_item__multiple_of(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(multiple_of=5))])
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 15 }]

def test__construct_item_list__single_item__multiple_of__low_inv_space_within_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(multiple_of=5))])
    agent.char_data["inventory_max_items"] = 11
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 10 }]

def test__construct_item_list__single_item__multiple_of__low_inv_space_outside_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(multiple_of=5))])
    agent.char_data["inventory_max_items"] = 4
    assert agent._construct_item_list(order) == []

def test__construct_item_list__single_item__multiple_of__check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(multiple_of=5))], check_inv=True)
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 12 }]

def test__construct_item_list__single_item__multiple_of__check_inv__low_inv_space_within_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(multiple_of=5))], check_inv=True)
    agent.char_data["inventory_max_items"] = 11
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    assert agent._construct_item_list(order) == [{ "code": "copper_ore", "quantity": 7 }]

def test__construct_item_list__single_item__multiple_of__check_inv__low_inv_space_outside_range(agent: CharacterAgent):
    order = ItemOrder(items=[ItemSelection("copper_ore", ItemQuantity(multiple_of=5))], check_inv=True)
    agent.char_data["inventory_max_items"] = 4
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 3 }]
    assert agent._construct_item_list(order) == []


def test__construct_item_list__multiple_items__exact_quantity(agent: CharacterAgent):
    order = ItemOrder(items=[
        ItemSelection("copper_ore", ItemQuantity(min=7, max=7)),
        ItemSelection("iron_ore", ItemQuantity(min=3, max=3))
    ])
    assert agent._construct_item_list(order) == [
        { "code": "copper_ore", "quantity": 7 },
        { "code": "iron_ore", "quantity": 3 },
    ]

def test__construct_item_list__multiple_items__exact_quantity__greedy(agent: CharacterAgent):
    order = ItemOrder(items=[
        ItemSelection("copper_ore", ItemQuantity(min=4, max=4)),
        ItemSelection("iron_ore", ItemQuantity(min=2, max=2))
    ], greedy_order=True)
    assert agent._construct_item_list(order) == [
        { "code": "copper_ore", "quantity": 12 },
        { "code": "iron_ore", "quantity": 6 },
    ]

def test__construct_item_list__multiple_items__exact_quantity__check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[
        ItemSelection("copper_ore", ItemQuantity(min=7, max=7)),
        ItemSelection("iron_ore", ItemQuantity(min=3, max=3))
    ], check_inv=True)
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 3 },
        { "code": "iron_ore", "quantity": 1 }
    ]
    assert agent._construct_item_list(order) == [
        { "code": "copper_ore", "quantity": 7 },
        { "code": "iron_ore", "quantity": 2 },
    ]

def test__construct_item__list_multiple_items__exact_quantity__check_inv__inv_is_sufficient(agent: CharacterAgent):
    order = ItemOrder(items=[
        ItemSelection("copper_ore", ItemQuantity(min=7, max=7)),
        ItemSelection("iron_ore", ItemQuantity(min=3, max=3))
    ], check_inv=True)
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 10 },
        { "code": "iron_ore", "quantity": 5 }
    ]
    assert agent._construct_item_list(order) == [
        { "code": "copper_ore", "quantity": 0 },
        { "code": "iron_ore", "quantity": 0 },
    ]

def test_construct_item_list_multiple_items_exact_quantity_greedy_check_inv(agent: CharacterAgent):
    order = ItemOrder(items=[
        ItemSelection("copper_ore", ItemQuantity(min=4, max=4)),
        ItemSelection("iron_ore", ItemQuantity(min=2, max=2))
    ], greedy_order=True)
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 4 },
        { "code": "iron_ore", "quantity": 3 }
    ]
    assert agent._construct_item_list(order) == [
        { "code": "copper_ore", "quantity": 8 },
        { "code": "iron_ore", "quantity": 3 },
    ]

def test_construct_item_list_multiple_items_range_quantity(agent: CharacterAgent):
    assert False
def test_construct_item_list_multiple_items_range_quantity_check_inv(agent: CharacterAgent):
    assert False

def test_construct_item_list_multiple_items_multiple_of(agent: CharacterAgent):
    assert False
def test_construct_item_list_multiple_items_multiple_of_check_inv(agent: CharacterAgent):
    assert False

#get_number_of_items_in_inventory
def test__get_number_of_items_in_inventory__inv_empty(agent: CharacterAgent):
    assert agent.get_number_of_items_in_inventory() == 0

def test__get_number_of_items_in_inventory__inv_filled(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 },
        { "code": "ash_wood", "quantity": 3 },
        { "code": "sunflower", "quantity": 4 }
    ]
    assert agent.get_number_of_items_in_inventory() == 27

#get_inventory_size
def test__get_inventory_size(agent: CharacterAgent):
    assert agent.get_inventory_size() == 100

#get_free_inventory_spaces
def test__get_free_inventory_spaces__empty_inv(agent: CharacterAgent):
    assert agent.get_free_inventory_spaces() == 100

def test__get_free_inventory_spaces__populated_inv(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.get_free_inventory_spaces() == 80

#get_quantity_of_item_in_inventory
def test__get_quantity_of_item_in_inventory__no_item(agent: CharacterAgent):
    assert agent.get_quantity_of_item_in_inventory("copper_ore") == 0

def test__get_quantity_of_item_in__inventory_inv_full__no_item(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.get_quantity_of_item_in_inventory("random_item") == 0

def test__get_quantity_of_item_in__inventory_inv_full__has_item(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.get_quantity_of_item_in_inventory("copper_ore") == 5
    assert agent.get_quantity_of_item_in_inventory("iron_ore") == 15

## Condition Checkers
#inventory_full
def test__inventory_full__no_items(agent: CharacterAgent):
    assert agent.inventory_full() == False

def test__inventory_full__no_items__zero_max_inv_space(agent: CharacterAgent):
    agent.char_data["inventory_max_items"] = 0
    assert agent.inventory_full() == True

def test__inventory_full__partial_fill(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.inventory_full() == False

def test__inventory_full__completed_filled(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 },
        { "code": "ash_wood", "quantity": 80 }
    ]
    assert agent.inventory_full() == True

#inventory_empty
def test__inventory_empty__no_items(agent: CharacterAgent):
    assert agent.inventory_empty() == True

def test__inventory_empty__partial_fill(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.inventory_empty() == False

def test__inventory_empty__no_items__no_max_space(agent: CharacterAgent):
    agent.char_data["inventory_max_items"] = 0
    assert agent.inventory_full() == True

#inventory_has_available_space
def test__inventory_has_available_space__empty_inv__low_request(agent: CharacterAgent):
    assert agent.inventory_has_available_space(10) == True

def test__inventory_has_available_space__empty_inv__request_above_inv_capacity(agent: CharacterAgent):
    assert agent.inventory_has_available_space(110) == False

def test__inventory_has_available_space__partially_filled_inv__low_request(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.inventory_has_available_space(10) == True

def test__inventory_has_available_space__partially_filled_inv__high_request(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.inventory_has_available_space(90) == False

#inventory_has_item_of_quantity
def test__inventory_has_item_of_quantity__empty_inv(agent: CharacterAgent):
    assert agent.inventory_has_item_of_quantity("copper_ore", 10) == False

def test__inventory_has_item_of_quantity__partially_filled_inv__no_item(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.inventory_has_item_of_quantity("ash_wood", 5) == False

def test__inventory_has_item_of_quantity__has_item__exact_quantity(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.inventory_has_item_of_quantity("copper_ore", 5) == True

def test__inventory_has_item_of_quantity__has_item__low_quantity(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.inventory_has_item_of_quantity("copper_ore", 3) == True

def test__inventory_has_item_of_quantity__has_item__too_high_quantity(agent: CharacterAgent):
    agent.char_data["inventory"] = [
        { "code": "copper_ore", "quantity": 5 },
        { "code": "iron_ore", "quantity": 15 }
    ]
    assert agent.inventory_has_item_of_quantity("copper_ore", 10) == False

#bank_has_item_of_quantity
def test__bank_has_item_of_quantity__bank_has_sufficent(agent: CharacterAgent):
    assert agent.bank_has_item_of_quantity("copper_ore", 5) == True

def test__bank_has_item_of_quantity__bank_has_exact(agent: CharacterAgent):
    assert agent.bank_has_item_of_quantity("copper_ore", 15) == True

def test__bank_has_item_of_quantity__bank_has_insufficent(agent: CharacterAgent):
    assert agent.bank_has_item_of_quantity("copper_ore", 25) == False

#bank_and_inventory_have_item_of_quantity
def test__bank_and_inventory_have_item_of_quantity__both_sufficient(agent: CharacterAgent):
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 20 }]
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 10) == True

def test__bank_and_inventory_have_item_of_quantity__bank_insufficient__inv_sufficient(agent: CharacterAgent):
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 20 }]
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 18) == True

def test__bank_and_inventory_have_item_of_quantity__bank_sufficient__inv_insufficient(agent: CharacterAgent):
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 10 }]
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 12) == True


def test__bank_and_inventory_have_item_of_quantity__both_insufficient__total_sufficient(agent: CharacterAgent):
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 5 }]
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 18) == True

def test__bank_and_inventory_have_item_of_quantity__both_insufficient__total_exact(agent: CharacterAgent):
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 5 }]
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 20) == True

def test__bank_and_inventory_have_item_of_quantity__both_insufficient__total_insufficient(agent: CharacterAgent):
    agent.char_data["inventory"] = [{ "code": "copper_ore", "quantity": 5 }]
    assert agent.bank_and_inventory_have_item_of_quantity("copper_ore", 25) == False
