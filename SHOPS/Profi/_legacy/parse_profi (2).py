#!/usr/bin/env python3
"""
Парсер Profi - загрузка в profi_* таблицы
Парсит XLS прайс-листы с siriust.ru

Использование:
  python3 parse_profi.py              # Один прайс (тест)
  python3 parse_profi.py --all        # Все прайсы
  python3 parse_profi.py --process    # Только обработка staging
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

# Транслитерация
TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}

def transliterate(text: str) -> str:
    result = []
    for c in text.lower():
        if c in TRANSLIT:
            result.append(TRANSLIT[c])
        elif c.isalnum() or c in '-_':
            result.append(c)
        elif c in ' .':
            result.append('-')
    return re.sub(r'-+', '-', ''.join(result)).strip('-')

def generate_outlet_code(city: str, shop: str = None) -> str:
    """Генерация уникального outlet_code из города и магазина"""
    base = f"profi-{transliterate(city)}"

    if shop:
        # Проверяем номер точки
        match = re.search(r'точка\s*(\d+)|(\d+)\s*$', shop, re.IGNORECASE)
        if match:
            num = match.group(1) or match.group(2)
            base = f"{base}-{num}"
        else:
            # Для уникальных названий магазинов добавляем краткий код
            shop_lower = shop.lower()
            if "оптов" in shop_lower:
                base = f"{base}-opt"
            elif "савел" in shop_lower:
                base = f"{base}-savelovo"
            elif "митин" in shop_lower:
                base = f"{base}-mitino"
            elif "южн" in shop_lower:
                base = f"{base}-yuzhny"
            elif shop != f"Профи {city}":
                # Транслитерируем первое слово названия
                shop_code = transliterate(shop.split()[0][:10])
                if shop_code and shop_code != transliterate(city):
                    base = f"{base}-{shop_code}"

    return base

# БД - отдельная база для Profi
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", 5433))
DB_NAME = os.environ.get("DB_NAME", "db_profi")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mi31415926pSss!")

def get_db():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def ensure_outlets(price_lists: list):
    """Создать отсутствующие outlet'ы"""
    if not price_lists:
        return

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM outlets")
            existing = {r[0] for r in cur.fetchall()}

            new_outlets = []
            for pl in price_lists:
                code = pl.get("outlet_code") or generate_outlet_code(pl["city"], pl.get("shop"))
                pl["outlet_code"] = code
                if code not in existing:
                    new_outlets.append({
                        "code": code,
                        "city": pl["city"],
                        "name": pl.get("shop") or f"Профи {pl['city']}"
                    })
                    existing.add(code)

            if new_outlets:
                print(f"[INFO] Creating {len(new_outlets)} outlets...")
                for o in new_outlets:
                    cur.execute("""
                        INSERT INTO outlets (code, city, name)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                    """, (o["code"], o["city"], o["name"]))
                    print(f"  + {o['code']} ({o['city']})")
                conn.commit()
    finally:
        conn.close()


def get_font_size(wb, sheet, row, col):
    try:
        xf = wb.xf_list[sheet.cell_xf_index(row, col)]
        return wb.font_list[xf.font_index].height / 20
    except:
        return None


def find_header(sheet):
    for r in range(min(sheet.nrows, 50)):
        for c in range(min(sheet.ncols, 50)):
            v = sheet.cell_value(r, c)
            if isinstance(v, str) and "наимен" in v.lower():
                return r
    return None


def clean_val(v):
    if v is None or v == "":
        return None
    if isinstance(v, float):
        return int(v) if v == int(v) else v
    return str(v).strip() or None


def parse_price(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("руб.", "").replace("руб", "").replace(" ", "").replace(",", ".").strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def download(url: str) -> str:
    print(f"[INFO] Downloading {url}...")
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=".xls")
    with os.fdopen(fd, 'wb') as f:
        f.write(resp.content)
    print(f"[INFO] Downloaded {len(resp.content)} bytes")
    return path


