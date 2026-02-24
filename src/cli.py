import asyncio
import logging
import json
import re

from src.action import *
from src.action_factories import *
from src.condition_factories import *
from src.control_factories import *
from src.api import APIClient
from src.scheduler import ActionScheduler
from src.planner import ActionPlanner, ActionIntent, Intention
from src.worldstate import WorldState
from src.goalcoordinator import GoalCoordinator
from src.character import CharacterAgent

def get_token() -> str:
    with open("token.txt", 'r') as f:
        TOKEN = f.read().strip()

    return TOKEN

async def get_bank_data(api: APIClient, query_api: bool = False) -> List[Dict[str, Any]]:
    # Get all bank data
    bank_data = await api.get_bank(1)
    all_bank_data: List[Dict[str, Any]] = bank_data.get("data")

    for i in range(2, bank_data.get("pages", 1)):
        bank_data = await api.get_bank(i)
        all_bank_data.extend(bank_data.get("data"))

    with open('data/bank_data.json', 'w') as f:
        f.write(json.dumps(all_bank_data))

    return all_bank_data

async def get_item_data(api: APIClient, query_api: bool = False) -> Dict[str, Dict]:
    if query_api:
        # Get all resource data
        item_data = await api.get_items(1)
        all_item_data: List[Dict[str, Any]] = item_data.get("data")

        for i in range(2, item_data.get("pages", 1)):
            item_data = await api.get_items(i)
            all_item_data.extend(item_data.get("data"))

        with open('data/item_data.json', 'w') as f:
            f.write(json.dumps(all_item_data))
    else:
        with open('data/item_data.json', 'r') as f:
            all_item_data = json.loads(f.read())

    return all_item_data

async def get_map_data(api: APIClient, query_api: bool = False) -> Dict[str, Dict]:
    if query_api:
        # Get all map data
        map_data = await api.get_maps(1)
        all_map_data: List[Dict[str, Any]] = map_data.get("data")

        for i in range(2, map_data.get("pages", 1)):
            map_data = await api.get_maps(i)
            all_map_data.extend(map_data.get("data"))

        with open('data/map_data.json', 'w') as f:
            f.write(json.dumps(all_map_data))
    else:
        with open('data/map_data.json', 'r') as f:
            all_map_data = json.loads(f.read())

    return all_map_data

async def get_resource_data(api: APIClient, query_api: bool = False) -> Dict[str, Dict]:
    if query_api:
        # Get all resource data
        resource_data = await api.get_resources(1)
        all_resource_data: List[Dict[str, Any]] = resource_data.get("data")

        for i in range(2, resource_data.get("pages", 1)):
            resource_data = await api.get_resources(i)
            all_resource_data.extend(resource_data.get("data"))

        with open('data/resource_data.json', 'w') as f:
            f.write(json.dumps(all_resource_data))
    else:
        with open('data/resource_data.json', 'r') as f:
            all_resource_data = json.loads(f.read())

    return all_resource_data

async def get_monster_data(api: APIClient, query_api: bool = False) -> Dict[str, Dict]:
    if query_api:
        # Get all resource data
        monster_data = await api.get_monsters(1)
        all_monster_data: List[Dict[str, Any]] = monster_data.get("data")

        for i in range(2, monster_data.get("pages", 1)):
            monster_data = await api.get_monsters(i)
            all_monster_data.extend(monster_data.get("data"))

        with open('data/monster_data.json', 'w') as f:
            f.write(json.dumps(all_monster_data))
    else:
        with open('data/monster_data.json', 'r') as f:
            all_monster_data = json.loads(f.read())

    return all_monster_data

async def get_character_data(api: APIClient) -> List[dict]:
    characters = await api.get_characters()
    character_data = characters["data"]
    
    with open('data/character_data.json', 'w') as f:
        f.write(json.dumps(character_data))

    return character_data

