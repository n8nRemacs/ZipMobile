"""
In-memory кэш zip_dict_* справочников
"""
from __future__ import annotations
from ..db import get_pool

_cache: dict[str, list[dict]] = {}


async def sync_dicts() -> dict[str, int]:
    """Загрузить справочники из БД в память."""
    pool = get_pool()
    tables = {
        "brands": "SELECT id, name FROM zip_dict_brands ORDER BY name",
        "models": "SELECT id, name, brand_id FROM zip_dict_models ORDER BY name",
        "part_types": "SELECT id, name FROM zip_dict_part_types ORDER BY name",
        "colors": "SELECT id, name FROM zip_dict_colors ORDER BY name",
    }
    counts = {}
    for key, sql in tables.items():
        rows = await pool.fetch(sql)
        _cache[key] = [dict(r) for r in rows]
        counts[key] = len(rows)
    return counts


def get_brands() -> list[dict]:
    return _cache.get("brands", [])


def get_models(brand_id: int | None = None) -> list[dict]:
    models = _cache.get("models", [])
    if brand_id is not None:
        return [m for m in models if m.get("brand_id") == brand_id]
    return models


def get_part_types() -> list[dict]:
    return _cache.get("part_types", [])


def get_colors() -> list[dict]:
    return _cache.get("colors", [])


def find_brand_by_name(name: str) -> dict | None:
    name_lower = name.strip().lower()
    for b in get_brands():
        if b["name"].strip().lower() == name_lower:
            return b
    return None


def find_part_type_by_name(name: str) -> dict | None:
    name_lower = name.strip().lower()
    for pt in get_part_types():
        if pt["name"].strip().lower() == name_lower:
            return pt
    return None
