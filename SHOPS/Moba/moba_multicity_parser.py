#!/usr/bin/env python3
"""
Moba.ru Multi-City Parser — parallel Playwright edition.

Prices are identical across all moba.ru cities.
Only product availability differs per city (different assortment).

Flow:
  1. Moscow parse (moba_playwright_parser.py) provides nomenclature + prices
  2. This script checks availability across all city subdomains in parallel
  3. Creates per-city outlet records + availability data

Uses N parallel Playwright browsers (default 4) for speed.

Requirements:
    pip install playwright beautifulsoup4
    playwright install chromium

Usage:
    python moba_multicity_parser.py                 # all cities, save to DB
    python moba_multicity_parser.py --no-db         # all cities, JSON only
    python moba_multicity_parser.py --cities 3      # first 3 cities only
    python moba_multicity_parser.py --parallel 6    # 6 browsers in parallel
    python moba_multicity_parser.py --list          # list cities and exit
"""
import asyncio
import json
import re
import os
import sys
import csv
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("moba_multi")

# ─── config ───────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent / "moba_data"
BASE_DOMAIN = "moba.ru"

# All known moba.ru city subdomains
# Format: (subdomain, city_name)
CITIES = [
    ("moba.ru", "Москва"),
    ("kazan.moba.ru", "Казань"),
    ("sankt-peterburg.moba.ru", "Санкт-Петербург"),
    ("novosibirsk.moba.ru", "Новосибирск"),
    ("krasnoyarsk.moba.ru", "Красноярск"),
    ("krasnodar.moba.ru", "Краснодар"),
    ("vladivostok.moba.ru", "Владивосток"),
    ("khabarovsk.moba.ru", "Хабаровск"),
    ("omsk.moba.ru", "Омск"),
    ("barnaul.moba.ru", "Барнаул"),
    ("bryansk.moba.ru", "Брянск"),
    ("vladimir.moba.ru", "Владимир"),
    ("vologda.moba.ru", "Вологда"),
    ("voronezh.moba.ru", "Воронеж"),
    ("irkutsk.moba.ru", "Иркутск"),
    ("kaluga.moba.ru", "Калуга"),
    ("kemerovo.moba.ru", "Кемерово"),
    ("nizhnevartovsk.moba.ru", "Нижневартовск"),
    ("nizhniy-novgorod.moba.ru", "Нижний Новгород"),
    ("petrozavodsk.moba.ru", "Петрозаводск"),
    ("samara.moba.ru", "Самара"),
    ("surgut.moba.ru", "Сургут"),
    ("tula.moba.ru", "Тула"),
    ("tyumen.moba.ru", "Тюмень"),
    ("ufa.moba.ru", "Уфа"),
    ("yaroslavl.moba.ru", "Ярославль"),
    ("anapa.moba.ru", "Анапа"),
    ("arhangelsk.moba.ru", "Архангельск"),
    ("mytishhi.moba.ru", "Мытищи"),
    ("noginsk.moba.ru", "Ногинск"),
    ("orekhovo-zuevo.moba.ru", "Орехово-Зуево"),
    ("lyubercy.moba.ru", "Люберцы"),
    ("reutov.moba.ru", "Реутов"),
]

# DB
TABLE_NOMENCLATURE = "moba_nomenclature"
TABLE_PRODUCT_URLS = "moba_product_urls"
TABLE_OUTLETS = "zip_outlets"

REQUEST_DELAY = 0.3
MAX_PAGES = 50


# ─── parsing ──────────────────────────────────────────────────────────

