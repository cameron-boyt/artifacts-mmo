import pytest
import json

from src.worldstate import WorldState

@pytest.fixture
def world_state() -> WorldState:
    with open("bank_data.json", 'r') as f:
        bank_data = json.loads(f.read())

    with open("item_data.json", 'r') as f:
        item_data = json.loads(f.read())

    with open("map_data.json", 'r') as f:
        map_data = json.loads(f.read())

    with open("monster_data.json", 'r') as f:
        monster_data = json.loads(f.read())

    with open("resource_data.json", 'r') as f:
        resource_data = json.loads(f.read())

    return WorldState(bank_data, map_data, item_data, resource_data, monster_data)

## Item Checkers
#is_an_item
@pytest.mark.parametrize(
    "item,expected",
    [
        pytest.param("copper_ore", True, id="is_item"),
        pytest.param("copper_pickaxe", True, id="is_equipment"),
        pytest.param("chicken", False, id="is_monster"),
        pytest.param("fake", False, id="is_fake"),
    ]
)

def test__is_an_item(world_state: WorldState, item, expected):
    result = world_state.is_an_item(item)
    assert result == expected

#get_item_info
@pytest.mark.parametrize(
    "item,expected,exception",
    [
        pytest.param("copper_ore", True, None, id="is_item"),
        pytest.param("copper_pickaxe", True, None, id="is_equipment"),
        pytest.param("chicken", None, KeyError, id="is_monster"),
        pytest.param("fake", None, KeyError, id="is_fake"),
    ]
)

