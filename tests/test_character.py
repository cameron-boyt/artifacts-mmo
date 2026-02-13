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
        "name": "Test Agnt",
        "account": "Test Account",
        "skin": "men1",
        "level": 1,
        "xp": 0,
        "max_xp": 0,
        "gold": 0,
        "speed": 0,
        "mining_level": 1,
        "mining_xp": 0,
        "mining_max_xp": 0,
        "woodcutting_level": 1,
        "woodcutting_xp": 0,
        "woodcutting_max_xp": 0,
        "fishing_level": 1,
        "fishing_xp": 0,
        "fishing_max_xp": 0,
        "weaponcrafting_level": 1,
        "weaponcrafting_xp": 0,
        "weaponcrafting_max_xp": 0,
        "gearcrafting_level": 1,
        "gearcrafting_xp": 0,
        "gearcrafting_max_xp": 0,
        "jewelrycrafting_level": 1,
        "jewelrycrafting_xp": 0,
        "jewelrycrafting_max_xp": 0,
        "cooking_level": 1,
        "cooking_xp": 0,
        "cooking_max_xp": 0,
        "alchemy_level": 1,
        "alchemy_xp": 0,
        "alchemy_max_xp": 0,
        "hp": 100,
        "max_hp": 100,
        "haste": 0,
        "critical_strike": 0,
        "wisdom": 0,
        "prospecting": 0,
        "initiative": 0,
        "threat": 0,
        "attack_fire": 0,
        "attack_earth": 0,
        "attack_water": 0,
        "attack_air": 0,
        "dmg": 0,
        "dmg_fire": 0,
        "dmg_earth": 0,
        "dmg_water": 0,
        "dmg_air": 0,
        "res_fire": 0,
        "res_earth": 0,
        "res_water": 0,
        "res_air": 0,
        "effects": [],
        "x": 0,
        "y": 0,
        "layer": "overworld",
        "map_id": 1,
        "cooldown": 0,
        "cooldown_expiration": "2026-02-13T00:04:01.609Z",
        "weapon_slot": "",
        "rune_slot": "",
        "shield_slot": "",
        "helmet_slot": "",
        "body_armor_slot": "",
        "leg_armor_slot": "",
        "boots_slot": "",
        "ring1_slot": "",
        "ring2_slot": "",
        "amulet_slot": "",
        "artifact1_slot": "",
        "artifact2_slot": "",
        "artifact3_slot": "",
        "utility1_slot": "",
        "utility1_slot_quantity": 0,
        "utility2_slot": "",
        "utility2_slot_quantity": 0,
        "bag_slot": "",
        "task": "",
        "task_type": "",
        "task_progress": 0,
        "task_total": 0,
        "inventory_max_items": 100,
        "inventory": []
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

def test__get_closest_location(agent: CharacterAgent, start, locations, expected):
    agent.char_data["x"], agent.char_data["y"] = start
    result = agent._get_closest_location(locations)
    assert result == expected
   
#_construct_item_list
def order_single_exact(code: str, qty: int, greedy=False, check_inv=False):
    return ItemOrder(
        items=[ItemSelection(item=code, quantity=ItemQuantity(min=qty, max=qty))],
        greedy_order=greedy,
        check_inv=check_inv,
    )

def order_single_range(code: str, min_q: int | None, max_q: int | None, check_inv=False):
    return ItemOrder(
        items=[ItemSelection(item=code, quantity=ItemQuantity(min=min_q, max=max_q))],
        check_inv=check_inv,
    )

def order_single_multiple_of(code: str, min_q: int | None, max_q: int | None, multiple_of: int, check_inv=False):
    return ItemOrder(
        items=[ItemSelection(item=code, quantity=ItemQuantity(min=min_q, max=max_q, multiple_of=multiple_of))],
        check_inv=check_inv,
    )

