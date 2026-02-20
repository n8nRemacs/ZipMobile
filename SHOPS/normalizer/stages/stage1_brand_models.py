"""
Stage 1: AI-извлечение бренда и моделей из наименования
"""
from ..models import ExtractResult
from ..n8n_client import N8nClient


async def extract_brand_models(name: str, n8n: N8nClient) -> ExtractResult:
    result = await n8n.extract_brand_models(name)
    return ExtractResult(
        brand=result.get("brand"),
        models=result.get("models", []),
        confidence=result.get("confidence", 0.0),
    )
