"""
Парсер TAGGSM.ru - запчасти для телефонов, ноутбуков и смарт-часов

Рекурсивный обход категорий с извлечением breadcrumbs.
Парсинг по всем городам с данными о наличии.

База данных: db_taggsm
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
from typing import Optional, List, Dict, Tuple

# === Конфигурация ===
BASE_URL = "https://taggsm.ru"
CATEGORY_URL = f"{BASE_URL}/index.php?route=product/category"
PRODUCT_URL = f"{BASE_URL}/index.php?route=product/product"

# Корневые категории для парсинга
ROOT_CATEGORIES = [
    "900000",   # Запчасти для телефонов и планшетов
    "900004",   # Запчасти для ноутбуков
    "900058",   # Запчасти для смарт-часов
]

# Настройки запросов
REQUEST_DELAY = 0.3
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
ITEMS_PER_PAGE = 100
MAX_PAGES = 500

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Пути к файлам
DATA_DIR = "data"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
CATEGORIES_JSON = f"{DATA_DIR}/categories.json"

# === Конфигурация БД (Supabase) ===
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db  # Автоматически маппит таблицы на новые имена


class TaggsmParser:
    """Парсер каталога TAGGSM.ru с рекурсивным обходом категорий"""

    # Города и их ID (85 городов)
    CITIES = {
        "Адлер": "206220",
        "Армавир": "4168",
        "Архангельск": "4929",
        "Астрахань": "4892",
        "Барнаул": "4761",
        "Белгород": "2786",
        "Биробиджан": "4115",
        "Благовещенск": "5753",
        "Брянск": "3762",
        "Буденновск": "4375",
        "Владивосток": "5033",
        "Владикавказ": "3854",
        "Волгоград": "3734",
        "Волгодонск": "4637",
        "Вологда": "2281",
        "Воронеж": "3145",
        "Геленджик": "3981",
        "Грозный": "3388",
        "Джанкой": "204261",
        "Дзержинск": "2304",
        "Димитровград": "7326",
        "Донецк (ДНР)": "400741",
        "Донецк (Рост.)": "2587",
        "Дубна": "2532",
        "Евпатория": "205739",
        "Ейск": "4213",
        "Екатеринбург": "3187",
        "Ессентуки": "3238",
        "Запорожье": "400760",
        "Иваново": "4768",
        "Ижевск": "3256",
        "Иркутск": "3278",
        "Казань": "4006",
        "Калининград": "3736",
        "Калуга": "3541",
        "Кемерово": "3224",
        "Керчь": "205078",
        "Кисловодск": "4753",
        "Краснодар": "5723",
        "Красноярск": "3753",
        "Курган": "4202",
        "Курск": "7292",
        "Липецк": "2749",
        "Луганск": "400874",
        "Мариуполь": "400894",
        "Махачкала": "2844",
        "Мелитополь": "400900",
        "Москва": "41",
        "Мурманск": "3314",
        "Нефтеюганск": "6292",
        "Нижневартовск": "6285",
        "Нижний Новгород": "2990",
        "Новокузнецк": "3317",
        "Новороссийск": "4825",
        "Омск": "3704",
        "Орел": "5221",
        "Пенза": "6123",
        "Пермь": "4131",
        "Пятигорск": "2630",
        "Ростов-на-Дону": "4187",
        "Рязань": "4682",
        "Самара": "2782",
        "Санкт-Петербург": "86",
        "Саратов": "3737",
        "Севастополь": "203915",
        "Симферополь": "205105",
        "Смоленск": "3385",
        "Сочи": "2877",
        "Ставрополь": "4986",
        "Сургут": "6980",
        "Сызрань": "4357",
        "Таганрог": "5003",
        "Тверь": "4333",
        "Тольятти": "2857",
        "Томск": "3053",
        "Тула": "4145",
        "Тюмень": "6115",
        "Улан-Удэ": "4186",
        "Ульяновск": "4521",
        "Уфа": "6125",
        "Хабаровск": "2638",
        "Ханты-Мансийск": "6804",
        "Херсон": "401107",
        "Челябинск": "4778",
        "Чита": "3218",
        "Южно-Сахалинск": "2730",
        "Ялта": "205310",
        "Ярославль": "4119",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })
        self.products: List[Dict] = []
        self.categories: Dict[str, str] = {}  # path -> name
        self.errors: List[Dict] = []
        self.seen_product_ids: set = set()

        os.makedirs(DATA_DIR, exist_ok=True)

    def set_city(self, city_name: str) -> bool:
        """Устанавливает город для сессии"""
        fias_id = self.CITIES.get(city_name)
        if not fias_id:
            return False

        url = f"{BASE_URL}/index.php?route=module/geoip/save&fias_id={fias_id}"
        try:
            self.session.get(url, timeout=REQUEST_TIMEOUT)
            return True
        except Exception as e:
            print(f"  [ERROR] Ошибка установки города: {e}")
            return False

    def get_page(self, url: str, retries: int = MAX_RETRIES) -> Optional[BeautifulSoup]:
        """Загружает страницу с повторными попытками"""
        for attempt in range(retries):
            try:
                time.sleep(REQUEST_DELAY)
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return BeautifulSoup(response.text, 'html.parser')
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

    def extract_breadcrumbs(self, soup: BeautifulSoup) -> Tuple[str, str]:
        """
        Извлекает breadcrumbs из страницы.
        Возвращает (category_path, category_name)
        """
        path_parts = []
        name_parts = []

        breadcrumb = soup.find('ul', class_='breadcrumb')
        if breadcrumb:
            links = breadcrumb.find_all('a', class_='line_tire')
            for link in links:
                href = link.get('href', '')
                name = link.get_text(strip=True)

                # Пропускаем главную
                if name.lower() == 'главная' or href.endswith('/'):
                    continue

                # Извлекаем path из URL
                match = re.search(r'path=([^&]+)', href)
                if match:
                    path = match.group(1)
                    path_parts.append(path)
                    name_parts.append(name)

            # Добавляем текущую категорию (последний элемент без ссылки)
            current = breadcrumb.find('li', recursive=False)
            if current:
                # Ищем последний li без ссылки
                all_li = breadcrumb.find_all('li')
                for li in reversed(all_li):
                    if not li.find('a'):
                        current_name = li.get_text(strip=True)
                        if current_name and current_name not in name_parts:
                            name_parts.append(current_name)
                        break

        return "_".join(path_parts) if path_parts else "", " / ".join(name_parts)

    def get_subcategories(self, soup: BeautifulSoup, current_path: str) -> List[Dict]:
        """Извлекает подкатегории из страницы"""
        subcategories = []

        # На TAGGSM подкатегории в ссылках вида path=PARENT_CHILD
        prefix = f"path={current_path}_"

        # Ищем все ссылки с подкатегориями
        all_links = soup.find_all('a', href=re.compile(rf'path={re.escape(current_path)}_\d+'))

        seen_paths = set()
        for link in all_links:
            href = link.get('href', '')
            match = re.search(r'path=([^&]+)', href)
            if match:
                path = match.group(1)
                # Проверяем что это прямой потомок (только один уровень вложенности)
                if path.startswith(current_path + "_") and path not in seen_paths:
                    # Проверяем что это не более глубокий уровень
                    suffix = path[len(current_path) + 1:]
                    if "_" not in suffix:  # Только прямые потомки
                        seen_paths.add(path)
                        name = link.get_text(strip=True)
                        if name and len(name) > 1:
                            subcategories.append({
                                'path': path,
                                'name': name,
                            })

        return subcategories

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Определяет количество страниц пагинации"""
        pagination = soup.find('ul', class_='pagination') or soup.find('div', class_='pagination')

        if pagination:
            page_links = pagination.find_all('a', href=re.compile(r'page=(\d+)'))
            max_page = 1
            for link in page_links:
                href = link.get('href', '')
                match = re.search(r'page=(\d+)', href)
                if match:
                    page_num = int(match.group(1))
                    max_page = max(max_page, page_num)
            return min(max_page, MAX_PAGES)

        return 1

    def parse_product_card(self, card, category_path: str, category_name: str) -> Optional[Dict]:
        """Парсит карточку товара"""
        try:
            # Product ID из атрибута или ссылки
            product_id = ""
            link = card.find('a', href=re.compile(r'product_id=\d+'))
            if link:
                href = link.get('href', '')
                match = re.search(r'product_id=(\d+)', href)
                if match:
                    product_id = match.group(1)

            if not product_id:
                return None

            # Пропускаем дубликаты
            if product_id in self.seen_product_ids:
                return None
            self.seen_product_ids.add(product_id)

            # Название
            name = ""
            name_elem = card.select_one("div.category_name h4 a") or \
                       card.select_one("h4 a") or \
                       card.find('a', href=re.compile(r'product_id='))
            if name_elem:
                name = name_elem.get('title') or name_elem.get_text(strip=True)

            if not name or len(name) < 3:
                return None

            # Артикул (zm...)
            sku = ""
            sku_elem = card.select_one("div.cat_articul")
            if sku_elem:
                sku = sku_elem.get_text(strip=True)
            if not sku:
                sku_match = re.search(r'(zm\d+)', card.get_text())
                if sku_match:
                    sku = sku_match.group(1)

            # Цена
            price = 0.0
            price_elem = card.select_one("div.category_price") or card.select_one(".price")
            if price_elem:
                price_text = price_elem.get_text()
                price_text = re.sub(r'[^\d,.]', '', price_text)
                price_text = price_text.replace(',', '.')
                try:
                    price = float(price_text) if price_text else 0.0
                except:
                    pass

            # Наличие по городам
            availability = {}
            nalichie = card.select_one("div.category_nalichie table")
            if nalichie:
                rows = nalichie.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        city_name = cells[0].get_text(strip=True)
                        status = cells[1].get_text(strip=True)
                        # Нормализуем название города
                        for city in self.CITIES.keys():
                            if city in city_name:
                                availability[city] = status
                                break

            return {
                "product_id": product_id,
                "article": sku,
                "name": name,
                "price": price,
                "category": category_name,
                "availability": availability,  # Сохраняем для per-city данных
                "url": f"{PRODUCT_URL}&path={category_path}&product_id={product_id}",
            }

        except Exception as e:
            return None

    def parse_category_page(self, url: str, category_path: str, category_name: str) -> List[Dict]:
        """Парсит страницу категории и возвращает список товаров"""
        soup = self.get_page(url)
        if not soup:
            return []

        products = []

        # Ищем карточки товаров
        cards = soup.select("div.product-thumb") or \
                soup.select("div.product-layout") or \
                soup.select("div.product-list .product-item")

        for card in cards:
            product = self.parse_product_card(card, category_path, category_name)
            if product:
                products.append(product)

        return products

    def crawl_category(self, category_path: str, depth: int = 0):
        """
        Рекурсивный обход категории.
        Собирает подкатегории и товары.
        """
        url = f"{CATEGORY_URL}&path={category_path}&limit={ITEMS_PER_PAGE}"
        indent = "  " * depth

        print(f"{indent}[{depth}] Обход: {category_path}")

        soup = self.get_page(url)
        if not soup:
            print(f"{indent}    [SKIP] Не удалось загрузить")
            return

        # Извлекаем breadcrumbs
        cat_path, cat_name = self.extract_breadcrumbs(soup)
        if not cat_name:
            # Fallback: берём из h1
            h1 = soup.find('h1')
            cat_name = h1.get_text(strip=True) if h1 else category_path

        # Сохраняем категорию
        self.categories[category_path] = cat_name

        # Проверяем подкатегории
        subcategories = self.get_subcategories(soup, category_path)

        if subcategories:
            print(f"{indent}    Подкатегорий: {len(subcategories)}")
            for subcat in subcategories:
                self.crawl_category(subcat['path'], depth + 1)
        else:
            # Конечная категория - собираем товары
            self._collect_products_from_category(soup, category_path, cat_name, depth)

    def _collect_products_from_category(self, first_page_soup: BeautifulSoup,
                                        category_path: str, category_name: str, depth: int):
        """Собирает все товары из категории со всех страниц"""
        indent = "  " * depth

        # Парсим первую страницу
        products = []
        cards = first_page_soup.select("div.product-thumb") or \
                first_page_soup.select("div.product-layout")

        for card in cards:
            product = self.parse_product_card(card, category_path, category_name)
            if product:
                products.append(product)

        # Определяем количество страниц
        total_pages = self.get_total_pages(first_page_soup)

        print(f"{indent}    Страница 1/{total_pages}: +{len(products)} товаров")

        self.products.extend(products)

        # Парсим остальные страницы
        for page in range(2, total_pages + 1):
            page_url = f"{CATEGORY_URL}&path={category_path}&limit={ITEMS_PER_PAGE}&page={page}"
            page_products = self.parse_category_page(page_url, category_path, category_name)

            print(f"{indent}    Страница {page}/{total_pages}: +{len(page_products)} товаров")

            self.products.extend(page_products)

            # Если товаров меньше лимита - это последняя страница
            if len(page_products) < ITEMS_PER_PAGE // 2:
                break

    def parse_all(self):
        """Парсит все корневые категории"""
        print(f"\n{'='*60}")
        print(f"Парсинг TAGGSM.ru")
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
            "source": "taggsm.ru",
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

        # Разворачиваем availability в отдельные колонки
        fieldnames = ["article", "name", "price", "category", "url"]
        for city in self.CITIES.keys():
            fieldnames.append(f"avail_{city}")

        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', extrasaction='ignore')
            writer.writeheader()

            for p in self.products:
                row = {
                    "article": p.get("article", ""),
                    "name": p.get("name", ""),
                    "price": p.get("price", 0),
                    "category": p.get("category", ""),
                    "url": p.get("url", ""),
                }
                # Добавляем availability по городам
                avail = p.get("availability", {})
                for city in self.CITIES.keys():
                    row[f"avail_{city}"] = avail.get(city, "")
                writer.writerow(row)

        print(f"Сохранено в {filename}")

    def save_categories(self, filename: str = None):
        """Сохранить категории"""
        filename = filename or CATEGORIES_JSON
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.categories, f, ensure_ascii=False, indent=2)
        print(f"Категории сохранены в {filename}")

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
        prices = [p.get("price", 0) for p in self.products if p.get("price", 0) > 0]
        if prices:
            print(f"\nЦены: от {min(prices):.0f} до {max(prices):.0f} руб")


