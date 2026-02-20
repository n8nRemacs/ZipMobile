"""
Парсер Signal23.ru - запчасти для телефонов, планшетов, ноутбуков, ПК

База данных: db_signal23
Формат: HTML парсинг (OpenCart 3.0)
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import psycopg2
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Set
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    BASE_URL, START_CATEGORIES, REQUEST_DELAY, REQUEST_TIMEOUT,
    MAX_RETRIES, ITEMS_PER_PAGE, USER_AGENT,
    DATA_DIR, PRODUCTS_JSON, PRODUCTS_CSV, CATEGORIES_JSON, ERRORS_LOG
)

# ============================================================
# КОНФИГУРАЦИЯ БД
# ============================================================

# === Конфигурация БД (Supabase) ===
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db  # Автоматически маппит таблицы на новые имена

# Код магазина для outlets
SHOP_CODE = "signal23-online"
SHOP_NAME = "Signal23"
SHOP_CITY = "Москва"


# ============================================================
# КЛАСС ПАРСЕРА
# ============================================================

class Signal23Parser:
    """Парсер каталога Signal23.ru"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })
        self.products: List[Dict] = []
        self.categories: Dict[str, str] = {}
        self.errors: List[Dict] = []
        self.visited_urls: Set[str] = set()
        self.last_request_time = 0

        os.makedirs(DATA_DIR, exist_ok=True)

    def _delay(self):
        """Задержка между запросами"""
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, url: str, retries: int = MAX_RETRIES) -> Optional[requests.Response]:
        """HTTP запрос с повторами"""
        self._delay()

        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.errors.append({
                        "url": url,
                        "error": str(e),
                        "time": datetime.now().isoformat()
                    })
        return None

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Получить BeautifulSoup для URL"""
        response = self._make_request(url)
        if response:
            return BeautifulSoup(response.text, 'html.parser')
        return None

    def parse_all(self, limit: int = None, parallel: bool = False) -> List[Dict]:
        """
        Основной метод парсинга.
        1. Обходит стартовые категории
        2. Рекурсивно собирает подкатегории
        3. Собирает товары из конечных категорий
        """
        print(f"{'='*60}")
        print(f"Парсинг {SHOP_NAME}")
        print(f"{'='*60}\n")

        # Собираем все категории
        all_categories = []
        for start_cat in START_CATEGORIES:
            url = urljoin(BASE_URL, start_cat)
            print(f"[КАТЕГОРИЯ] {start_cat}")
            cats = self._collect_categories(url)
            all_categories.extend(cats)
            print(f"  Найдено подкатегорий: {len(cats)}")

        print(f"\nВсего категорий для парсинга: {len(all_categories)}")

        # Сохраняем категории
        self._save_categories(all_categories)

        # Парсим товары из категорий
        if parallel and len(all_categories) > 1:
            self._parse_categories_parallel(all_categories, limit)
        else:
            self._parse_categories_sequential(all_categories, limit)

        print(f"\n{'='*60}")
        print(f"Итого собрано товаров: {len(self.products)}")
        print(f"Ошибок: {len(self.errors)}")
        print(f"{'='*60}")

        return self.products

    def _collect_categories(self, url: str, depth: int = 0, max_depth: int = 5) -> List[Dict]:
        """Рекурсивный сбор категорий"""
        if depth > max_depth or url in self.visited_urls:
            return []

        self.visited_urls.add(url)
        categories = []

        soup = self._get_soup(url)
        if not soup:
            return []

        # Ищем подкатегории в сайдбаре или основном контенте
        # OpenCart обычно показывает подкатегории в left-sidebar или main content
        subcats = soup.select('.category-parent a, .category-list a, .list-group-item')

        if not subcats:
            # Это конечная категория - возвращаем её
            name = self._extract_category_name(soup)
            if name:
                categories.append({
                    "url": url,
                    "name": name,
                    "depth": depth
                })
        else:
            # Есть подкатегории - рекурсивно обходим
            for link in subcats:
                href = link.get('href', '')
                if href and href.startswith(('http', '/')):
                    sub_url = urljoin(BASE_URL, href)
                    # Пропускаем ссылки не на категории
                    if '/category/' in sub_url or any(cat in sub_url for cat in ['zapchasti-', 'akkumulyatory', 'displei', 'tachskr']):
                        sub_cats = self._collect_categories(sub_url, depth + 1)
                        categories.extend(sub_cats)

        # Если не нашли подкатегории через сайдбар, проверяем карточки категорий
        if not categories:
            cat_cards = soup.select('.category-card, .category-item, .sub-category')
            if cat_cards:
                for card in cat_cards:
                    link = card.find('a')
                    if link and link.get('href'):
                        sub_url = urljoin(BASE_URL, link['href'])
                        sub_cats = self._collect_categories(sub_url, depth + 1)
                        categories.extend(sub_cats)
            else:
                # Это конечная категория
                name = self._extract_category_name(soup)
                if name:
                    categories.append({
                        "url": url,
                        "name": name,
                        "depth": depth
                    })

        return categories

    def _extract_category_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечь название категории из страницы"""
        # Из breadcrumbs
        breadcrumbs = soup.select('.breadcrumb li, .breadcrumb a')
        if breadcrumbs:
            return ' / '.join([b.get_text(strip=True) for b in breadcrumbs[1:]])  # Пропускаем "Главная"

        # Из заголовка
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        title = soup.find('title')
        if title:
            return title.get_text(strip=True).split('|')[0].strip()

        return None

    def _parse_categories_sequential(self, categories: List[Dict], limit: int = None):
        """Последовательный парсинг категорий"""
        total = len(categories)
        for i, cat in enumerate(categories, 1):
            print(f"\n[{i}/{total}] {cat['name'][:50]}...")
            products = self._parse_category_products(cat['url'], limit)
            self.products.extend(products)
            print(f"  Товаров: {len(products)}")

            if limit and len(self.products) >= limit:
                print(f"\nДостигнут лимит {limit} товаров")
                break

    def _parse_categories_parallel(self, categories: List[Dict], limit: int = None, workers: int = 3):
        """Параллельный парсинг категорий"""
        print(f"\nПараллельный парсинг ({workers} потоков)...")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._parse_category_products, cat['url'], limit): cat
                for cat in categories
            }

            for future in as_completed(futures):
                cat = futures[future]
                try:
                    products = future.result()
                    self.products.extend(products)
                    print(f"[OK] {cat['name'][:40]}: {len(products)} товаров")
                except Exception as e:
                    print(f"[ERR] {cat['name'][:40]}: {e}")

                if limit and len(self.products) >= limit:
                    break

    def _parse_category_products(self, category_url: str, limit: int = None) -> List[Dict]:
        """Парсинг товаров из категории с пагинацией"""
        products = []
        page = 1

        while True:
            # URL с пагинацией
            url = f"{category_url}?limit={ITEMS_PER_PAGE}&page={page}"

            soup = self._get_soup(url)
            if not soup:
                break

            # Ищем карточки товаров
            product_cards = soup.select('.product-layout, .product-thumb, .product-card')
            if not product_cards:
                break

            for card in product_cards:
                # Извлекаем ссылку на товар
                link = card.select_one('a[href*=".html"]')
                if not link:
                    link = card.select_one('.product-thumb__title a, .name a, a.product-title')

                if link and link.get('href'):
                    product_url = urljoin(BASE_URL, link['href'])

                    # Парсим страницу товара
                    product = self._parse_product_page(product_url)
                    if product:
                        products.append(product)

                        if limit and len(products) >= limit:
                            return products

            # Проверяем наличие следующей страницы
            next_page = soup.select_one('.pagination .active + li a, a[aria-label="Next"]')
            if not next_page:
                break

            page += 1
            if page > 100:  # Защита от бесконечного цикла
                break

        return products

    def _parse_product_page(self, url: str) -> Optional[Dict]:
        """Парсинг страницы товара"""
        if url in self.visited_urls:
            return None
        self.visited_urls.add(url)

        soup = self._get_soup(url)
        if not soup:
            return None

        try:
            product = {
                "url": url,
                "parsed_at": datetime.now().isoformat()
            }

            # 1. Название
            h1 = soup.find('h1')
            product["name"] = h1.get_text(strip=True) if h1 else ""

            # 2. SKU/Артикул - ищем в разных местах
            sku = None

            # В мета-тегах или schema.org
            sku_meta = soup.find('meta', {'itemprop': 'sku'})
            if sku_meta:
                sku = sku_meta.get('content', '')

            # В таблице характеристик
            if not sku:
                for row in soup.select('tr, .specification-row, .product-attribute'):
                    label = row.find(['th', 'td', '.label'])
                    if label and any(x in label.get_text().lower() for x in ['артикул', 'sku', 'код', 'модель']):
                        value = row.find_all(['td', '.value'])
                        if len(value) > 1:
                            sku = value[-1].get_text(strip=True)
                        break

            # В тексте страницы
            if not sku:
                sku_patterns = [
                    r'Артикул[:\s]*([A-Za-z0-9\-_]+)',
                    r'SKU[:\s]*([A-Za-z0-9\-_]+)',
                    r'Код[:\s]*([A-Za-z0-9\-_]+)',
                    r'SN-\d+',
                    r'НФ-[А-Яа-яA-Za-z0-9]+'
                ]
                text = soup.get_text()
                for pattern in sku_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        sku = match.group(1) if match.lastindex else match.group(0)
                        break

            product["article"] = sku or self._generate_article_from_url(url)

            # 3. Штрихкод
            barcode = None
            barcode_meta = soup.find('meta', {'itemprop': 'gtin13'})
            if barcode_meta:
                barcode = barcode_meta.get('content', '')
            if not barcode:
                barcode_match = re.search(r'"gtin13"[:\s]*"?(\d{13})"?', str(soup))
                if barcode_match:
                    barcode = barcode_match.group(1)
            product["barcode"] = barcode

            # 4. Цена
            price = 0
            price_elem = soup.select_one('.product-price, .price-new, [itemprop="price"]')
            if price_elem:
                price_text = price_elem.get('content') or price_elem.get_text()
                price_match = re.search(r'[\d\s]+[.,]?\d*', price_text.replace(' ', ''))
                if price_match:
                    price = float(price_match.group().replace(',', '.').replace(' ', ''))
            product["price"] = price

            # 6. Категория из breadcrumbs
            breadcrumbs = soup.select('.breadcrumb li a, .breadcrumb a')
            if breadcrumbs:
                product["category"] = ' / '.join([
                    b.get_text(strip=True) for b in breadcrumbs[1:-1]  # Пропускаем "Главная" и текущий
                ])
            else:
                product["category"] = ""

            # 7. Product ID из URL или страницы
            product_id = None
            id_match = re.search(r'product_id[=:](\d+)', str(soup))
            if id_match:
                product_id = id_match.group(1)
            product["external_id"] = product_id

            # Проверяем обязательные поля
            if not product["name"] or not product["article"]:
                return None

            return product

        except Exception as e:
            self.errors.append({
                "url": url,
                "error": str(e),
                "time": datetime.now().isoformat()
            })
            return None

    def _generate_article_from_url(self, url: str) -> str:
        """Генерация артикула из URL если не найден"""
        # Берём slug из URL
        path = urlparse(url).path
        slug = path.rstrip('/').split('/')[-1].replace('.html', '')
        return f"S23-{slug[:50]}"

    def _save_categories(self, categories: List[Dict]):
        """Сохранить категории в JSON"""
        with open(CATEGORIES_JSON, 'w', encoding='utf-8') as f:
            json.dump(categories, f, ensure_ascii=False, indent=2)
        print(f"Категории сохранены в {CATEGORIES_JSON}")

    def save_to_json(self, filename: str = None):
        """Сохранить товары в JSON"""
        filename = filename or PRODUCTS_JSON
        data = {
            "source": SHOP_NAME,
            "url": BASE_URL,
            "date": datetime.now().isoformat(),
            "total": len(self.products),
            "products": self.products,
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Сохранено в {filename}: {len(self.products)} товаров")

        # Сохраняем ошибки
        if self.errors:
            with open(ERRORS_LOG, 'w', encoding='utf-8') as f:
                json.dump(self.errors, f, ensure_ascii=False, indent=2)
            print(f"Ошибки сохранены в {ERRORS_LOG}")

    def save_to_csv(self, filename: str = None):
        """Сохранить товары в CSV"""
        import csv
        filename = filename or PRODUCTS_CSV
        if not self.products:
            return

        fieldnames = ["article", "name", "price", "category", "barcode", "url"]
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.products)
        print(f"Сохранено в {filename}")


