#!/usr/bin/env python3
"""
Парсер Profi для ZIP архитектуры
Парсит XLS прайс-листы и пишет в zip_staging, затем UPSERT в zip_nomenclature/prices/stock

Использование:
  python3 parse_profi_to_zip.py              # Один прайс (Астрахань)
  python3 parse_profi_to_zip.py --all        # Все прайсы
  python3 parse_profi_to_zip.py --process    # Только обработка staging -> zip таблицы
"""
import os
import sys
import re
import time
import argparse
import tempfile
import httpx
import psycopg2
from psycopg2.extras import execute_values

try:
    import xlrd
except ImportError:
    print("ERROR: pip install xlrd", file=sys.stderr)
    sys.exit(1)

try:
    from fetch_price_lists import fetch_price_lists, get_info_by_url
except ImportError:
    from price_lists_config import PRICE_LISTS, get_info_by_url
    def fetch_price_lists():
        return PRICE_LISTS

# Транслитерация кириллицы в латиницу
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def transliterate(text: str) -> str:
    """Транслитерация текста в латиницу"""
    result = []
    for char in text.lower():
        if char in TRANSLIT_MAP:
            result.append(TRANSLIT_MAP[char])
        elif char.isalnum() or char in '-_':
            result.append(char)
        elif char in ' .':
            result.append('-')
    # Убираем дублирование дефисов и начальные/конечные
    return re.sub(r'-+', '-', ''.join(result)).strip('-')


def generate_outlet_code(city: str, shop: str = None) -> str:
    """Генерация outlet_code из города и магазина"""
    base = f"profi-{transliterate(city)}"

    # Проверяем номер точки в названии магазина
    if shop:
        match = re.search(r'точка\s*(\d+)|(\d+)\s*$', shop, re.IGNORECASE)
        if match:
            num = match.group(1) or match.group(2)
            base = f"{base}-{num}"

    return base


# Настройки
DEFAULT_PRICE_URL = "https://www.siriust.ru/club/price/Astraxan.xls"
DEFAULT_OUTLET_CODE = "profi-astrakhan"
SOURCE = "profi"

# БД (5433 = прямой PostgreSQL, 5432 = через pooler)
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", 5433))
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mi31415926pSss!")


def get_db_connection():
    """Получить соединение с БД"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def ensure_outlets_exist(price_lists: list):
    """Создать отсутствующие города и outlet'ы в БД"""
    if not price_lists:
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Получаем ID магазина Profi
            cur.execute("SELECT id FROM zip_shops WHERE code = 'profi'")
            row = cur.fetchone()
            if not row:
                print("[WARN] Shop 'profi' not found in zip_shops, creating...")
                # Получаем country_id для России
                cur.execute("SELECT id FROM zip_countries WHERE code = 'RU'")
                country_row = cur.fetchone()
                country_id = country_row[0] if country_row else None
                cur.execute("""
                    INSERT INTO zip_shops (code, name, country_id)
                    VALUES ('profi', 'Profi (siriust.ru)', %s)
                    RETURNING id
                """, (country_id,))
                profi_shop_id = cur.fetchone()[0]
            else:
                profi_shop_id = row[0]

            # Получаем все уникальные города из прайсов
            cities_needed = {pl["city"] for pl in price_lists}

            # Получаем существующие города
            cur.execute("SELECT code, name, id FROM zip_cities")
            existing_cities = {r[1]: {"code": r[0], "id": r[2]} for r in cur.fetchall()}

            # Создаём отсутствующие города
            for city_name in cities_needed:
                if city_name not in existing_cities:
                    city_code = transliterate(city_name)
                    print(f"[INFO] Creating city: {city_name} ({city_code})")
                    # Получаем country_id для России
                    cur.execute("SELECT id FROM zip_countries WHERE code = 'RU'")
                    country_row = cur.fetchone()
                    country_id = country_row[0] if country_row else None
                    cur.execute("""
                        INSERT INTO zip_cities (code, name, country_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                        RETURNING id
                    """, (city_code, city_name, country_id))
                    result = cur.fetchone()
                    if result:
                        existing_cities[city_name] = {"code": city_code, "id": result[0]}
                    else:
                        # Город уже существует с таким кодом
                        cur.execute("SELECT id FROM zip_cities WHERE code = %s", (city_code,))
                        existing_cities[city_name] = {"code": city_code, "id": cur.fetchone()[0]}

            conn.commit()

            # Получаем существующие outlet'ы
            cur.execute("SELECT code FROM zip_outlets WHERE shop_id = %s", (profi_shop_id,))
            existing_codes = {r[0] for r in cur.fetchall()}

            # Добавляем новые outlet'ы
            new_outlets = []
            for pl in price_lists:
                outlet_code = pl.get("outlet_code") or generate_outlet_code(pl["city"], pl.get("shop"))
                if outlet_code not in existing_codes:
                    city_info = existing_cities.get(pl["city"])
                    if city_info:
                        new_outlets.append({
                            "code": outlet_code,
                            "name": pl.get("shop") or f"Профи {pl['city']}",
                            "city_id": city_info["id"],
                            "shop_id": profi_shop_id
                        })
                        existing_codes.add(outlet_code)

            if new_outlets:
                print(f"[INFO] Creating {len(new_outlets)} new outlets...")
                for outlet in new_outlets:
                    cur.execute("""
                        INSERT INTO zip_outlets (code, name, city_id, shop_id)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                    """, (outlet["code"], outlet["name"], outlet["city_id"], outlet["shop_id"]))
                    print(f"  + {outlet['code']}")
                conn.commit()
                print(f"[OK] Created {len(new_outlets)} outlets")
            else:
                print("[INFO] All outlets already exist")

    finally:
        conn.close()