def parse_products_from_html(html: str) -> List[Dict]:
    """Extract product articles and basic info from a catalog page."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("tr.item.main_item_wrapper")
    if not items:
        for sel in ["div.catalog-item", "div.item-card", "div.product-item"]:
            items = soup.select(sel)
            if items:
                break

    products = []
    for item in items:
        try:
            for a in item.find_all("a", href=True):
                href = a.get("href", "")
                if href.startswith("/catalog/") and href.count("/") >= 3:
                    text = a.get_text(strip=True)
                    if text and len(text) > 5:
                        parts = href.rstrip("/").split("/")
                        pid = parts[-1] if parts[-1].isdigit() else None
                        if pid:
                            # Get price
                            price_el = item.select_one(".cost") or item.find(class_="price")
                            price = 0.0
                            if price_el:
                                m = re.search(r"([\d\s]+)", price_el.get_text(strip=True).replace("\xa0", " "))
                                if m:
                                    try:
                                        price = float(m.group(1).replace(" ", "").strip())
                                    except ValueError:
                                        pass
                            products.append({
                                "article": f"MOBA-{pid}",
                                "name": text[:200],
                                "price": price,
                                "url": href,
                            })
                        break
        except Exception:
            continue

    return products


def has_next_page(html: str, current_page: int) -> bool:
    """Check if there's a next page in pagination."""
    soup = BeautifulSoup(html, "html.parser")
    next_link = (
        soup.find("a", class_="flex-next")
        or soup.find("a", class_="next")
        or soup.find("a", {"rel": "next"})
    )
    if next_link:
        return True
    pagen = soup.find_all("a", href=lambda h: h and f"PAGEN_1={current_page+1}" in h)
    return bool(pagen)


def get_categories_from_html(html: str) -> List[Dict]:
    """Extract categories from catalog page."""
    soup = BeautifulSoup(html, "html.parser")
    categories = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if (href.startswith("/catalog/") and href != "/catalog/"
                and "filter" not in href and "?" not in href):
            clean = href.split("?")[0]
            if clean not in [c["url"] for c in categories]:
                name = link.get_text(strip=True)
                if name and len(name) > 1:
                    categories.append({"url": clean, "name": name[:100]})
    return categories


# ─── city parser ──────────────────────────────────────────────────────

async def parse_city(
    subdomain: str,
    city_name: str,
    sem: asyncio.Semaphore,
    pw_instance,
) -> Tuple[str, str, List[Dict]]:
    """
    Parse all products from one city subdomain.
    Returns (subdomain, city_name, products).
    """
    async with sem:
        base = f"https://{subdomain}"
        log.info("[%s] Starting ...", city_name)

        browser = await pw_instance.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--lang=ru-RU,ru"],
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
            )
            page = await context.new_page()

            # Initial navigation — pass SmartCaptcha
            await page.goto(base, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3000)

            # Get categories
            html = await page.goto(
                f"{base}/catalog/", wait_until="domcontentloaded", timeout=20_000
            )
            await page.wait_for_timeout(1000)
            cat_html = await page.content()
            categories = get_categories_from_html(cat_html)
            log.info("[%s] %d categories", city_name, len(categories))

            all_products = []
            seen_articles = set()

            for ci, cat in enumerate(categories, 1):
                for page_num in range(1, MAX_PAGES + 1):
                    url = f"{base}{cat['url']}"
                    if page_num > 1:
                        url += f"?PAGEN_1={page_num}"

                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
                        await page.wait_for_timeout(500)
                        html = await page.content()
                    except Exception:
                        break

                    prods = parse_products_from_html(html)
                    if not prods:
                        break

                    new_count = 0
                    for p in prods:
                        if p["article"] not in seen_articles:
                            seen_articles.add(p["article"])
                            p["category"] = cat["name"]
                            all_products.append(p)
                            new_count += 1

                    if not has_next_page(html, page_num):
                        break

                    await asyncio.sleep(REQUEST_DELAY)

                if ci % 20 == 0:
                    log.info("[%s] %d/%d categories, %d unique products",
                             city_name, ci, len(categories), len(all_products))

            log.info("[%s] DONE: %d products from %d categories",
                     city_name, len(all_products), len(categories))
            return (subdomain, city_name, all_products)

        except Exception as e:
            log.error("[%s] FAILED: %s", city_name, e)
            return (subdomain, city_name, [])
        finally:
            await browser.close()


# ─── DB functions ─────────────────────────────────────────────────────

