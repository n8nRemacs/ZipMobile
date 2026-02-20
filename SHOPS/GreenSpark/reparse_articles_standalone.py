"""
Допарсинг артикулов GreenSpark - standalone скрипт

Выбирает уникальные товары без артикула из staging,
допарсивает артикулы через API, обновляет staging.

Запуск после завершения основного парсинга:
    python reparse_articles_standalone.py --all

Или только допарсинг без обработки:
    python reparse_articles_standalone.py
"""

import httpx
import json
import time
import os
import re
import argparse
import psycopg2
from datetime import datetime
from typing import Optional, List, Dict
from urllib.parse import unquote

# === Конфигурация ===
HOST = "green-spark.ru"
BASE_URL = f"https://{HOST}"
API_URL = f"https://{HOST}/local/api"

REQUEST_DELAY = 1.0  # Задержка между запросами (секунды)
REQUEST_TIMEOUT = 30
COOKIES_FILE = "cookies.json"
BATCH_SIZE = 100  # Сохранять в БД каждые N товаров

# === Конфигурация БД ===
DB_HOST = os.environ.get("DB_HOST", "85.198.98.104")
DB_PORT = int(os.environ.get("DB_PORT", 5433))
DB_NAME = os.environ.get("DB_NAME", "db_greenspark")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mi31415926pSss!")