def canon(s: str) -> str:
    """Канонизация строки"""
    s = s.strip().lower().replace("ё", "е")
    return re.sub(r"[^a-z0-9а-я]+", "", s)


def get_font_size(wb, sheet, row, col):
    """Получить размер шрифта ячейки в points"""
    try:
        xf_index = sheet.cell_xf_index(row, col)
        xf = wb.xf_list[xf_index]
        font = wb.font_list[xf.font_index]
        return font.height / 20
    except:
        return None


def find_header_row(sheet):
    """Найти строку заголовка"""
    for r in range(min(sheet.nrows, 50)):
        for c in range(min(sheet.ncols, 50)):
            v = sheet.cell_value(r, c)
            if isinstance(v, str) and "наимен" in v.lower():
                return r
    return None


def row_empty_fast(sheet, r, cols):
    """Быстрая проверка пустой строки"""
    for idx in cols:
        if idx is not None:
            v = sheet.cell_value(r, idx)
            if v not in (None, "", " "):
                return False
    return True


def clean_value(v):
    """Очистка значения"""
    if v is None or v == "":
        return None
    if isinstance(v, float):
        if v == int(v):
            return int(v)
        return v
    return str(v).strip() if str(v).strip() else None


def parse_price(v):
    """Парсинг цены"""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("руб.", "").replace("руб", "").replace(" ", "").replace(",", ".").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def download_file(url: str) -> str:
    """Скачать файл"""
    print(f"[INFO] Downloading {url}...")
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=".xls")
    with os.fdopen(fd, 'wb') as f:
        f.write(resp.content)
    print(f"[INFO] Downloaded {len(resp.content)} bytes")
    return path


