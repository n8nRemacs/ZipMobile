"""
Нормализация песочницы Profi: сопоставление предподготовленных данных с zip_dict_*.

Предподготовка (ProfiNormalizer) уже выполнена при парсинге:
- brand/part_type разложены и очищены (шаги 2.1–2.9)

Проход 1 (rules):
- Бренды: прямой exact match SQL запросом к zip_dict_brands
  (в Profi бренды чёткие, без склонений и альтернатив)
- Типы запчастей: PART_TYPE_MAPPING → canonical → exact match к zip_dict_part_types

Проход 2 (AI):
- Только для записей с needs_ai=true (то что rules не закрыли)
- match_and_normalize_v3() — 4-агентный формат
"""
from __future__ import annotations
import json
from uuid import UUID

from ..db import get_pool
from ..tasks import update_task


# ─── Profi-специфичный маппинг part_type → каноническая форма ───
# Один раз настраивается для песочницы, закрывает склонения/множественное число
PART_TYPE_MAPPING = {
    # Дисплеи
    'ДИСПЛЕИ': 'ДИСПЛЕЙ',
    'ДИСПЛЕИ INCELL': 'ДИСПЛЕЙ',
    'ДИСПЛЕИ OLED': 'ДИСПЛЕЙ',
    'ДИСПЛЕИ ORIGINAL': 'ДИСПЛЕЙ',
    'ДИСПЛЕИ PREMIUM': 'ДИСПЛЕЙ',
    'ДИСПЛЕИ TIANMA': 'ДИСПЛЕЙ',
    # Камеры
    'КАМЕРЫ': 'КАМЕРА',
    # SIM
    'ДЕРЖАТЕЛИ SIM': 'SIM-ЛОТОК',
    'ДЕРЖАТЕЛИ, КОННЕКТОРЫ SIM/КАРТЫ ПАМЯТИ': 'SIM-ЛОТОК',
    'КОННЕКТОРЫ SIM/КАРТЫ ПАМЯТИ': 'SIM-ЛОТОК',
    # Прочее
    'ДЖОЙСТИКИ': 'ДЖОЙСТИК',
    'ДИНАМИК': 'ДИНАМИК',
    'ЗВОНКИ, ВИБРОЗВОНКИ, ДИНАМИКИ': 'ДИНАМИК',
    'ЗВОНКИ, ДИНАМИКИ': 'ДИНАМИК',
    'ЗВОНКИ, ДИНАМИКИ, ВИБРОМОТОРЫ': 'ДИНАМИК',
    'ЗАГЛУШКИ': 'ЗАГЛУШКА',
    'ЗАДНИЕ КРЫШКИ': 'КРЫШКА ЗАДНЯЯ',
    'ЗАДНЯЯ КРЫШКИ': 'КРЫШКА ЗАДНЯЯ',
    'КНОПКИ': 'КНОПКА',
    'КНОПКИ ВКЛЮЧЕНИЯ': 'КНОПКА',
    'КНОПКИ ВКЛЮЧЕНИЯ, ТОЛКАТЕЛИ': 'КНОПКА',
    'КОРПУСА': 'КОРПУС',
    'МИКРОСХЕМЫ': 'МИКРОСХЕМА',
    'МИКРОФОНЫ': 'МИКРОФОН',
    'ПЛАТЫ КЛАВИАТУРЫ': 'ПЛАТА',
    'ПРОКЛЕЙКИ ДЛЯ ДИСПЛЕЙНЫХ МОДУЛЕЙ И ЗАДНИХ КРЫШЕК': 'СКОТЧ',
    'СКОТЧ ДЛЯ ФИКСАЦИИ АКБ': 'СКОТЧ',
    'РАЗЪЕМЫ': 'РАЗЪЕМ',
    'РАЗЪЕМЫ ДЛЯ ЗАРЯДКИ': 'РАЗЪЕМ ЗАРЯДКИ',
    'РАЗЪЕМЫ ДЛЯ ЗАРЯДКИ, АУДИО РАЗЪЕМЫ': 'РАЗЪЕМ ЗАРЯДКИ',
    'РАЗЪЕМЫ ЗАРЯДКИ': 'РАЗЪЕМ ЗАРЯДКИ',
    'РАМКИ': 'РАМКА',
    'СТЕКЛА КАМЕРЫ': 'СТЕКЛО КАМЕРЫ',
    'СТЕКЛО КАМЕРЫ': 'СТЕКЛО КАМЕРЫ',
    'ТАЧСКРИНЫ': 'ТАЧСКРИН',
    'ТАЧСКРИНЫ ДЛЯ IPAD': 'ТАЧСКРИН',
    'ШЛЕЙФА': 'ШЛЕЙФ',
    'ШЛЕЙФА ДЛЯ IPAD': 'ШЛЕЙФ',
    'ШЛЕЙФЫ': 'ШЛЕЙФ',
}