# ============================================================
# ФУНКЦИИ РАБОТЫ С БД
# ============================================================

def ensure_outlet():
    """Создаёт outlet если не существует"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO outlets (code, city, name, is_active)
            VALUES (%s, %s, %s, true)
            ON CONFLICT (code) DO NOTHING
        """, (SHOP_CODE, SHOP_CITY, SHOP_NAME))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def save_staging(products: List[Dict]):
    """Сохранение товаров в staging таблицу"""
    if not products:
        print("Нет товаров для сохранения в staging")
        return

    conn = get_db()
    cur = conn.cursor()
    try:
        # Очищаем staging
        cur.execute("TRUNCATE TABLE staging")

        # Вставляем товары
        insert_sql = """
            INSERT INTO staging (
                outlet_code, name, article, barcode, category,
                price, url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        for p in products:
            cur.execute(insert_sql, (
                SHOP_CODE,
                p.get("name", ""),
                p.get("article", ""),
                p.get("barcode", ""),
                p.get("category", ""),
                p.get("price", 0),
                p.get("url", ""),
            ))

        conn.commit()
        print(f"Сохранено в staging: {len(products)} товаров")
    finally:
        cur.close()
        conn.close()


def process_staging():
    """Обработка staging: UPSERT в nomenclature и current_prices (старая схема)"""
    conn = get_db()
    cur = conn.cursor()
    try:
        ensure_outlet()

        # 1. UPSERT в nomenclature
        cur.execute("""
            INSERT INTO nomenclature (article, name, barcode, category, first_seen_at, updated_at)
            SELECT DISTINCT ON (article)
                article, name, barcode, category, NOW(), NOW()
            FROM staging
            WHERE article IS NOT NULL AND article != ''
            ON CONFLICT (article) DO UPDATE SET
                name = EXCLUDED.name,
                barcode = COALESCE(EXCLUDED.barcode, nomenclature.barcode),
                category = EXCLUDED.category,
                updated_at = NOW()
        """)
        nom_count = cur.rowcount
        print(f"Nomenclature: {nom_count} записей")

        # 2. UPSERT в current_prices
        cur.execute("""
            INSERT INTO current_prices (nomenclature_id, outlet_id, price, updated_at)
            SELECT DISTINCT ON (n.id, o.id)
                n.id, o.id, s.price, NOW()
            FROM staging s
            JOIN nomenclature n ON n.article = s.article
            JOIN outlets o ON o.code = s.outlet_code
            WHERE s.article IS NOT NULL AND s.article != ''
            ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
                price = EXCLUDED.price,
                updated_at = NOW()
        """)
        price_count = cur.rowcount
        print(f"Current prices: {price_count} записей")

        conn.commit()

        # Статистика
        cur.execute("SELECT COUNT(*) FROM nomenclature")
        total_nom = cur.fetchone()[0]

        print(f"\n=== Итого в БД ===")
        print(f"Номенклатура: {total_nom}")

    finally:
        cur.close()
        conn.close()


def save_to_db(products: List[Dict]):
    """
    Сохранение в новую схему БД v10: signal23_nomenclature (с price) + signal23_product_urls
    Single-URL: один URL на товар (outlet_id = NULL), price в nomenclature
    """
    if not products:
        print("Нет товаров для сохранения")
        return

    conn = get_db()
    cur = conn.cursor()
    try:
        ensure_outlet()

        saved_nom = 0
        saved_urls = 0

        for p in products:
            url = p.get("url", "").strip()
            name = p.get("name", "").strip()
            if not url or not name:
                continue

            article = p.get("article", "").strip() or None
            barcode = (p.get("barcode") or "").strip() or None
            category = p.get("category", "").strip() or None

            # UPSERT в signal23_nomenclature (price в nomenclature)
            cur.execute("""
                INSERT INTO signal23_nomenclature (name, article, barcode, category, price, first_seen_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (article) DO UPDATE SET
                    name = EXCLUDED.name,
                    barcode = COALESCE(EXCLUDED.barcode, signal23_nomenclature.barcode),
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    updated_at = NOW()
                RETURNING id
            """, (name, article, barcode, category, p.get("price", 0)))

            nom_row = cur.fetchone()
            if not nom_row:
                continue
            nom_id = nom_row[0]
            saved_nom += 1

            # INSERT в signal23_product_urls (single-URL: outlet_id = NULL)
            cur.execute("""
                INSERT INTO signal23_product_urls (nomenclature_id, outlet_id, url, updated_at)
                VALUES (%s, NULL, %s, NOW())
                ON CONFLICT (url) DO NOTHING
            """, (nom_id, url))
            saved_urls += 1

        conn.commit()

        print(f"\n=== Сохранено в БД (v10) ===")
        print(f"signal23_nomenclature: {saved_nom} товаров")
        print(f"signal23_product_urls: {saved_urls} URL")

        # Статистика
        cur.execute("SELECT COUNT(*) FROM signal23_nomenclature")
        total = cur.fetchone()[0]
        print(f"Всего в БД: {total} товаров")

    finally:
        cur.close()
        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():
    arg_parser = argparse.ArgumentParser(description=f'Парсер {SHOP_NAME}')
    arg_parser.add_argument('--all', action='store_true',
                           help='Полный парсинг: сбор + сохранение в БД')
    arg_parser.add_argument('--process', action='store_true',
                           help='Только обработка staging (старая схема)')
    arg_parser.add_argument('--no-db', action='store_true',
                           help='Не сохранять в БД')
    arg_parser.add_argument('--limit', '-l', type=int, default=None,
                           help='Лимит товаров')
    arg_parser.add_argument('--parallel', '-p', action='store_true',
                           help='Параллельный парсинг категорий')
    arg_parser.add_argument('--old-schema', action='store_true',
                           help='Использовать старую схему БД (staging)')
    args = arg_parser.parse_args()

    # Только обработка staging (старая схема)
    if args.process:
        print("Обработка staging (старая схема)...")
        process_staging()
        return

    # Парсинг
    parser = Signal23Parser()
    parser.parse_all(limit=args.limit, parallel=args.parallel)
    parser.save_to_json()
    parser.save_to_csv()

    # Сохранение в БД
    if not args.no_db:
        if args.old_schema:
            # Старая схема через staging
            save_staging(parser.products)
            if args.all:
                process_staging()
        else:
            # Новая схема: signal23_nomenclature + signal23_prices
            save_to_db(parser.products)

    print("\nГотово!")


if __name__ == "__main__":
    main()
