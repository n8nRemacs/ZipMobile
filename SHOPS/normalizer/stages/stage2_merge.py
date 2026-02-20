"""
Stage 2: SQL exact match + AI валидация + модерация
"""
import asyncpg

from ..models import ExtractResult, MergeResult
from ..n8n_client import N8nClient
from ..moderation import create_moderation
from ..config import settings


async def merge_and_validate(
    extract: ExtractResult,
    pool: asyncpg.Pool,
    n8n: N8nClient,
    source_article: str,
    source_name: str,
    source_shop: str,
) -> MergeResult:
    moderation_ids = []
    brand_id = None
    brand_name = None
    model_ids = []
    model_names = []
    confidence = extract.confidence

    # --- Бренд ---
    if extract.brand:
        brand_row = await pool.fetchrow(
            "SELECT id, name FROM zip_dict_brands WHERE LOWER(TRIM(name)) = LOWER(TRIM($1))",
            extract.brand,
        )

        if brand_row:
            brand_id = brand_row["id"]
            brand_name = brand_row["name"]
        else:
            # AI валидация: ищем похожий бренд
            all_brands = await pool.fetch(
                "SELECT id, name FROM zip_dict_brands ORDER BY name"
            )
            brands_list = [{"id": r["id"], "name": r["name"]} for r in all_brands]

            try:
                ai_result = await n8n.validate_brand(extract.brand, brands_list)
                if ai_result.get("is_new", True):
                    mod_id = await create_moderation(
                        entity_type="brand",
                        proposed_name=extract.brand,
                        source_article=source_article,
                        source_name=source_name,
                        source_shop=source_shop,
                        ai_confidence=ai_result.get("confidence"),
                        ai_reasoning=ai_result.get("reasoning"),
                    )
                    moderation_ids.append(mod_id)
                else:
                    brand_id = ai_result["match_id"]
                    brand_name = ai_result.get("match", extract.brand)
                    confidence = min(confidence, ai_result.get("confidence", 0.0))
            except Exception:
                mod_id = await create_moderation(
                    entity_type="brand",
                    proposed_name=extract.brand,
                    source_article=source_article,
                    source_name=source_name,
                    source_shop=source_shop,
                    ai_confidence=0.0,
                    ai_reasoning="n8n validation failed",
                )
                moderation_ids.append(mod_id)

    # --- Модели ---
    if extract.models and brand_id:
        all_models = await pool.fetch(
            "SELECT id, name FROM zip_dict_models WHERE brand_id = $1 ORDER BY name",
            brand_id,
        )
        models_list = [{"id": r["id"], "name": r["name"]} for r in all_models]

        for model_raw in extract.models:
            model_row = await pool.fetchrow(
                """SELECT id, name FROM zip_dict_models
                   WHERE brand_id = $1 AND LOWER(TRIM(name)) = LOWER(TRIM($2))""",
                brand_id,
                model_raw,
            )

            if model_row:
                model_ids.append(model_row["id"])
                model_names.append(model_row["name"])
            else:
                try:
                    ai_result = await n8n.validate_models(
                        [model_raw], brand_id, models_list
                    )
                    matches = ai_result.get("matches", [])
                    if matches and not matches[0].get("is_new", True):
                        model_ids.append(matches[0]["match_id"])
                        model_names.append(matches[0].get("match", model_raw))
                    else:
                        mod_id = await create_moderation(
                            entity_type="model",
                            proposed_name=model_raw,
                            proposed_data={"brand_id": brand_id},
                            source_article=source_article,
                            source_name=source_name,
                            source_shop=source_shop,
                            ai_confidence=matches[0].get("confidence", 0.0) if matches else 0.0,
                            ai_reasoning=matches[0].get("reasoning") if matches else None,
                        )
                        moderation_ids.append(mod_id)
                except Exception:
                    mod_id = await create_moderation(
                        entity_type="model",
                        proposed_name=model_raw,
                        proposed_data={"brand_id": brand_id},
                        source_article=source_article,
                        source_name=source_name,
                        source_shop=source_shop,
                        ai_confidence=0.0,
                        ai_reasoning="n8n validation failed",
                    )
                    moderation_ids.append(mod_id)

    elif extract.models and not brand_id:
        # Бренд не найден — модели тоже на модерацию
        for model_raw in extract.models:
            mod_id = await create_moderation(
                entity_type="model",
                proposed_name=model_raw,
                source_article=source_article,
                source_name=source_name,
                source_shop=source_shop,
                ai_confidence=0.0,
                ai_reasoning="Brand not resolved, model pending",
            )
            moderation_ids.append(mod_id)

    # Определяем статус
    if moderation_ids:
        status = "needs_moderation"
    elif brand_id:
        status = "normalized"
    else:
        status = "needs_moderation"

    return MergeResult(
        status=status,
        brand_id=brand_id,
        brand_name=brand_name,
        model_ids=model_ids,
        model_names=model_names,
        moderation_ids=moderation_ids,
        confidence=confidence,
    )
