import asyncio
from action import *
from action_factories import *
from condition_factories import *
from control_factories import *
from api import APIClient
from scheduler import ActionScheduler
from planner import ActionPlanner, ActionIntent, Intention
import logging
import json


def get_token() -> str:
    with open("C:/Users/Cameron/Desktop/Artifacts/token.txt", 'r') as f:
        TOKEN = f.read().strip()

    return TOKEN

async def get_bank_data(api: APIClient, query_api: bool = False) -> List[Dict[str, Any]]:
    # Get all bank data
    bank_data = await api.get_bank(1)
    all_bank_data: List[Dict[str, Any]] = bank_data.get("data")

    for i in range(2, bank_data.get("pages", 1)):
        bank_data = await api.get_maps(i)
        all_bank_data.extend(bank_data.get("data"))

    with open('bank_data.json', 'w') as f:
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

        with open('item_data.json', 'w') as f:
            f.write(json.dumps(all_item_data))
    else:
        with open('item_data.json', 'r') as f:
            all_item_data = json.loads(f.read())

    # Parse it
    items = {}
    for item in all_item_data:
        item_code = item["code"]
        items[item_code] = item

    return items 

async def get_map_data(api: APIClient, query_api: bool = False) -> Dict[str, Dict]:
    if query_api:
        # Get all map data
        map_data = await api.get_maps(1)
        all_map_data: List[Dict[str, Any]] = map_data.get("data")

        for i in range(2, map_data.get("pages", 1)):
            map_data = await api.get_maps(i)
            all_map_data.extend(map_data.get("data"))

        with open('map_data.json', 'w') as f:
            f.write(json.dumps(all_map_data))
    else:
        with open('map_data.json', 'r') as f:
            all_map_data = json.loads(f.read())

    # Parse it
    interactions: Dict[str, Dict] = {
        "resource": {},
        "monster": {},
        "workshop": {},
        "bank": {},
        "grand_exchange": {},
        "tasks_master": {},
        "npc": {},
    }

    for map_tile in all_map_data:
        content_data = map_tile.get("interactions", {}).get("content", None)

        if content_data:
            content_type = content_data["type"]
            content_code = content_data["code"]
            x, y = map_tile["x"], map_tile["y"]
            interactions[content_type].setdefault(content_code, []).append((x, y))

    return interactions 

async def get_resource_data(api: APIClient, query_api: bool = False) -> Dict[str, Dict]:
    if query_api:
        # Get all resource data
        resource_data = await api.get_resources(1)
        all_resource_data: List[Dict[str, Any]] = resource_data.get("data")

        for i in range(2, resource_data.get("pages", 1)):
            resource_data = await api.get_resources(i)
            all_resource_data.extend(resource_data.get("data"))

        with open('resource_data.json', 'w') as f:
            f.write(json.dumps(all_resource_data))
    else:
        with open('resource_data.json', 'r') as f:
            all_resource_data = json.loads(f.read())

    # Parse it
    resource_sources = {}
    for resource in all_resource_data:
        for drop in resource["drops"]:
            resource_sources.setdefault(drop["code"], set()).add(resource["code"])

    return resource_sources 

async def get_monster_data(api: APIClient, query_api: bool = False) -> Dict[str, Dict]:
    if query_api:
        # Get all resource data
        monster_data = await api.get_monsters(1)
        all_monster_data: List[Dict[str, Any]] = monster_data.get("data")

        for i in range(2, monster_data.get("pages", 1)):
            monster_data = await api.get_monsters(i)
            all_monster_data.extend(monster_data.get("data"))

        with open('monster_data.json', 'w') as f:
            f.write(json.dumps(all_monster_data))
    else:
        with open('monster_data.json', 'r') as f:
            all_monster_data = json.loads(f.read())

    # Parse it
    monster_sources = {}
    for monster in all_monster_data:
        for drop in monster["drops"]:
            monster_sources.setdefault(drop["code"], set()).add(monster["code"])

    return monster_sources 

