"""
Парсер каталога NAFFAS с b2b.moysklad.ru

База данных: db_moysklad
Таблицы: staging, outlets, nomenclature, current_prices, price_history
"""

import requests
import json
import csv
import os
import psycopg2
import argparse
from datetime import datetime
from typing import List, Dict

# Конфигурация
CATALOG_ID = "S1AlNWEsMzM7"
SHOP_NAME = "Naffas"
SHOP_CODE = "moysklad-naffas"
API_URL = f"https://b2b.moysklad.ru/desktop-api/public/{CATALOG_ID}/products.json"
DATA_DIR = "data"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# === Конфигурация БД (Supabase) ===
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from db_wrapper import get_db  # Автоматически маппит таблицы на новые имена


def fetch_products():
    """Загружает все товары из API с пагинацией"""
    print(f"Загрузка товаров из API...")
    print(f"URL: {API_URL}")

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    all_products = []
    offset = 0
    page_size = 100

    while True:
        url = f"{API_URL}?offset={offset}"
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        products = data.get("products", [])
        total_size = data.get("size", 0)

        if not products:
            break

        all_products.extend(products)
        print(f"  Загружено: {len(all_products)} / {total_size}")

        if len(products) < page_size or len(all_products) >= total_size:
            break

        offset += page_size

    print(f"Всего загружено: {len(all_products)} товаров")
    return all_products


def process_products(products):
    """Обрабатывает и нормализует товары"""
    processed = []

    for p in products:
        processed.append({
            "id": p.get("id", ""),
            "code": p.get("code", ""),
            "article": p.get("article") or "",
            "name": p.get("name", ""),
            "category": p.get("category", ""),
            "price": p.get("price", 0),
            "currency": p.get("currency", "руб"),
            "stock": p.get("stock", 0),
            "available": p.get("available", False),
            "description": p.get("description") or "",
            "imageURL": p.get("imageURL") or "",
        })

    return processed


def save_to_csv(products, filename=PRODUCTS_CSV):
    """Сохраняет товары в CSV (стандартный формат)"""
    if not products:
        print("Нет товаров для сохранения")
        return

    # Конвертируем в стандартный формат
    standard = []
    for p in products:
        stock = p.get("stock", 0) or 0
        available = p.get("available", False)
        availability = "В наличии" if stock > 0 or available else "Нет в наличии"
        sku = p.get("article") or p.get("code", "")

        standard.append({
            "product_id": p.get("code", ""),
            "sku": sku,
            "name": p.get("name", ""),
            "price": p.get("price", 0),
            "availability": availability,
            "category": p.get("category", ""),
            "url": "",
        })

    fieldnames = ["product_id", "sku", "name", "price", "availability", "category", "url"]

    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(standard)

    print(f"Сохранено в {filename}: {len(products)} товаров")