def parse_excel(file_path: str, outlet_code: str) -> list:
    """Парсинг Excel файла, возвращает записи для zip_staging"""
    print(f"[INFO] Parsing {file_path} for outlet {outlet_code}...")

    wb = xlrd.open_workbook(file_path, formatting_info=True)
    sheet = wb.sheet_by_index(0)
    print(f"[INFO] Sheet: {sheet.name}, rows: {sheet.nrows}")

    header_row = find_header_row(sheet)
    if header_row is None:
        raise ValueError("Header row not found")

    # Карта заголовков
    headers_map = {}
    for c in range(sheet.ncols):
        v = sheet.cell_value(header_row, c)
        if isinstance(v, str) and v.strip():
            headers_map[v.strip()] = c
    canon_map = {canon(k): v for k, v in headers_map.items()}

    # Синонимы
    targets = {
        "name": ["наимен", "наименование"],
        "article": ["артикул", "код"],
        "barcode": ["штрихкод", "штрих-код", "barcode"],
        "price": ["цена", "розница", "price"],
        "stock": ["количество", "наличие", "остаток"],
    }

    resolved = {}
    for target, keys in targets.items():
        found = None
        for key in keys:
            for hdr_canon, col in canon_map.items():
                if key in hdr_canon:
                    found = col
                    break
            if found is not None:
                break
        resolved[target] = found

    name_col = resolved["name"]
    if name_col is None:
        raise ValueError("Column 'Наименование' not found")

    empty_check_cols = [name_col] + [c for c in resolved.values() if c is not None]

    # Парсим
    current_brand = current_model = current_type = None
    products = []

    for r in range(header_row + 1, sheet.nrows):
        if row_empty_fast(sheet, r, empty_check_cols):
            break

        name_val = sheet.cell_value(r, name_col)
        if not name_val or not str(name_val).strip():
            continue
        name_val = str(name_val).strip()

        fsize = get_font_size(wb, sheet, r, name_col)

        # Иерархия по размеру шрифта
        if fsize and fsize >= 10.5:
            current_brand = name_val
            current_model = None
            current_type = None
            continue
        elif fsize and 9.5 <= fsize < 10.5:
            current_model = name_val
            current_type = None
            continue
        elif fsize and 8.5 <= fsize < 9.5:
            current_type = name_val
            continue
        else:
            # Товар
            article = clean_value(sheet.cell_value(r, resolved["article"])) if resolved["article"] is not None else None
            barcode = clean_value(sheet.cell_value(r, resolved["barcode"])) if resolved["barcode"] is not None else None
            price = parse_price(sheet.cell_value(r, resolved["price"])) if resolved["price"] is not None else None

            # Stock
            stock_level = None
            in_stock = False
            stock_val = clean_value(sheet.cell_value(r, resolved["stock"])) if resolved["stock"] is not None else None
            if stock_val:
                if isinstance(stock_val, (int, float)):
                    stock_level = min(int(stock_val), 5) if stock_val <= 5 else 5
                    in_stock = stock_val > 0
                elif "+" in str(stock_val) or "*" in str(stock_val):
                    stock_level = max(str(stock_val).count("+"), str(stock_val).count("*"))
                    in_stock = stock_level > 0

            products.append({
                "source": SOURCE,
                "outlet_code": outlet_code,
                "name": name_val,
                "article": str(article) if article else None,
                "barcode": str(barcode) if barcode else None,
                "brand_raw": current_brand,
                "model_raw": current_model,
                "part_type_raw": current_type,
                "price": price,
                "stock_level": stock_level,
                "in_stock": in_stock,
            })

        if len(products) % 1000 == 0:
            print(f"[PROGRESS] {len(products)} products...")

    print(f"[INFO] Parsed {len(products)} products")
    return products


def save_to_staging(products: list, truncate: bool = True):
    """Сохранить в profi_staging"""
    if not products:
        print("[WARN] No products to save")
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if truncate:
                cur.execute("TRUNCATE profi_staging")
                print("[INFO] Truncated profi_staging")

            # Вставляем
            sql = """
                INSERT INTO profi_staging
                (outlet_code, name, article, barcode, brand_raw, model_raw, part_type_raw, price, stock_level, in_stock)
                VALUES %s
            """
            values = [
                (p["outlet_code"], p["name"], p["article"], p["barcode"],
                 p["brand_raw"], p["model_raw"], p["part_type_raw"], p["price"], p["stock_level"], p["in_stock"])
                for p in products
            ]
            execute_values(cur, sql, values, page_size=1000)
            conn.commit()
            print(f"[OK] Inserted {len(products)} rows to profi_staging")
    finally:
        conn.close()