def _canonical_part_type(raw: str) -> str:
    """Привести part_type к канонической форме через маппинг."""
    key = raw.strip().upper()
    return PART_TYPE_MAPPING.get(key, raw.strip())


# ─── Проход 1: Rule-based (SQL exact match) ───

async def normalize_rules(task_id: UUID):
    """
    Бренды — прямой exact match запросом (LOWER(TRIM)):
      бренды в Profi чёткие, совпадают 1:1 с zip_dict_brands.
    Типы запчастей — PART_TYPE_MAPPING → canonical → exact match.
    """
    pool = get_pool()

    # Шаг 1: Бренды одним UPDATE через JOIN
    brand_result = await pool.execute(
        """UPDATE profi_nomenclature pn
           SET zip_brand_id = zb.id,
               brand_normalized = zb.name
           FROM zip_dict_brands zb
           WHERE LOWER(TRIM(pn.brand)) = LOWER(TRIM(zb.name))
             AND pn.zip_brand_id IS NULL
             AND pn.is_spare_part = true
             AND pn.brand IS NOT NULL"""
    )
    brands_matched = _extract_count(brand_result)

    await update_task(task_id, progress={
        "message": f"Brands matched: {brands_matched}",
    })

    # Шаг 2: Типы запчастей — сначала маппинг в canonical, потом exact match
    # Обновляем part_type_normalized через PART_TYPE_MAPPING
    rows = await pool.fetch(
        """SELECT id, part_type
           FROM profi_nomenclature
           WHERE zip_part_type_id IS NULL
             AND is_spare_part = true
             AND part_type IS NOT NULL"""
    )

    for row in rows:
        canonical = _canonical_part_type(row["part_type"] or "")
        if canonical:
            await pool.execute(
                "UPDATE profi_nomenclature SET part_type_normalized = $2 WHERE id = $1",
                row["id"], canonical,
            )

    # Теперь exact match canonical → zip_dict_part_types
    pt_result = await pool.execute(
        """UPDATE profi_nomenclature pn
           SET zip_part_type_id = zpt.id
           FROM zip_dict_part_types zpt
           WHERE LOWER(TRIM(pn.part_type_normalized)) = LOWER(TRIM(zpt.name))
             AND pn.zip_part_type_id IS NULL
             AND pn.is_spare_part = true
             AND pn.part_type_normalized IS NOT NULL"""
    )
    pt_matched = _extract_count(pt_result)

    await update_task(task_id, progress={
        "message": f"Brands: {brands_matched}, Part types: {pt_matched}",
    })

    # Шаг 3: Определяем needs_ai
    # Полный матч (оба найдены) → needs_ai = false
    full_match = await pool.execute(
        """UPDATE profi_nomenclature
           SET needs_ai = false
           WHERE zip_brand_id IS NOT NULL
             AND zip_part_type_id IS NOT NULL
             AND is_spare_part = true"""
    )

    # Частичный или нулевой матч → needs_ai = true
    partial = await pool.execute(
        """UPDATE profi_nomenclature
           SET needs_ai = true
           WHERE (zip_brand_id IS NULL OR zip_part_type_id IS NULL)
             AND is_spare_part = true
             AND needs_ai IS DISTINCT FROM true"""
    )

    full_count = _extract_count(full_match)
    needs_ai_count = _extract_count(partial)

    await update_task(task_id, result={
        "brands_matched": brands_matched,
        "part_types_matched": pt_matched,
        "full_match": full_count,
        "needs_ai": needs_ai_count,
    })


