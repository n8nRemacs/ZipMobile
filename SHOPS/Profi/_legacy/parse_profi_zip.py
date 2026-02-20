#!/usr/bin/env python3
"""
Парсер прайс-листов Profi (siriust.ru)
Интегрирован с архитектурой zip_*

Использование:
  # Один прайс:
  python3 parse_profi_zip.py --url "https://..." --city "Москва" --outlet "Савеловский"

  # Все прайсы:
  python3 parse_profi_zip.py --all

Иерархия по размеру шрифта:
  11pt = Бренд
  10pt = Модель
  9pt  = Тип запчасти
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

# Импорт конфига с прайс-листами
try:
    from price_lists_config import PRICE_LISTS, get_info_by_url
except ImportError:
    PRICE_LISTS = []
    def get_info_by_url(url):
        return {"city": "Неизвестно", "shop": "Неизвестно"}

# Настройки БД
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "Mi31415926pSss!"

# Код магазина в системе
SHOP_CODE = "profi"


def slugify(s: str) -> str:
    """Преобразовать строку в slug"""
    s = s.lower().strip()
    s = s.replace("ё", "е")
    # Транслитерация
    tr = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l',
        'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's',
        'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
        'ю': 'yu', 'я': 'ya', ' ': '-', '_': '-'
    }
    result = ""
    for c in s:
        if c in tr:
            result += tr[c]
        elif c.isalnum() or c == '-':
            result += c
    return re.sub(r'-+', '-', result).strip('-')


def canon(s: str) -> str:
    """Канонизация строки для сравнения"""
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
    """Найти строку заголовка (содержит 'наимен')"""
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
    """Парсинг цены из строки"""
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


def stock_to_indicator(stock_val) -> tuple:
    """Преобразовать значение остатка в (in_stock: bool, quantity: str, stock_indicator: str)"""
    if stock_val is None:
        return (False, None, None)

    if isinstance(stock_val, (int, float)):
        qty = int(stock_val)
        if qty <= 0:
            return (False, "0", "none")
        elif qty <= 2:
            return (True, str(qty), "low")
        elif qty <= 10:
            return (True, str(qty), "medium")
        else:
            return (True, str(qty), "high")

    s = str(stock_val).strip()
    if not s:
        return (False, None, None)

    # Подсчёт звёзд или плюсов
    if "+" in s:
        count = s.count("+")
        indicators = {1: "low", 2: "medium", 3: "medium", 4: "high", 5: "high"}
        return (True, f"{count}+", indicators.get(count, "medium"))
    elif "*" in s:
        count = s.count("*")
        indicators = {1: "low", 2: "medium", 3: "medium", 4: "high", 5: "high"}
        return (True, f"{count}*", indicators.get(count, "medium"))

    return (True, s, "medium")


def download_file(url: str) -> str:
    """Скачать файл во временную директорию"""
    print(f"[INFO] Downloading {url}...")

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()

    fd, path = tempfile.mkstemp(suffix=".xls")
    with os.fdopen(fd, 'wb') as f:
        f.write(resp.content)

    print(f"[INFO] Downloaded to {path} ({len(resp.content)} bytes)")
    return path


def parse_excel(file_path: str, city: str, outlet_name: str, outlet_code: str) -> list:
    """Парсинг Excel файла"""
    print(f"[INFO] Parsing {file_path}...")

    wb = xlrd.open_workbook(file_path, formatting_info=True)
    sheet = wb.sheet_by_index(0)

    print(f"[INFO] Sheet: {sheet.name}, rows: {sheet.nrows}, cols: {sheet.ncols}")

    header_row = find_header_row(sheet)
    if header_row is None:
        raise ValueError("Header row with 'Наименование' not found")
    print(f"[INFO] Header row: {header_row}")

    headers_map = {}
    for c in range(sheet.ncols):
        v = sheet.cell_value(header_row, c)
        if isinstance(v, str) and v.strip():
            headers_map[v.strip()] = c
    canon_map = {canon(k): v for k, v in headers_map.items()}

    targets = {
        "name": ["наимен", "наименование", "name"],
        "article": ["артикул", "код", "code", "sku"],
        "barcode": ["штрихкод", "штрих-код", "barcode", "ean"],
        "price_rub": ["цена", "розница", "retail", "price"],
        "stock": ["количество", "наличие", "остаток", "stock", "qty"],
        "note": ["примечание", "комментарий", "comment", "note"],
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

    print(f"[INFO] Resolved columns: {resolved}")

    empty_check_cols = [name_col] + [c for c in resolved.values() if c is not None]

    current_brand = current_model = current_type = None
    products = []

    for r in range(header_row + 1, sheet.nrows):
        if row_empty_fast(sheet, r, empty_check_cols):
            print(f"[INFO] Stop at row {r} (empty)")
            break

        name_val = sheet.cell_value(r, name_col)
        if not name_val or not str(name_val).strip():
            continue
        name_val = str(name_val).strip()

        fsize = get_font_size(wb, sheet, r, name_col)

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
            article = clean_value(sheet.cell_value(r, resolved["article"])) if resolved["article"] is not None else None
            barcode = clean_value(sheet.cell_value(r, resolved["barcode"])) if resolved["barcode"] is not None else None
            price = parse_price(sheet.cell_value(r, resolved["price_rub"])) if resolved["price_rub"] is not None else None

            stock_val = clean_value(sheet.cell_value(r, resolved["stock"])) if resolved["stock"] is not None else None
            in_stock, quantity, stock_indicator = stock_to_indicator(stock_val)

            # Формируем category_path из иерархии
            category_path = []
            if current_brand:
                category_path.append(current_brand)
            if current_model:
                category_path.append(current_model)
            if current_type:
                category_path.append(current_type)

            # Определяем бренд для записи
            brand = None
            if current_brand:
                # Очищаем от номеров типа "1. ЗАПЧАСТИ ДЛЯ APPLE"
                brand_clean = re.sub(r'^\d+\.\s*', '', current_brand).strip()
                # Извлекаем бренд устройства
                if 'APPLE' in brand_clean.upper():
                    brand = 'Apple'
                elif 'SAMSUNG' in brand_clean.upper():
                    brand = 'Samsung'
                elif 'XIAOMI' in brand_clean.upper():
                    brand = 'Xiaomi'
                elif 'HUAWEI' in brand_clean.upper():
                    brand = 'Huawei'
                elif 'HONOR' in brand_clean.upper():
                    brand = 'Honor'

            # Определяем part_type
            part_type = current_type if current_type else None

            products.append({
                "article": str(article) if article else None,
                "barcode": str(barcode) if barcode else None,
                "name": name_val,
                "part_type": part_type,
                "brand": brand,
                "models": None,  # Будет заполнено позже через SQL
                "price": price,
                "in_stock": in_stock,
                "quantity": quantity,
                "stock_indicator": stock_indicator,
                "shop": SHOP_CODE,
                "region_name": city,
                "category_path": category_path if category_path else None,
                "outlet_code": outlet_code,
                "outlet_name": outlet_name,
            })

        if len(products) % 1000 == 0:
            print(f"[PROGRESS] {len(products)} products...")

    print(f"[INFO] Parsed {len(products)} products")
    return products


def get_or_create_outlet(conn, city: str, outlet_name: str) -> str:
    """Получить или создать outlet, вернуть code"""
    outlet_code = f"{SHOP_CODE}-{slugify(city)}-{slugify(outlet_name)}"

    with conn.cursor() as cur:
        # Проверяем существование
        cur.execute("SELECT code FROM zip_outlets WHERE code = %s", (outlet_code,))
        row = cur.fetchone()
        if row:
            return row[0]

        # Получаем shop_id
        cur.execute("SELECT id FROM zip_shops WHERE code = %s", (SHOP_CODE,))
        shop_row = cur.fetchone()
        if not shop_row:
            # Создаём магазин
            cur.execute("""
                INSERT INTO zip_shops (code, name, website, shop_type, is_active)
                VALUES (%s, %s, %s, %s, true)
                RETURNING id
            """, (SHOP_CODE, 'Профи', 'https://siriust.ru', 'wholesale'))
            shop_row = cur.fetchone()
        shop_id = shop_row[0]

        # Получаем или создаём город
        city_code = slugify(city)
        cur.execute("SELECT id FROM zip_cities WHERE code = %s", (city_code,))
        city_row = cur.fetchone()
        if not city_row:
            cur.execute("""
                INSERT INTO zip_cities (code, name, is_active)
                VALUES (%s, %s, true)
                RETURNING id
            """, (city_code, city))
            city_row = cur.fetchone()
        city_id = city_row[0]

        # Создаём outlet
        cur.execute("""
            INSERT INTO zip_outlets (shop_id, city_id, code, name, stock_mode, is_active)
            VALUES (%s, %s, %s, %s, 'parse', true)
            ON CONFLICT (code) DO NOTHING
            RETURNING code
        """, (shop_id, city_id, outlet_code, outlet_name))

        conn.commit()
        return outlet_code


def save_to_db(products: list, conn, truncate_outlet: str = None):
    """Сохранить в БД zip_prices"""
    if not products:
        print("[INFO] No products to save")
        return

    with conn.cursor() as cur:
        if truncate_outlet:
            # Удаляем старые записи только для этого outlet
            print(f"[INFO] Deleting old records for outlet: {truncate_outlet}")
            cur.execute("""
                DELETE FROM zip_prices
                WHERE shop = %s AND category_path[1] IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM zip_outlets o
                    WHERE o.code = %s
                  )
            """, (SHOP_CODE, truncate_outlet))

        print(f"[INFO] Inserting {len(products)} rows into zip_prices...")

        # Подготавливаем данные для вставки
        values = []
        for p in products:
            values.append((
                p["article"],
                p["barcode"],
                p["name"],
                p["part_type"],
                p["brand"],
                p["price"],
                p["in_stock"],
                p["quantity"],
                p["stock_indicator"],
                SHOP_CODE,
                p["region_name"],
                p["category_path"],
            ))

        sql = """
            INSERT INTO zip_prices
            (article, barcode, name, part_type, brand, price, in_stock, quantity, stock_indicator, shop, region_name, category_path)
            VALUES %s
        """
        execute_values(cur, sql, values, page_size=1000)
        conn.commit()
        print(f"[OK] Inserted {len(products)} rows")


def parse_single(url: str, city: str, outlet_name: str, conn) -> int:
    """Парсинг одного прайс-листа"""
    # Получаем или создаём outlet
    outlet_code = get_or_create_outlet(conn, city, outlet_name)

    file_path = download_file(url)
    try:
        products = parse_excel(file_path, city, outlet_name, outlet_code)
        save_to_db(products, conn, truncate_outlet=outlet_code)
        return len(products)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def parse_all(conn):
    """Парсинг всех прайс-листов"""
    if not PRICE_LISTS:
        print("[ERROR] No price lists configured", file=sys.stderr)
        return 1

    total_products = 0
    failed = []

    for i, pl in enumerate(PRICE_LISTS, 1):
        url = pl["url"]
        city = pl["city"]
        shop = pl["shop"]

        print(f"\n[{i}/{len(PRICE_LISTS)}] {city} - {shop}")
        print(f"    URL: {url}")

        try:
            count = parse_single(url, city, shop, conn)
            total_products += count
            print(f"    OK: {count} products")
        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr)
            failed.append({"url": url, "city": city, "shop": shop, "error": str(e)})

    print(f"\n[SUMMARY] Total products: {total_products}")
    print(f"[SUMMARY] Failed: {len(failed)}")

    if failed:
        print("\nFailed price lists:")
        for f in failed:
            print(f"  - {f['city']} / {f['shop']}: {f['error']}")

    return 0 if not failed else 1


def main():
    parser = argparse.ArgumentParser(description="Profi price list parser (zip_* integration)")
    parser.add_argument("--url", help="URL of specific price list")
    parser.add_argument("--city", help="City name")
    parser.add_argument("--outlet", help="Outlet/shop name")
    parser.add_argument("--all", action="store_true", help="Parse all configured price lists")

    args = parser.parse_args()

    start = time.time()

    try:
        print(f"[INFO] Connecting to database...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        try:
            if args.all:
                result = parse_all(conn)
            elif args.url:
                info = get_info_by_url(args.url)
                city = args.city or info.get("city", "Неизвестно")
                outlet = args.outlet or info.get("shop", "Профи")

                parse_single(args.url, city, outlet, conn)
                result = 0
            else:
                # По умолчанию - Астрахань
                url = "https://www.siriust.ru/club/price/Astraxan.xls"
                parse_single(url, "Астрахань", "Профи", conn)
                result = 0

            print(f"\n[OK] Total time: {time.time() - start:.2f}s")
            return result

        finally:
            conn.close()

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
