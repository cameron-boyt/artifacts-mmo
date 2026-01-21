import httpx
from typing import List, Dict
import logging

class APIClient:
    """Handles all HTTP communication with the remote server."""
    def __init__(self, base_url: str, api_key: str):
        self.logger = logging.getLogger(__name__)

        self._base_url = base_url
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = httpx.AsyncClient(base_url=self._base_url, headers=self._headers)

    async def get_characters(self) -> dict:
        response = await self._client.get(f"/my/characters")
        response.raise_for_status()
        return response.json()

    async def get_character_state(self, character_name: str) -> dict:
        response = await self._client.get(f"/characters/{character_name}/state")
        response.raise_for_status()
        return response.json()
    
    async def get_maps(self) -> dict:
        response = await self._client.get(f"/maps")
        response.raise_for_status()
        return response.json()
    
    async def get_bank_items(self) -> dict:
        response = await self._client.get(f"/my/bank/items")
        response.raise_for_status()
        return response.json()
    
    async def handle_status(self, response: httpx.Response):
        match response.status_code:
            case 200:
                # All good
                return response.json()
            
            case 422:
                # Invalid payload
                raise Exception("fuck")
            
            case 404:
                # Not found
                raise Exception("fuck")

            case 490:
                # Character already at destination
                self.logger.warning("Character already at destination")
                pass

            case 497:
                # Character inventory is full
                self.logger.warning("Character inventory is full")
                pass

            case 499:
                # Character on cooldown
                self.logger.warning("Character is on cooldown")
                pass

            case 598:
                # No resource/monster on map
                self.logger.warning("No resource/monster on map")
                pass

            case _:
                raise Exception("fuck")

    async def move(self, character_name: str, x: int, y: int) -> dict:
        payload = { "x": x, "y": y }
        response = await self._client.post(f"/my/{character_name}/action/move", json=payload)
        return await self.handle_status(response)

    async def fight(self, character_name: str) -> dict:
        response = await self._client.post(f"/my/{character_name}/action/fight")
        return await self.handle_status(response)

    async def rest(self, character_name: str) -> dict:
        response = await self._client.post(f"/my/{character_name}/action/rest")
        return await self.handle_status(response)

    async def gather(self, character_name: str) -> dict:
        response = await self._client.post(f"/my/{character_name}/action/gathering")
        return await self.handle_status(response)

    async def bank_deposit_item(self, character_name: str, items: List[Dict[str, str | int]]) -> dict:
        response = await self._client.post(f"/my/{character_name}/action/bank/deposit/item", json=items)
        return await self.handle_status(response)

    async def bank_withdraw_item(self, character_name: str, items: List[Dict[str, str | int]]) -> dict:
        response = await self._client.post(f"/my/{character_name}/action/bank/deposit/item", json=items)
        return await self.handle_status(response)

    async def bank_deposit_gold(self, character_name: str, quantity: int) -> dict:
        response = await self._client.post(f"/my/{character_name}/action/bank/withdraw/gold", json=quantity)
        return await self.handle_status(response)

    async def bank_withdraw_gold(self, character_name: str, quantity: int) -> dict:
        response = await self._client.post(f"/my/{character_name}/action/bank/withdraw/gold", json=quantity)
        return await self.handle_status(response)

    async def unequip(self, character_name: str, item_slot: str) -> dict:
        payload = { "slot": item_slot }
        response = await self._client.post(f"/my/{character_name}/action/unequip", json=payload)
        return await self.handle_status(response)

    async def craft(self, character_name: str, item_slot: str) -> dict:
        payload = { "code": item_slot }
        response = await self._client.post(f"/my/{character_name}/action/crafting", json=payload)
        return await self.handle_status(response)

    async def equip(self, character_name: str, item_code: str, item_slot: str, ) -> dict:
        payload = { "code": item_code, "slot": item_slot }
        response = await self._client.post(f"/my/{character_name}/action/equip", json=payload)
        return await self.handle_status(response)