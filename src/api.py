import httpx
from typing import List, Dict

class APIClient:
    """Handles all HTTP communication with the remote server."""
    def __init__(self, base_url: str, api_key: str):
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
                print("Character already at destination")
                pass

            case 497:
                # Character inventory is full
                print("Character inventory is full")
                pass

            case 499:
                with open(f"{response.url.replace('/', '_')}.log", 'a') as f:
                    f.write(response.text)

                error_msg = response.json()["error"]["message"]
                print(error_msg)

            case 598:
                # No resource/monster on map
                print("No resource/monster on map")
                pass

            case _:
                raise Exception("fuck")

    async def move(self, character_name: str, x: int, y: int) -> dict:
        payload = {"x": x, "y": y}
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

    async def bank(self, character_name: str, items: List[Dict[str, str | int]]) -> dict:
        response = await self._client.post(f"/my/{character_name}/action/bank/deposit/item", json=items)
        return await self.handle_status(response)