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

def test_bank_missing_item_returns_0(world_state: WorldState):
    assert world_state.get_amount_of_item_in_bank("does_not_exist") == 0

def test_reservation_reduces_available(world_state: WorldState):
    world_state._bank_data = {"copper_ore": 100}
    assert world_state.get_amount_of_item_in_bank("copper_ore") == 100
    rid = world_state.reserve_bank_items([{"code":"copper_ore","quantity":30}])
    assert world_state.get_amount_of_item_in_bank("copper_ore") == 70
    world_state.clear_bank_reservation(rid)
    assert world_state.get_amount_of_item_in_bank("copper_ore") == 100