def get_db():
    """Подключение к БД"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"
    )


def load_cookies() -> dict:
    """Загрузить cookies из файла"""
    if os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            print(f"Cookies загружены из {COOKIES_FILE}")
            return cookies
        except Exception as e:
            print(f"Ошибка загрузки cookies: {e}")
    return {}


def get_products_without_article() -> List[Dict]:
    """Получить уникальные товары без артикула из staging"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT name, url
            FROM staging
            WHERE (article IS NULL OR article = '')
              AND url IS NOT NULL AND url != ''
            ORDER BY name
        """)
        rows = cur.fetchall()
        return [{"name": row[0], "url": row[1]} for row in rows]
    finally:
        cur.close()
        conn.close()


def update_staging_article(name: str, article: str):
    """Обновить артикул в staging по названию товара"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE staging
            SET article = %s
            WHERE name = %s AND (article IS NULL OR article = '')
        """, (article, name))
        updated = cur.rowcount
        conn.commit()
        return updated
    finally:
        cur.close()
        conn.close()


def batch_update_articles(updates: List[Dict]):
    """Пакетное обновление артикулов"""
    if not updates:
        return 0

    conn = get_db()
    cur = conn.cursor()
    total_updated = 0
    try:
        for item in updates:
            cur.execute("""
                UPDATE staging
                SET article = %s
                WHERE name = %s AND (article IS NULL OR article = '')
            """, (item["article"], item["name"]))
            total_updated += cur.rowcount
        conn.commit()
        return total_updated
    finally:
        cur.close()
        conn.close()


def get_staging_stats():
    """Получить статистику staging"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN article IS NULL OR article = '' THEN 1 ELSE 0 END) as no_article,
                SUM(CASE WHEN article IS NOT NULL AND article != '' THEN 1 ELSE 0 END) as with_article
            FROM staging
        """)
        row = cur.fetchone()
        return {"total": row[0], "no_article": row[1], "with_article": row[2]}
    finally:
        cur.close()
        conn.close()


class ArticleParser:
    """Парсер артикулов"""

    def __init__(self):
        cookies = load_cookies()

        default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        user_agent = unquote(cookies.get("__jua_", "")) or default_ua

        self.client = httpx.Client(
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru,en;q=0.9",
            },
            cookies=cookies,
            follow_redirects=True,
        )
        self.delay = REQUEST_DELAY
        self.last_request = 0

    def _rate_limit(self):
        """Ограничение частоты запросов"""
        elapsed = time.time() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request = time.time()

    def _build_path_params(self, path_parts: List[str]) -> str:
        """Построить параметры path[] для URL"""
        params = []
        for part in path_parts:
            params.append(f"path[]={part}")
        return "&".join(params)

    def fetch_article_from_api(self, product_url: str) -> str:
        """Получить артикул через детальный API"""
        self._rate_limit()
        try:
            # Извлекаем path из URL: /catalog/a/b/c/product.html -> ["a", "b", "c", "product"]
            match = re.search(r'/catalog/(.+?)(?:\.html)?/?$', product_url)
            if not match:
                return ""

            path_str = match.group(1).rstrip('/')
            path_parts = path_str.split('/')

            # Строим URL для detail API
            path_params = self._build_path_params(path_parts)
            api_url = f"{API_URL}/catalog/detail/?{path_params}"

            response = self.client.get(api_url)
            if response.status_code != 200:
                return ""

            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                return ""

            data = response.json()
            product = data.get("product", {})
            article = product.get("article", "")

            return article.strip() if article else ""

        except Exception as e:
            return ""

    def fetch_article_from_html(self, product_url: str) -> str:
        """Получить артикул через HTML (fallback)"""
        self._rate_limit()
        try:
            response = self.client.get(product_url)
            if response.status_code != 200:
                return ""

            html = response.text
            # Ищем паттерн "Артикул: XXX-XXXXX"
            match = re.search(r'Артикул[:\s]*([А-ЯA-Zа-яa-z]{2,3}-\d+)', html, re.IGNORECASE)
            if match:
                return match.group(1).upper()
            return ""
        except Exception:
            return ""

    def fetch_article(self, product_url: str) -> str:
        """Получить артикул (сначала API, потом HTML)"""
        article = self.fetch_article_from_api(product_url)
        if article:
            return article
        return self.fetch_article_from_html(product_url)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def process_staging():
    """Обработка staging: UPSERT в nomenclature и current_prices"""
    conn = get_db()
    cur = conn.cursor()
    try:
        # 1. UPSERT в nomenclature
        cur.execute("""
            INSERT INTO nomenclature (article, name, category, first_seen_at, updated_at)
            SELECT DISTINCT ON (article)
                article, name, category, NOW(), NOW()
            FROM staging
            WHERE article IS NOT NULL AND article != ''
            ON CONFLICT (article) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                updated_at = NOW()
        """)
        nom_count = cur.rowcount
        print(f"Nomenclature: {nom_count} записей")

        # 2. UPSERT в current_prices
        cur.execute("""
            INSERT INTO current_prices (nomenclature_id, outlet_id, price, price_wholesale, updated_at)
            SELECT DISTINCT ON (n.id, o.id)
                n.id, o.id, s.price, s.price_wholesale, NOW()
            FROM staging s
            JOIN nomenclature n ON n.article = s.article
            JOIN outlets o ON o.code = s.outlet_code
            WHERE s.article IS NOT NULL AND s.article != ''
            ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
                price = EXCLUDED.price,
                price_wholesale = EXCLUDED.price_wholesale,
                updated_at = NOW()
        """)
        price_count = cur.rowcount
        print(f"Current prices: {price_count} записей")

        # 3. INSERT в price_history
        cur.execute("""
            INSERT INTO price_history (nomenclature_id, outlet_id, price, recorded_date, recorded_at)
            SELECT DISTINCT ON (n.id, o.id)
                n.id, o.id, s.price, CURRENT_DATE, NOW()
            FROM staging s
            JOIN nomenclature n ON n.article = s.article
            JOIN outlets o ON o.code = s.outlet_code
            WHERE s.article IS NOT NULL AND s.article != ''
            ON CONFLICT (nomenclature_id, outlet_id, recorded_date) DO UPDATE SET
                price = EXCLUDED.price,
                recorded_at = NOW()
        """)
        hist_count = cur.rowcount
        print(f"Price history: {hist_count} записей")

        conn.commit()

        # Статистика
        cur.execute("SELECT COUNT(*) FROM nomenclature")
        total_nom = cur.fetchone()[0]
        print(f"\n=== Итого в БД ===")
        print(f"Номенклатура: {total_nom}")

    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Допарсинг артикулов GreenSpark')
    parser.add_argument('--all', action='store_true',
                       help='После допарсинга запустить process_staging()')
    parser.add_argument('--limit', '-l', type=int, default=0,
                       help='Лимит товаров для допарсинга (0 = все)')
    parser.add_argument('--stats', action='store_true',
                       help='Только показать статистику')
    args = parser.parse_args()

    # Статистика
    print(f"\n{'='*60}")
    print(f"Допарсинг артикулов GreenSpark")
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    stats = get_staging_stats()
    print(f"Staging: {stats['total']} записей")
    print(f"  С артикулом: {stats['with_article']}")
    print(f"  Без артикула: {stats['no_article']}")

    if args.stats:
        return

    # Получаем товары без артикула
    products = get_products_without_article()
    print(f"\nУникальных товаров без артикула: {len(products)}")

    if not products:
        print("Нет товаров для допарсинга!")
        return

    if args.limit > 0:
        products = products[:args.limit]
        print(f"Лимит: {args.limit} товаров")

    # Допарсинг
    print(f"\n{'='*60}")
    print(f"Начинаем допарсинг {len(products)} товаров...")
    print(f"Примерное время: {len(products) * REQUEST_DELAY / 60:.1f} минут")
    print(f"{'='*60}\n")

    found = 0
    not_found = 0
    batch_updates = []

    with ArticleParser() as article_parser:
        for idx, product in enumerate(products):
            url = product["url"]
            name = product["name"]

            article = article_parser.fetch_article(url)

            if article:
                found += 1
                batch_updates.append({"name": name, "article": article})
            else:
                not_found += 1

            # Пакетное сохранение
            if len(batch_updates) >= BATCH_SIZE:
                updated = batch_update_articles(batch_updates)
                print(f"  [{idx+1}/{len(products)}] Сохранено {updated} записей в staging")
                batch_updates = []

            # Прогресс каждые 100 товаров
            if (idx + 1) % 100 == 0:
                print(f"  Обработано {idx+1}/{len(products)}: найдено {found}, не найдено {not_found}")

    # Сохранить оставшиеся
    if batch_updates:
        updated = batch_update_articles(batch_updates)
        print(f"  Финальное сохранение: {updated} записей")

    print(f"\n{'='*60}")
    print(f"Допарсинг завершён!")
    print(f"  Найдено артикулов: {found}")
    print(f"  Не найдено: {not_found}")
    print(f"{'='*60}")

    # Итоговая статистика
    stats = get_staging_stats()
    print(f"\nStaging после допарсинга:")
    print(f"  С артикулом: {stats['with_article']}")
    print(f"  Без артикула: {stats['no_article']}")

    # Обработка staging
    if args.all:
        print(f"\n{'='*60}")
        print("Обработка staging...")
        print(f"{'='*60}\n")
        process_staging()

    print("\nГотово!")


if __name__ == "__main__":
    main()
