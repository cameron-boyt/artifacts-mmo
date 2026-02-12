from __future__ import annotations

import logging
import httpx
import json
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum, auto

class RequestOutcome(Enum):
    SUCCESS = auto()
    FAIL = auto()

class RequestOutcomeDetail(Enum):
    OK = auto()
    NOT_FOUND = auto()
    INVALID_PAYLOAD = auto()
    MISSING_REQUIRED_ITEMS = auto()
    ALREADY_AT_DESTINATION = auto()
    ALREADY_HAS_TASK = auto()
    LEVEL_TOO_LOW = auto()
    CONDITIONS_NOT_MET = auto()
    INVENTORY_FULL = auto()
    ON_COOLDOWN = auto()
    NO_INTERACTION = auto()

@dataclass 
class APIResult:
    response: dict
    outcome: RequestOutcome
    detail: RequestOutcomeDetail

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

    ## API General Requests for Characters
    async def move(self, character_name: str, x: int, y: int) -> APIResult:
        payload = { "x": x, "y": y }
        response = await self._client.post(f"/my/{character_name}/action/move", json=payload)
        return await self.handle_status(response)
    
    async def transition(self) -> APIResult:
        raise NotImplementedError()

    async def rest(self, character_name: str) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/rest")
        return await self.handle_status(response)

    async def equip(self, character_name: str, item_code: str, item_slot: str, ) -> APIResult:
        payload = { "code": item_code, "slot": item_slot }
        response = await self._client.post(f"/my/{character_name}/action/equip", json=payload)
        return await self.handle_status(response)

    async def unequip(self, character_name: str, item_slot: str) -> APIResult:
        payload = { "slot": item_slot }
        response = await self._client.post(f"/my/{character_name}/action/unequip", json=payload)
        return await self.handle_status(response)
    
    async def use(self) -> APIResult:
        raise NotImplementedError()

    async def fight(self, character_name: str) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/fight")
        return await self.handle_status(response)

    async def gather(self, character_name: str) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/gathering")
        return await self.handle_status(response)

    async def craft(self, character_name: str, item_code: str, quantity: int = 1) -> APIResult:
        payload = { "code": item_code, "quantity": quantity }
        response = await self._client.post(f"/my/{character_name}/action/crafting", json=payload)
        return await self.handle_status(response)

    async def bank_deposit_gold(self, character_name: str, quantity: int) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/bank/deposit/gold", json=quantity)
        return await self.handle_status(response)

    async def bank_deposit_item(self, character_name: str, items: List[Dict[str, str | int]]) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/bank/deposit/item", json=items)
        return await self.handle_status(response)

    async def bank_withdraw_item(self, character_name: str, items: List[Dict[str, str | int]]) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/bank/withdraw/item", json=items)
        return await self.handle_status(response)

    async def bank_withdraw_gold(self, character_name: str, quantity: int) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/bank/withdraw/gold", json=quantity)
        return await self.handle_status(response)
    
    async def buy_bank_expansion(self) -> APIResult:
        raise NotImplementedError()
    
    async def npc_buy_item(self) -> APIResult:
        raise NotImplementedError()
    
    async def npc_sell_item(self) -> APIResult:
        raise NotImplementedError()
    
    async def recycle(self) -> APIResult:
        raise NotImplementedError()
    
    async def ge_buy_item(self) -> APIResult:
        raise NotImplementedError()
    
    async def ge_create_sell_order(self) -> APIResult:
        raise NotImplementedError()
    
    async def ge_cancel_sell_order(self) -> APIResult:
        raise NotImplementedError()
    
    async def complete_task(self, character_name: str) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/task/complete")
        return await self.handle_status(response)
    
    async def task_exchange(self, character_name: str) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/task/exchange")
        return await self.handle_status(response)
    
    async def accept_new_task(self, character_name: str) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/task/new")
        return await self.handle_status(response)
    
    async def task_trade(self, character_name: str, item_code: str, quantity: int) -> APIResult:
        payload = { "code": item_code, "quantity": quantity }
        response = await self._client.post(f"/my/{character_name}/action/task/trade", json=payload)
        return await self.handle_status(response)
    
    async def task_cancel(self, character_name: str) -> APIResult:
        response = await self._client.post(f"/my/{character_name}/action/task/cancel")
        return await self.handle_status(response)
    
    async def give_gold(self) -> APIResult:
        raise NotImplementedError()
    
    async def give_items(self) -> APIResult:
        raise NotImplementedError()
    
    async def delete_item(self) -> APIResult:
        raise NotImplementedError()
    
    async def handle_status(self, response: httpx.Response) -> APIResult:
        try:
            data = response.json()
        except:
            data = {"raw": response.text}
    
        match response.status_code:
            case 200:
                # All good
                outcome = RequestOutcome.SUCCESS
                detail = RequestOutcomeDetail.OK
            
            case 404:
                # Not found
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.NOT_FOUND
            
            case 422:
                # Invalid payload
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.INVALID_PAYLOAD
            
            case 478:
                # Missing required items
                self.logger.error("Character missing required items for action.")
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.MISSING_REQUIRED_ITEMS

            case 489:
                # Character already has task
                self.logger.warning("Character already has task.")
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.ALREADY_HAS_TASK

            case 490:
                # Character already at destination
                self.logger.warning("Character already at destination.")
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.ALREADY_AT_DESTINATION

            case 493:
                # Character level too low
                self.logger.warning("Character level too low.")
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.LEVEL_TOO_LOW

            case 496:
                # Conditions not met
                self.logger.warning("Conditions not met.")
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.CONDITIONS_NOT_MET

            case 497:
                # Character inventory is full
                self.logger.warning("Character inventory is full.")
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.INVENTORY_FULL

            case 499:
                # Character on cooldown
                self.logger.warning("Character is on cooldown.")
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.ON_COOLDOWN

            case 598:
                # No resource/monster on map
                self.logger.warning("No resource/monster on map.")
                outcome = RequestOutcome.FAIL
                detail = RequestOutcomeDetail.NO_INTERACTION

            case _:
                raise Exception(f"oh no; saw {response.status_code}")
            
        return APIResult(data, outcome, detail)