def process_staging_to_zip():
    """Обработка profi_staging -> zip таблицы"""
    print("\n[INFO] Processing profi_staging to ZIP tables...")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. UPSERT в zip_nomenclature (уникальные товары по артикулу)
            print("[INFO] UPSERT zip_nomenclature...")
            cur.execute("""
                INSERT INTO zip_nomenclature (article, name)
                SELECT DISTINCT ON (article) article, name
                FROM profi_staging
                WHERE article IS NOT NULL AND TRIM(article) != ''
                ORDER BY article, loaded_at DESC
                ON CONFLICT (article) DO UPDATE SET
                    name = EXCLUDED.name,
                    parsed_at = NOW()
            """)
            nom_count = cur.rowcount
            print(f"[OK] Upserted {nom_count} nomenclature items")

            # 2. UPSERT в zip_current_prices (цены по точкам)
            print("[INFO] UPSERT zip_current_prices...")
            cur.execute("""
                INSERT INTO zip_current_prices (nomenclature_id, outlet_id, price_type_id, price, updated_at)
                SELECT
                    n.id as nomenclature_id,
                    o.id as outlet_id,
                    1 as price_type_id,  -- retail
                    s.price,
                    NOW()
                FROM profi_staging s
                JOIN zip_nomenclature n ON n.article = s.article
                JOIN zip_outlets o ON o.code = s.outlet_code
                WHERE s.article IS NOT NULL
                  AND s.price IS NOT NULL
                ON CONFLICT (nomenclature_id, outlet_id, price_type_id) DO UPDATE SET
                    price = EXCLUDED.price,
                    updated_at = NOW()
            """)
            price_count = cur.rowcount
            print(f"[OK] Upserted {price_count} prices")

            # 3. UPSERT в zip_current_stock (остатки по точкам)
            print("[INFO] UPSERT zip_current_stock...")
            cur.execute("""
                INSERT INTO zip_current_stock (nomenclature_id, outlet_id, stock_level, in_stock, updated_at)
                SELECT
                    n.id as nomenclature_id,
                    o.id as outlet_id,
                    s.stock_level,
                    COALESCE(s.in_stock, s.stock_level > 0),
                    NOW()
                FROM profi_staging s
                JOIN zip_nomenclature n ON n.article = s.article
                JOIN zip_outlets o ON o.code = s.outlet_code
                WHERE s.article IS NOT NULL
                ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
                    stock_level = EXCLUDED.stock_level,
                    in_stock = EXCLUDED.in_stock,
                    updated_at = NOW()
            """)
            stock_count = cur.rowcount
            print(f"[OK] Upserted {stock_count} stock records")

            # 4. Сохраняем историю (только если цена изменилась)
            print("[INFO] Saving price history...")
            cur.execute("""
                INSERT INTO zip_price_history (nomenclature_id, outlet_id, price_type_id, price, recorded_date)
                SELECT
                    cp.nomenclature_id,
                    cp.outlet_id,
                    cp.price_type_id,
                    cp.price,
                    CURRENT_DATE
                FROM zip_current_prices cp
                JOIN zip_outlets o ON o.id = cp.outlet_id
                JOIN zip_shops s ON s.id = o.shop_id
                WHERE s.code = 'profi'
                ON CONFLICT (nomenclature_id, outlet_id, price_type_id, recorded_date)
                DO UPDATE SET price = EXCLUDED.price
            """)
            history_count = cur.rowcount
            print(f"[OK] Saved {history_count} price history records")

            # 5. Сохраняем историю остатков
            print("[INFO] Saving stock history...")
            cur.execute("""
                INSERT INTO zip_stock_history (nomenclature_id, outlet_id, stock_level, in_stock, recorded_date)
                SELECT
                    cs.nomenclature_id,
                    cs.outlet_id,
                    cs.stock_level,
                    cs.in_stock,
                    CURRENT_DATE
                FROM zip_current_stock cs
                JOIN zip_outlets o ON o.id = cs.outlet_id
                JOIN zip_shops s ON s.id = o.shop_id
                WHERE s.code = 'profi'
                ON CONFLICT (nomenclature_id, outlet_id, recorded_date)
                DO UPDATE SET
                    stock_level = EXCLUDED.stock_level,
                    in_stock = EXCLUDED.in_stock
            """)
            stock_hist_count = cur.rowcount
            print(f"[OK] Saved {stock_hist_count} stock history records")

            conn.commit()

            # Статистика
            cur.execute("SELECT COUNT(*) FROM zip_nomenclature")
            total_nom = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM zip_current_prices")
            total_prices = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM zip_current_stock WHERE in_stock = true")
            total_in_stock = cur.fetchone()[0]

            print(f"\n[SUMMARY]")
            print(f"  Total nomenclature: {total_nom}")
            print(f"  Total prices: {total_prices}")
            print(f"  Items in stock: {total_in_stock}")

    finally:
        conn.close()


