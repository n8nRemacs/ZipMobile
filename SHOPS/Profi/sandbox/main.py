"""
Profi MCP Sandbox — FastAPI server
All endpoints for parsing, normalization, price checking, and export.
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException

from .db import init_pool, close_pool, get_pool
from .models import (
    HealthResponse, StatsResponse, TaskResponse,
    PriceCheckRequest, PriceCheckResponse, PriceItem,
    NormalizeStatusResponse, ExportPreviewResponse,
)
from .tasks import create_task, get_task, get_running_tasks, launch_background_task
from .services import dict_service, parser_service, normalizer_service, price_service, export_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="Profi Sandbox", version="1.0.0", lifespan=lifespan)


# ──────────────────── Инфра ────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    try:
        pool = get_pool()
        row = await pool.fetchrow("SELECT NOW() AS ts")
        last_parse = await pool.fetchval(
            "SELECT MAX(completed_at) FROM profi_tasks WHERE task_type LIKE 'parse%' AND status = 'completed'"
        )
        return HealthResponse(status="ok", db_connected=True, last_parse=last_parse)
    except Exception as e:
        return HealthResponse(status="error", db_connected=False)


@app.get("/status")
async def status():
    tasks = await get_running_tasks()
    return {"running_tasks": [t.model_dump() for t in tasks]}


@app.get("/stats", response_model=StatsResponse)
async def stats():
    pool = get_pool()
    nom = await pool.fetchval("SELECT COUNT(*) FROM profi_nomenclature")
    prices = await pool.fetchval("SELECT COUNT(*) FROM profi_prices")
    outlets = await pool.fetchval("SELECT COUNT(DISTINCT outlet_code) FROM profi_prices")
    running = await pool.fetchval("SELECT COUNT(*) FROM profi_tasks WHERE status IN ('pending', 'running')")
    return StatsResponse(
        nomenclature_count=nom or 0,
        prices_count=prices or 0,
        outlets_count=outlets or 0,
        tasks_running=running or 0,
    )


# ──────────────────── Парсинг ────────────────────

@app.post("/parse/all")
async def parse_all():
    task_id = await create_task("parse_all")
    launch_background_task(parser_service.parse_all_outlets, task_id)
    return {"task_id": str(task_id)}


@app.post("/parse/outlet/{code}")
async def parse_outlet(code: str):
    task_id = await create_task("parse_outlet", {"outlet_code": code})

    async def _run(tid: UUID):
        await parser_service.parse_outlet(tid, code)

    launch_background_task(_run, task_id)
    return {"task_id": str(task_id)}


@app.post("/parse/dynamic")
async def parse_dynamic():
    task_id = await create_task("parse_dynamic")
    launch_background_task(parser_service.parse_dynamic, task_id)
    return {"task_id": str(task_id)}


@app.get("/parse/task/{task_id}", response_model=TaskResponse)
async def parse_task_status(task_id: UUID):
    task = await get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


# ──────────────────── Цены ────────────────────

@app.post("/prices/check", response_model=PriceCheckResponse)
async def prices_check(req: PriceCheckRequest):
    return await price_service.check_prices(req.articles)


@app.post("/prices/update")
async def prices_update():
    task_id = await create_task("prices_update")
    launch_background_task(parser_service.parse_all_outlets, task_id)
    return {"task_id": str(task_id)}


@app.get("/prices/{article}")
async def prices_by_article(article: str):
    items = await price_service.get_prices_by_article(article)
    return {"article": article, "prices": [i.model_dump() for i in items]}


# ──────────────────── Нормализация ────────────────────

@app.post("/normalize/rules")
async def normalize_rules():
    task_id = await create_task("normalize_rules")
    launch_background_task(normalizer_service.normalize_rules, task_id)
    return {"task_id": str(task_id)}


@app.post("/normalize/ai")
async def normalize_ai():
    task_id = await create_task("normalize_ai")
    launch_background_task(normalizer_service.normalize_ai, task_id)
    return {"task_id": str(task_id)}


@app.post("/normalize/full")
async def normalize_full():
    task_id = await create_task("normalize_full")
    launch_background_task(normalizer_service.normalize_full, task_id)
    return {"task_id": str(task_id)}


@app.get("/normalize/status", response_model=NormalizeStatusResponse)
async def normalize_status():
    data = await normalizer_service.get_normalize_status()
    return NormalizeStatusResponse(**data)


# ──────────────────── Справочники ────────────────────

@app.post("/dict/sync")
async def dict_sync():
    counts = await dict_service.sync_dicts()
    return {"synced": counts}


@app.get("/dict/brands")
async def dict_brands():
    return dict_service.get_brands()


@app.get("/dict/models")
async def dict_models(brand_id: int | None = None):
    return dict_service.get_models(brand_id)


@app.get("/dict/part_types")
async def dict_part_types():
    return dict_service.get_part_types()


# ──────────────────── Экспорт ────────────────────

@app.post("/export/nomenclature")
async def export_nomenclature():
    task_id = await create_task("export_nomenclature")
    launch_background_task(export_service.export_nomenclature, task_id)
    return {"task_id": str(task_id)}


@app.post("/export/prices")
async def export_prices():
    task_id = await create_task("export_prices")
    launch_background_task(export_service.export_prices, task_id)
    return {"task_id": str(task_id)}


@app.post("/export/full")
async def export_full():
    task_id = await create_task("export_full")
    launch_background_task(export_service.export_full, task_id)
    return {"task_id": str(task_id)}


@app.get("/export/preview", response_model=ExportPreviewResponse)
async def export_preview():
    return await export_service.get_export_preview()
