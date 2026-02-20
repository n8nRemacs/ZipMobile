"""
HTTP client для n8n webhook вызовов
"""
import httpx
from .config import settings


class N8nClient:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.n8n_base_url,
                timeout=settings.http_timeout,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _post(self, url: str, data: dict) -> dict:
        client = await self._get_client()
        for attempt in range(3):
            try:
                resp = await client.post(url, json=data)
                resp.raise_for_status()
                result = resp.json()
                # n8n может вернуть список из одного элемента
                if isinstance(result, list) and len(result) == 1:
                    return result[0]
                return result
            except (httpx.HTTPStatusError, httpx.ConnectError) as e:
                if attempt == 2:
                    raise
                continue

    async def classify(self, name: str, article: str) -> dict:
        return await self._post(settings.n8n_classify_url, {
            "name": name,
            "article": article,
        })

    async def extract_brand_models(self, name: str) -> dict:
        return await self._post(settings.n8n_extract_brand_models_url, {
            "name": name,
        })

    async def validate_brand(self, brand_raw: str, all_brands: list[dict]) -> dict:
        return await self._post(settings.n8n_validate_brand_url, {
            "brand_raw": brand_raw,
            "all_brands": all_brands,
        })

    async def validate_models(
        self, models_raw: list[str], brand_id: int, all_models: list[dict]
    ) -> dict:
        return await self._post(settings.n8n_validate_models_url, {
            "models_raw": models_raw,
            "brand_id": brand_id,
            "all_models": all_models,
        })


n8n_client = N8nClient()
