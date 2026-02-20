"""
Moba.ru Parser - ZipMobile Integration v2.0
Парсер номенклатуры moba.ru с обходом Yandex SmartCaptcha

БД: Supabase (griexhozxrqtepcilfnu)
Таблицы: moba_staging, moba_nomenclature, moba_prices, zip_outlets
"""
import json
import time
import re
import os
import sys
import csv
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from urllib.parse import urljoin

# Подключение к Supabase через db_wrapper
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

BASE_URL = "https://moba.ru"
COOKIES_FILE = "moba_cookies.json"
DATA_DIR = "moba_data"

# Код магазина
SHOP_CODE = "moba-online"
SHOP_NAME = "Moba.ru"
SHOP_CITY = "Москва"

# Параметры парсинга
REQUEST_DELAY = 0.5
MAX_PAGES_PER_CATEGORY = 50

# Таблицы (полные имена в Supabase)
TABLE_STAGING = "moba_staging"
TABLE_NOMENCLATURE = "moba_nomenclature"
TABLE_PRODUCT_URLS = "moba_product_urls"
TABLE_OUTLETS = "zip_outlets"


# ============================================================
# ПАРСЕР
# ============================================================

class MobaParser:
    """Парсер каталога Moba.ru"""

    def __init__(self, cookies_file=COOKIES_FILE):
        self.base_url = BASE_URL
        self.session = curl_requests.Session(impersonate="chrome120")
        self.cookies = {}
        self.products: List[Dict] = []
        self.errors: List[Dict] = []

        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?1",
            "Sec-Ch-Ua-Platform": '"Android"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Referer": "https://moba.ru/",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36",
        }

        # Load cookies
        if os.path.exists(cookies_file):
            with open(cookies_file, "r") as f:
                self.cookies = json.load(f)
            self.headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
            print(f"[+] Loaded {len(self.cookies)} cookies")
        else:
            print(f"[!] Cookies file not found: {cookies_file}")

        Path(DATA_DIR).mkdir(exist_ok=True)

    def get(self, url, **kwargs):
        """Make GET request with cookies"""
        full_url = urljoin(self.base_url, url)
        resp = self.session.get(full_url, headers=self.headers, **kwargs)
        return resp

    def test_access(self) -> bool:
        """Test if we can access the site"""
        try:
            resp = self.get("/")
            if resp.status_code == 200 and "каталог" in resp.text.lower():
                print("[+] Access OK!")
                return True
            print(f"[!] Access failed: {resp.status_code}")
            return False
        except Exception as e:
            print(f"[!] Connection error: {e}")
            return False

    def get_categories(self) -> List[Dict]:
        """Get all product categories"""
        print("[*] Getting categories...")
        resp = self.get("/catalog/")

        if resp.status_code != 200:
            print(f"[!] Failed to get catalog: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        categories = []

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if (href.startswith("/catalog/") and
                href != "/catalog/" and
                "filter" not in href and
                "?" not in href):
                clean_url = href.split("?")[0]
                if clean_url not in [c["url"] for c in categories]:
                    name = link.get_text(strip=True)
                    if name and len(name) > 1:
                        categories.append({
                            "url": clean_url,
                            "name": name[:100]
                        })

        print(f"[+] Found {len(categories)} categories")
        return categories

    def get_category_products(self, category_url: str, max_pages: int = MAX_PAGES_PER_CATEGORY) -> List[Dict]:
        """Get all products from a category with pagination"""
        products = []
        page = 1

        while page <= max_pages:
            url = f"{category_url}?PAGEN_1={page}" if page > 1 else category_url
            print(f"  Page {page}: {url}")

            resp = self.get(url)
            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            page_products = self.parse_product_list(soup)

            if not page_products:
                break

            products.extend(page_products)

            # Check pagination - Moba uses flex-next class
            next_link = (soup.find("a", class_="flex-next") or
                        soup.find("a", class_="next") or
                        soup.find("a", {"rel": "next"}))
            if not next_link:
                # Also check for PAGEN links
                pagen_links = soup.find_all("a", href=lambda h: h and f"PAGEN_1={page+1}" in h)
                if not pagen_links:
                    break

            page += 1
            time.sleep(REQUEST_DELAY)

        return products

    def parse_product_list(self, soup) -> List[Dict]:
        """Parse products from listing page"""
        products = []

        # Moba.ru uses table-based layout
        items = soup.select("tr.item.main_item_wrapper")

        if not items:
            for selector in ["div.catalog-item", "div.item-card", "div.product-item"]:
                items = soup.select(selector)
                if items:
                    break

        for item in items:
            try:
                product = self.parse_product_item(item)
                if product:
                    products.append(product)
            except Exception as e:
                self.errors.append({
                    "type": "parse_error",
                    "error": str(e),
                    "time": datetime.now().isoformat()
                })

        return products

    def parse_product_item(self, item) -> Optional[Dict]:
        """Parse single product from listing"""
        product = {}
        product_id = None

        # Find product link
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

        # Get price
        price_elem = item.select_one(".cost") or item.find(class_="price")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'([\d\s]+)', price_text.replace("\xa0", " "))
            if price_match:
                try:
                    product["price"] = float(price_match.group(1).replace(" ", "").strip())
                except ValueError:
                    product["price"] = 0

        # Get image
        img = item.find("img")
        if img:
            src = img.get("src") or img.get("data-src", "")
            if src:
                product["image"] = src

        # (stock fields removed)

        return product if product.get("name") and product.get("article") else None

    def parse_all(self, max_categories: int = None, max_pages: int = MAX_PAGES_PER_CATEGORY) -> List[Dict]:
        """Parse all products from all categories"""
        self.products = []
        categories = self.get_categories()

        if max_categories:
            categories = categories[:max_categories]

        for i, cat in enumerate(categories, 1):
            print(f"\n[{i}/{len(categories)}] {cat['name']}")

            products = self.get_category_products(cat["url"], max_pages=max_pages)
            print(f"  -> {len(products)} products")

            for p in products:
                p["category"] = cat["name"]
                self.products.append(p)

            time.sleep(1)

        return self.products

    def save_to_json(self, filename: str = None):
        """Save to JSON"""
        filename = filename or f"{DATA_DIR}/moba_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = {
            "source": SHOP_NAME,
            "date": datetime.now().isoformat(),
            "total": len(self.products),
            "products": self.products,
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[+] Saved JSON: {filename} ({len(self.products)} products)")

    def save_to_csv(self, filename: str = None):
        """Save to CSV"""
        filename = filename or f"{DATA_DIR}/moba_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        if not self.products:
            return

        fieldnames = ["article", "name", "price", "category", "url", "image"]
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.products)
        print(f"[+] Saved CSV: {filename}")