def _extract_count(result: str) -> int:
    """Извлечь количество затронутых строк из asyncpg result string."""
    # asyncpg returns e.g. "UPDATE 123"
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


# ─── Проход 2: AI (match_and_normalize_v3, 4-агентный формат) ───

async def normalize_ai(task_id: UUID):
    """
    AI нормализация для записей с needs_ai=true.
    Формирует 4-агентный payload для match_and_normalize_v3:
    - agent1: brand + part_type (hints из предподготовки)
    - agent2: models (пока пустой, AI определит)
    - agent3: features (пока пустой, AI определит)
    - agent4: manufacturer + color (пока пустой, AI определит)
    """
    pool = get_pool()

    rows = await pool.fetch(
        """SELECT id, article, name, brand, model, part_type,
                  brand_normalized, part_type_normalized,
                  zip_brand_id, zip_part_type_id
           FROM profi_nomenclature
           WHERE needs_ai = true
           ORDER BY id
           LIMIT 50"""
    )

    total = len(rows)
    done = 0
    success = 0

    for row in rows:
        # Формируем 4-агентный payload
        payload = json.dumps({
            "article": row["article"],
            "name": row["name"],
            "shop_code": "profi",

            "agent1": {
                "brand_raw": row["brand_normalized"] or row["brand"] or "",
                "part_type_raw": row["part_type_normalized"] or row["part_type"] or "",
                "confidence": 0.7,  # hints из предподготовки, не полная уверенность
            },

            "agent2": {
                "models": [],  # AI должен определить из name
                "confidence": 0.5,
            },

            "agent3": {
                "features": {},  # AI должен извлечь из name
                "confidence": 0.5,
            },

            "agent4": {
                "manufacturer": None,  # AI должен определить из name
                "color": None,
                "confidence": 0.5,
            },
        })

        try:
            ai_result = await pool.fetchrow(
                "SELECT * FROM match_and_normalize_v3($1::jsonb)", payload
            )

            if ai_result and ai_result.get("success"):
                nom_id = ai_result.get("nomenclature_id")
                await pool.execute(
                    """UPDATE profi_nomenclature
                       SET zip_nomenclature_id = $2, needs_ai = false
                       WHERE id = $1""",
                    row["id"], nom_id,
                )
                success += 1
        except Exception:
            pass

        done += 1
        if done % 10 == 0:
            await update_task(task_id, progress={
                "current": done, "total": total,
                "message": f"AI: {success}/{done} matched",
            })

    await update_task(task_id, result={"total": total, "success": success})


async def normalize_full(task_id: UUID):
    """Full pipeline: rules → AI."""
    await update_task(task_id, progress={"message": "Running rule-based matching..."})
    await normalize_rules(task_id)

    await update_task(task_id, progress={"message": "Running AI normalization..."})
    await normalize_ai(task_id)

    await update_task(task_id, result={"pipeline": "completed"})


async def get_normalize_status() -> dict:
    pool = get_pool()
    row = await pool.fetchrow(
        """SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE zip_brand_id IS NOT NULL AND zip_part_type_id IS NOT NULL AND needs_ai = false) AS rule_done,
            COUNT(*) FILTER (WHERE zip_nomenclature_id IS NOT NULL) AS ai_done,
            COUNT(*) FILTER (WHERE needs_ai = true) AS needs_ai,
            COUNT(*) FILTER (WHERE zip_brand_id IS NULL AND (needs_ai IS NULL OR needs_ai = false) AND is_spare_part = true) AS pending
           FROM profi_nomenclature"""
    )
    return dict(row)