def save_to_json(products, filename=PRODUCTS_JSON):
    """Сохраняет товары в JSON (стандартный формат)"""
    # Конвертируем в стандартный формат
    standard = []
    for p in products:
        stock = p.get("stock", 0) or 0
        available = p.get("available", False)
        availability = "В наличии" if stock > 0 or available else "Нет в наличии"
        sku = p.get("article") or p.get("code", "")

        standard.append({
            "product_id": p.get("code", ""),
            "sku": sku,
            "name": p.get("name", ""),
            "price": p.get("price", 0),
            "availability": availability,
            "category": p.get("category", ""),
            "url": "",
        })

    data = {
        "source": "b2b.moysklad.ru (NAFFAS)",
        "date": datetime.now().isoformat(),
        "total": len(standard),
        "products": standard,
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Сохранено в {filename}")


def print_stats(products):
    """Выводит статистику по товарам"""
    print("\n" + "=" * 60)
    print("СТАТИСТИКА")
    print("=" * 60)

    # По категориям
    categories = {}
    for p in products:
        cat = p.get("category", "Без категории")
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\nКатегорий: {len(categories)}")
    print("\nТоп-10 категорий:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:10]:
        print(f"  {count:4d} | {cat}")


    # Ценовой диапазон
    prices = [p.get("price", 0) for p in products if p.get("price", 0) > 0]
    if prices:
        print(f"Цены: от {min(prices):.0f} до {max(prices):.0f} руб")


def ensure_outlet():
    """Создаёт outlet для Naffas если не существует"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO outlets (code, city, name, catalog_id, is_active)
            VALUES (%s, %s, %s, %s, true)
            ON CONFLICT (code) DO UPDATE SET catalog_id = EXCLUDED.catalog_id
        """, (SHOP_CODE, 'Интернет', SHOP_NAME, CATALOG_ID))
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
        # Очищаем staging только для текущего магазина (append mode для других)
        cur.execute("DELETE FROM moysklad_naffas_staging WHERE outlet_code = %s", (SHOP_CODE,))

        # Вставляем товары
        insert_sql = """
            INSERT INTO moysklad_naffas_staging (
                outlet_code, name, article, category,
                price, url
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """

        for p in products:
            sku = p.get("article") or p.get("code", "")

            cur.execute(insert_sql, (
                SHOP_CODE,
                p.get("name", ""),
                sku,
                p.get("category", ""),
                p.get("price", 0),
                "",  # URL not available in MoySklad API
            ))

        conn.commit()
        print(f"Сохранено в staging: {len(products)} товаров ({SHOP_NAME})")
    finally:
        cur.close()
        conn.close()


def process_staging():
    """Обработка staging: UPSERT в nomenclature (с price). Naffas не имеет URL — product_urls не заполняется."""
    conn = get_db()
    cur = conn.cursor()
    try:
        # Убеждаемся что outlet существует
        ensure_outlet()

        # 1. UPSERT в nomenclature (price в nomenclature)
        cur.execute("""
            INSERT INTO moysklad_naffas_nomenclature (article, name, category, price, first_seen_at, updated_at)
            SELECT DISTINCT ON (article)
                article, name, category, price, NOW(), NOW()
            FROM moysklad_naffas_staging
            WHERE article IS NOT NULL AND article != ''
            ON CONFLICT (article) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                price = EXCLUDED.price,
                updated_at = NOW()
        """)
        nom_count = cur.rowcount
        print(f"Nomenclature: {nom_count} записей обновлено/добавлено (price в nomenclature)")

        # 2. INSERT в price_history
        cur.execute("""
            INSERT INTO moysklad_naffas_price_history (nomenclature_id, outlet_id, price, recorded_date, recorded_at)
            SELECT DISTINCT ON (n.id, o.id)
                n.id, o.id, s.price, CURRENT_DATE, NOW()
            FROM moysklad_naffas_staging s
            JOIN moysklad_naffas_nomenclature n ON n.article = s.article
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
        cur.execute("SELECT COUNT(*) FROM moysklad_naffas_nomenclature")
        total_nom = cur.fetchone()[0]
        print(f"\n=== Итого в БД ===")
        print(f"Номенклатура: {total_nom}")

    finally:
        cur.close()
        conn.close()


def main():
    arg_parser = argparse.ArgumentParser(description=f'Парсер каталога {SHOP_NAME} (MoySklad)')
    arg_parser.add_argument('--all', action='store_true',
                           help='Полный парсинг: сбор + сохранение в БД + обработка')
    arg_parser.add_argument('--process', action='store_true',
                           help='Только обработка staging (без парсинга)')
    arg_parser.add_argument('--no-db', action='store_true',
                           help='Не сохранять в БД (только CSV/JSON)')
    args = arg_parser.parse_args()

    # Только обработка staging
    if args.process:
        print("Обработка staging...")
        process_staging()
        print("\nОбработка завершена!")
        return

    # Создаём папку data
    os.makedirs(DATA_DIR, exist_ok=True)

    print(f"\nПарсинг каталога {SHOP_NAME}")
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Загружаем товары
    products = fetch_products()

    # Обрабатываем
    products = process_products(products)

    # Статистика
    print_stats(products)

    # Сохраняем в файлы
    print("\n" + "=" * 60)
    print("СОХРАНЕНИЕ")
    print("=" * 60)
    save_to_csv(products)
    save_to_json(products)

    # Сохраняем в БД
    if not args.no_db:
        save_staging(products)

        if args.all:
            process_staging()

    print("\nПарсинг завершён!")


if __name__ == "__main__":
    main()