# ============================================================
# ФУНКЦИИ РАБОТЫ С БД
# ============================================================

def ensure_outlets():
    """Создаёт outlets для всех городов TAGGSM (85 городов)"""
    conn = get_db()
    cur = conn.cursor()
    try:
        for city, city_id in TaggsmParser.CITIES.items():
            outlet_code = f"taggsm-{city_id}"
            cur.execute("""
                INSERT INTO zip_outlets (code, city, name, is_active)
                VALUES (%s, %s, %s, true)
                ON CONFLICT (code) DO UPDATE SET city = EXCLUDED.city, name = EXCLUDED.name
            """, (outlet_code, city, f"TAGGSM {city}"))
        conn.commit()
        print(f"Создано/обновлено {len(TaggsmParser.CITIES)} outlets для TAGGSM")
    finally:
        cur.close()
        conn.close()


def get_outlet_code(city: str) -> str:
    """Возвращает код outlet по названию города"""
    city_id = TaggsmParser.CITIES.get(city)
    if city_id:
        return f"taggsm-{city_id}"
    return "taggsm-online"


def save_staging(products: List[Dict]):
    """Сохранение товаров в staging таблицу (по всем городам)"""
    if not products:
        print("Нет товаров для сохранения в staging")
        return

    conn = get_db()
    cur = conn.cursor()
    try:
        # Очищаем staging
        cur.execute("TRUNCATE TABLE taggsm_staging")

        # Собираем все строки (товары x города)
        cities = list(TaggsmParser.CITIES.keys())
        values = []

        for p in products:
            avail = p.get("availability", {})
            for city in cities:
                outlet_code = get_outlet_code(city)
                values.append((
                    outlet_code,
                    p.get("name", ""),
                    p.get("article", ""),
                    p.get("category", ""),
                    p.get("price", 0),
                    p.get("url", ""),
                ))

        cur.batch_insert(
            "INSERT INTO taggsm_staging (outlet_code, name, article, category, price, url) VALUES %s",
            values, page_size=1000
        )
        print(f"Сохранено в staging: {len(values)} записей ({len(products)} товаров x {len(cities)} городов)")
    finally:
        cur.close()
        conn.close()


