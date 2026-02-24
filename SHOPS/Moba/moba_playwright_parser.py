#!/usr/bin/env python3
"""
Moba.ru Parser — Playwright edition.

Uses headless Chromium to bypass Yandex SmartCaptcha automatically.
No cookies file needed — the browser handles captcha on its own.
Parsing logic (BeautifulSoup) reused from moba_parser.py.
DB functions imported from moba_parser.py.

Requirements:
    pip install playwright playwright-stealth beautifulsoup4
    playwright install chromium && playwright install-deps

Usage:
    python moba_playwright_parser.py --all            # parse + write DB (staging → process)
    python moba_playwright_parser.py --direct         # parse + direct UPSERT
    python moba_playwright_parser.py --no-db          # parse + JSON/CSV only
    python moba_playwright_parser.py --categories     # list categories
    python moba_playwright_parser.py --limit 5        # first 5 categories
"""
import asyncio
import json
import re
import os
import sys
import csv
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from bs4 import BeautifulSoup

# DB functions from existing parser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("moba_pw")

# ─── config ───────────────────────────────────────────────────────────

BASE_URL = "https://moba.ru"
DATA_DIR = Path(__file__).resolve().parent / "moba_data"

SHOP_CODE = "moba-online"
SHOP_NAME = "Moba.ru"
SHOP_CITY = "Москва"

REQUEST_DELAY = 0.5          # seconds between page loads
MAX_PAGES_PER_CATEGORY = 50

# DB table names (shared with moba_parser.py)
TABLE_STAGING = "moba_staging"
TABLE_NOMENCLATURE = "moba_nomenclature"
TABLE_PRODUCT_URLS = "moba_product_urls"
TABLE_OUTLETS = "zip_outlets"

SUCCESS_INDICATORS = ["каталог", "catalog", "main_item_wrapper", "корзин"]

# Фиксированный список категорий для парсинга
ROOT_CATEGORIES = [
    {"url": "/catalog/displei/", "name": "Дисплеи"},
    {"url": "/catalog/akkumulyatory-1/", "name": "Аккумуляторы"},
    {"url": "/catalog/korpusa-zadnie-kryshki/", "name": "Корпуса, задние крышки"},
    {"url": "/catalog/zapchasti/", "name": "Запчасти"},
    {"url": "/catalog/zapchasti-dlya-igrovykh-pristavok/", "name": "Запчасти для игровых приставок"},
    {"url": "/catalog/dlya-noutbukov/", "name": "Для ноутбуков"},
    {"url": "/catalog/korpusnye-chasti-ramki-skotch-stilusy-tolkateli-i-t-p/", "name": "Корпусные части, рамки, скотч, стилусы"},
    {"url": "/catalog/mikroskhemy-kontrollery-usiliteli-i-t-p/", "name": "Микросхемы, контроллеры, усилители"},
    {"url": "/catalog/stekla-plenki-oca-polyarizatory-i-t-p-dlya-displeynykh-moduley/", "name": "Стёкла, плёнки, OCA, поляризаторы"},
    {"url": "/catalog/shleyfy-platy/", "name": "Шлейфы, платы"},
]


# ─── Playwright-based HTTP layer ──────────────────────────────────────

class PlaywrightFetcher:
    """Manages a Playwright browser for fetching pages through SmartCaptcha."""

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self):
        from playwright.async_api import async_playwright
        self._pw_cm = async_playwright()
        self._pw = await self._pw_cm.__aenter__()
        self._browser = await self._pw.chromium.launch(
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--lang=ru-RU,ru",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        # Apply stealth if available
        try:
            from playwright_stealth import stealth_async
            self._page = await self._context.new_page()
            await stealth_async(self._page)
        except ImportError:
            self._page = await self._context.new_page()

        # Initial navigation — passes SmartCaptcha
        log.info("Opening %s ...", BASE_URL)
        await self._page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30_000)
        await self._page.wait_for_timeout(3000)

        content = await self._page.content()
        if any(s in content.lower() for s in SUCCESS_INDICATORS):
            log.info("SmartCaptcha passed — site accessible")
        else:
            log.warning("Initial page may not be catalog — continuing anyway")

    async def get(self, path: str) -> Optional[str]:
        """Navigate to path and return page HTML. Returns None on error."""
        url = BASE_URL + path if path.startswith("/") else path
        try:
            resp = await self._page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            await self._page.wait_for_timeout(500)  # small settle time
            html = await self._page.content()
            return html
        except Exception as e:
            log.error("Failed to fetch %s: %s", url, e)
            return None

    async def close(self):
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_pw_cm") and self._pw_cm:
            await self._pw_cm.__aexit__(None, None, None)


# ─── parsing (reused from moba_parser.py) ─────────────────────────────

def parse_product_list(soup: BeautifulSoup) -> List[Dict]:
    products = []
    items = soup.select("tr.item.main_item_wrapper")
    if not items:
        for sel in ["div.catalog-item", "div.item-card", "div.product-item"]:
            items = soup.select(sel)
            if items:
                break
    for item in items:
        try:
            p = parse_product_item(item)
            if p:
                products.append(p)
        except Exception:
            continue
    return products