def save_city_to_db(subdomain: str, city_name: str, products: List[Dict]):
    """Save city products to DB v10 — nomenclature (with price) + product_urls (multi-URL)."""
    try:
        from db_wrapper import get_db
    except ImportError:
        log.error("Cannot import db_wrapper")
        return

    outlet_code = f"moba-{subdomain.split('.')[0]}" if subdomain != "moba.ru" else "moba-online"

    conn = get_db()
    if not conn:
        return
    cur = conn.cursor()

    try:
        # Ensure outlet
        cur.execute(f"""
            INSERT INTO {TABLE_OUTLETS} (code, city, name, is_active)
            VALUES (%s, %s, %s, true)
            ON CONFLICT (code) DO UPDATE SET city = EXCLUDED.city, name = EXCLUDED.name
        """, (outlet_code, city_name, f"Moba.ru {city_name}"))
        conn.commit()

        # Get outlet_id
        cur.execute(f"SELECT id FROM {TABLE_OUTLETS} WHERE code = %s", (outlet_code,))
        outlet_id = cur.fetchone()[0]

        count = 0
        BATCH = 500
        for i, p in enumerate(products):
            article = p.get("article", "").strip()
            if not article:
                continue

            price = p.get("price", 0)

            # UPSERT nomenclature (price в nomenclature)
            cur.execute(f"""
                INSERT INTO {TABLE_NOMENCLATURE} (name, article, category, price, first_seen_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (article) DO UPDATE SET
                    price = EXCLUDED.price,
                    updated_at = NOW()
                RETURNING id
            """, (p.get("name", ""), article, p.get("category"), price))
            row = cur.fetchone()

            nom_id = row[0]
            url = p.get("url", "")
            if url and not url.startswith("http"):
                url = f"https://{subdomain}{url}"

            # INSERT в product_urls (multi-URL: сохраняем outlet_id)
            if url:
                cur.execute(f"""
                    INSERT INTO {TABLE_PRODUCT_URLS} (nomenclature_id, outlet_id, url, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (url) DO NOTHING
                """, (nom_id, outlet_id, url))
            count += 1

            if (i + 1) % BATCH == 0:
                conn.commit()
                log.info("[%s] DB: %d/%d written", city_name, i + 1, len(products))

        conn.commit()
        log.info("[%s] DB: %d records saved (outlet=%s)", city_name, count, outlet_code)

    except Exception as e:
        log.error("[%s] DB error: %s", city_name, e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# ─── main ─────────────────────────────────────────────────────────────

async def amain():
    ap = argparse.ArgumentParser(description="Moba.ru multi-city parser")
    ap.add_argument("--no-db", action="store_true", help="JSON only, no DB")
    ap.add_argument("--cities", type=int, default=None, help="Limit cities count")
    ap.add_argument("--parallel", "-j", type=int, default=4, help="Parallel browsers")
    ap.add_argument("--list", action="store_true", help="List cities and exit")
    ap.add_argument("--skip-moscow", action="store_true",
                    help="Skip Moscow (already parsed separately)")
    args = ap.parse_args()

    cities = CITIES[:]
    if args.skip_moscow:
        cities = [(s, c) for s, c in cities if s != "moba.ru"]
    if args.cities:
        cities = cities[:args.cities]

    if args.list:
        for i, (sub, name) in enumerate(cities, 1):
            print(f"{i:3d}. {name:25s} https://{sub}/")
        print(f"\nTotal: {len(cities)} cities")
        return

    log.info("Parsing %d cities with %d parallel browsers", len(cities), args.parallel)
    sem = asyncio.Semaphore(args.parallel)

    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        tasks = [
            parse_city(sub, name, sem, pw)
            for sub, name in cities
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    DATA_DIR.mkdir(exist_ok=True)
    all_results = {}
    total_products = 0

    for r in results:
        if isinstance(r, Exception):
            log.error("Task failed: %s", r)
            continue
        subdomain, city_name, products = r
        all_results[city_name] = {
            "subdomain": subdomain,
            "products": len(products),
        }
        total_products += len(products)

        if products:
            # Save per-city JSON
            fname = DATA_DIR / f"moba_{subdomain.split('.')[0]}_{datetime.now().strftime('%Y%m%d')}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump({
                    "city": city_name,
                    "subdomain": subdomain,
                    "date": datetime.now().isoformat(),
                    "total": len(products),
                    "products": products,
                }, f, ensure_ascii=False, indent=2)

            # Save to DB
            if not args.no_db:
                save_city_to_db(subdomain, city_name, products)

    # Summary
    log.info("\n=== SUMMARY ===")
    for city, info in sorted(all_results.items()):
        log.info("  %s (%s): %d products", city, info["subdomain"], info["products"])
    log.info("Total: %d products across %d cities", total_products, len(all_results))


if __name__ == "__main__":
    asyncio.run(amain())