# ============================================================
# ФУНКЦИИ БД
# ============================================================

def ensure_outlet():
    """Create outlet if not exists"""
    conn = get_db()
    if not conn:
        return
    cur = conn.cursor()
    try:
        cur.execute(f"""
            INSERT INTO {TABLE_OUTLETS} (code, city, name, is_active)
            VALUES (%s, %s, %s, true)
            ON CONFLICT (code) DO NOTHING
        """, (SHOP_CODE, SHOP_CITY, SHOP_NAME))
        conn.commit()
        print(f"[+] Outlet ensured: {SHOP_CODE}")
    finally:
        cur.close()
        conn.close()


def save_staging(products: List[Dict]):
    """Save products to moba_staging table"""
    if not products:
        print("[!] No products to save to staging")
        return

    conn = get_db()
    if not conn:
        return

    cur = conn.cursor()
    try:
        cur.execute(f"TRUNCATE TABLE {TABLE_STAGING}")

        insert_sql = f"""
            INSERT INTO {TABLE_STAGING} (
                outlet_code, name, article, category,
                price, url
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """

        for p in products:
            cur.execute(insert_sql, (
                SHOP_CODE,
                p.get("name", ""),
                p.get("article", ""),
                p.get("category", ""),
                p.get("price", 0),
                p.get("url", ""),
            ))

        conn.commit()
        print(f"[+] Saved to staging: {len(products)} products")
    finally:
        cur.close()
        conn.close()


def process_staging():
    """Process moba_staging: UPSERT to moba_nomenclature (with price) + moba_product_urls"""
    conn = get_db()
    if not conn:
        return

    cur = conn.cursor()
    try:
        ensure_outlet()

        # 1. UPSERT moba_nomenclature (price в nomenclature)
        cur.execute(f"""
            INSERT INTO {TABLE_NOMENCLATURE} (article, name, category, price, first_seen_at, updated_at)
            SELECT DISTINCT ON (article)
                article, name, category, price, NOW(), NOW()
            FROM {TABLE_STAGING}
            WHERE article IS NOT NULL AND article != ''
            ON CONFLICT (article) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                price = EXCLUDED.price,
                updated_at = NOW()
        """)
        nom_count = cur.rowcount
        print(f"[+] Nomenclature: {nom_count} records")

        # 2. INSERT moba_product_urls (multi-URL: outlet_id сохраняется)
        cur.execute(f"""
            INSERT INTO {TABLE_PRODUCT_URLS} (nomenclature_id, outlet_id, url, updated_at)
            SELECT DISTINCT ON (s.url)
                n.id, o.id, s.url, NOW()
            FROM {TABLE_STAGING} s
            JOIN {TABLE_NOMENCLATURE} n ON n.article = s.article
            JOIN {TABLE_OUTLETS} o ON o.code = s.outlet_code
            WHERE s.article IS NOT NULL AND s.article != ''
              AND s.url IS NOT NULL AND s.url != ''
            ON CONFLICT (url) DO NOTHING
        """)
        url_count = cur.rowcount
        print(f"[+] Product URLs: {url_count} records")

        conn.commit()

        # Stats
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NOMENCLATURE}")
        total_nom = cur.fetchone()[0]

        print(f"\n=== DB Stats ===")
        print(f"Nomenclature: {total_nom}")

    finally:
        cur.close()
        conn.close()


