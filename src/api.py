import httpx
from typing import List, Dict
import logging
from dataclasses import dataclass

@dataclass 
class ActionResult:
    response: dict
    """Data response from the action request."""
    success: bool
    """If the action was successful."""
    cascade: bool = False
    """If the result of failure should cascade through the action and cancel all remaining items in the queue."""

class APIClient:
    """Handles all HTTP communication with the remote server."""
    def __init__(self, base_url: str, api_key: str):
        self.logger = logging.getLogger(__name__)

        self._base_url = base_url
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = httpx.AsyncClient(base_url=self._base_url, headers=self._headers)

    ## Get Character/Player Data
    async def get_characters(self) -> dict:
        response = await self._client.get(f"/my/characters")
        response.raise_for_status()
        return response.json()

    async def get_character_state(self, character_name: str) -> dict:
        response = await self._client.get(f"/characters/{character_name}/state")
        response.raise_for_status()
        return response.json()
    
    async def get_bank(self, page=1) -> dict:
        response = await self._client.get(f"/my/bank/items?page={page}&size=100")
        response.raise_for_status()
        return response.json()
    
    ## Get World Encyclopedia Data
    async def get_items(self, page=1) -> dict:
        response = await self._client.get(f"/items?page={page}&size=100")
        response.raise_for_status()
        return response.json()
    
    async def get_maps(self, page=1) -> dict:
        response = await self._client.get(f"/maps?page={page}&size=100")
        response.raise_for_status()
        return response.json()
    
    async def get_resources(self, page=1) -> dict:
        response = await self._client.get(f"/resources?page={page}&size=100")
        response.raise_for_status()
        return response.json()
    
    async def get_monsters(self, page=1) -> dict:
        response = await self._client.get(f"/monsters?page={page}&size=100")
        response.raise_for_status()
        return response.json()

    ## API General Requests
    async def move(self, character_name: str, x: int, y: int) -> ActionResult:
        payload = { "x": x, "y": y }
        response = await self._client.post(f"/my/{character_name}/action/move", json=payload)
        return await self.handle_status(response)

    async def fight(self, character_name: str) -> ActionResult:
        response = await self._client.post(f"/my/{character_name}/action/fight")
        return await self.handle_status(response)

    async def rest(self, character_name: str) -> ActionResult:
        response = await self._client.post(f"/my/{character_name}/action/rest")
        return await self.handle_status(response)

    async def gather(self, character_name: str) -> ActionResult:
        response = await self._client.post(f"/my/{character_name}/action/gathering")
        return await self.handle_status(response)

    async def bank_deposit_item(self, character_name: str, items: List[Dict[str, str | int]]) -> ActionResult:
        response = await self._client.post(f"/my/{character_name}/action/bank/deposit/item", json=items)
        return await self.handle_status(response)

    async def bank_withdraw_item(self, character_name: str, items: List[Dict[str, str | int]]) -> ActionResult:
        response = await self._client.post(f"/my/{character_name}/action/bank/withdraw/item", json=items)
        return await self.handle_status(response)

    async def bank_deposit_gold(self, character_name: str, quantity: int) -> ActionResult:
        response = await self._client.post(f"/my/{character_name}/action/bank/deposit/gold", json=quantity)
        return await self.handle_status(response)

    async def bank_withdraw_gold(self, character_name: str, quantity: int) -> ActionResult:
        response = await self._client.post(f"/my/{character_name}/action/bank/withdraw/gold", json=quantity)
        return await self.handle_status(response)

    async def unequip(self, character_name: str, item_slot: str) -> ActionResult:
        payload = { "slot": item_slot }
        response = await self._client.post(f"/my/{character_name}/action/unequip", json=payload)
        return await self.handle_status(response)

    async def craft(self, character_name: str, item_code: str, quantity: int = 1) -> ActionResult:
        payload = { "code": item_code, "quantity": quantity }
        response = await self._client.post(f"/my/{character_name}/action/crafting", json=payload)
        return await self.handle_status(response)

    async def equip(self, character_name: str, item_code: str, item_slot: str, ) -> ActionResult:
        payload = { "code": item_code, "slot": item_slot }
        response = await self._client.post(f"/my/{character_name}/action/equip", json=payload)
        return await self.handle_status(response)
    
    async def handle_status(self, response: httpx.Response) -> ActionResult:
        data = response.json()
        cascade = True

        match response.status_code:
            case 200:
                # All good
                success = True
            
            case 404:
                # Not found
                success = False
            
            case 422:
                # Invalid payload
                success = False
            
            case 478:
                # Missing required items

                self.logger.error("Character missing required items for action.")
                success = False

            case 490:
                # Character already at destination
                self.logger.warning("Character already at destination.")
                success = False
                cascade = False

            case 497:
                # Character inventory is full
                self.logger.warning("Character inventory is full.")
                success = False

            case 499:
                # Character on cooldown
                self.logger.warning("Character is on cooldown.")
                success = False

            case 598:
                # No resource/monster on map
                self.logger.warning("No resource/monster on map.")
                success = False

            case _:
                raise Exception(f"fuck; saw {response.status_code}")
            
        return ActionResult(data, success, cascade)