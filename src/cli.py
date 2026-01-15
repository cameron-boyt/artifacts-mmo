import asyncio
from action import Action, ActionGroup, CharacterAction, ActionCondition
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
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    TOKEN = get_token()
    BASE_URL = "https://api.artifactsmmo.com/"

    api = APIClient(base_url=BASE_URL, api_key=TOKEN)
    scheduler = ActionScheduler(api)

    characters = await api.get_characters()
    for character in characters["data"]:
        scheduler.add_character(character)

    while True:
        c = await asyncio.to_thread(input, "Enter Command: ")
        parse_input(scheduler, c)
         

def parse_input(scheduler: ActionScheduler, c: str):
    data = c.split() 
    character_name = data[0]   
    action_kw = data[1]

    try:
        args = data[2:]
    except:
        args = []

    match action_kw:
        case 'move':
            params_dict = { "x": args[0], "y": args[1] }
            action = Action(CharacterAction.MOVE, params_dict)
            scheduler.queue_action(character_name, action)

        case 'fight':
            action = Action(CharacterAction.FIGHT)
            scheduler.queue_action(character_name, action)

        case 'rest':
            action = Action(CharacterAction.REST)
            scheduler.queue_action(character_name, action)

        case 'gather':
            action = Action(CharacterAction.GATHER)
            scheduler.queue_action(character_name, action)

        # create combo actions
        case 'gather_endless':
            action_group = ActionGroup([
                Action(CharacterAction.GATHER, repeat=True, repeat_until=ActionCondition.INVENTORY_FULL),
                Action(CharacterAction.MOVE, params={ "x": 4, "y": 1 }),
                Action(CharacterAction.BANK, params={ "bank_preset": "all" }),
                Action(CharacterAction.MOVE, params={ "x": -1, "y": 0 })
            ], repeat=True, repeat_until=ActionCondition.FOREVER)
            scheduler.queue_action(character_name, action_group)

        case 'fight_endless':
            action_group = ActionGroup([
                ActionGroup([
                    Action(CharacterAction.FIGHT),
                    Action(CharacterAction.REST)
                ], repeat=True, repeat_until=ActionCondition.INVENTORY_FULL),
                Action(CharacterAction.MOVE, params={ "x": 4, "y": 1 }),
                Action(CharacterAction.BANK, params={ "bank_preset": "all" }),
                Action(CharacterAction.MOVE, params={ "x": 0, "y": 1 })
            ], repeat=True, repeat_until=ActionCondition.FOREVER)
            scheduler.queue_action(character_name, action_group)


if __name__ == '__main__':
    asyncio.run(main())
