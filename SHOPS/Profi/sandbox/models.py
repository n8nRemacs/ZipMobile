"""
Pydantic request/response schemas
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


# --- Tasks ---

class TaskResponse(BaseModel):
    task_id: UUID
    task_type: str
    status: str
    progress: dict | None = None
    result: dict | None = None
    error: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# --- Health / Stats ---

class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    last_parse: datetime | None = None


class StatsResponse(BaseModel):
    nomenclature_count: int = 0
    prices_count: int = 0
    outlets_count: int = 0
    tasks_running: int = 0


# --- Prices ---

class PriceCheckRequest(BaseModel):
    articles: list[str]


class PriceItem(BaseModel):
    article: str
    name: str | None = None
    outlet_code: str | None = None
    city: str | None = None
    price: float | None = None


class PriceCheckResponse(BaseModel):
    articles_requested: int
    prices_found: int
    items: list[PriceItem]


# --- Normalize ---

class NormalizeStatusResponse(BaseModel):
    total: int = 0
    rule_done: int = 0
    ai_done: int = 0
    needs_ai: int = 0
    pending: int = 0


# --- Export ---

class ExportPreviewResponse(BaseModel):
    nomenclature_ready: int = 0
    prices_ready: int = 0
    new_nomenclature: int = 0
    updated_nomenclature: int = 0
    new_prices: int = 0
