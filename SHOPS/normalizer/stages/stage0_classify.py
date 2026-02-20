"""
Stage 0: AI-классификация — является ли товар запчастью
"""
from ..models import ClassifyResult
from ..n8n_client import N8nClient


async def classify(name: str, article: str, n8n: N8nClient) -> ClassifyResult:
    result = await n8n.classify(name, article)
    return ClassifyResult(
        is_spare_part=result.get("is_spare_part", True),
        nomenclature_type=result.get("nomenclature_type"),
        confidence=result.get("confidence", 0.0),
    )
