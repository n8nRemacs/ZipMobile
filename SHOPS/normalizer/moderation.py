"""
CRUD операции с zip_moderation_queue
"""
import json
from .db import get_pool
from .models import ModerationItem, ResolveRequest


async def create_moderation(
    entity_type: str,
    proposed_name: str,
    proposed_data: dict | None = None,
    source_article: str | None = None,
    source_name: str | None = None,
    source_shop: str | None = None,
    ai_confidence: float | None = None,
    ai_reasoning: str | None = None,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """INSERT INTO zip_moderation_queue
           (entity_type, proposed_name, proposed_data, source_article,
            source_name, source_shop, ai_confidence, ai_reasoning)
           VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, $8)
           RETURNING id""",
        entity_type,
        proposed_name,
        json.dumps(proposed_data) if proposed_data else None,
        source_article,
        source_name,
        source_shop,
        ai_confidence,
        ai_reasoning,
    )
    return row["id"]


async def get_pending(
    entity_type: str | None = None,
    shop_code: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ModerationItem]:
    pool = get_pool()
    conditions = ["status = 'pending'"]
    args = []
    idx = 1

    if entity_type:
        conditions.append(f"entity_type = ${idx}")
        args.append(entity_type)
        idx += 1

    if shop_code:
        conditions.append(f"source_shop = ${idx}")
        args.append(shop_code)
        idx += 1

    where = " AND ".join(conditions)
    args.extend([limit, offset])

    rows = await pool.fetch(
        f"""SELECT * FROM zip_moderation_queue
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}""",
        *args,
    )
    return [_row_to_item(r) for r in rows]


async def get_moderation_by_id(mod_id: int) -> ModerationItem | None:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM zip_moderation_queue WHERE id = $1", mod_id
    )
    if not row:
        return None
    return _row_to_item(row)


async def resolve(mod_id: int, req: ResolveRequest) -> int | None:
    """Разрешить запись модерации. Возвращает ID сущности."""
    pool = get_pool()

    item = await get_moderation_by_id(mod_id)
    if not item:
        return None

    resolved_entity_id = req.existing_id

    if req.create_new and req.new_name:
        resolved_entity_id = await _create_entity(
            item.entity_type, req.new_name, req.new_data, item.proposed_data
        )

    resolution = {
        "action": "create_new" if req.create_new else "use_existing",
        "entity_id": resolved_entity_id,
    }

    await pool.execute(
        """UPDATE zip_moderation_queue
           SET status = 'resolved',
               resolution = $1::jsonb,
               resolved_entity_id = $2,
               reviewed_by = $3,
               reviewed_at = NOW()
           WHERE id = $4""",
        json.dumps(resolution),
        resolved_entity_id,
        req.reviewed_by,
        mod_id,
    )
    return resolved_entity_id


async def get_stats() -> dict:
    pool = get_pool()
    rows = await pool.fetch(
        """SELECT entity_type, status, COUNT(*) as cnt
           FROM zip_moderation_queue
           GROUP BY entity_type, status
           ORDER BY entity_type, status"""
    )
    stats = {}
    for r in rows:
        et = r["entity_type"]
        if et not in stats:
            stats[et] = {}
        stats[et][r["status"]] = r["cnt"]
    return stats


async def _create_entity(
    entity_type: str,
    name: str,
    new_data: dict | None,
    proposed_data: dict | None,
) -> int:
    pool = get_pool()

    if entity_type == "brand":
        row = await pool.fetchrow(
            "INSERT INTO zip_dict_brands (name) VALUES ($1) RETURNING id", name
        )
    elif entity_type == "model":
        brand_id = (new_data or proposed_data or {}).get("brand_id")
        row = await pool.fetchrow(
            "INSERT INTO zip_dict_models (name, brand_id) VALUES ($1, $2) RETURNING id",
            name,
            brand_id,
        )
    elif entity_type == "part_type":
        row = await pool.fetchrow(
            "INSERT INTO zip_dict_part_types (name) VALUES ($1) RETURNING id", name
        )
    elif entity_type == "color":
        row = await pool.fetchrow(
            "INSERT INTO zip_dict_colors (name) VALUES ($1) RETURNING id", name
        )
    else:
        raise ValueError(f"Unknown entity_type: {entity_type}")

    return row["id"]


def _row_to_item(row) -> ModerationItem:
    return ModerationItem(
        id=row["id"],
        entity_type=row["entity_type"],
        proposed_name=row["proposed_name"],
        proposed_data=json.loads(row["proposed_data"]) if row["proposed_data"] else None,
        source_article=row["source_article"],
        source_name=row["source_name"],
        source_shop=row["source_shop"],
        ai_confidence=float(row["ai_confidence"]) if row["ai_confidence"] else None,
        ai_reasoning=row["ai_reasoning"],
        status=row["status"],
        resolution=json.loads(row["resolution"]) if row.get("resolution") else None,
        resolved_entity_id=row.get("resolved_entity_id"),
        reviewed_by=row.get("reviewed_by"),
        reviewed_at=row.get("reviewed_at"),
        created_at=row["created_at"],
    )
