"""
ZipMobile Normalizer API — FastAPI application
"""
import json
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_pool, close_pool, get_pool
from .models import (
    NormalizeRequest,
    NormalizeResult,
    NormalizeBatchRequest,
    ModerationItem,
    ResolveRequest,
    TaskResponse,
)
from .n8n_client import n8n_client
from .tasks import create_task, get_task, update_task, launch_background_task
from .moderation import (
    get_pending,
    get_moderation_by_id,
    resolve as resolve_moderation,
    get_stats as get_moderation_stats,
)
from .stages.stage0_classify import classify
from .stages.stage1_brand_models import extract_brand_models
from .stages.stage2_merge import merge_and_validate


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await n8n_client.close()
    await close_pool()


app = FastAPI(title="ZipMobile Normalizer", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Нормализация ==========

async def _normalize_one(req: NormalizeRequest) -> NormalizeResult:
    pool = get_pool()

    # Stage 0: классификация (опционально)
    if req.classify:
        cls_result = await classify(req.name, req.article, n8n_client)
        if not cls_result.is_spare_part:
            return NormalizeResult(
                article=req.article,
                status="not_spare_part",
                confidence=cls_result.confidence,
            )

    # Stage 1: извлечение бренда и моделей
    extract = await extract_brand_models(req.name, n8n_client)

    # Stage 2: merge + валидация
    merge = await merge_and_validate(
        extract=extract,
        pool=pool,
        n8n=n8n_client,
        source_article=req.article,
        source_name=req.name,
        source_shop=req.shop_code,
    )

    return NormalizeResult(
        article=req.article,
        status=merge.status,
        brand_id=merge.brand_id,
        brand_name=merge.brand_name,
        model_ids=merge.model_ids,
        model_names=merge.model_names,
        moderation_ids=merge.moderation_ids,
        confidence=merge.confidence,
    )


@app.post("/normalize", response_model=NormalizeResult)
async def normalize(req: NormalizeRequest):
    return await _normalize_one(req)


@app.post("/normalize/batch")
async def normalize_batch(req: NormalizeBatchRequest):
    task_id = await create_task("normalize_batch", {"count": len(req.items)})
    items = req.items

    async def _run(tid: UUID):
        results = []
        for i, item in enumerate(items):
            result = await _normalize_one(item)
            results.append(result.model_dump())
            await update_task(tid, progress={"done": i + 1, "total": len(items)})
        await update_task(tid, result={"results": results})

    launch_background_task(_run, task_id)
    return {"task_id": str(task_id)}


@app.post("/normalize/shop/{shop_code}")
async def normalize_shop(shop_code: str):
    """Нормализовать все ненормализованные товары магазина."""
    pool = get_pool()

    # Проверяем наличие таблицы
    table = f"{shop_code}_nomenclature"
    count_row = await pool.fetchrow(
        f"SELECT COUNT(*) as cnt FROM {table} WHERE zip_nomenclature_id IS NULL AND is_active = true"
    )
    total = count_row["cnt"] if count_row else 0

    task_id = await create_task("normalize_shop", {"shop_code": shop_code, "total": total})

    async def _run(tid: UUID):
        rows = await pool.fetch(
            f"SELECT article, name, url FROM {table} WHERE zip_nomenclature_id IS NULL AND is_active = true"
        )
        results = []
        for i, row in enumerate(rows):
            req = NormalizeRequest(
                article=row["article"],
                name=row["name"],
                shop_code=shop_code,
                url=row.get("url"),
            )
            result = await _normalize_one(req)
            results.append(result.model_dump())
            if (i + 1) % 10 == 0:
                await update_task(tid, progress={"done": i + 1, "total": len(rows)})

        await update_task(
            tid,
            progress={"done": len(rows), "total": len(rows)},
            result={"normalized": sum(1 for r in results if r["status"] == "normalized"),
                    "needs_moderation": sum(1 for r in results if r["status"] == "needs_moderation"),
                    "total": len(results)},
        )

    launch_background_task(_run, task_id)
    return {"task_id": str(task_id), "total": total}


@app.get("/normalize/status")
async def normalize_status():
    pool = get_pool()
    # Статистика по таблицам номенклатуры
    shops = await pool.fetch("SELECT id, code, name FROM zip_shops WHERE is_active = true ORDER BY code")
    stats = []
    for shop in shops:
        table = f"{shop['code']}_nomenclature"
        try:
            row = await pool.fetchrow(
                f"""SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE zip_nomenclature_id IS NOT NULL) as normalized,
                    COUNT(*) FILTER (WHERE zip_nomenclature_id IS NULL AND is_active = true) as pending
                FROM {table}"""
            )
            stats.append({
                "shop_code": shop["code"],
                "shop_name": shop["name"],
                "total": row["total"],
                "normalized": row["normalized"],
                "pending": row["pending"],
            })
        except Exception:
            continue
    return stats


# ========== Модерация ==========

@app.get("/moderate", response_model=list[ModerationItem])
async def moderate_list(
    entity_type: str | None = Query(None),
    shop_code: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    return await get_pending(entity_type, shop_code, limit, offset)


@app.get("/moderate/stats")
async def moderate_stats():
    return await get_moderation_stats()


@app.get("/moderate/{mod_id}", response_model=ModerationItem)
async def moderate_detail(mod_id: int):
    item = await get_moderation_by_id(mod_id)
    if not item:
        raise HTTPException(404, "Moderation item not found")
    return item


@app.post("/moderate/{mod_id}/resolve")
async def moderate_resolve(mod_id: int, req: ResolveRequest):
    entity_id = await resolve_moderation(mod_id, req)
    if entity_id is None:
        raise HTTPException(404, "Moderation item not found")
    return {"resolved_entity_id": entity_id}


# ========== Справочники ==========

@app.get("/dict/brands")
async def dict_brands(q: str | None = Query(None)):
    pool = get_pool()
    if q:
        rows = await pool.fetch(
            "SELECT id, name FROM zip_dict_brands WHERE LOWER(name) LIKE $1 ORDER BY name LIMIT 50",
            f"%{q.lower()}%",
        )
    else:
        rows = await pool.fetch("SELECT id, name FROM zip_dict_brands ORDER BY name")
    return [{"id": r["id"], "name": r["name"]} for r in rows]


@app.get("/dict/models")
async def dict_models(brand_id: int | None = Query(None), q: str | None = Query(None)):
    pool = get_pool()
    conditions = []
    args = []
    idx = 1

    if brand_id:
        conditions.append(f"brand_id = ${idx}")
        args.append(brand_id)
        idx += 1

    if q:
        conditions.append(f"LOWER(name) LIKE ${idx}")
        args.append(f"%{q.lower()}%")
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await pool.fetch(
        f"SELECT id, name, brand_id FROM zip_dict_models {where} ORDER BY name LIMIT 200",
        *args,
    )
    return [{"id": r["id"], "name": r["name"], "brand_id": r["brand_id"]} for r in rows]


@app.get("/dict/part_types")
async def dict_part_types():
    pool = get_pool()
    rows = await pool.fetch("SELECT id, name FROM zip_dict_part_types ORDER BY name")
    return [{"id": r["id"], "name": r["name"]} for r in rows]


@app.get("/dict/colors")
async def dict_colors():
    pool = get_pool()
    rows = await pool.fetch("SELECT id, name FROM zip_dict_colors ORDER BY name")
    return [{"id": r["id"], "name": r["name"]} for r in rows]


# ========== Задачи ==========

@app.get("/task/{task_id}", response_model=TaskResponse)
async def task_detail(task_id: UUID):
    task = await get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


# ========== Инфра ==========

@app.get("/health")
async def health():
    pool = get_pool()
    row = await pool.fetchrow("SELECT 1 as ok")
    return {"status": "ok", "db": bool(row)}


@app.get("/stats")
async def stats():
    pool = get_pool()
    mod_stats = await get_moderation_stats()
    return {
        "moderation": mod_stats,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("SHOPS.normalizer.main:app", host="0.0.0.0", port=settings.server_port, reload=True)