async def main():
    logging.basicConfig(
        filename="logs/artifacts.log",
        filemode='a',
        format='%(asctime)s %(levelname)-8s- %(message)s',
        level=logging.DEBUG,
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    for logger_name in ["httpx", "httpcore", "h11", "h2"]:
        log = logging.getLogger(logger_name)
        log.setLevel(logging.WARNING)
        log.propagate = False

    TOKEN = get_token()
    BASE_URL = "https://api.artifactsmmo.com/"

    api = APIClient(base_url=BASE_URL, api_key=TOKEN)

    GET_API_DATA = False
    bank_data = await get_bank_data(api, True)
    item_data = await get_item_data(api, GET_API_DATA)
    map_data = await get_map_data(api, GET_API_DATA)
    resource_data = await get_resource_data(api, GET_API_DATA)
    monster_data = await get_monster_data(api, GET_API_DATA)
    character_data = await get_character_data(api)

    world_state = WorldState(bank_data, map_data, item_data, resource_data, monster_data)
    scheduler = ActionScheduler()
    planner = ActionPlanner(world_state)
    coordinator = GoalCoordinator(world_state, planner, scheduler)

    scheduler.register_coordinator(coordinator)

    for character in character_data:
        agent = CharacterAgent(character, world_state, api, scheduler)
        scheduler.add_character(agent)

    # Run some starting commands
    # parse_input(planner, scheduler, world_state, "Maett complete-tasks monsters")
    # parse_input(planner, scheduler, world_state, "Oscar complete-tasks monsters")
    # parse_input(planner, scheduler, world_state, "Cameron craft-or-gather copper_bar max")
    # parse_input(planner, scheduler, world_state, "Jayne gather copper_ore")
    # parse_input(planner, scheduler, world_state, "Moira gather copper_ore")

    scheduler.agents["Cameron"].set_mode_leader()
    # scheduler.agents["Moira"].set_mode_support()
    # scheduler.agents["Jayne"].set_mode_support()

    while True:
        c = await asyncio.to_thread(input, "Enter Command: ")
        parse_input(planner, scheduler, world_state, c)
    

def parse_input(planner: ActionPlanner, scheduler: ActionScheduler, world: WorldState, c: str):
    data = c.split() 

    try:
        character_name = data[0].title().strip()
        action_kw = data[1].lower().strip()
    except:
        print("bad input")
        return

    try:
        agent = scheduler.agents[character_name]
    except:
        print("not a char")
        return
    
    try:
        args = data[2:]
    except:
        args = []

    match action_kw:
        case "status":
            scheduler.get_status()

        case "abort":
            agent.set_abort_actions()
            
        case 'move':
            if len(args) == 1 and args[0] == "prev":
                node = planner.plan(ActionIntent(Intention.MOVE, previous=True))
            elif len(args) == 2:
                node = planner.plan(ActionIntent(Intention.MOVE, x=args[0], y=args[1]))
            else: 
                return

            scheduler.queue_action_node(character_name, node)

        case 'rest':
            node = planner.plan(ActionIntent(Intention.REST))
            scheduler.queue_action_node(character_name, node)

        case 'equip':
            if len(args) == 2:
                if world.is_an_item(args[0]):
                    node = planner.plan(ActionIntent(Intention.EQUIP, items=args[0], slot=args[1]))
                else:
                    print("not an item")
            else:
                return
            
            scheduler.queue_action_node(character_name, node)

        case 'unequip':
            if len(args) == 1:
                node = planner.plan(ActionIntent(Intention.UNEQUIP, slot=args[0]))
            else:
                return
            
            scheduler.queue_action_node(character_name, node)

        case 'craft':
            if not world.is_an_item(args[0]):
                print("not an item")
                return
            
            if not world.item_is_craftable(args[0]):
                print("item not craftable")
                return
            
            if len(args) == 2:
                if args[1] == "max":
                    node = planner.plan(ActionIntent(Intention.CRAFT, item=args[0], as_many_as_possible=True))
                else:
                    node = planner.plan(ActionIntent(Intention.CRAFT, item=args[0], quantity=args[1]))
            elif len(args) == 1:
                node = planner.plan(ActionIntent(Intention.CRAFT, item=args[0], quantity=1))
            else:
                return
            
            scheduler.queue_action_node(character_name, node)

        case 'bank':
            if args[0] == 'deposit' and args[1] == 'gold':
                node = planner.plan(ActionIntent(Intention.DEPOSIT_GOLD, quantity=int(args[2])))
            elif args[0] == 'withdraw' and args[1] == 'gold':
                node = planner.plan(ActionIntent(Intention.WITHDRAW_GOLD, quantity=int(args[2])))
            elif args[0] == 'deposit' and args[1] == 'item':
                if args[2] == "all":
                    node = planner.plan(ActionIntent(Intention.DEPOSIT_ITEMS, preset="all"))
                else:
                    items = [] 
                    for i in range(2, len(args), 2):
                       items.append({ "code": args[i], "quantity": args[i + 1] })

                    node = planner.plan(ActionIntent(Intention.DEPOSIT_ITEMS, items=items))
            elif args[0] == 'withdraw' and args[1] == 'item':
                items = [] 
                for i in range(2, len(args), 2):
                    items.append({ "code": args[i], "quantity": args[i + 1] })

                node = planner.plan(ActionIntent(Intention.WITHDRAW_ITEMS, items=items))
            
            scheduler.queue_action_node(character_name, node)

        # create combo actions
        case 'gather':
            if len(args) != 1:
                return
            
            if not world.is_a_resource(args[0]): 
                print("not a resource")
                return
                
            node = planner.plan(ActionIntent(Intention.GATHER_RESOURCES, resource=args[0], condition=cond(ActionCondition.FOREVER)))
            scheduler.queue_action_node(character_name, node)

        case 'fight':
            if len(args) != 1:
                return
            
            if not world.is_a_monster(args[0]): 
                print("not a monster")
                return
                
            node = planner.plan(ActionIntent(Intention.FIGHT_MONSTERS, monster=args[0], condition=cond(ActionCondition.FOREVER)))
            scheduler.queue_action_node(character_name, node)

        case 'smart-craft':
            if len(args) == 0 or len(args) > 2:
                return 
            
            if len(args) > 0:
                if not world.is_an_item(args[0]):
                    print("not an item")
                    return
                
                if not world.item_is_craftable(args[0]):
                    print("item not craftable")
                    return
                
                item = args[0]
                quantity = '1'
            
            if len(args) == 2:
                quantity = args[1]
          
            if re.match(r'\d+', quantity):
                quantity = int(quantity)
                node = planner.plan(ActionIntent(Intention.COLLECT_THEN_CRAFT, item=item, quantity=quantity))
            elif re.match(r'max', quantity):
                node = planner.plan(ActionIntent(Intention.COLLECT_THEN_CRAFT, item=item, craft_max=True))
            else:
                raise Exception("Invalid quantity argument.")
            
            scheduler.queue_action_node(character_name, node)

        case 'craft-or-gather':
            if len(args) != 2:
                return
            
            if not world.is_an_item(args[0]):
                print("not an item")
                return
                
            if not world.item_is_craftable(args[0]):
                print("item not craftable")
                return
            
            item = args[0]

            if re.match(r'\d+', args[1]):
                quantity = int(args[1])
                node = planner.plan(ActionIntent(Intention.CRAFT_OR_GATHER_INTERMEDIARIES, item=item, quantity=quantity, gather_intermediaries=True))
            elif re.match(r'max', args[1]):
                node = planner.plan(ActionIntent(Intention.CRAFT_OR_GATHER_INTERMEDIARIES, item=item, craft_max=True, gather_intermediaries=True))
            else:
                raise Exception("Invalid quantity argument.")
            
            scheduler.queue_action_node(character_name, node)

        case 'complete-tasks':
            if len(args) != 1:
                return
            
            if args[0] == "monsters":
                node = planner.plan(ActionIntent(Intention.COMPLETE_TASKS, type="monsters"))
            elif args[0] == "items":
                node = planner.plan(ActionIntent(Intention.COMPLETE_TASKS, type="items"))
            else:
                return
            
            scheduler.queue_action_node(character_name, node)

        case 'craft-until-level':
            if len(args) != 2:
                return
            
            item = args[0]
            level = int(args[1])
            node = planner.plan(ActionIntent(Intention.CRAFT_UNTIL_LEVEL, item=item, level=level))
            scheduler.queue_action_node(character_name, node)


if __name__ == '__main__':
    asyncio.run(main())