def parse_product_item(item) -> Optional[Dict]:
    product = {}
    product_id = None
    name_link = None
    for a in item.find_all("a", href=True):
        href = a.get("href", "")
        if href.startswith("/catalog/") and href.count("/") >= 3:
            text = a.get_text(strip=True)
            if text and len(text) > 5:
                name_link = a
                parts = href.rstrip("/").split("/")
                if parts and parts[-1].isdigit():
                    product_id = parts[-1]
                break
    if name_link:
        product["name"] = name_link.get_text(strip=True)
        product["url"] = name_link.get("href", "")
        if product_id:
            product["article"] = f"MOBA-{product_id}"
    price_elem = item.select_one(".cost") or item.find(class_="price")
    if price_elem:
        price_text = price_elem.get_text(strip=True)
        m = re.search(r'([\d\s]+)', price_text.replace("\xa0", " "))
        if m:
            try:
                product["price"] = float(m.group(1).replace(" ", "").strip())
            except ValueError:
                product["price"] = 0
    img = item.find("img")
    if img:
        src = img.get("src") or img.get("data-src", "")
        if src:
            product["image"] = src
    return product if product.get("name") and product.get("article") else None


# ─── main parser ──────────────────────────────────────────────────────

async def get_categories(fetcher: PlaywrightFetcher) -> List[Dict]:
    html = await fetcher.get("/catalog/")
    if not html:
        return []
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
    log.info("Found %d categories", len(categories))
    return categories


async def get_category_products(
    fetcher: PlaywrightFetcher,
    category_url: str,
    max_pages: int = MAX_PAGES_PER_CATEGORY,
) -> List[Dict]:
    products = []
    for page_num in range(1, max_pages + 1):
        url = f"{category_url}?PAGEN_1={page_num}" if page_num > 1 else category_url
        html = await fetcher.get(url)
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        page_prods = parse_product_list(soup)
        if not page_prods:
            break
        products.extend(page_prods)

        # Pagination check
        next_link = (
            soup.find("a", class_="flex-next")
            or soup.find("a", class_="next")
            or soup.find("a", {"rel": "next"})
        )
        if not next_link:
            pagen = soup.find_all("a", href=lambda h: h and f"PAGEN_1={page_num+1}" in h)
            if not pagen:
                break

        await asyncio.sleep(REQUEST_DELAY)

    return products


async def parse_all(
    fetcher: PlaywrightFetcher,
    max_categories: int = None,
    max_pages: int = MAX_PAGES_PER_CATEGORY,
) -> List[Dict]:
    all_products = []
    categories = list(ROOT_CATEGORIES)
    if max_categories:
        categories = categories[:max_categories]

    for i, cat in enumerate(categories, 1):
        log.info("[%d/%d] %s", i, len(categories), cat["name"])
        prods = await get_category_products(fetcher, cat["url"], max_pages)
        log.info("  → %d products", len(prods))
        for p in prods:
            p["category"] = cat["name"]
        all_products.extend(prods)
        await asyncio.sleep(0.5)

    log.info("Total: %d products from %d categories", len(all_products), len(categories))
    return all_products


# ─── save helpers ─────────────────────────────────────────────────────

def save_json(products: List[Dict]):
    DATA_DIR.mkdir(exist_ok=True)
    fname = DATA_DIR / f"moba_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    data = {
        "source": SHOP_NAME,
        "date": datetime.now().isoformat(),
        "total": len(products),
        "products": products,
    }
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("JSON → %s (%d products)", fname, len(products))


def save_csv(products: List[Dict]):
    DATA_DIR.mkdir(exist_ok=True)
    fname = DATA_DIR / f"moba_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    if not products:
        return
    fields = ["article", "name", "price", "category", "url", "image"]
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(products)
    log.info("CSV → %s", fname)


# ─── DB (import from existing moba_parser.py) ─────────────────────────

def _import_db_functions():
    """Lazy import DB functions from moba_parser.py."""
    try:
        from moba_parser import ensure_outlet, save_staging, process_staging, save_to_db
        return ensure_outlet, save_staging, process_staging, save_to_db
    except ImportError as e:
        log.error("Cannot import DB functions from moba_parser.py: %s", e)
        return None, None, None, None


# ─── CLI ──────────────────────────────────────────────────────────────

async def amain():
    ap = argparse.ArgumentParser(description="Moba.ru parser (Playwright)")
    ap.add_argument("--all", action="store_true", help="Parse + staging → process")
    ap.add_argument("--direct", action="store_true", help="Parse + direct UPSERT")
    ap.add_argument("--no-db", action="store_true", help="Parse → JSON/CSV only")
    ap.add_argument("--categories", action="store_true", help="List categories")
    ap.add_argument("--limit", "-l", type=int, default=None, help="Max categories")
    ap.add_argument("--pages", "-p", type=int, default=MAX_PAGES_PER_CATEGORY, help="Max pages/category")
    ap.add_argument("--headed", action="store_true", help="Visible browser")
    args = ap.parse_args()

    fetcher = PlaywrightFetcher(headless=not args.headed)
    await fetcher.start()

    try:
        if args.categories:
            cats = await get_categories(fetcher)
            for i, c in enumerate(cats, 1):
                print(f"{i}. {c['name']}: {c['url']}")
            return

        products = await parse_all(fetcher, max_categories=args.limit, max_pages=args.pages)
        save_json(products)
        save_csv(products)

        if args.no_db:
            log.info("Done (no DB write)")
            return

        ensure_outlet, save_staging, process_staging, save_to_db = _import_db_functions()
        if not save_to_db:
            log.error("DB functions not available — saved to JSON/CSV only")
            return

        if args.direct:
            save_to_db(products)
        else:
            save_staging(products)
            if args.all:
                process_staging()

        log.info("Done!")

    finally:
        await fetcher.close()


if __name__ == "__main__":
    asyncio.run(amain())
