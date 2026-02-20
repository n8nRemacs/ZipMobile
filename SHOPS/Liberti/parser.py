"""
Парсер прайс-листов Liberti.ru (Liberty Project)

База данных: db_liberti
Таблицы: staging, outlets, nomenclature, current_prices, price_history

Скачивает Excel прайс-листы по городам и парсит ветку "1. Запчасти"
"""

import os
import re
import psycopg2
import argparse
import time
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from io import BytesIO

# === Конфигурация ===
BASE_URL = "https://liberti.ru"
PRICE_URL = f"{BASE_URL}/upload/price_region/liberti_{{city}}_price.xlsx"

# Города с рабочими прайс-листами (37 городов)
CITIES = {
    "Internet_magazin": "Интернет-магазин",
    "adler": "Адлер",
    "velikiy_novgorod": "Великий Новгород",
    "vladimir": "Владимир",
    "volgograd": "Волгоград",
    "voronezh": "Воронеж",
    "ekaterinburg": "Екатеринбург",
    "izhevsk": "Ижевск",
    "kazan": "Казань",
    "kaliningrad": "Калининград",
    "kirov": "Киров",
    "krasnodar": "Краснодар",
    "kursk": "Курск",
    "lipetsk": "Липецк",
    "mahachkala": "Махачкала",
    "murmansk": "Мурманск",
    "n_chelny": "Набережные Челны",
    "novosibirsk": "Новосибирск",
    "omsk": "Омск",
    "orenburg": "Оренбург",
    "penza": "Пенза",
    "perm": "Пермь",
    "rostov": "Ростов-на-Дону",
    "ryazan": "Рязань",
    "samara": "Самара",
    "saratov": "Саратов",
    "simferopol": "Симферополь",
    "sochi": "Сочи",
    "stavropol": "Ставрополь",
    "tver": "Тверь",
    "tolyatti": "Тольятти",
    "tula": "Тула",
    "tumen": "Тюмень",
    "ulyanovsk": "Ульяновск",
    "ufa": "Уфа",
    "cheboksary": "Чебоксары",
    "chelyabinsk": "Челябинск",
}

REQUEST_DELAY = 0.5
REQUEST_TIMEOUT = 60
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# === Конфигурация БД (Supabase) ===
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db  # Автоматически маппит таблицы на новые имена

SHOP_CODE = "liberti"
SHOP_NAME = "Liberti"


class LibertiPriceParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        })
        self.products: List[Dict] = []
        self.seen_articles: set = set()

    def download_price(self, city_code: str) -> Optional[bytes]:
        """Скачивает прайс-лист города"""
        url = PRICE_URL.format(city=city_code)
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.content
            else:
                print(f"  Ошибка {response.status_code} для {city_code}")
                return None
        except Exception as e:
            print(f"  Ошибка загрузки {city_code}: {e}")
            return None

    def parse_price_excel(self, content: bytes, city_code: str, city_name: str) -> List[Dict]:
        """Парсит Excel прайс-лист"""
        products = []

        try:
            df = pd.read_excel(BytesIO(content), header=None)
        except Exception as e:
            print(f"  Ошибка чтения Excel: {e}")
            return products

        current_category = ""
        in_zapchasti = False  # Флаг что мы в ветке "1. Запчасти"
        header_row = -1
        qty_col = -1

        for idx, row in df.iterrows():
            cell0 = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""

            # Ищем строку заголовка
            if cell0 == "Код товара":
                header_row = idx
                # Ищем колонку с остатками (название города)
                for col_idx, val in enumerate(row):
                    if pd.notna(val) and str(val).strip() not in ["Код товара", "Наименование", "Розница", "Заказ"]:
                        qty_col = col_idx
                        break
                continue

            # Пропускаем до заголовка
            if header_row < 0:
                continue

            # Проверяем категории
            if cell0.startswith("1. Запчасти"):
                in_zapchasti = True
                current_category = "Запчасти"
                continue
            elif cell0.startswith("2. ") or cell0.startswith("3. "):
                # Вышли из ветки запчастей
                in_zapchasti = False
                continue
            elif cell0.startswith("1_"):
                # Подкатегория в ветке запчастей
                if in_zapchasti:
                    # Извлекаем название категории после "1_X_X. "
                    match = re.match(r'1_[\d_]+\.\s*(.+)', cell0)
                    if match:
                        current_category = match.group(1).strip()
                continue

            # Пропускаем если не в ветке запчастей
            if not in_zapchasti:
                continue

            # Парсим товар
            article = cell0.strip()
            if not article or article == "nan":
                continue

            # Пропускаем если это категория
            if re.match(r'^\d+[\._]', article):
                continue

            name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
            if not name or name == "nan":
                continue

            # Цена
            price = 0
            try:
                price_val = row.iloc[2]
                if pd.notna(price_val):
                    price = float(str(price_val).replace(",", ".").replace(" ", ""))
            except:
                pass

            products.append({
                "article": article,
                "name": name,
                "price": price,
                "category": current_category,
                "city_code": city_code,
                "city_name": city_name,
            })

        return products

    def parse_city(self, city_code: str, city_name: str) -> int:
        """Парсит прайс одного города"""
        print(f"\n{city_name} ({city_code})...")

        content = self.download_price(city_code)
        if not content:
            return 0

        products = self.parse_price_excel(content, city_code, city_name)

        # Добавляем только уникальные товары (по article)
        new_count = 0
        for p in products:
            if p["article"] not in self.seen_articles:
                self.seen_articles.add(p["article"])
                new_count += 1
            self.products.append(p)

        print(f"  Товаров: {len(products)}, новых: {new_count}")

        return len(products)

    def parse_all_cities(self, cities: Dict[str, str] = None) -> List[Dict]:
        """Парсит все города"""
        if cities is None:
            cities = CITIES

        print(f"\nПарсинг прайс-листов {SHOP_NAME}")
        print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Городов: {len(cities)}")
        print("=" * 60)

        total = 0
        for city_code, city_name in cities.items():
            count = self.parse_city(city_code, city_name)
            total += count
            time.sleep(REQUEST_DELAY)

        print(f"\n{'='*60}")
        print(f"ИТОГО: {len(self.products)} записей, уникальных артикулов: {len(self.seen_articles)}")
        print("=" * 60)

        return self.products

    def print_stats(self):
        """Выводит статистику"""
        print("\n" + "=" * 60)
        print("СТАТИСТИКА")
        print("=" * 60)

        # По городам
        cities = {}
        for p in self.products:
            city = p.get("city_name", "Неизвестно")
            if city not in cities:
                cities[city] = {"total": 0}
            cities[city]["total"] += 1

        print(f"\nГородов: {len(cities)}")
        print("\nТоп-10 городов по товарам:")
        sorted_cities = sorted(cities.items(), key=lambda x: -x[1]["total"])
        for city, stats in sorted_cities[:10]:
            print(f"  {stats['total']:5d} | {city}")

        # По категориям
        categories = {}
        for p in self.products:
            cat = p.get("category", "Без категории")
            categories[cat] = categories.get(cat, 0) + 1

        print(f"\nКатегорий: {len(categories)}")
        print("\nТоп-10 категорий:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:10]:
            print(f"  {count:5d} | {cat}")

        # Общая статистика
        print(f"\nВсего товаров: {len(self.products)}")

        prices = [p.get("price", 0) for p in self.products if p.get("price", 0) > 0]
        if prices:
            print(f"Цены: от {min(prices):.0f} до {max(prices):.0f} руб")


def ensure_outlets():
    """Создаёт outlets для всех городов"""
    conn = get_db()
    cur = conn.cursor()
    try:
        for city_code, city_name in CITIES.items():
            outlet_code = f"liberti_{city_code}"
            cur.execute("""
                INSERT INTO outlets (code, city, name, is_active)
                VALUES (%s, %s, %s, true)
                ON CONFLICT (code) DO UPDATE SET
                    city = EXCLUDED.city,
                    name = EXCLUDED.name
            """, (outlet_code, city_name, f"Liberti {city_name}"))
        conn.commit()
        print(f"Outlets: {len(CITIES)} городов")
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
        # Очищаем старые данные
        cur.execute("DELETE FROM staging WHERE outlet_code LIKE 'liberti_%'")

        insert_sql = """
            INSERT INTO staging (
                outlet_code, name, article, category,
                price, url, product_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        for p in products:
            outlet_code = f"liberti_{p.get('city_code', 'unknown')}"
            cur.execute(insert_sql, (
                outlet_code,
                p.get("name", ""),
                p.get("article", ""),
                p.get("category", ""),
                p.get("price", 0),
                "",  # URL не используем для прайсов
                p.get("article", ""),  # product_id = article
            ))

        conn.commit()
        print(f"Сохранено в staging: {len(products)} записей")
    finally:
        cur.close()
        conn.close()


def process_staging():
    """Обработка staging: UPSERT в nomenclature и current_prices (старая схема)"""
    conn = get_db()
    cur = conn.cursor()
    try:
        ensure_outlets()

        # 1. UPSERT в nomenclature
        cur.execute("""
            INSERT INTO nomenclature (article, name, category, product_id, first_seen_at, updated_at)
            SELECT DISTINCT ON (article)
                article, name, category, product_id, NOW(), NOW()
            FROM staging
            WHERE article IS NOT NULL AND article != ''
            ON CONFLICT (article) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                product_id = COALESCE(EXCLUDED.product_id, nomenclature.product_id),
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
        cur.execute("SELECT COUNT(DISTINCT outlet_id) FROM current_prices")
        outlets_count = cur.fetchone()[0]

        print(f"\n=== Итого в БД ===")
        print(f"Номенклатура: {total_nom}")
        print(f"Городов с данными: {outlets_count}")

    finally:
        cur.close()
        conn.close()


def save_to_db(products: List[Dict]):
    """
    Сохранение в новую схему БД v10: liberti_nomenclature (с price) + liberti_product_urls
    Single-URL: один URL на товар (outlet_id = NULL), price в nomenclature
    """
    if not products:
        print("Нет товаров для сохранения")
        return

    conn = get_db()
    cur = conn.cursor()
    try:
        ensure_outlets()

        saved_nom = 0
        saved_urls = 0

        for p in products:
            article = p.get("article", "").strip()
            name = p.get("name", "").strip()
            if not article or not name:
                continue

            # Генерируем URL из article
            url = f"https://liberti.ru/product/{article}"
            category = p.get("category", "").strip() or None

            # UPSERT в liberti_nomenclature (price в nomenclature)
            cur.execute("""
                INSERT INTO liberti_nomenclature (name, article, category, price, first_seen_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (article) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    updated_at = NOW()
                RETURNING id
            """, (name, article, category, p.get("price", 0)))

            nom_row = cur.fetchone()
            if not nom_row:
                continue
            nom_id = nom_row[0]
            saved_nom += 1

            # INSERT в liberti_product_urls (single-URL: outlet_id = NULL)
            cur.execute("""
                INSERT INTO liberti_product_urls (nomenclature_id, outlet_id, url, updated_at)
                VALUES (%s, NULL, %s, NOW())
                ON CONFLICT (url) DO NOTHING
            """, (nom_id, url))
            saved_urls += 1

        conn.commit()

        print(f"\n=== Сохранено в БД (v10) ===")
        print(f"liberti_nomenclature: {saved_nom} товаров")
        print(f"liberti_product_urls: {saved_urls} URL")

        # Статистика
        cur.execute("SELECT COUNT(*) FROM liberti_nomenclature")
        total = cur.fetchone()[0]
        print(f"Всего: {total} товаров")

    finally:
        cur.close()
        conn.close()


def main():
    arg_parser = argparse.ArgumentParser(description=f'Парсер прайс-листов {SHOP_NAME}')
    arg_parser.add_argument('--all', action='store_true',
                           help='Полный парсинг: все города + сохранение в БД')
    arg_parser.add_argument('--process', action='store_true',
                           help='Только обработка staging (старая схема)')
    arg_parser.add_argument('--no-db', action='store_true',
                           help='Не сохранять в БД')
    arg_parser.add_argument('--city', type=str,
                           help='Парсить только указанный город (код)')
    arg_parser.add_argument('--limit', type=int, default=0,
                           help='Лимит городов (0 = все)')
    arg_parser.add_argument('--old-schema', action='store_true',
                           help='Использовать старую схему БД (staging)')
    args = arg_parser.parse_args()

    if args.process:
        print("Обработка staging (старая схема)...")
        process_staging()
        print("\nОбработка завершена!")
        return

    parser = LibertiPriceParser()

    # Выбор городов
    cities = CITIES
    if args.city:
        if args.city in CITIES:
            cities = {args.city: CITIES[args.city]}
        else:
            print(f"Город '{args.city}' не найден. Доступные: {', '.join(CITIES.keys())}")
            return
    elif args.limit > 0:
        cities = dict(list(CITIES.items())[:args.limit])

    products = parser.parse_all_cities(cities)
    parser.print_stats()

    if not args.no_db:
        print("\n" + "=" * 60)
        print("СОХРАНЕНИЕ В БД")
        print("=" * 60)
        if args.old_schema:
            save_staging(products)
            if args.all:
                process_staging()
        else:
            save_to_db(products)

    print("\nПарсинг завершён!")


if __name__ == "__main__":
    main()
