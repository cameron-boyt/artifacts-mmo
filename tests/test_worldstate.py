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
def test__is_an_item__is_item(world_state: WorldState):
    assert world_state.is_an_item("copper_ore")

def test__is_an_item__not_item(world_state: WorldState):
    assert not world_state.is_an_item("fake")

#is_equipment
def test__is_equipment__is_equipment(world_state: WorldState):
    assert world_state.is_equipment("copper_pickaxe")

def test__is_equipment__is_resource(world_state: WorldState):
    assert not world_state.is_equipment("copper_ore")

def test__is_equipment__is_monster(world_state: WorldState):
    assert not world_state.is_equipment("chicken")

def test__is_equipment__is_fake(world_state: WorldState):
    assert not world_state.is_equipment("fake")

#get_item_info
def test__get_item_info__is_item(world_state: WorldState):
    assert world_state.get_item_info("copper_ore")

def test__get_item_info__not_item(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_item_info("chicken")

def test__get_item_info__is_fake(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_item_info("fake")  

#item_is_craftable
def test__item_is_craftable__is_craftable(world_state: WorldState):
    assert world_state.item_is_craftable("copper_bar")
    
def test__item_is_craftable__not_craftable(world_state: WorldState):
    assert not world_state.item_is_craftable("copper_ore")

def test__item_is_craftable__is_monster(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.item_is_craftable("chicken")

def test__item_is_craftable__is_fake(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.item_is_craftable("fake")
    
#get_crafting_materials_for_item
def test__get_crafting_materials_for_item__is_craftable(world_state: WorldState):
    assert world_state.get_crafting_materials_for_item("copper_bar") == [{ "code": "copper_ore", "quantity": 10 }]

def test__get_crafting_materials_for_item__not_craftable(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_crafting_materials_for_item("copper_ore")

def test__get_crafting_materials_for_item__is_fake(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_crafting_materials_for_item("fake")

#get_workshop_for_item
def test__get_workshop_for_item__is_craftable(world_state: WorldState):
    assert world_state.get_workshop_for_item("copper_bar") == "mining"

def test__get_workshop_for_item__not_craftable(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_workshop_for_item("copper_ore")

def test__get_workshop_for_item__is_fake(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_workshop_for_item("fake")

#get_workshop_location
def test__get_workshop_locations__real_skill(world_state: WorldState):
    assert world_state.get_workshop_locations("mining")

def test__get_workshop_locations__fake_skill(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_workshop_locations("fake")

#get_equip_slot_for_item
def test__get_equip_slot_for_item__is_equipment(world_state: WorldState):
    assert world_state.get_equip_slot_for_item("copper_pickaxe") == "weapon"
    
def test__get_equip_slot_for_item__not_equipment(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_equip_slot_for_item("copper_ore")
        
def test__get_equip_slot_for_item__is_fake(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_equip_slot_for_item("fake")
    
#get_best_tool_for_skill_in_bank
def test__get_best_tool_for_skill_in_bank(world_state: WorldState):
    assert False
    
#get_best_weapon_for_monster_in_bank
def test__get_best_weapon_for_monster_in_bank(world_state: WorldState):
    assert False
    
# Resource Checkers
#is_a_resource
def test__is_a_resource__is_resource(world_state: WorldState):
    assert world_state.is_a_resource("copper_ore")

def test__is_a_resource__not_resource(world_state: WorldState):
    assert not world_state.is_a_resource("chicken")

def test__is_a_resource__is_fake(world_state: WorldState):
    assert not world_state.is_a_resource("fake")

#get_resource_at_location
def test__get_resource_at_location__resource_present(world_state: WorldState):
    assert world_state.get_resource_at_location(-1, 0) == {'apple', 'ash_wood', 'sap'}
    
def test__get_resource_at_location__resource_absent(world_state: WorldState):
    assert world_state.get_resource_at_location(0, 0) is None
    
def test__get_resource_at_location__map_out_of_bounds(world_state: WorldState):
    assert world_state.get_resource_at_location(999, 999) is None

#get_locations_of_resource
def test__get_locations_of_resource__is_resource(world_state: WorldState):
    assert world_state.get_locations_of_resource("copper_ore") == {(2, 0)}
    
def test__get_locations_of_resource__not_gatherable(world_state: WorldState):
    assert world_state.get_locations_of_resource("copper_bar") == []
    
def test__get_locations_of_resource__not_resource(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_locations_of_resource("copper_helmet")  
        
def test__get_locations_of_resource__is_fake(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_locations_of_resource("fake")  

#get_gather_skill_for_resource
def test__get_gather_skill_for_resource__is_resource(world_state: WorldState):
    assert world_state.get_gather_skill_for_resource("copper_ore") == "mining"
    
def test__get_gather_skill_for_resource__not_resource(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_gather_skill_for_resource("copper_helmet")
        
def test__get_gather_skill_for_resource__is_fake(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_gather_skill_for_resource("fake")
    
# Monster Checkers
#is_a_monster
def test__is_a_monster__is_monster(world_state: WorldState):
    assert world_state.is_a_monster("chicken")

def test__is_a_monster__not_monster(world_state: WorldState):
    assert not world_state.is_a_monster("copper_bar")

def test__is_a_monster__is_fake(world_state: WorldState):
    assert not world_state.is_a_monster("fake")

#get_monster_info
def test__get_monster_info__is_monster(world_state: WorldState):
    assert world_state.get_monster_info("chicken")
    
def test__get_monster_info__not_resource(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_monster_info("copper_ore")
        
def test__get_monster_info__is_fake(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_monster_info("fake")

#get_monster_at_location
def test__get_monster_at_location__monster_present(world_state: WorldState):
    assert world_state.get_monster_at_location(0, 1) == "chicken"
    
def test__get_monster_at_location__monster_absent(world_state: WorldState):
    assert world_state.get_monster_at_location(0, 0) is None
    
def test__get_monster_at_location__map_out_of_bounds(world_state: WorldState):
    assert world_state.get_monster_at_location(999, 999) is None

#get_locations_of_monster
def test__get_locations_of_monster__is_monster(world_state: WorldState):
    assert world_state.get_locations_of_monster("cow") == {(0, 2)}
    
def test__get_locations_of_monster__not_monster(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_locations_of_monster("copper_bar")
        
def test__get_locations_of_monster_is_fake(world_state: WorldState):
    with pytest.raises(KeyError):
        world_state.get_locations_of_monster("fake")  
    
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
 