def parse_single(url: str, outlet_code: str) -> list:
    """Парсинг одного прайса"""
    file_path = download_file(url)
    try:
        return parse_excel(file_path, outlet_code)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def parse_all() -> tuple:
    """Парсинг всех прайсов с динамическим получением списка"""
    # Динамически получаем актуальный список прайсов с сайта
    print("\n[STEP 1] Fetching current price lists from site...")
    price_lists = fetch_price_lists()

    if not price_lists:
        print("[ERROR] No price lists found", file=sys.stderr)
        return [], []

    print(f"[INFO] Found {len(price_lists)} price lists")

    # Генерируем outlet_code для каждого прайса
    for pl in price_lists:
        if "outlet_code" not in pl:
            pl["outlet_code"] = generate_outlet_code(pl["city"], pl.get("shop"))

    # Создаём отсутствующие outlet'ы в БД
    print("\n[STEP 2] Ensuring outlets exist in database...")
    ensure_outlets_exist(price_lists)

    # Парсим прайсы
    print("\n[STEP 3] Parsing price lists...")
    all_products = []
    failed = []

    for i, pl in enumerate(price_lists, 1):
        url = pl["url"]
        outlet_code = pl["outlet_code"]

        print(f"\n[{i}/{len(price_lists)}] {pl['city']} - {pl.get('shop', 'N/A')}")
        print(f"    outlet: {outlet_code}")
        print(f"    url: {url}")

        try:
            products = parse_single(url, outlet_code)
            all_products.extend(products)
            print(f"    OK: {len(products)} products")
        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr)
            failed.append({"url": url, "outlet_code": outlet_code, "city": pl["city"], "error": str(e)})

    return all_products, failed


def main():
    parser = argparse.ArgumentParser(description="Profi parser for ZIP architecture")
    parser.add_argument("--url", help="URL of specific price list")
    parser.add_argument("--outlet", help="Outlet code (e.g. profi-astrakhan)")
    parser.add_argument("--all", action="store_true", help="Parse all price lists")
    parser.add_argument("--process", action="store_true", help="Only process staging to ZIP tables")
    parser.add_argument("--no-process", action="store_true", help="Skip processing after parsing")

    args = parser.parse_args()
    start = time.time()

    try:
        if args.process:
            # Только обработка
            process_staging_to_zip()
        elif args.all:
            # Все прайсы
            all_products, failed = parse_all()

            print(f"\n[SUMMARY] Total: {len(all_products)}, Failed: {len(failed)}")
            if failed:
                for f in failed:
                    print(f"  FAILED: {f['outlet_code']}: {f['error']}")

            if all_products:
                save_to_staging(all_products, truncate_source=True)
                if not args.no_process:
                    process_staging_to_zip()
        elif args.url:
            # Конкретный URL
            info = get_info_by_url(args.url)
            outlet_code = args.outlet or info.get("outlet_code", DEFAULT_OUTLET_CODE)
            products = parse_single(args.url, outlet_code)
            save_to_staging(products, truncate_source=True)
            if not args.no_process:
                process_staging_to_zip()
        else:
            # По умолчанию - Астрахань
            products = parse_single(DEFAULT_PRICE_URL, DEFAULT_OUTLET_CODE)
            save_to_staging(products, truncate_source=True)
            if not args.no_process:
                process_staging_to_zip()

        print(f"\n[OK] Total time: {time.time() - start:.2f}s")
        return 0

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
