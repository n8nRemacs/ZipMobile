"""
Pydantic модели для Normalizer API
"""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


# --- Нормализация ---

class NormalizeRequest(BaseModel):
    article: str
    name: str
    shop_code: str
    url: str | None = None
    classify: bool = False


class NormalizeResult(BaseModel):
    article: str
    status: str  # "normalized", "needs_moderation", "not_spare_part"
    brand_id: int | None = None
    brand_name: str | None = None
    model_ids: list[int] = []
    model_names: list[str] = []
    moderation_ids: list[int] = []
    confidence: float = 0.0


class NormalizeBatchRequest(BaseModel):
    items: list[NormalizeRequest]


# --- Модерация ---

class ModerationItem(BaseModel):
    id: int
    entity_type: str
    proposed_name: str
    proposed_data: dict | None = None
    source_article: str | None = None
    source_name: str | None = None
    source_shop: str | None = None
    ai_confidence: float | None = None
    ai_reasoning: str | None = None
    status: str
    resolution: dict | None = None
    resolved_entity_id: int | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class ResolveRequest(BaseModel):
    existing_id: int | None = None
    create_new: bool = False
    new_name: str | None = None
    new_data: dict | None = None
    reviewed_by: str = "admin"


# --- Задачи ---

class TaskResponse(BaseModel):
    task_id: UUID
    task_type: str
    status: str
    progress: dict | None = None
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


# --- Внутренние модели стадий ---

class ClassifyResult(BaseModel):
    is_spare_part: bool
    nomenclature_type: str | None = None
    confidence: float


class ExtractResult(BaseModel):
    brand: str | None = None
    models: list[str] = []
    confidence: float


class MergeResult(BaseModel):
    status: str  # "normalized", "needs_moderation"
    brand_id: int | None = None
    brand_name: str | None = None
    model_ids: list[int] = []
    model_names: list[str] = []
    moderation_ids: list[int] = []
    confidence: float = 0.0
