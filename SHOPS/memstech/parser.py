"""
Парсер каталога MemsTech.ru

База данных: db_memstech
Таблицы: staging, outlets, nomenclature, current_prices, price_history

Парсит категории:
- VoltPack, iPhone, Android, iPad, MacBook, Watch, Ноутбуки
"""

import requests
import json
import csv
import os
import re
import psycopg2
import argparse
import time
from datetime import datetime
from typing import List, Dict, Optional, Set
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from config import (
    BASE_URL, CATALOG_URL, ROOT_CATEGORIES,
    ITEMS_PER_PAGE, MAX_PAGES, REQUEST_DELAY, REQUEST_TIMEOUT,
    USER_AGENT, DATA_DIR, PRODUCTS_CSV, PRODUCTS_JSON
)

# === Конфигурация БД (Supabase) ===
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db  # Автоматически маппит таблицы на новые имена

SHOP_CODE = "memstech"
SHOP_NAME = "MemsTech"
# === Города MemsTech (15 городов с поддоменами) ===
# Формат: subdomain -> (city_name, shops_count)
CITIES = {
    "memstech.ru": ("Москва", 4),
    "ekb": ("Екатеринбург", 1),
    "khb": ("Хабаровск", 1),
    "krd": ("Краснодар", 1),
    "ktl": ("Котлас", 1),
    "mgg": ("Магнитогорск", 1),
    "kzn": ("Казань", 1),
    "omsk": ("Омск", 1),
    "rnd": ("Ростов-на-Дону", 1),
    "spb": ("Санкт-Петербург", 2),
    "skt": ("Сыктывкар", 1),
    "nn": ("Нижний Новгород", 1),
    "chel": ("Челябинск", 1),
    "yar": ("Ярославль", 1),
    "perm": ("Пермь", 1),
}

def get_city_url(subdomain: str) -> str:
    """Возвращает базовый URL для города"""
    if subdomain == "memstech.ru":
        return "https://memstech.ru"
    return f"https://{subdomain}.memstech.ru"


class MemsTechParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })
        self.products: List[Dict] = []
        self.seen_product_ids: Set[str] = set()
        self.categories_crawled: Set[str] = set()
        self.current_city_id: Optional[str] = None
        self.current_city_name: Optional[str] = None
        self.base_url: str = BASE_URL
        self.catalog_url: str = CATALOG_URL

        os.makedirs(DATA_DIR, exist_ok=True)

    def set_city(self, subdomain: str, city_name: str):
        """Устанавливает город через смену поддомена"""
        self.current_city_id = subdomain
        self.current_city_name = city_name
        self.base_url = get_city_url(subdomain)
        self.catalog_url = f"{self.base_url}/catalog"
        print(f"  URL: {self.base_url}")

    def reset_for_new_city(self):
        """Сбрасывает состояние для парсинга нового города"""
        self.products = []
        self.seen_product_ids = set()
        self.categories_crawled = set()
        # Пересоздаём сессию — старая накапливает cookies/connections и ломается после ~8 городов
        self.session.close()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })

    def fetch_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """Загружает страницу и возвращает BeautifulSoup"""
        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                return BeautifulSoup(response.text, 'html.parser')
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                print(f"  Ошибка загрузки (попытка {attempt}/{retries}) {url}: {e}")
                if attempt < retries:
                    time.sleep(2 * attempt)
                    continue
                return None
            except Exception as e:
                print(f"  Ошибка загрузки {url}: {e}")
                return None

    def get_subcategories(self, soup: BeautifulSoup, current_url: str) -> List[str]:
        """Извлекает ссылки на подкатегории из плиток категорий"""
        subcategories = []

        # Ищем только плитки подкатегорий (catalog-section-list-item)
        for tile in soup.find_all('div', class_='catalog-section-list-item'):
            link = tile.find('a', class_='catalog-section-list-item-name')
            if link:
                href = link.get('href', '')
                if href and href.startswith('/catalog/'):
                    full_url = urljoin(self.base_url, href)
                    # Пропускаем если уже обработали
                    if full_url not in self.categories_crawled:
                        subcategories.append(full_url)

        return list(set(subcategories))

    def extract_breadcrumbs(self, soup: BeautifulSoup) -> str:
        """Извлекает категорию из хлебных крошек"""
        breadcrumbs = []
        bc_container = soup.find('div', class_='intec-content-wrapper')
        if bc_container:
            for link in bc_container.find_all('a', href=re.compile(r'/catalog/')):
                text = link.get_text(strip=True)
                if text and text not in ['Каталог', 'Главная']:
                    breadcrumbs.append(text)
        return ' > '.join(breadcrumbs) if breadcrumbs else ''

    def parse_product_from_data(self, item_div, category: str) -> Optional[Dict]:
        """Парсит товар из data-data атрибута"""
        try:
            product_id = item_div.get('data-id', '')
            if not product_id or product_id in self.seen_product_ids:
                return None

            # Парсим JSON из data-data
            data_json = item_div.get('data-data', '{}')
            data = json.loads(data_json)

            name = data.get('name', '')
            available = data.get('available', False)

            # Цена
            price = 0
            prices = data.get('prices', [])
            if prices and len(prices) > 0:
                price_info = prices[0]
                if 'discount' in price_info:
                    price = price_info['discount'].get('value', 0)
                elif 'base' in price_info:
                    price = price_info['base'].get('value', 0)

            # Артикул из HTML
            article = ''
            article_div = item_div.find('div', class_='catalog-section-item-article')
            if article_div:
                article_span = article_div.find('span')
                if article_span:
                    article_text = article_span.get_text(strip=True)
                    # Извлекаем код после "Код: "
                    match = re.search(r'Код:\s*(.+)', article_text)
                    if match:
                        article = match.group(1).strip()

            # URL товара
            url = ''
            link = item_div.find('a', class_='catalog-section-item-name-wrapper')
            if link:
                url = urljoin(self.base_url, link.get('href', ''))

            # Наличие из HTML
            quantity_div = item_div.find('div', class_='catalog-section-item-quantity')
            stock_text = ''
            if quantity_div:
                stock_text = quantity_div.get_text(strip=True).lower()

            self.seen_product_ids.add(product_id)

            product = {
                'product_id': product_id,
                'article': article or f"MT-{product_id}",
                'name': name,
                'price': price,
                'category': category,
                'url': url,
            }
            if self.current_city_id:
                product['city_id'] = self.current_city_id
                product['city_name'] = self.current_city_name
            return product

        except Exception as e:
            print(f"    Ошибка парсинга товара: {e}")
            return None

    def parse_category_page(self, url: str, category: str, page: int = 1) -> List[Dict]:
        """Парсит одну страницу категории"""
        products = []

        page_url = url if page == 1 else f"{url}?PAGEN_3={page}"
        soup = self.fetch_page(page_url)

        if not soup:
            return products

        # Находим все товары
        items = soup.find_all('div', class_='catalog-section-item', attrs={'data-entity': 'items-row'})

        for item in items:
            product = self.parse_product_from_data(item, category)
            if product:
                products.append(product)

        return products

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Определяет количество страниц из NavPageCount"""
        try:
            scripts = soup.find_all('script')
            for script in scripts:
                text = script.string or ''
                match = re.search(r"'NavPageCount':\s*(\d+)", text)
                if match:
                    return int(match.group(1))
        except:
            pass
        return 1

    def crawl_category(self, url: str, depth: int = 0) -> int:
        """Рекурсивно обходит категорию и её подкатегории"""
        if url in self.categories_crawled:
            return 0

        self.categories_crawled.add(url)
        indent = "  " * depth

        print(f"{indent}Категория: {url}")
        time.sleep(REQUEST_DELAY)

        soup = self.fetch_page(url)
        if not soup:
            return 0

        # Извлекаем категорию из хлебных крошек
        category = self.extract_breadcrumbs(soup)
        if not category:
            category = url.split('/')[-2].replace('_', ' ').title()

        # Проверяем есть ли товары на странице
        items = soup.find_all('div', class_='catalog-section-item', attrs={'data-entity': 'items-row'})
        total_products = 0

        if items:
            # Есть товары - парсим пагинацию
            total_pages = self.get_total_pages(soup)
            print(f"{indent}  Найдено страниц: {total_pages}")

            # Первая страница уже загружена
            for item in items:
                product = self.parse_product_from_data(item, category)
                if product:
                    self.products.append(product)
                    total_products += 1

            # Остальные страницы
            for page in range(2, min(total_pages + 1, MAX_PAGES + 1)):
                time.sleep(REQUEST_DELAY)
                page_products = self.parse_category_page(url, category, page)
                self.products.extend(page_products)
                total_products += len(page_products)

                if len(page_products) == 0:
                    break

            print(f"{indent}  Товаров: {total_products}")

        # Ищем подкатегории
        subcategories = self.get_subcategories(soup, url)
        for subcat_url in subcategories:
            total_products += self.crawl_category(subcat_url, depth + 1)

        return total_products

    def parse_all(self) -> List[Dict]:
        """Парсит все корневые категории"""
        print(f"\nПарсинг каталога {SHOP_NAME}")
        print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        for category_slug in ROOT_CATEGORIES:
            url = f"{self.catalog_url}/{category_slug}/"
            print(f"\n{'='*60}")
            print(f"КОРНЕВАЯ КАТЕГОРИЯ: {category_slug}")
            print("=" * 60)
            self.crawl_category(url)

        print(f"\n{'='*60}")
        print(f"ИТОГО: {len(self.products)} товаров")
        print("=" * 60)

        return self.products

    def parse_all_cities(self) -> List[Dict]:
        """Парсит все города"""
        import traceback
        all_products = []
        failed_cities = []
        print("\n" + "=" * 60)
        print(f"МУЛЬТИГОРОДСКОЙ ПАРСИНГ: {len(CITIES)} городов")
        print("=" * 60)
        for i, (subdomain, (city_name, shops_count)) in enumerate(CITIES.items(), 1):
            print("\n" + "#" * 60)
            print(f"ГОРОД [{i}/{len(CITIES)}]: {city_name} ({subdomain}, {shops_count} магазин(ов))")
            print(f"Накоплено товаров: {len(all_products)}")
            print("#" * 60)
            try:
                self.reset_for_new_city()
                self.set_city(subdomain, city_name)
                self.parse_all()
                all_products.extend(self.products)
                print(f"\nГород {city_name}: {len(self.products)} товаров (всего: {len(all_products)})")
            except Exception as e:
                print(f"\n!!! ОШИБКА в городе {city_name}: {e}")
                traceback.print_exc()
                failed_cities.append((city_name, str(e)))
                # Продолжаем со следующим городом
                continue
        self.products = all_products
        print("\n" + "=" * 60)
        print(f"ВСЕГО ПО ВСЕМ ГОРОДАМ: {len(all_products)} товаров")
        if failed_cities:
            print(f"ОШИБКИ В ГОРОДАХ ({len(failed_cities)}):")
            for city, err in failed_cities:
                print(f"  - {city}: {err}")
        print("=" * 60)
        return all_products
    def save_to_csv(self, filename: str = PRODUCTS_CSV):
        """Сохраняет товары в CSV"""
        if not self.products:
            print("Нет товаров для сохранения")
            return
        has_cities = any("city_id" in p for p in self.products)
        if has_cities:
            fieldnames = ["product_id", "article", "name", "price", "category", "city_id", "city_name", "url"]
        else:
            fieldnames = ["product_id", "article", "name", "price", "category", "url"]
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            for p in self.products:
                row = {"product_id": p.get("product_id", ""), "article": p.get("article", ""),
                       "name": p.get("name", ""), "price": p.get("price", 0),
                       "category": p.get("category", ""), "url": p.get("url", "")}
                if has_cities:
                    row["city_id"] = p.get("city_id", "")
                    row["city_name"] = p.get("city_name", "")
                writer.writerow(row)
        print(f"Сохранено в {filename}: {len(self.products)} товаров")

    def save_to_json(self, filename: str = PRODUCTS_JSON):
        """Сохраняет товары в JSON"""
        data = {
            "source": f"{SHOP_NAME} ({self.base_url})",
            "date": datetime.now().isoformat(),
            "total": len(self.products),
            "products": self.products,
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Сохранено в {filename}")

    def print_stats(self):
        """Выводит статистику"""
        print("\n" + "=" * 60)
        print("СТАТИСТИКА")
        print("=" * 60)

        # По категориям
        categories = {}
        for p in self.products:
            cat = p.get("category", "Без категории")
            categories[cat] = categories.get(cat, 0) + 1

        print(f"\nКатегорий: {len(categories)}")
        print("\nТоп-10 категорий:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:10]:
            print(f"  {count:5d} | {cat}")

        # По городам (если есть)
        cities_stats = {}
        for p in self.products:
            city = p.get("city_name", "Не указан")
            cities_stats[city] = cities_stats.get(city, 0) + 1
        if len(cities_stats) > 1:
            print(f"\nПо городам ({len(cities_stats)}):")
            for city, count in sorted(cities_stats.items(), key=lambda x: -x[1]):
                print(f"  {count:5d} | {city}")
        # Ценовой диапазон

        # Ценовой диапазон
        prices = [p.get("price", 0) for p in self.products if p.get("price", 0) > 0]
        if prices:
            print(f"Цены: от {min(prices):.0f} до {max(prices):.0f} руб")


def get_outlet_code(city_id: str) -> str:
    """Возвращает код outlet для города"""
    return f"{SHOP_CODE}-{city_id}"


def ensure_outlets():
    """Создаёт outlets для всех городов MemsTech"""
    conn = get_db()
    cur = conn.cursor()
    try:
        for subdomain, (city_name, shops_count) in CITIES.items():
            outlet_code = get_outlet_code(subdomain)
            cur.execute("""
                INSERT INTO outlets (code, city, name, is_active)
                VALUES (%s, %s, %s, true)
                ON CONFLICT (code) DO UPDATE SET city = EXCLUDED.city, name = EXCLUDED.name
            """, (outlet_code, city_name, f"{SHOP_NAME} {city_name}"))
        conn.commit()
        print(f"Outlets: создано/обновлено {len(CITIES)} точек")
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
        has_cities = any("city_id" in p for p in products)
        if has_cities:
            for subdomain in CITIES.keys():
                cur.execute("DELETE FROM staging WHERE outlet_code = %s", (get_outlet_code(subdomain),))
        else:
            cur.execute("DELETE FROM staging WHERE outlet_code = %s", (get_outlet_code("memstech.ru"),))
        insert_sql = """
            INSERT INTO staging (outlet_code, name, article, category, price, url, product_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        for p in products:
            outlet_code = get_outlet_code(p["city_id"]) if "city_id" in p else get_outlet_code("memstech.ru")
            cur.execute(insert_sql, (
                outlet_code, p.get("name", ""), p.get("article", ""), p.get("category", ""),
                p.get("price", 0),
                p.get("url", ""), p.get("product_id", ""),
            ))
        conn.commit()
        print(f"Сохранено в staging: {len(products)} товаров ({SHOP_NAME})")
    finally:
        cur.close()
        conn.close()


def process_staging():
    """Обработка staging: UPSERT в nomenclature и current_prices (LEGACY)"""
    conn = get_db()
    cur = conn.cursor()
    try:
        ensure_outlets()

        # 1. UPSERT в nomenclature
        cur.execute("""
            INSERT INTO nomenclature (article, name, category, product_id, first_seen_at, updated_at)
            SELECT DISTINCT ON (article)
                article,
                name,
                category,
                product_id,
                NOW(),
                NOW()
            FROM staging
            WHERE article IS NOT NULL AND article != ''
            ON CONFLICT (article) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                product_id = COALESCE(NULLIF(EXCLUDED.product_id, ''), nomenclature.product_id),
                updated_at = NOW()
        """)
        nom_count = cur.rowcount
        print(f"Nomenclature: {nom_count} записей обновлено/добавлено")

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
        print(f"Current prices: {price_count} записей обновлено/добавлено")

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
    Сохранение в новую схему БД v10: memstech_nomenclature (с price) + memstech_product_urls
    Multi-URL: разные URL по поддоменам (outlet_id сохраняется)
    Свежее соединение + коммит каждые BATCH_SIZE записей.
    """
    if not products:
        print("Нет товаров для сохранения")
        return

    BATCH_SIZE = 500

    ensure_outlets()

    # Свежее соединение для записи
    conn = get_db()
    cur = conn.cursor()

    try:
        # Кэш outlet_id по city_code
        cur.execute("SELECT code, id FROM outlets WHERE code LIKE 'memstech-%'")
        outlet_cache = {row[0]: row[1] for row in cur.fetchall()}

        nom_inserted = 0
        nom_updated = 0
        urls_inserted = 0

        for i, p in enumerate(products):
            # Определяем outlet
            city_id = p.get("city_id", "memstech.ru")
            outlet_code = get_outlet_code(city_id)
            outlet_id = outlet_cache.get(outlet_code)

            if not outlet_id:
                print(f"  Outlet не найден: {outlet_code}")
                continue

            product_url = p.get("url", "")
            if not product_url:
                product_url = f"https://memstech.ru/product/{p.get('article', p.get('product_id', 'unknown'))}"

            # 1. UPSERT в memstech_nomenclature (price в nomenclature)
            article = p.get("article", "").strip()
            price = p.get("price", 0)

            cur.execute("""
                INSERT INTO memstech_nomenclature (name, article, category, price, first_seen_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (article) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    updated_at = NOW()
                RETURNING id, (xmax = 0) as inserted
            """, (
                p.get("name", ""),
                article,
                p.get("category", ""),
                price
            ))

            row = cur.fetchone()
            nomenclature_id = row[0]
            if row[1]:
                nom_inserted += 1
            else:
                nom_updated += 1

            # 2. INSERT в memstech_product_urls (multi-URL: сохраняем outlet_id)
            cur.execute("""
                INSERT INTO memstech_product_urls (nomenclature_id, outlet_id, url, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (url) DO NOTHING
            """, (nomenclature_id, outlet_id, product_url))
            urls_inserted += 1

            # Коммит + переподключение каждые BATCH_SIZE записей
            if (i + 1) % BATCH_SIZE == 0:
                conn.commit()
                print(f"  БД: {i + 1}/{len(products)} записано...")
                # Переподключение чтобы PgBouncer не убил соединение
                cur.close()
                conn.close()
                time.sleep(1)
                conn = get_db()
                cur = conn.cursor()

        conn.commit()

        print(f"\n=== Сохранено в БД (v10) ===")
        print(f"memstech_nomenclature: +{nom_inserted} новых, ~{nom_updated} обновлено")
        print(f"memstech_product_urls: {urls_inserted} URL")

        # Итоговая статистика
        cur.execute("SELECT COUNT(*) FROM memstech_nomenclature")
        total_nom = cur.fetchone()[0]
        print(f"\nИтого в БД: {total_nom} товаров")

    finally:
        cur.close()
        conn.close()


def main():
    arg_parser = argparse.ArgumentParser(description=f'Парсер каталога {SHOP_NAME}')
    arg_parser.add_argument('--all', action='store_true',
                           help='Полный парсинг: сбор + сохранение в БД')
    arg_parser.add_argument('--all-cities', action='store_true',
                           help='Парсить все 15 городов')
    arg_parser.add_argument('--city', type=str, default=None,
                           help='Парсить конкретный город (ID или название)')
    arg_parser.add_argument('--process', action='store_true',
                           help='Только обработка staging (LEGACY, без парсинга)')
    arg_parser.add_argument('--old-schema', action='store_true',
                           help='Использовать старую схему БД (staging -> nomenclature)')
    arg_parser.add_argument('--no-db', action='store_true',
                           help='Не сохранять в БД (только CSV/JSON)')
    arg_parser.add_argument('--limit', type=int, default=0,
                           help='Лимит товаров (0 = без лимита)')
    args = arg_parser.parse_args()

    if args.process:
        print("Обработка staging (LEGACY)...")
        process_staging()
        print("\nОбработка завершена!")
        return

    parser = MemsTechParser()

    if args.all_cities:
        products = parser.parse_all_cities()
    elif args.city:
        subdomain, city_name = None, None
        if args.city in CITIES:
            subdomain = args.city
            city_name = CITIES[args.city][0]
        else:
            for sub, (cname, _) in CITIES.items():
                if args.city.lower() in cname.lower():
                    subdomain, city_name = sub, cname
                    break
        if not subdomain:
            print(f"Город '{args.city}' не найден!")
            print("Доступные города:")
            for sub, (cname, shops) in CITIES.items():
                print(f"  {sub}: {cname} ({shops} магазин(ов))")
            return
        parser.set_city(subdomain, city_name)
        products = parser.parse_all()
    else:
        # По умолчанию - Москва (memstech.ru)
        parser.set_city("memstech.ru", "Москва")
        products = parser.parse_all()

    # Лимит
    if args.limit > 0 and len(products) > args.limit:
        products = products[:args.limit]
        parser.products = products
        print(f"Ограничено до {args.limit} товаров")

    # Статистика
    parser.print_stats()

    # Сохраняем в файлы
    print("\n" + "=" * 60)
    print("СОХРАНЕНИЕ")
    print("=" * 60)
    parser.save_to_csv()
    parser.save_to_json()

    # Сохраняем в БД
    if not args.no_db:
        if args.old_schema:
            # LEGACY: staging -> nomenclature -> current_prices
            save_staging(products)
            if args.all:
                process_staging()
        else:
            # НОВАЯ СХЕМА: memstech_nomenclature + memstech_prices
            save_to_db(products)

    print("\nПарсинг завершён!")


if __name__ == "__main__":
    main()