def test__get_item_info(world_state: WorldState, item, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_item_info(item)
    else:
        result = world_state.get_item_info(item)
        assert isinstance(result, dict) == expected

#item_is_craftable
@pytest.mark.parametrize(
    "item,expected,exception",
    [
        pytest.param("copper_pickaxe", True, None, id="is_craftable"),
        pytest.param("copper_ore", False, None, id="is_not_craftable"),
        pytest.param("chicken", None, KeyError, id="is_monster"),
        pytest.param("fake", None, KeyError, id="is_fake"),
    ]
)

def test__item_is_craftable(world_state: WorldState, item, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.item_is_craftable(item)
    else:
        result = world_state.item_is_craftable(item)
        assert result == expected
    
#get_crafting_materials_for_item
@pytest.mark.parametrize(
    "item,expected,exception",
    [
        pytest.param("copper_bar", [{ "code": "copper_ore", "quantity": 10 }], None, id="is_craftable"),
        pytest.param("copper_ore", None, KeyError, id="is_not_craftable"),
        pytest.param("chicken", None, KeyError, id="is_monster"),
        pytest.param("fake", None, KeyError, id="is_fake"),
    ]
)

def test__get_crafting_materials_for_item(world_state: WorldState, item, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_crafting_materials_for_item(item)
    else:
        result = world_state.get_crafting_materials_for_item(item)
        assert result == expected

#get_workshop_for_item
@pytest.mark.parametrize(
    "item,expected,exception",
    [
        pytest.param("copper_bar", "mining", None, id="is_craftable"),
        pytest.param("copper_ore", None, KeyError, id="is_not_craftable"),
        pytest.param("chicken", None, KeyError, id="is_monster"),
        pytest.param("fake", None, KeyError, id="is_fake"),
    ]
)

def test__get_workshop_for_item_for_item(world_state: WorldState, item, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_workshop_for_item(item)
    else:
        result = world_state.get_workshop_for_item(item)
        assert result == expected

#get_workshop_location
@pytest.mark.parametrize(
    "skill,expected,exception",
    [
        pytest.param("mining", None, None, id="is_skill"),
        pytest.param("copper_ore", None, KeyError, id="is_not_skill"),
        pytest.param("chicken", None, KeyError, id="is_monster"),
        pytest.param("fake", None, KeyError, id="is_fake"),
    ]
)

def test__get_workshop_locations(world_state: WorldState, skill, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_workshop_locations(skill)
    else:
        assert world_state.get_workshop_locations(skill)
## Equipment Checkers
#is_equipment
@pytest.mark.parametrize(
    "item,expected",
    [
        pytest.param("copper_pickaxe", True, id="is_equipment"),
        pytest.param("copper_ore", False, id="is_item"),
        pytest.param("chicken", False, id="is_monster"),
        pytest.param("fake", False, id="is_fake"),
    ]
)

def test__is_equipment(world_state: WorldState, item, expected):
    result = world_state.is_equipment(item)
    assert result == expected

#get_equip_slot_for_item
@pytest.mark.parametrize(
    "item,expected,exception",
    [
        pytest.param("copper_pickaxe", "weapon", None, id="is_equipment"),
        pytest.param("copper_ore", None, KeyError, id="is_not_equipment"),
        pytest.param("chicken", None, KeyError, id="is_monster"),
        pytest.param("fake", None, KeyError, id="is_fake"),
    ]
)

def test__get_equip_slot_for_item(world_state: WorldState, item, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_equip_slot_for_item(item)
    else:
        result = world_state.get_equip_slot_for_item(item)
        assert result == expected

#is_tool
@pytest.mark.parametrize(
    "item,expected",
    [
        pytest.param("copper_pickaxe", True, id="is_tool"),
        pytest.param("copper_ore", False, id="is_item"),
        pytest.param("chicken", False, id="is_monster"),
        pytest.param("fake", False, id="is_fake"),
    ]
)

def test__is_tool(world_state: WorldState, item, expected):
    result = world_state.is_tool(item)
    assert result == expected
    
#get_best_tool_for_skill_in_bank
@pytest.mark.parametrize(
    "bank,skill,expected",
    [
        pytest.param([], "mining", None, id="bank_empty"),
        pytest.param({ "copper_pickaxe": 1 }, "mining", ("copper_pickaxe", -10), id="bank_has_tool"),
        pytest.param({ "copper_pickaxe": 1, "iron_pickaxe": 1 }, "mining", ("iron_pickaxe", -20), id="bank_has_multiple_tools"),
        pytest.param({ "copper_pickaxe": 1, "iron_pickaxe": 1, "iron_axe": 1 }, "mining", ("iron_pickaxe", -20), id="bank_has_multiple_tools__multiple_skills__mining"),
        pytest.param({ "copper_pickaxe": 1, "iron_pickaxe": 1, "iron_axe": 1 }, "woodcutting", ("iron_axe", -20), id="bank_has_multiple_tools__multiple_skills__woodcutting"),
    ]
)

def test__get_best_tool_for_skill_in_bank(world_state: WorldState, bank, skill, expected):
    world_state._bank_data = bank
    result = world_state.get_best_tool_for_skill_in_bank(skill)
    assert result == expected

#get_gather_power_of_tool
@pytest.mark.parametrize(
    "tool,skill,expected,exception",
    [
        pytest.param("copper_pickaxe", "mining", -10, None, id="tool_matching_skill"),
        pytest.param("copper_pickaxe", "woodcutting", 0, None, id="tool_not_matching_skill"),
        pytest.param("copper_ore", "mining", None, KeyError, id="not_tool"),
    ]
)

def test__get_gather_power_of_tool(world_state: WorldState, tool, skill, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_gather_power_of_tool(tool, skill)
    else:
        result = world_state.get_gather_power_of_tool(tool, skill)
        assert result == expected
    
#is_weapon
@pytest.mark.parametrize(
    "item,expected",
    [
        pytest.param("sticky_sword", True, id="is_weapon"),
        pytest.param("copper_pickaxe", True, id="is_tool"),
        pytest.param("chicken", False, id="is_monster"),
        pytest.param("fake", False, id="is_fake"),
    ]
)

def test__is_weapon(world_state: WorldState, item, expected):
    result = world_state.is_weapon(item)
    assert result == expected

#get_best_weapon_for_monster_in_bank
@pytest.mark.parametrize(
    "bank,monster,expected",
    [
        pytest.param({}, "chicken", None, id="bank_empty"),
        pytest.param({ "copper_pickaxe": 1 }, "chicken", "copper_pickaxe", id="bank_has_weapon"),
        pytest.param({ "copper_pickaxe": 1, "mushstaff": 1 }, "chicken", "mushstaff", id="bank_has_multiple_weapons"),
        pytest.param({ "fire_staff": 1, "water_bow": 1 }, "cow", "water_bow", id="bank_has_multiple_tools__water_resistence__resisted_has_high_crit_chance"),
        pytest.param({ "fire_staff": 1, "sticky_sword": 1 }, "wolf", "fire_staff", id="bank_has_multiple_tools__fire_weakness"),
        pytest.param({ "fire_staff": 1, "water_bow": 1 }, "wolf", "water_bow", id="bank_has_multiple_tools__fire_weakness__other_weapon_high_crit_chance"),
    ]
)

def test__get_best_weapon_for_monster_in_bank(world_state: WorldState, bank, monster, expected):
    world_state._bank_data = bank
    result = world_state.get_best_weapon_for_monster_in_bank(monster)
    assert result[0] == expected

#get_attack_power_of_weapon
@pytest.mark.parametrize(
    "weapon,monster,expected,exception",
    [
        pytest.param("copper_pickaxe", "chicken", 5, None, id="weapon_against_normal_enemy"),
        pytest.param("copper_pickaxe", "cow", 7, None, id="weapon_against_weak_enemy"),
        pytest.param("copper_pickaxe", "yellow_slime", 4, None, id="weapon_against_resist_enemy"),
        pytest.param("copper_ore", "yellow_slime", None, KeyError, id="not_a_weapon"),
    ]
)

def test__get_attack_power_of_weapon(world_state: WorldState, weapon, monster, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_attack_power_of_weapon(weapon, monster)
    else:
        result = world_state.get_attack_power_of_weapon(weapon, monster)
        assert result == expected

#is_armour
@pytest.mark.parametrize(
    "item,expected",
    [
        pytest.param("copper_helmet", True, id="is_armour"),
        pytest.param("sticky_sword", False, id="is_weapon"),
        pytest.param("chicken", False, id="is_monster"),
        pytest.param("fake", False, id="is_fake"),
    ]
)

def test__is_armour(world_state: WorldState, item, expected):
    result = world_state.is_armour(item)
    assert result == expected

#get_best_armour_for_monster_in_bank
@pytest.mark.parametrize(
    "bank,monster,expected",
    [
        pytest.param({}, "chicken", None, id="bank_empty"),
        pytest.param({ "copper_pickaxe": 1 }, "chicken", "copper_pickaxe", id="bank_has_weapon"),
        pytest.param({ "copper_pickaxe": 1, "mushstaff": 1 }, "chicken", "mushstaff", id="bank_has_multiple_weapons"),
        pytest.param({ "fire_staff": 1, "water_bow": 1 }, "cow", "water_bow", id="bank_has_multiple_tools__water_resistence__resisted_has_high_crit_chance"),
        pytest.param({ "fire_staff": 1, "sticky_sword": 1 }, "wolf", "fire_staff", id="bank_has_multiple_tools__fire_weakness"),
        pytest.param({ "fire_staff": 1, "water_bow": 1 }, "wolf", "water_bow", id="bank_has_multiple_tools__fire_weakness__other_weapon_high_crit_chance"),
    ]
)

def test__get_best_armour_for_monster_in_bank(world_state: WorldState, bank, monster, expected):
    world_state._bank_data = bank
    result = world_state.get_best_armour_for_monster_in_bank(monster)
    assert result[0] == expected


#get_defence_power_of_armour
@pytest.mark.parametrize(
    "weapon,monster,expected,exception",
    [
        pytest.param("copper_pickaxe", "chicken", 5, None, id="weapon_against_normal_enemy"),
        pytest.param("copper_pickaxe", "cow", 7, None, id="weapon_against_weak_enemy"),
        pytest.param("copper_pickaxe", "yellow_slime", 4, None, id="weapon_against_resist_enemy"),
        pytest.param("copper_ore", "yellow_slime", None, KeyError, id="not_armour"),
    ]
)

def test__get_defence_power_of_armour(world_state: WorldState, weapon, monster, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_defence_power_of_armour(weapon, monster)
    else:
        result = world_state.get_defence_power_of_armour(weapon, monster)
        assert result == expected

# Resource Checkers
#is_a_resource
@pytest.mark.parametrize(
    "resource,expected",
    [
        pytest.param("copper_ore", True, id="is_item"),
        pytest.param("copper_pickaxe", False, id="is_equipment"),
        pytest.param("chicken", False, id="is_monster"),
        pytest.param("fake", False, id="is_fake"),
    ]
)

def test__is_a_resource(world_state: WorldState, resource, expected):
    result = world_state.is_a_resource(resource)
    assert result == expected

#get_resource_at_location
@pytest.mark.parametrize(
    "x,y,expected",
    [
        pytest.param(-1, 0, {'apple', 'ash_wood', 'sap'}, id="resource_present"),
        pytest.param(0, 0, None, id="resource_absent"),
        pytest.param(999, 999, None, id="map_out_of_bounds"),
    ]
)

def test__get_resource_at_location(world_state: WorldState, x, y, expected):
    result = world_state.get_resource_at_location(x, y)
    assert result == expected

#get_locations_of_resource
@pytest.mark.parametrize(
    "resource,expected,exception",
    [
        pytest.param("copper_ore", {(2, 0)}, None, id="is_resource"),
        pytest.param("copper_bar", [], None, id="not_gatherable"),
        pytest.param("copper_helmet", None, KeyError, id="not_resource"),
        pytest.param("fake", None, KeyError, id="is_fake"),
    ]
)

def test__get_locations_of_resource(world_state: WorldState, resource, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_locations_of_resource(resource)
    else:
        result = world_state.get_locations_of_resource(resource)
        assert result == expected

#get_gather_skill_for_resource
@pytest.mark.parametrize(
    "resource,expected,exception",
    [
        pytest.param("copper_ore", "mining", None, id="is_resource"),
        pytest.param("copper_helmet", False, KeyError, id="not_resource"),
        pytest.param("fake", False, KeyError, id="is_fake"),
    ]
)

def test__get_gather_skill_for_resource(world_state: WorldState, resource, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_gather_skill_for_resource(resource)
    else:
        result = world_state.get_gather_skill_for_resource(resource)
        assert result == expected
    
# Monster Checkers
#is_a_monster
@pytest.mark.parametrize(
    "monster,expected",
    [
        pytest.param("chicken", True, id="is_monster"),
        pytest.param("copper_ore", False, id="is_item"),
        pytest.param("copper_pickaxe", False, id="is_equipment"),
        pytest.param("fake", False, id="is_fake"),
    ]
)

def test__is_a_monster(world_state: WorldState, monster, expected):
    result = world_state.is_a_monster(monster)
    assert result == expected

#get_monster_info
@pytest.mark.parametrize(
    "monster,expected,exception",
    [
        pytest.param("chicken", True, None, id="is_monster"),
        pytest.param("copper_ore", False, KeyError, id="is_item"),
        pytest.param("copper_pickaxe", False, KeyError, id="is_equipment"),
        pytest.param("fake", None, KeyError, id="is_fake"),
    ]
)    

def test__get_monster_info(world_state: WorldState, monster, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_monster_info(monster)
    else:
        result =  world_state.get_monster_info(monster)
        assert isinstance(result, dict) == expected

#get_monster_at_location
@pytest.mark.parametrize(
    "x,y,expected",
    [
        pytest.param(0, 1, "chicken", id="monster_present"),
        pytest.param(0, 0, None, id="monster_absent"),
        pytest.param(999, 999, None, id="map_out_of_bounds"),
    ]
)

def test__get_monster_at_location(world_state: WorldState, x, y, expected):
    result = world_state.get_monster_at_location(x, y)
    assert result == expected

#get_locations_of_monster
@pytest.mark.parametrize(
    "monster,expected,exception",
    [
        pytest.param("cow", {(0, 2)}, None, id="is_resource"),
        pytest.param("copper_bar", None, KeyError, id="not_monster"),
        pytest.param("fake", None, KeyError, id="is_fake"),
    ]
)

def test__get_locations_of_monster(world_state: WorldState, monster, expected, exception):
    if exception:
        with pytest.raises(exception):
            world_state.get_locations_of_monster(monster)
    else:
        result = world_state.get_locations_of_monster(monster)
        assert result == expected
    
# Bank Checkers
def test__get_bank_locations(world_state: WorldState):
    assert world_state.get_bank_locations()

def test__items_in_bank_and_reservations(world_state: WorldState):
    world_state._bank_data = { "copper_ore": 100, "iron_ore": 50 }
    assert world_state.get_amount_of_item_in_bank("copper_ore") == 100
    assert world_state.get_amount_of_item_in_bank("iron_ore") == 50
    assert world_state.get_amount_of_item_in_bank("copper_bar") == 0
    
    rid = world_state.reserve_bank_items([{"code":"copper_ore","quantity": 30}])
    assert world_state.get_amount_of_item_reserved_in_bank("copper_ore") == 30
    assert world_state.get_amount_of_item_in_bank("copper_ore") == 70

    rid2 = world_state.reserve_bank_items([{"code":"copper_ore","quantity": 20}])
    assert world_state.get_amount_of_item_reserved_in_bank("copper_ore") == 50
    assert world_state.get_amount_of_item_in_bank("copper_ore") == 50

    world_state.clear_bank_reservation(rid)
    assert world_state.get_amount_of_item_reserved_in_bank("copper_ore") == 20
    assert world_state.get_amount_of_item_in_bank("copper_ore") == 80

def test__update_bank_data(world_state: WorldState):
    world_state._bank_data = { "copper_ore": 100, "iron_ore": 50 }
    assert world_state.get_amount_of_item_in_bank("copper_ore") == 100
    world_state.update_bank_data([
      {
        "code": "copper_ore",
        "quantity": 10
      }
    ])
    assert world_state.get_amount_of_item_in_bank("copper_ore") == 10
    assert world_state.get_amount_of_item_in_bank("iron_ore") == 0

# Other Checkers
#get_task_master_locations
def test__get_task_master_locations(world_state: WorldState):
    assert world_state.get_task_master_locations()
 