"""
Real-time concurrent HTTP проверка цен по артикулам
"""
from __future__ import annotations
import asyncio
import os
import sys

import httpx

_profi_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Profi")
if _profi_dir not in sys.path:
    sys.path.insert(0, _profi_dir)

from price_lists_config import PRICE_LISTS

from ..db import get_pool
from ..config import settings
from ..models import PriceCheckResponse, PriceItem
from .parser_service import _download_file, _parse_excel_sync


async def check_prices(articles: list[str]) -> PriceCheckResponse:
    """Download relevant Excel files and extract prices for given articles."""
    article_set = {a.strip().upper() for a in articles}
    sem = asyncio.Semaphore(settings.max_concurrent_downloads)
    results: list[PriceItem] = []
    lock = asyncio.Lock()

    async def _check_outlet(pl: dict):
        async with sem:
            async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
                file_path = await _download_file(client, pl["url"])

            if not file_path:
                return

            products = await asyncio.to_thread(
                _parse_excel_sync, file_path,
                pl["city"], pl["shop"], pl.get("outlet_code", ""),
            )

            matched = [
                PriceItem(
                    article=p["article"],
                    name=p["name"],
                    outlet_code=p.get("outlet_code"),
                    city=p.get("city"),
                    price=p["price"],
                )
                for p in products
                if p.get("article", "").strip().upper() in article_set and p.get("price")
            ]

            if matched:
                async with lock:
                    results.extend(matched)

    # Check all outlets in parallel
    tasks = [_check_outlet(pl) for pl in PRICE_LISTS]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Also update DB
    pool = get_pool()
    for item in results:
        await pool.execute(
            """INSERT INTO profi_prices (article, outlet_code, city, price)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (article, outlet_code) DO UPDATE SET
                   price = EXCLUDED.price, updated_at = NOW()""",
            item.article, item.outlet_code or "", item.city or "", item.price,
        )

    return PriceCheckResponse(
        articles_requested=len(articles),
        prices_found=len(results),
        items=results,
    )


async def get_prices_by_article(article: str) -> list[PriceItem]:
    """Get stored prices for an article from all outlets."""
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT article, outlet_code, city, price FROM profi_prices WHERE article = $1",
        article,
    )
    return [
        PriceItem(article=r["article"], outlet_code=r["outlet_code"], city=r["city"], price=r["price"])
        for r in rows
    ]