def order_multi(items: list[tuple[str, ItemQuantity]], greedy=False, check_inv=False) -> ItemOrder:
    """Helper to define multi-item orders compactly in test cases."""
    return ItemOrder(
        items=[ItemSelection(item=code, quantity=qty) for code, qty in items],
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

def test__construct_item_list(agent: CharacterAgent, order, inv, bank, expected):
    set_inv(agent, inv)
    set_bank(agent, bank)
    result = agent._construct_item_list(order)
    assert result == expected

#get_number_of_items_in_inventory
@pytest.mark.parametrize(
    "inv,expected",
    [
        pytest.param({}, 0, id="empty_inv"),
        pytest.param({ "copper_ore": 10 }, 10, id="partial_inv__single_item"),
        pytest.param({ "copper_ore": 10, "iron_ore": 5 }, 15, id="partial_inv__multiple_items"),
    ]
)

def test__get_number_of_items_in_inventory(agent: CharacterAgent, inv, expected):
    set_inv(agent, inv)
    result = agent.get_number_of_items_in_inventory()
    assert result == expected

#get_inventory_size
def test__get_inventory_size(agent: CharacterAgent):
    assert agent.get_inventory_size() == 100

#get_free_inventory_spaces
@pytest.mark.parametrize(
    "inv,expected",
    [
        pytest.param({}, 100, id="empty_inv"),
        pytest.param({ "copper_ore": 10 }, 90, id="partial_inv__single_item"),
        pytest.param({ "copper_ore": 10, "iron_ore": 5 }, 85, id="partial_inv__multiple_items"),
        pytest.param({ "copper_ore": 100 }, 0, id="full_inv"),
    ]
)

def test__get_free_inventory_spaces(agent: CharacterAgent, inv, expected):
    set_inv(agent, inv)
    result = agent.get_free_inventory_spaces()
    assert result == expected

#get_quantity_of_item_in_inventory
@pytest.mark.parametrize(
    "inv,item,expected",
    [
        pytest.param({}, "copper_ore", 0, id="not_in_inv"),
        pytest.param({ "copper_ore": 10 }, "copper_ore", 10, id="in_inv__single_item"),
        pytest.param({ "copper_ore": 10, "item_ore": 5 }, "item_ore", 5, id="in_inv__multiple_items"),
    ]
)

def test__get_quantity_of_item_in_inventory(agent: CharacterAgent, inv, item, expected):
    set_inv(agent, inv)
    result = agent.get_quantity_of_item_in_inventory(item)
    assert result == expected

#set_abort_actions
def test__set_abort_actions(agent: CharacterAgent):
    agent.abort_actions = False
    agent.set_abort_actions()
    assert agent.abort_actions == True

#unset_abort_actions()
def test__unset_abort_actions(agent: CharacterAgent):
    agent.abort_actions = True
    agent.unset_abort_actions()
    assert agent.abort_actions == False

## Condition Checkers
#inventory_full
@pytest.mark.parametrize(
    "inv,expected",
    [
        pytest.param({}, False, id="empty_inv"),
        pytest.param({ "copper_ore": 10 }, False, id="partial_inv"),
        pytest.param({ "copper_ore": 10, "iron_ore": 5, "mithril_ore": 85 }, True, id="full_inv"),
    ]
)

def test__inventory_full(agent: CharacterAgent, inv, expected):
    set_inv(agent, inv)
    result = agent.inventory_full()
    assert result == expected

#inventory_empty
@pytest.mark.parametrize(
    "inv,expected",
    [
        pytest.param({}, True, id="empty_inv"),
        pytest.param({ "copper_ore": 10 }, False, id="partial_inv"),
        pytest.param({ "copper_ore": 10, "iron_ore": 5, "mithril_ore": 85 }, False, id="full_inv"),
    ]
)

def test__inventory_empty(agent: CharacterAgent, inv, expected):
    set_inv(agent, inv)
    result = agent.inventory_empty()
    assert result == expected

#inventory_has_available_space
@pytest.mark.parametrize(
    "inv,space,expected",
    [
        pytest.param({}, 10, True, id="empty_inv__low_request"),
        pytest.param({}, 110, False, id="empty_inv__request_above_inv_capacity"),
        pytest.param({ "copper_ore": 10 }, 10, True, id="partial_inv__low_request"),
        pytest.param({ "copper_ore": 10 }, 95, False, id="partial_inv__high_request"),
    ]
)

def test__inventory_has_available_space(agent: CharacterAgent, inv, space, expected):
    set_inv(agent, inv)
    result = agent.inventory_has_available_space(space)
    assert result == expected

#inventory_has_item_of_quantity
@pytest.mark.parametrize(
    "inv,item,quantity,expected",
    [
        pytest.param({}, "copper_ore", 10, False, id="empty_inv"),
        pytest.param({ "copper_ore": 5 }, "iron_ore", 5, False, id="partial_inv__no_item"),
        pytest.param({ "copper_ore": 5 }, "copper_ore", 4, True, id="partial_inv__sufficient_quantity"),
        pytest.param({ "copper_ore": 5 }, "copper_ore", 5, True, id="partial_inv__exact_quantity"),
        pytest.param({ "copper_ore": 5 }, "copper_ore", 6, False, id="partial_inv__low_quantity"),
    ]
)

def test__inventory_has_item_of_quantity(agent: CharacterAgent, inv, item, quantity, expected):
    set_inv(agent, inv)
    result = agent.inventory_has_item_of_quantity(item, quantity)
    assert result == expected

#bank_has_item_of_quantity
@pytest.mark.parametrize(
    "bank,item,quantity,expected",
    [
        pytest.param({}, "copper_ore", 10, False, id="empty_bank"),
        pytest.param({ "copper_ore": 5 }, "iron_ore", 5, False, id="partial_bank__no_item"),
        pytest.param({ "copper_ore": 5 }, "copper_ore", 4, True, id="partial_bank__sufficient_quantity"),
        pytest.param({ "copper_ore": 5 }, "copper_ore", 5, True, id="partial_bank__exact_quantity"),
        pytest.param({ "copper_ore": 5 }, "copper_ore", 6, False, id="partial_bank__low_quantity"),
    ]
)

def test__bank_has_item_of_quantity(agent: CharacterAgent, bank, item, quantity, expected):
    set_bank(agent, bank)
    result = agent.bank_has_item_of_quantity(item, quantity)
    assert result == expected

#bank_and_inventory_have_item_of_quantity
@pytest.mark.parametrize(
    "inv,bank,item,quantity,expected",
    [
        pytest.param({}, {}, "copper_ore", 10, False, id="both_empty"),
        pytest.param({}, { "copper_ore": 3 }, "copper_ore", 10, False, id="bank_empty__inv_insufficient"),
        pytest.param({ "copper_ore": 3 }, {}, "copper_ore", 10, False, id="bank_insufficient__inv_empty"),
        pytest.param({ "copper_ore": 3 }, { "copper_ore": 5 }, "copper_ore", 10, False, id="both_insufficient__total_insufficient"),
        pytest.param({ "copper_ore": 6 }, { "copper_ore": 5 }, "copper_ore", 10, True, id="both_insufficient__total_sufficient"),
        pytest.param({}, { "copper_ore": 11 }, "copper_ore", 10, True, id="bank_sufficient"),
        pytest.param({ "copper_ore": 11 }, {}, "copper_ore", 10, True, id="inv_sufficient"),
    ]
)

def test__bank_and_inventory_have_item_of_quantity(agent: CharacterAgent, inv, bank, item, quantity, expected):
    set_inv(agent, inv)
    set_bank(agent, bank)
    result = agent.bank_and_inventory_have_item_of_quantity(item, quantity)
    assert result == expected

#has_task
@pytest.mark.parametrize(
    "task,expected",
    [
        pytest.param("chicken", True, id="has_task"),
        pytest.param("", False, id="no_task"),
    ]
)

def test__has_task(agent: CharacterAgent, task, expected):
    agent.char_data["task"] = task
    result = agent.has_task()
    assert result == expected
    
#items_in_equip_queue
@pytest.mark.parametrize(
    "context,expected",
    [
        pytest.param({}, False, id="not_defined"),
        pytest.param({ "equip_queue": [] }, False, id="no_withdrawals"),
        pytest.param({ "equip_queue": [{ "code": "copper_helmet", "quantity": 1 }] }, True, id="has_withdrawals"),
    ]
)

def test__items_in_equip_queue(agent: CharacterAgent, context, expected):
    agent.context = context
    result = agent.items_in_equip_queue()
    assert result == expected
    