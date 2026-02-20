#!/usr/bin/env python3
"""
Парсер прайс-листов Profi (siriust.ru)
Скачивает XLS, парсит по размеру шрифта, пишет в БД

Использование:
  # Один прайс (по умолчанию Астрахань):
  python3 parse_profi.py

  # Конкретный прайс:
  python3 parse_profi.py --url "https://..." --city "Москва" --shop "Савеловский"

  # Все прайсы:
  python3 parse_profi.py --all

Иерархия по размеру шрифта:
  11pt (220 twips) = Бренд
  10pt (200 twips) = Модель
  9pt  (180 twips) = Тип запчасти
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

# Динамическое получение прайс-листов с сайта
# Old static import removed
    from price_lists_config import PRICE_LISTS, get_info_by_url
except ImportError:
    PRICE_LISTS = []
    def get_info_by_url(url):
        return {"city": "Неизвестно", "shop": "Неизвестно", "outlet_code": None}

# Old static import removed
    import xlrd
except ImportError:
    print("ERROR: pip install xlrd", file=sys.stderr)
    sys.exit(1)

# Настройки
DEFAULT_PRICE_URL = "https://www.siriust.ru/club/price/Astraxan.xls"
DEFAULT_CITY = "Астрахань"
DEFAULT_SHOP = "Профи Астрахань"
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "Mi31415926pSss!"
SELLER = "Профи"


def canon(s: str) -> str:
    """Канонизация строки для сравнения"""
    s = s.strip().lower().replace("ё", "е")
    return re.sub(r"[^a-z0-9а-я]+", "", s)


def get_font_size(wb, sheet, row, col):
    """Получить размер шрифта ячейки в points"""
    # Old static import removed
        xf_index = sheet.cell_xf_index(row, col)
        xf = wb.xf_list[xf_index]
        font = wb.font_list[xf.font_index]
        # height в twips (1/20 точки), делим на 20 для получения pt
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
        # Excel хранит числа как float
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
    # Убираем "руб.", пробелы, заменяем запятую на точку
    s = str(v).replace("руб.", "").replace("руб", "").replace(" ", "").replace(",", ".").strip()
    if not s:
        return None
    # Old static import removed
        return float(s)
    except ValueError:
        return None


def download_file(url: str) -> str:
    """Скачать файл во временную директорию"""
    print(f"[INFO] Downloading {url}...")

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()

    # Сохраняем во временный файл
    fd, path = tempfile.mkstemp(suffix=".xls")
    with os.fdopen(fd, 'wb') as f:
        f.write(resp.content)

    print(f"[INFO] Downloaded to {path} ({len(resp.content)} bytes)")
    return path


def parse_excel(file_path: str, city: str = None, shop: str = None) -> list:
    """Парсинг Excel файла"""
    print(f"[INFO] Parsing {file_path}...")
    print(f"[INFO] City: {city}, Shop: {shop}")

    # Открываем с поддержкой форматирования
    wb = xlrd.open_workbook(file_path, formatting_info=True)
    sheet = wb.sheet_by_index(0)

    print(f"[INFO] Sheet: {sheet.name}, rows: {sheet.nrows}, cols: {sheet.ncols}")

    # Ищем заголовок
    header_row = find_header_row(sheet)
    if header_row is None:
        raise ValueError("Header row with 'Наименование' not found")
    print(f"[INFO] Header row: {header_row}")

    # Карта заголовков
    headers_map = {}
    for c in range(sheet.ncols):
        v = sheet.cell_value(header_row, c)
        if isinstance(v, str) and v.strip():
            headers_map[v.strip()] = c
    canon_map = {canon(k): v for k, v in headers_map.items()}

    # Синонимы колонок
    targets = {
        "name": ["наимен", "наименование", "name"],
        "article": ["артикул", "код", "code", "sku"],
        "barcode": ["штрихкод", "штрих-код", "barcode", "ean"],
        "price_rub": ["цена", "розница", "retail", "price"],
        "stock": ["количество", "наличие", "остаток", "stock", "qty"],
        "note": ["примечание", "комментарий", "comment", "note"],
    }

    # Резолвим колонки
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

    # Парсим данные
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

        # Получаем размер шрифта
        fsize = get_font_size(wb, sheet, r, name_col)

        # Иерархия по размеру шрифта (в points)
        if fsize and fsize >= 10.5:  # ~11pt
            current_brand = name_val
            current_model = None
            current_type = None
            continue
        elif fsize and 9.5 <= fsize < 10.5:  # ~10pt
            current_model = name_val
            current_type = None
            continue
        elif fsize and 8.5 <= fsize < 9.5:  # ~9pt
            current_type = name_val
            continue
        else:
            # Это товар
            article = clean_value(sheet.cell_value(r, resolved["article"])) if resolved["article"] is not None else None
            barcode = clean_value(sheet.cell_value(r, resolved["barcode"])) if resolved["barcode"] is not None else None
            price = parse_price(sheet.cell_value(r, resolved["price_rub"])) if resolved["price_rub"] is not None else None
            note = clean_value(sheet.cell_value(r, resolved["note"])) if resolved["note"] is not None else None

            # Преобразуем stock в звёзды
            stock_stars = None
            stock_val = clean_value(sheet.cell_value(r, resolved["stock"])) if resolved["stock"] is not None else None
            if stock_val:
                if isinstance(stock_val, (int, float)):
                    stock_stars = min(int(stock_val), 5) if stock_val <= 5 else 5
                elif "+" in str(stock_val):
                    stock_stars = str(stock_val).count("+")
                elif "*" in str(stock_val):
                    stock_stars = str(stock_val).count("*")

            products.append((
                name_val,
                str(article) if article else None,
                str(barcode) if barcode else None,
                price,
                stock_stars,
                note,
                current_brand,
                current_model,
                current_type,
                SELLER,
                city,
                shop
            ))

        if len(products) % 1000 == 0:
            print(f"[PROGRESS] {len(products)} products...")

    print(f"[INFO] Parsed {len(products)} products")
    return products


def save_to_db(products: list, truncate: bool = True):
    """Сохранить в БД"""
    print(f"[INFO] Connecting to database...")

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

    # Old static import removed
        with conn.cursor() as cur:
            if truncate:
                # Очищаем таблицу
                print("[INFO] Truncating profi_price_for_update...")
                cur.execute("TRUNCATE TABLE public.profi_price_for_update RESTART IDENTITY")

            # Вставляем данные
            print(f"[INFO] Inserting {len(products)} rows...")
            sql = """
                INSERT INTO public.profi_price_for_update
                (name, article, barcode, price_rub, stock_stars, note, brand_attr, model_attr, part_type_attr, seller, city, shop)
                VALUES %s
            """
            execute_values(cur, sql, products, page_size=1000)

            conn.commit()
            print(f"[OK] Inserted {len(products)} rows")
    finally:
        conn.close()


def parse_single(url: str, city: str, shop: str) -> list:
    """Парсинг одного прайс-листа"""
    file_path = download_file(url)
    # Old static import removed
        products = parse_excel(file_path, city, shop)
        return products
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def parse_all() -> tuple:
    """Парсинг всех прайс-листов, возвращает (all_products, failed)"""
    if not PRICE_LISTS:
        print("[ERROR] No price lists configured", file=sys.stderr)
        return [], []

    all_products = []
    failed = []

    for i, pl in enumerate(PRICE_LISTS, 1):
        url = pl["url"]
        city = pl["city"]
        shop = pl["shop"]

        print(f"\n[{i}/{len(PRICE_LISTS)}] {city} - {shop}")
        print(f"    URL: {url}")

        # Old static import removed
            products = parse_single(url, city, shop)
            all_products.extend(products)
            print(f"    OK: {len(products)} products")
        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr)
            failed.append({"url": url, "city": city, "shop": shop, "error": str(e)})

    return all_products, failed


def main():
    parser = argparse.ArgumentParser(description="Profi price list parser")
    parser.add_argument("--url", help="URL of specific price list")
    parser.add_argument("--city", help="City name")
    parser.add_argument("--shop", help="Shop/outlet name")
    parser.add_argument("--all", action="store_true", help="Parse all configured price lists")

    args = parser.parse_args()

    start = time.time()

    # Old static import removed
        if args.all:
            # Парсим все прайс-листы
            all_products, failed = parse_all()

            print(f"\n[SUMMARY] Total products: {len(all_products)}")
            print(f"[SUMMARY] Failed: {len(failed)}")

            if failed:
                print("\nFailed price lists:")
                for f in failed:
                    print(f"  - {f['city']} / {f['shop']}: {f['error']}")

            if all_products:
                save_to_db(all_products, truncate=True)

            result = 0 if not failed else 1

        elif args.url:
            # Парсим конкретный URL
            info = get_info_by_url(args.url)
            city = args.city or info.get("city", DEFAULT_CITY)
            shop = args.shop or info.get("shop", DEFAULT_SHOP)

            products = parse_single(args.url, city, shop)
            save_to_db(products)
            result = 0

        else:
            # По умолчанию - Астрахань
            products = parse_single(DEFAULT_PRICE_URL, DEFAULT_CITY, DEFAULT_SHOP)
            save_to_db(products)
            result = 0

        print(f"\n[OK] Total time: {time.time() - start:.2f}s")
        return result

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