def process_staging(full_mode: bool = False):
    """Обработка staging: UPSERT в taggsm_nomenclature (с price) + taggsm_product_urls"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.set_timeout(300)  # тяжёлые INSERT...SELECT
        ensure_outlets()

        # 1. UPSERT в nomenclature (с product_id и price)
        _nom_update = (
            "name = EXCLUDED.name, "
            "category = EXCLUDED.category, "
            "product_id = COALESCE(NULLIF(EXCLUDED.product_id, ''), taggsm_nomenclature.product_id), "
            "price = EXCLUDED.price, "
            "updated_at = NOW()"
            if full_mode else
            "product_id = COALESCE(NULLIF(EXCLUDED.product_id, ''), taggsm_nomenclature.product_id), "
            "price = EXCLUDED.price, "
            "updated_at = NOW()"
        )
        cur.execute(f"""
            INSERT INTO taggsm_nomenclature (article, name, category, product_id, price, first_seen_at, updated_at)
            SELECT DISTINCT ON (article)
                article,
                name,
                category,
                substring(url from 'product_id=([0-9]+)'),
                price,
                NOW(),
                NOW()
            FROM taggsm_staging
            WHERE article IS NOT NULL AND article != ''
            ON CONFLICT (article) DO UPDATE SET
                {_nom_update}
        """)
        nom_count = cur.rowcount
        print(f"Nomenclature: {nom_count} записей")

        # 2. INSERT в product_urls (single-URL: outlet_id = NULL)
        cur.execute("""
            INSERT INTO taggsm_product_urls (nomenclature_id, outlet_id, url, updated_at)
            SELECT DISTINCT ON (s.url)
                n.id, NULL, s.url, NOW()
            FROM taggsm_staging s
            JOIN taggsm_nomenclature n ON n.article = s.article
            WHERE s.article IS NOT NULL AND s.article != ''
              AND s.url IS NOT NULL AND s.url != ''
            ON CONFLICT (url) DO NOTHING
        """)
        url_count = cur.rowcount
        print(f"Product URLs: {url_count} записей")

        conn.commit()

        # Статистика
        cur.execute("SELECT COUNT(*) FROM taggsm_nomenclature")
        total_nom = cur.fetchone()[0]

        print(f"\n=== Итого в БД ===")
        print(f"Номенклатура: {total_nom}")

    finally:
        cur.close()
        conn.close()


def save_to_db(products: List[Dict], full_mode: bool = False):
    """
    Сохранение в новую схему БД v10: taggsm_nomenclature (с price) + taggsm_product_urls
    Single-URL: один URL на товар (outlet_id = NULL), price в nomenclature
    """
    if not products:
        print("Нет товаров для сохранения")
        return

    conn = get_db()
    cur = conn.cursor()
    try:
        ensure_outlets()

        nom_inserted = 0
        nom_updated = 0
        urls_inserted = 0

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
            product_url = p.get("url", "")
            if not product_url:
                product_url = f"https://taggsm.ru/product/{p.get('article', p.get('product_id', 'unknown'))}"

            # 1. UPSERT в taggsm_nomenclature (price в nomenclature)
            article = p.get("article", "").strip()
            if not article:
                article = p.get("product_id", "")

            price = p.get("price", 0)

            cur.execute(f"""
                INSERT INTO taggsm_nomenclature (name, article, category, price, first_seen_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (article) DO UPDATE SET
                    {_nom_update}
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

            # 2. INSERT в taggsm_product_urls (single-URL: outlet_id = NULL)
            cur.execute("""
                INSERT INTO taggsm_product_urls (nomenclature_id, outlet_id, url, updated_at)
                VALUES (%s, NULL, %s, NOW())
                ON CONFLICT (url) DO NOTHING
            """, (nomenclature_id, product_url))
            urls_inserted += 1

        conn.commit()

        print(f"\n=== Сохранено в БД (v10) ===")
        print(f"taggsm_nomenclature: +{nom_inserted} новых, ~{nom_updated} обновлено")
        print(f"taggsm_product_urls: {urls_inserted} URL")

        # Итоговая статистика
        cur.execute("SELECT COUNT(*) FROM taggsm_nomenclature")
        total_nom = cur.fetchone()[0]
        print(f"\nИтого в БД: {total_nom} товаров")

    finally:
        cur.close()
        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():
    arg_parser = argparse.ArgumentParser(description='Парсер TAGGSM.ru')
    arg_parser.add_argument('--all', action='store_true',
                           help='Полный парсинг: сбор + сохранение в БД')
    arg_parser.add_argument('--process', action='store_true',
                           help='Только обработка staging (LEGACY)')
    arg_parser.add_argument('--old-schema', action='store_true',
                           help='Использовать старую схему БД (staging -> nomenclature)')
    arg_parser.add_argument('--full', action='store_true',
                           help='Полный парсинг (UPSERT и так полный для этого парсера)')
    arg_parser.add_argument('--no-db', action='store_true',
                           help='Не сохранять в БД')
    arg_parser.add_argument('--category', '-c', type=str, default=None,
                           help='Парсить только указанную категорию (path)')
    args = arg_parser.parse_args()

    # Только обработка (LEGACY)
    if args.process:
        print("Обработка staging (LEGACY)...")
        process_staging(full_mode=args.full)
        return

    # Парсинг
    parser = TaggsmParser()

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

    # Сохранение в БД
    if not args.no_db:
        if args.all:
            # Bulk: staging pipeline
            save_staging(parser.products)
            process_staging(full_mode=args.full)
        elif args.old_schema:
            save_staging(parser.products)
        else:
            save_to_db(parser.products, full_mode=args.full)

    print("\nГотово!")


if __name__ == "__main__":
    main()