async def main():
    logging.basicConfig(
        filename="artifacts.log",
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
    bank_data = await get_bank_data(api, GET_API_DATA)
    item_data = await get_item_data(api, GET_API_DATA)
    interactions = await get_map_data(api, GET_API_DATA)
    resource_drop_data = await get_resource_data(api, GET_API_DATA)
    monster_drop_data = await get_monster_data(api, GET_API_DATA)

    world_data = {
        'interactions': interactions,
        'items': item_data,
        'resources': resource_drop_data,
        'monsters': monster_drop_data
    }

    scheduler = ActionScheduler(api)
    planner = ActionPlanner(world_data)

    characters = await api.get_characters()
    for character in characters["data"]:
        scheduler.add_character(character, bank_data)

    while True:
        c = await asyncio.to_thread(input, "Enter Command: ")
        parse_input(planner, scheduler, c, world_data)
    

def parse_input(planner: ActionPlanner, scheduler: ActionScheduler, c: str, interactions: Dict):
    data = c.split() 
    character_name = data[0].title().strip()
    action_kw = data[1].lower().strip()

    agent = scheduler.agents[character_name]

    try:
        args = data[2:]
    except:
        args = []

    match action_kw:
        case "status":
            scheduler.get_status()
            
        case 'move':
            action = move(prev_location=True) if args[0] == "prev" else move(x=args[0], y=args[1])
            scheduler.queue_action_node(character_name, action)

        case 'fight':
            scheduler.queue_action_node(character_name, fight())

        case 'rest':
            scheduler.queue_action_node(character_name, rest())

        case 'gather':
            if len(args) == 1:
                resource = args[0]
                action = planner.plan_intent(agent, ActionIntent(Intention.GATHER, params={"resource": resource}))
            else:
                action = planner.plan_intent(agent, ActionIntent(Intention.GATHER))
            
            scheduler.queue_action_node(character_name, action)

        case 'equip':                
            action = equip(items_code=args[0], item_slot=args[1])
            scheduler.queue_action_node(character_name, action)

        case 'unequip':
            action = unequip(item_slot=args[0])
            scheduler.queue_action_node(character_name, action)

        case 'craft':
            action = craft(item_code=args[0], quantity=args[1])
            scheduler.queue_action_node(character_name, action)

        case 'bank':
            if args[0] == 'deposit' and args[1] == 'gold':
                params_dict = { "quantity": args[2] }
                action = Action(CharacterAction.BANK_DEPOSIT_GOLD, params_dict)
            elif args[0] == 'withdraw' and args[1] == 'gold':
                params_dict = { "quantity": args[2] }
                action = Action(CharacterAction.BANK_WITHDRAW_GOLD, params_dict)
            elif args[0] == 'deposit' and args[1] == 'item':
                if args[2] == "all":
                    params_dict = { "preset": "all"  }
                else:
                    params_dict = { "items": [] }
                    for i in range(2, len(args), 2):
                        params_dict["items"].append({ "code": args[i], "quantity": args[i + 1] })

                action = Action(CharacterAction.BANK_DEPOSIT_ITEM, params_dict)
            elif args[0] == 'withdraw' and args[1] == 'item':
                params_dict = { "items": [] }
                for i in range(2, len(args), 2):
                    params_dict["items"].append({ "code": args[i], "quantity": args[i + 1] })

                action = Action(CharacterAction.BANK_WITHDRAW_ITEM, params_dict)
            
            scheduler.queue_action_node(character_name, action)

        # create combo actions
        case 'gather_endless':
            action_group = group(
                gather(until=cond(ActionCondition.INVENTORY_FULL)),
                move(x=4, y=1),
                bank_all_items(),
                move(prev_location=True),
                until=cond(ActionCondition.FOREVER)
            )
            scheduler.queue_action_node(character_name, action_group)

        case 'fight_endless':
            action_group = group(
                group(
                    fight(),
                    rest(),
                    until=cond(ActionCondition.INVENTORY_FULL)
                ),
                move(x=4, y=1),
                bank_all_items(),
                move(prev_location=True),
                until=cond(ActionCondition.FOREVER)
            )
            scheduler.queue_action_node(character_name, action_group)

        # tests
        case 'test':
            node = REPEAT(
                IF(
                    (
                        cond(ActionCondition.BANK_HAS_ITEM_OF_QUANTITY, item_code='copper_ore', quantity=10),                    
                        group(
                            planner.plan_intent(agent, ActionIntent(Intention.WITHDRAW, item="copper_ore", quantity=10)),
                            planner.plan_intent(agent, ActionIntent(Intention.CRAFT, item="copper_bar", quantity=1))
                        )
                    ),
                    fail_path=planner.plan_intent(agent, ActionIntent(Intention.FIGHT, monster="chicken"))
                ), 
                until=cond(ActionCondition.FOREVER)
            )

            scheduler.queue_action_node(character_name, node)


if __name__ == '__main__':
    asyncio.run(main())