def save_to_db(products: List[Dict]):
    """
    Прямое сохранение v10: moba_nomenclature (с price) + moba_product_urls (multi-URL)
    UPSERT по article (уникальный ключ товара)
    Batch commit каждые 200 записей + reconnect
    """
    if not products:
        print("[!] No products to save")
        return

    BATCH_SIZE = 200

    ensure_outlet()
    import time
    time.sleep(1)

    conn = get_db()
    if not conn:
        return

    cur = conn.cursor()
    try:
        # Получаем outlet_id
        cur.execute(f"SELECT id FROM {TABLE_OUTLETS} WHERE code = %s", (SHOP_CODE,))
        outlet_row = cur.fetchone()
        if not outlet_row:
            print(f"[!] Outlet {SHOP_CODE} not found")
            return
        outlet_id = outlet_row[0]

        nom_inserted = 0
        nom_updated = 0
        urls_inserted = 0

        for i, p in enumerate(products):
            article = p.get("article", "").strip()
            if not article:
                continue

            name = p.get("name", "").strip()
            if not name:
                continue

            # URL товара
            product_url = p.get("url", "")
            if product_url and not product_url.startswith("http"):
                product_url = BASE_URL + product_url

            category = p.get("category", "").strip() or None
            price = p.get("price", 0)

            # 1. UPSERT в moba_nomenclature (price в nomenclature)
            cur.execute(f"""
                INSERT INTO {TABLE_NOMENCLATURE} (name, article, category, price, first_seen_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (article) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    updated_at = NOW()
                RETURNING id, (xmax = 0) as inserted
            """, (name, article, category, price))

            row = cur.fetchone()
            nomenclature_id = row[0]
            if row[1]:
                nom_inserted += 1
            else:
                nom_updated += 1

            # 2. INSERT в moba_product_urls (multi-URL: сохраняем outlet_id)
            if product_url:
                cur.execute(f"""
                    INSERT INTO {TABLE_PRODUCT_URLS} (nomenclature_id, outlet_id, url, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (url) DO NOTHING
                """, (nomenclature_id, outlet_id, product_url))
                urls_inserted += 1

            # Batch commit + reconnect
            if (i + 1) % BATCH_SIZE == 0:
                conn.commit()
                print(f"  [DB] {i + 1}/{len(products)} записано...")
                cur.close()
                conn.close()
                import time
                time.sleep(1)
                conn = get_db()
                cur = conn.cursor()
                # Re-fetch outlet_id after reconnect
                cur.execute(f"SELECT id FROM {TABLE_OUTLETS} WHERE code = %s", (SHOP_CODE,))
                outlet_id = cur.fetchone()[0]

        conn.commit()

        print(f"\n=== Saved to DB (v10) ===")
        print(f"moba_nomenclature: +{nom_inserted} new, ~{nom_updated} updated")
        print(f"moba_product_urls: {urls_inserted} URL")

        # Итоговая статистика
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NOMENCLATURE}")
        total_nom = cur.fetchone()[0]
        print(f"\nTotal in DB: {total_nom} products")

    finally:
        cur.close()
        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():
    arg_parser = argparse.ArgumentParser(description=f'Parser {SHOP_NAME}')
    arg_parser.add_argument('--all', action='store_true',
                           help='Full cycle: parse → save_staging → process_staging')
    arg_parser.add_argument('--process', action='store_true',
                           help='Only process staging → nomenclature + prices')
    arg_parser.add_argument('--no-db', action='store_true',
                           help='Do not save to DB (parse + JSON/CSV only)')
    arg_parser.add_argument('--direct', action='store_true',
                           help='Direct UPSERT to moba_nomenclature + moba_prices (without staging)')
    arg_parser.add_argument('--categories', action='store_true',
                           help='List categories only')
    arg_parser.add_argument('--limit', '-l', type=int, default=None,
                           help='Limit categories count')
    arg_parser.add_argument('--pages', '-p', type=int, default=MAX_PAGES_PER_CATEGORY,
                           help='Max pages per category')

    args = arg_parser.parse_args()

    # Only process staging
    if args.process:
        print("[*] Processing staging...")
        process_staging()
        return

    # Parse
    parser = MobaParser()

    if not parser.test_access():
        print("[!] Cannot access site. Update cookies!")
        return

    # List categories
    if args.categories:
        cats = parser.get_categories()
        for i, c in enumerate(cats, 1):
            print(f"{i}. {c['name']}: {c['url']}")
        return

    # Full parse
    parser.parse_all(max_categories=args.limit, max_pages=args.pages)
    parser.save_to_json()
    parser.save_to_csv()

    # Save to DB
    if not args.no_db:
        if args.direct:
            # Direct UPSERT (without staging)
            save_to_db(parser.products)
        else:
            # Standard: staging → process
            save_staging(parser.products)
            if args.all:
                process_staging()

    print("\n[+] Done!")


if __name__ == "__main__":
    main()
