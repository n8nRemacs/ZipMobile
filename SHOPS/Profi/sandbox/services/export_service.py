"""
Экспорт profi_* → zip_* центральные таблицы
"""
from __future__ import annotations
import json
from uuid import UUID

from ..db import get_pool
from ..tasks import update_task
from ..models import ExportPreviewResponse


async def export_nomenclature(task_id: UUID):
    """Export profi_nomenclature → zip_nomenclature."""
    pool = get_pool()

    rows = await pool.fetch(
        """SELECT pn.id, pn.article, pn.name,
                  pn.zip_brand_id, pn.zip_model_id,
                  pn.zip_part_type_id, pn.zip_color_id,
                  pn.zip_nomenclature_id
           FROM profi_nomenclature pn
           WHERE pn.zip_brand_id IS NOT NULL
             AND pn.zip_part_type_id IS NOT NULL
             AND pn.is_spare_part != false"""
    )

    exported = 0
    for row in rows:
        result = await pool.fetchrow(
            """INSERT INTO zip_nomenclature (article, name, brand_id, model_id, part_type_id, color_id, source_shop)
               VALUES ($1, $2, $3, $4, $5, $6, 'profi')
               ON CONFLICT (article, source_shop) DO UPDATE SET
                   name = EXCLUDED.name,
                   brand_id = EXCLUDED.brand_id,
                   model_id = EXCLUDED.model_id,
                   part_type_id = EXCLUDED.part_type_id,
                   color_id = EXCLUDED.color_id,
                   updated_at = NOW()
               RETURNING id""",
            row["article"], row["name"],
            row["zip_brand_id"], row["zip_model_id"],
            row["zip_part_type_id"], row["zip_color_id"],
        )

        if result:
            await pool.execute(
                "UPDATE profi_nomenclature SET zip_nomenclature_id = $2 WHERE id = $1",
                row["id"], result["id"],
            )
            exported += 1

        if exported % 100 == 0:
            await update_task(task_id, progress={
                "current": exported, "total": len(rows),
                "message": f"Exported {exported} nomenclature items",
            })

    await update_task(task_id, result={"nomenclature_exported": exported})


async def export_prices(task_id: UUID):
    """Export profi_prices → zip_current_prices."""
    pool = get_pool()

    rows = await pool.fetch(
        """SELECT pp.article, pp.outlet_code, pp.city, pp.price,
                  pn.zip_nomenclature_id
           FROM profi_prices pp
           JOIN profi_nomenclature pn ON pp.article = pn.article
           WHERE pn.zip_nomenclature_id IS NOT NULL"""
    )

    exported = 0
    for row in rows:
        await pool.execute(
            """INSERT INTO zip_current_prices (nomenclature_id, outlet_code, city, price, source_shop)
               VALUES ($1, $2, $3, $4, 'profi')
               ON CONFLICT (nomenclature_id, outlet_code, source_shop) DO UPDATE SET
                   price = EXCLUDED.price,
                   city = EXCLUDED.city,
                   updated_at = NOW()""",
            row["zip_nomenclature_id"], row["outlet_code"], row["city"], row["price"],
        )
        exported += 1

    await update_task(task_id, result={"prices_exported": exported})


async def export_full(task_id: UUID):
    """Export both nomenclature and prices."""
    await update_task(task_id, progress={"message": "Exporting nomenclature..."})
    await export_nomenclature(task_id)
    await update_task(task_id, progress={"message": "Exporting prices..."})
    await export_prices(task_id)
    await update_task(task_id, result={"pipeline": "export_completed"})


async def get_export_preview() -> ExportPreviewResponse:
    pool = get_pool()

    nom_ready = await pool.fetchval(
        """SELECT COUNT(*) FROM profi_nomenclature
           WHERE zip_brand_id IS NOT NULL AND zip_part_type_id IS NOT NULL AND is_spare_part != false"""
    )

    prices_ready = await pool.fetchval(
        """SELECT COUNT(*) FROM profi_prices pp
           JOIN profi_nomenclature pn ON pp.article = pn.article
           WHERE pn.zip_nomenclature_id IS NOT NULL"""
    )

    new_nom = await pool.fetchval(
        """SELECT COUNT(*) FROM profi_nomenclature
           WHERE zip_brand_id IS NOT NULL AND zip_part_type_id IS NOT NULL
             AND zip_nomenclature_id IS NULL AND is_spare_part != false"""
    )

    return ExportPreviewResponse(
        nomenclature_ready=nom_ready or 0,
        prices_ready=prices_ready or 0,
        new_nomenclature=new_nom or 0,
    )
