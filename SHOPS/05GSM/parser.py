"""
Парсер 05GSM.ru - запчасти для телефонов и ноутбуков

Рекурсивный обход категорий с извлечением breadcrumbs.
База данных: db_05gsm
Таблицы: staging, outlets, nomenclature, current_prices, price_history
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import re
import os
import psycopg2
import argparse
from datetime import datetime
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# === Конфигурация ===
BASE_URL = "https://05gsm.ru"

# Корневые категории для парсинга
ROOT_CATEGORIES = [
    "zapchasti_dlya_telefonov",
    "zapchasti_dlya_noutbukov",
]

# Настройки запросов
REQUEST_DELAY = 0.3
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
ITEMS_PER_PAGE = 40
MAX_PAGES = 100

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Пути к файлам
DATA_DIR = "data"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
CATEGORIES_JSON = f"{DATA_DIR}/categories.json"
ERRORS_LOG = f"{DATA_DIR}/errors.json"

# === Конфигурация БД (Supabase) ===
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db  # Автоматически маппит таблицы на новые имена


class Parser05GSM:
    """Парсер каталога 05GSM.ru с рекурсивным обходом категорий"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })
        self.products: List[Dict] = []
        self.categories: Dict[str, str] = {}  # slug -> name
        self.errors: List[Dict] = []
        self.seen_urls: set = set()

        os.makedirs(DATA_DIR, exist_ok=True)

    def get_page(self, url: str, retries: int = MAX_RETRIES) -> Optional[BeautifulSoup]:
        """Загружает страницу с повторными попытками"""
        for attempt in range(retries):
            try:
                time.sleep(REQUEST_DELAY)
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return BeautifulSoup(response.text, 'lxml')
            except Exception as e:
                if attempt == retries - 1:
                    self.errors.append({
                        "url": url,
                        "error": str(e),
                        "time": datetime.now().isoformat()
                    })
                    return None
                time.sleep(REQUEST_DELAY * (attempt + 1))
        return None

    def extract_breadcrumbs(self, soup: BeautifulSoup) -> tuple:
        """
        Извлекает breadcrumbs из страницы.
        Возвращает (category_slug, category_name)
        """
        slug_parts = []
        name_parts = []

        # Ищем breadcrumbs (разные варианты разметки)
        breadcrumb = soup.find('ul', class_='breadcrumb') or \
                     soup.find('div', class_='breadcrumb') or \
                     soup.find('nav', {'aria-label': 'breadcrumb'})

        if breadcrumb:
            links = breadcrumb.find_all('a')
            for link in links:
                href = link.get('href', '')
                name = link.get_text(strip=True)

                # Пропускаем главную и каталог
                if href in ['/', '/catalog/'] or name.lower() in ['главная', 'каталог']:
                    continue

                # Извлекаем slug из URL
                match = re.search(r'/catalog/(.+?)/?$', href)
                if match:
                    path = match.group(1).rstrip('/')
                    last_part = path.split('/')[-1]
                    slug_parts.append(last_part)
                    name_parts.append(name)

        # Добавляем текущую категорию (последний элемент без ссылки)
        current = breadcrumb.find('span', class_='current') if breadcrumb else None
        if not current:
            current = breadcrumb.find('li', class_='active') if breadcrumb else None
        if current:
            name = current.get_text(strip=True)
            if name and name.lower() not in ['главная', 'каталог']:
                name_parts.append(name)

        return "/".join(slug_parts), " / ".join(name_parts)

    def get_subcategories(self, soup: BeautifulSoup) -> List[Dict]:
        """Извлекает подкатегории из страницы"""
        subcategories = []

        # Ищем блок с подкатегориями - на 05gsm.ru это sections-list
        subcat_container = soup.find('div', class_='sections-list') or \
                          soup.find('div', class_='catalog-sections') or \
                          soup.find('div', class_='subcategories')

        if subcat_container:
            # На 05gsm.ru ссылки в классе sections-list__item-link
            links = subcat_container.find_all('a', class_='sections-list__item-link') or \
                   subcat_container.find_all('a', href=re.compile(r'/catalog/'))

            for link in links:
                href = link.get('href', '')

                # Пропускаем ссылки с параметрами (сортировка и т.п.)
                if '?' in href:
                    continue

                # Имя из span.sections-list__item-text или текста ссылки
                name_elem = link.find('span', class_='sections-list__item-text')
                name = name_elem.get_text(strip=True) if name_elem else link.get_text(strip=True)

                # Извлекаем slug
                match = re.search(r'/catalog/(.+?)/?$', href)
                if match and name:
                    slug = match.group(1).rstrip('/')
                    subcategories.append({
                        'slug': slug,
                        'name': name,
                        'url': BASE_URL + href if not href.startswith('http') else href
                    })

        return subcategories

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Определяет количество страниц пагинации"""
        # Ищем пагинацию
        pagination = soup.find('div', class_='pagination') or \
                    soup.find('ul', class_='pagination') or \
                    soup.find('nav', class_='pagination')

        if pagination:
            # Ищем последнюю страницу
            page_links = pagination.find_all('a', href=re.compile(r'PAGEN_1=(\d+)'))
            max_page = 1
            for link in page_links:
                href = link.get('href', '')
                match = re.search(r'PAGEN_1=(\d+)', href)
                if match:
                    page_num = int(match.group(1))
                    max_page = max(max_page, page_num)
            return min(max_page, MAX_PAGES)

        return 1

    def parse_product_card(self, card, category_slug: str, category_name: str) -> Optional[Dict]:
        """Парсит карточку товара"""
        try:
            # URL товара - ищем ссылку на товар
            link = card.find('a', href=re.compile(r'/catalog/\d+/'))
            if not link:
                # Попробуем найти любую ссылку на каталог с числовым ID
                all_links = card.find_all('a', href=True)
                for a in all_links:
                    href = a.get('href', '')
                    if re.search(r'/catalog/\d+/', href):
                        link = a
                        break

            if not link:
                return None

            url = link.get('href', '')
            if not url.startswith('http'):
                url = BASE_URL + url

            # Пропускаем дубликаты
            if url in self.seen_urls:
                return None
            self.seen_urls.add(url)

            # ID товара из URL
            match = re.search(r'/catalog/(\d+)/', url)
            product_id = match.group(1) if match else ""

            # Название - разные варианты селекторов
            name = ""
            name_elem = card.find('a', class_=re.compile(r'dark_link.*switcher-title')) or \
                       card.find(class_=re.compile(r'item-title|product-name|catalog-title')) or \
                       card.find('a', title=True)
            if name_elem:
                name = name_elem.get('title') or name_elem.get_text(strip=True)
            if not name:
                # Fallback: текст первой ссылки на товар
                name = link.get('title') or link.get_text(strip=True)

            # Цена - ищем элемент с ценой
            price = 0.0
            price_elem = card.find(class_=re.compile(r'price__new-val|price-new|current-price'))
            if not price_elem:
                price_elem = card.find(class_=re.compile(r'price'))
            if price_elem:
                price_text = price_elem.get_text()
                # Извлекаем число
                price_match = re.search(r'[\d\s]+', price_text.replace('\xa0', ' '))
                if price_match:
                    price_text = price_match.group().replace(' ', '')
                    try:
                        price = float(price_text)
                    except:
                        pass

            if not name or len(name) < 3:
                return None

            return {
                "product_id": product_id,
                "article": product_id,
                "name": name,
                "price": price,
                "category": category_name,
                "url": url,
            }

        except Exception as e:
            self.errors.append({
                "error": str(e),
                "time": datetime.now().isoformat()
            })
            return None

    def parse_category_page(self, url: str, category_slug: str, category_name: str) -> List[Dict]:
        """Парсит страницу категории и возвращает список товаров"""
        soup = self.get_page(url)
        if not soup:
            return []

        products = []

        # Ищем карточки товаров - на 05gsm.ru это catalog-block__item
        cards = soup.find_all('div', class_='catalog-block__item') or \
                soup.find_all('div', class_=re.compile(r'product-item|catalog-item'))

        for card in cards:
            product = self.parse_product_card(card, category_slug, category_name)
            if product:
                products.append(product)

        return products

    def crawl_category(self, category_slug: str, depth: int = 0):
        """
        Рекурсивный обход категории.
        Собирает подкатегории и товары.
        """
        url = f"{BASE_URL}/catalog/{category_slug}/"
        indent = "  " * depth

        print(f"{indent}[{depth}] Обход: {category_slug}")

        soup = self.get_page(url)
        if not soup:
            print(f"{indent}    [SKIP] Не удалось загрузить")
            return

        # Извлекаем breadcrumbs
        cat_slug, cat_name = self.extract_breadcrumbs(soup)
        if not cat_name:
            # Fallback: берём из title или h1
            h1 = soup.find('h1')
            cat_name = h1.get_text(strip=True) if h1 else category_slug
            cat_slug = category_slug

        # Сохраняем категорию
        self.categories[cat_slug] = cat_name

        # Проверяем подкатегории
        subcategories = self.get_subcategories(soup)

        if subcategories:
            print(f"{indent}    Подкатегорий: {len(subcategories)}")
            for subcat in subcategories:
                self.crawl_category(subcat['slug'], depth + 1)
        else:
            # Конечная категория - собираем товары
            self._collect_products_from_category(soup, url, cat_slug, cat_name, depth)

    def _collect_products_from_category(self, first_page_soup: BeautifulSoup,
                                        base_url: str, category_slug: str,
                                        category_name: str, depth: int):
        """Собирает все товары из категории со всех страниц"""
        indent = "  " * depth

        # Парсим первую страницу
        products = []
        cards = first_page_soup.find_all('div', class_='catalog-block__item') or \
                first_page_soup.find_all('div', class_=re.compile(r'product-item|catalog-item'))

        for card in cards:
            product = self.parse_product_card(card, category_slug, category_name)
            if product:
                products.append(product)

        # Определяем количество страниц
        total_pages = self.get_total_pages(first_page_soup)

        print(f"{indent}    Страница 1/{total_pages}: +{len(products)} товаров")

        self.products.extend(products)

        # Парсим остальные страницы
        for page in range(2, total_pages + 1):
            page_url = f"{base_url}?PAGEN_1={page}"
            page_products = self.parse_category_page(page_url, category_slug, category_name)

            print(f"{indent}    Страница {page}/{total_pages}: +{len(page_products)} товаров")

            self.products.extend(page_products)

    def parse_all(self):
        """Парсит все корневые категории"""
        print(f"\n{'='*60}")
        print(f"Парсинг 05GSM.ru")
        print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Корневые категории: {', '.join(ROOT_CATEGORIES)}")
        print(f"{'='*60}\n")

        for root_cat in ROOT_CATEGORIES:
            print(f"\n=== Категория: {root_cat} ===\n")
            self.crawl_category(root_cat)

        # Итоги
        print(f"\n{'='*60}")
        print(f"ИТОГО: {len(self.products)} товаров")
        print(f"Категорий: {len(self.categories)}")
        print(f"Ошибок: {len(self.errors)}")
        print(f"{'='*60}")

    def save_to_json(self, filename: str = None):
        """Сохранить в JSON"""
        filename = filename or PRODUCTS_JSON
        data = {
            "source": "05gsm.ru",
            "date": datetime.now().isoformat(),
            "total": len(self.products),
            "categories": self.categories,
            "products": self.products,
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Сохранено в {filename}: {len(self.products)} товаров")

    def save_to_csv(self, filename: str = None):
        """Сохранить в CSV"""
        filename = filename or PRODUCTS_CSV
        if not self.products:
            return

        fieldnames = ["article", "name", "price", "category", "url"]
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.products)
        print(f"Сохранено в {filename}")

    def save_categories(self, filename: str = None):
        """Сохранить категории"""
        filename = filename or CATEGORIES_JSON
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.categories, f, ensure_ascii=False, indent=2)
        print(f"Категории сохранены в {filename}")

    def save_errors(self, filename: str = None):
        """Сохранить лог ошибок"""
        filename = filename or ERRORS_LOG
        if self.errors:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.errors, f, ensure_ascii=False, indent=2)
            print(f"Ошибки сохранены в {filename}")

    def print_stats(self):
        """Выводит статистику"""
        print(f"\n{'='*60}")
        print("СТАТИСТИКА")
        print(f"{'='*60}")

        # По категориям
        cat_counts = {}
        for p in self.products:
            cat = p.get("category", "Без категории")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        print(f"\nКатегорий: {len(cat_counts)}")
        print("\nТоп-10 категорий:")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {count:4d} | {cat[:60]}")

        # Ценовой диапазон

        # Ценовой диапазон
        prices = [p.get("price", 0) for p in self.products if p.get("price", 0) > 0]
        if prices:
            print(f"Цены: от {min(prices):.0f} до {max(prices):.0f} руб")


# ============================================================
# ФУНКЦИИ РАБОТЫ С БД
# ============================================================

def ensure_outlet():
    """Создаёт outlet для 05GSM если не существует"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO outlets (code, city, name, is_active)
            VALUES ('05gsm-online', 'Интернет', '05GSM Online', true)
            ON CONFLICT (code) DO NOTHING
        """)
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
        cur.execute("TRUNCATE TABLE staging")

        insert_sql = """
            INSERT INTO staging (
                outlet_code, name, article, category,
                price, url
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """

        for p in products:
            cur.execute(insert_sql, (
                "05gsm-online",
                p.get("name", ""),
                p.get("article", ""),
                p.get("category", ""),
                p.get("price", 0),
                p.get("url", ""),
            ))

        conn.commit()
        print(f"Сохранено в staging: {len(products)} товаров")
    finally:
        cur.close()
        conn.close()


def process_staging(full_mode: bool = False):
    """Обработка staging: UPSERT в nomenclature и current_prices (старая схема)"""
    conn = get_db()
    cur = conn.cursor()
    try:
        ensure_outlet()

        # 1. UPSERT в nomenclature
        _nom_update = (
            "name = EXCLUDED.name, "
            "category = EXCLUDED.category, "
            "updated_at = NOW()"
            if full_mode else
            "updated_at = NOW()"
        )
        cur.execute(f"""
            INSERT INTO nomenclature (article, name, category, first_seen_at, updated_at)
            SELECT DISTINCT ON (article)
                article, name, category, NOW(), NOW()
            FROM staging
            WHERE article IS NOT NULL AND article != ''
            ON CONFLICT (article) DO UPDATE SET
                {_nom_update}
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


def save_to_db(products: List[Dict], full_mode: bool = False):
    """
    Сохранение в новую схему БД v10: gsm05_nomenclature (с price) + gsm05_product_urls
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

        _nom_update = (
            "name = EXCLUDED.name, "
            "category = EXCLUDED.category, "
            "price = EXCLUDED.price, "
            "updated_at = NOW()"
            if full_mode else
            "price = EXCLUDED.price, "
            "updated_at = NOW()"
        )
        for p in products:
            url = p.get("url", "").strip()
            name = p.get("name", "").strip()
            if not url or not name:
                continue

            article = p.get("article", "").strip() or None
            category = p.get("category", "").strip() or None

            # UPSERT в gsm05_nomenclature (price в nomenclature)
            cur.execute(f"""
                INSERT INTO gsm05_nomenclature (name, article, category, price, first_seen_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (article) DO UPDATE SET
                    {_nom_update}
                RETURNING id
            """, (name, article, category, p.get("price", 0)))

            nom_row = cur.fetchone()
            if not nom_row:
                continue
            nom_id = nom_row[0]
            saved_nom += 1

            # INSERT в gsm05_product_urls (single-URL: outlet_id = NULL)
            cur.execute("""
                INSERT INTO gsm05_product_urls (nomenclature_id, outlet_id, url, updated_at)
                VALUES (%s, NULL, %s, NOW())
                ON CONFLICT (url) DO NOTHING
            """, (nom_id, url))
            saved_urls += 1

        conn.commit()

        print(f"\n=== Сохранено в БД (v10) ===")
        print(f"gsm05_nomenclature: {saved_nom} товаров")
        print(f"gsm05_product_urls: {saved_urls} URL")

        # Статистика
        cur.execute("SELECT COUNT(*) FROM gsm05_nomenclature")
        total = cur.fetchone()[0]
        print(f"Всего в БД: {total} товаров")

    finally:
        cur.close()
        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():
    arg_parser = argparse.ArgumentParser(description='Парсер 05GSM.ru')
    arg_parser.add_argument('--all', action='store_true',
                           help='Полный парсинг: сбор + сохранение в БД')
    arg_parser.add_argument('--process', action='store_true',
                           help='Только обработка staging (старая схема)')
    arg_parser.add_argument('--no-db', action='store_true',
                           help='Не сохранять в БД')
    arg_parser.add_argument('--category', '-c', type=str, default=None,
                           help='Парсить только указанную категорию')
    arg_parser.add_argument('--old-schema', action='store_true',
                           help='Использовать старую схему БД (staging)')
    arg_parser.add_argument('--full', action='store_true',
                           help='Полный парсинг (UPSERT и так полный для этого парсера)')
    args = arg_parser.parse_args()

    # Только обработка staging (старая схема)
    if args.process:
        print("Обработка staging (старая схема)...")
        process_staging(full_mode=args.full)
        return

    # Парсинг
    parser = Parser05GSM()

    if args.category:
        # Парсим одну категорию
        parser.crawl_category(args.category)
    else:
        # Парсим все корневые категории
        parser.parse_all()

    parser.print_stats()
    parser.save_to_json()
    parser.save_to_csv()
    parser.save_categories()
    parser.save_errors()

    # Сохранение в БД
    if not args.no_db:
        if args.old_schema:
            # Старая схема через staging
            save_staging(parser.products)
            if args.all:
                process_staging(full_mode=args.full)
        else:
            # Новая схема: gsm05_nomenclature + gsm05_prices
            save_to_db(parser.products, full_mode=args.full)

    print("\nГотово!")


if __name__ == "__main__":
    main()
