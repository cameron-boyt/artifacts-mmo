import asyncio
from action import *
from action_factories import *
from condition_factories import *
from control_factories import *
from api import APIClient
from scheduler import ActionScheduler
import logging


def get_token() -> str:
    with open("C:/Users/Cameron/Desktop/Artifacts/token.txt", 'r') as f:
        TOKEN = f.read().strip()

    return TOKEN


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
    scheduler = ActionScheduler(api)

    bank_data = (await api.get_bank_items())["data"]
    map_data = await api.get_maps()

    characters = await api.get_characters()
    for character in characters["data"]:
        scheduler.add_character(character, bank_data, map_data)

    while True:
        c = await asyncio.to_thread(input, "Enter Command: ")
        parse_input(scheduler, c)
         
#


def parse_input(scheduler: ActionScheduler, c: str):
    data = c.split() 
    character_name = data[0]   
    action_kw = data[1]

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
            scheduler.queue_action_node(character_name, gather())

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
                move(x=0, y=1),
                group(

                    group(
                        fight(),
                        rest(),
                        until=OR(
                            cond(ActionCondition.INVENTORY_FULL),
                            cond(ActionCondition.BANK_HAS_ITEM_OF_QUANTITY, item_code="copper_ore", quantity=20)
                        )
                    ),
                    move(x=4, y=1),
                    bank_all_items(),
                    move(prev_location=True),
                    until=OR(cond(ActionCondition.INVENTORY_FULL), cond(ActionCondition.BANK_HAS_ITEM_OF_QUANTITY, item_code="copper_ore", quantity=20))
                ),
                move(x=1, y=5),
                craft(item_code="copper_bar", quantity=1),
                until=cond(ActionCondition.FOREVER)
            )
            scheduler.queue_action_node(character_name, action_group)

        # tests
        case test:
            node = REPEAT(
                IF(
                    (
                        cond(ActionCondition.BANK_HAS_ITEM_OF_QUANTITY, item_code='copper_ore', quantity=2),                    
                        group(
                            move(x=1, y=5),
                            bank_withdraw_item(item_code='copper_ore', quantity=10),
                            craft(item_code="copper_bar", quantity=1)
                        )
                    ),
                    fail_path=group(
                        move(x=0, y=1),
                        fight(),
                        rest()
                    )
                ), 
                until=cond(ActionCondition.FOREVER)
            )

            scheduler.queue_action_node(character_name, node)


if __name__ == '__main__':
    asyncio.run(main())