def parse_xls(path: str, outlet_code: str) -> list:
    """Парсинг XLS файла"""
    print(f"[INFO] Parsing for {outlet_code}...")

    wb = xlrd.open_workbook(path, formatting_info=True)
    sheet = wb.sheet_by_index(0)

    header_row = find_header(sheet)
    if header_row is None:
        raise ValueError("Header not found")

    # Маппинг колонок
    headers = {}
    for c in range(sheet.ncols):
        v = sheet.cell_value(header_row, c)
        if isinstance(v, str) and v.strip():
            headers[v.strip().lower()] = c

    def find_col(*keys):
        for k in keys:
            for h, c in headers.items():
                if k in h:
                    return c
        return None

    name_col = find_col("наимен")
    article_col = find_col("артикул", "код")
    barcode_col = find_col("штрих", "barcode")
    price_col = find_col("цена", "розница", "price")
    stock_col = find_col("количество", "наличие", "остаток")

    if name_col is None:
        raise ValueError("Name column not found")

    # Парсинг
    brand = model = part_type = None
    products = []

    for r in range(header_row + 1, sheet.nrows):
        name_val = sheet.cell_value(r, name_col)
        if not name_val or not str(name_val).strip():
            continue
        name_val = str(name_val).strip()

        fsize = get_font_size(wb, sheet, r, name_col)

        # Иерархия по шрифту
        if fsize and fsize >= 10.5:
            brand = name_val
            model = part_type = None
            continue
        elif fsize and 9.5 <= fsize < 10.5:
            model = name_val
            part_type = None
            continue
        elif fsize and 8.5 <= fsize < 9.5:
            part_type = name_val
            continue

        # Товар
        article = clean_val(sheet.cell_value(r, article_col)) if article_col else None
        barcode = clean_val(sheet.cell_value(r, barcode_col)) if barcode_col else None
        price = parse_price(sheet.cell_value(r, price_col)) if price_col else None

        stock_stars = None
        in_stock = False
        if stock_col:
            sv = clean_val(sheet.cell_value(r, stock_col))
            if sv:
                if isinstance(sv, (int, float)):
                    stock_stars = min(int(sv), 5) if sv <= 5 else 5
                    in_stock = sv > 0
                elif "+" in str(sv) or "*" in str(sv):
                    stock_stars = max(str(sv).count("+"), str(sv).count("*"))
                    in_stock = stock_stars > 0

        products.append({
            "outlet_code": outlet_code,
            "name": name_val,
            "article": str(article) if article else None,
            "barcode": str(barcode) if barcode else None,
            "brand_raw": brand,
            "model_raw": model,
            "part_type_raw": part_type,
            "price": price,
            "stock_stars": stock_stars,
            "in_stock": in_stock,
        })

        if len(products) % 1000 == 0:
            print(f"[PROGRESS] {len(products)} products...")

    print(f"[INFO] Parsed {len(products)} products")
    return products


def save_staging(products: list):
    """Сохранить в staging"""
    if not products:
        return

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE staging")

            sql = """
                INSERT INTO staging
                (outlet_code, name, article, barcode, brand_raw, model_raw, part_type_raw, price, stock_level, in_stock)
                VALUES %s
            """
            values = [
                (p["outlet_code"], p["name"], p["article"], p["barcode"],
                 p["brand_raw"], p["model_raw"], p["part_type_raw"], p["price"], p["stock_stars"], p["in_stock"])
                for p in products
            ]
            execute_values(cur, sql, values, page_size=1000)
            conn.commit()
            print(f"[OK] Inserted {len(products)} rows to staging")
    finally:
        conn.close()


def process_staging():
    """Обработка staging -> nomenclature, current_prices"""
    print("\n[INFO] Processing staging...")

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # 1. UPSERT nomenclature
            print("[INFO] UPSERT nomenclature...")
            cur.execute("""
                INSERT INTO nomenclature (article, name, barcode, brand_raw, model_raw, part_type_raw)
                SELECT DISTINCT ON (article)
                    article, name, barcode, brand_raw, model_raw, part_type_raw
                FROM staging
                WHERE article IS NOT NULL AND TRIM(article) != ''
                ORDER BY article, loaded_at DESC
                ON CONFLICT (article) DO UPDATE SET
                    name = EXCLUDED.name,
                    barcode = COALESCE(EXCLUDED.barcode, nomenclature.barcode),
                    brand_raw = COALESCE(EXCLUDED.brand_raw, nomenclature.brand_raw),
                    model_raw = COALESCE(EXCLUDED.model_raw, nomenclature.model_raw),
                    part_type_raw = COALESCE(EXCLUDED.part_type_raw, nomenclature.part_type_raw),
                    updated_at = NOW()
            """)
            print(f"[OK] Upserted {cur.rowcount} nomenclature")

            # 2. UPSERT current_prices (используем DISTINCT ON для избежания дубликатов)
            print("[INFO] UPSERT current_prices...")
            cur.execute("""
                INSERT INTO current_prices (nomenclature_id, outlet_id, price, stock_stars, in_stock)
                SELECT DISTINCT ON (n.id, o.id)
                    n.id,
                    o.id,
                    s.price,
                    s.stock_level,
                    COALESCE(s.in_stock, s.stock_level > 0)
                FROM staging s
                JOIN nomenclature n ON n.article = s.article
                JOIN outlets o ON o.code = s.outlet_code
                WHERE s.article IS NOT NULL
                ORDER BY n.id, o.id, s.loaded_at DESC
                ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
                    price = EXCLUDED.price,
                    stock_stars = EXCLUDED.stock_stars,
                    in_stock = EXCLUDED.in_stock,
                    updated_at = NOW()
            """)
            print(f"[OK] Upserted {cur.rowcount} prices")

            # 3. История цен
            print("[INFO] Saving price history...")
            cur.execute("""
                INSERT INTO price_history (nomenclature_id, outlet_id, price, stock_stars, recorded_date)
                SELECT nomenclature_id, outlet_id, price, stock_stars, CURRENT_DATE
                FROM current_prices
                ON CONFLICT (nomenclature_id, outlet_id, recorded_date)
                DO UPDATE SET price = EXCLUDED.price, stock_stars = EXCLUDED.stock_stars
            """)
            print(f"[OK] Saved {cur.rowcount} history records")

            conn.commit()

            # Статистика
            cur.execute("SELECT COUNT(*) FROM nomenclature")
            nom = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM current_prices")
            prices = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM current_prices WHERE in_stock")
            in_stock = cur.fetchone()[0]

            print(f"\n[SUMMARY]")
            print(f"  Nomenclature: {nom}")
            print(f"  Prices: {prices}")
            print(f"  In stock: {in_stock}")
    finally:
        conn.close()


def parse_single(url: str, outlet_code: str) -> list:
    path = download(url)
    try:
        return parse_xls(path, outlet_code)
    finally:
        if os.path.exists(path):
            os.remove(path)


def parse_all() -> tuple:
    """Парсинг всех прайсов"""
    print("\n[STEP 1] Fetching price lists...")
    price_lists = fetch_price_lists()

    if not price_lists:
        print("[ERROR] No price lists found")
        return [], []

    print(f"[INFO] Found {len(price_lists)} price lists")

    # Генерируем outlet_code
    for pl in price_lists:
        if "outlet_code" not in pl:
            pl["outlet_code"] = generate_outlet_code(pl["city"], pl.get("shop"))

    # Создаём outlet'ы
    print("\n[STEP 2] Ensuring outlets exist...")
    ensure_outlets(price_lists)

    # Парсим
    print("\n[STEP 3] Parsing...")
    all_products = []
    failed = []

    for i, pl in enumerate(price_lists, 1):
        url = pl["url"]
        outlet_code = pl["outlet_code"]

        print(f"\n[{i}/{len(price_lists)}] {pl['city']} - {pl.get('shop', 'N/A')}")
        print(f"    outlet: {outlet_code}")

        try:
            products = parse_single(url, outlet_code)
            all_products.extend(products)
            print(f"    OK: {len(products)} products")
        except Exception as e:
            print(f"    ERROR: {e}")
            failed.append({"url": url, "outlet_code": outlet_code, "error": str(e)})

    return all_products, failed


def main():
    parser = argparse.ArgumentParser(description="Profi parser")
    parser.add_argument("--all", action="store_true", help="Parse all price lists")
    parser.add_argument("--process", action="store_true", help="Only process staging")
    parser.add_argument("--no-process", action="store_true", help="Skip processing after parsing")
    args = parser.parse_args()

    start = time.time()

    try:
        if args.process:
            process_staging()
        elif args.all:
            products, failed = parse_all()

            print(f"\n[SUMMARY] Total: {len(products)}, Failed: {len(failed)}")
            for f in failed:
                print(f"  FAILED: {f['outlet_code']}: {f['error']}")

            if products:
                save_staging(products)
                if not args.no_process:
                    process_staging()
        else:
            # Тест - один прайс
            url = "https://www.siriust.ru/club/price/Astraxan.xls"
            ensure_outlets([{"city": "Астрахань", "shop": "Профи Астрахань", "outlet_code": "profi-astrakhan"}])
            products = parse_single(url, "profi-astrakhan")
            save_staging(products)
            if not args.no_process:
                process_staging()

        print(f"\n[OK] Done in {time.time() - start:.2f}s")
        return 0
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
