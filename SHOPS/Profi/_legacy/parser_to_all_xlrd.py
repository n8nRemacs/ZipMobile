"""
Парсер Profi - ЭТАП 1: Сбор СЫРЫХ данных (с xlrd)

Парсит .xls файлы напрямую через xlrd (без LibreOffice)
Сохраняет в profi_nomenclature_all БЕЗ нормализации.
"""

import json
import re
import os
import argparse
import httpx
import xlrd
from datetime import datetime
from typing import List, Dict, Optional

from config import DATA_DIR, PRODUCTS_CSV, PRODUCTS_JSON
from price_lists_config import PRICE_LISTS
from fetch_price_lists import fetch_price_lists

# === Конфигурация БД (Supabase) ===
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db


class ProfiParserXLRD:
    """Парсер .xls файлов через xlrd"""

    def __init__(self):
        self.products: List[Dict] = []
        self.outlets_parsed: List[Dict] = []
        self.errors: List[Dict] = []
        self.stats = {'total_parsed': 0}
        os.makedirs(DATA_DIR, exist_ok=True)

    def download_price_list(self, url: str) -> Optional[str]:
        """Скачивает прайс-лист"""
        try:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()

                # Сохраняем во временный файл
                import tempfile
                suffix = ".xls"
                fd, path = tempfile.mkstemp(suffix=suffix)
                os.write(fd, response.content)
                os.close(fd)
                return path
        except Exception as e:
            self.errors.append({
                "url": url,
                "error": str(e),
                "time": datetime.now().isoformat()
            })
            return None

    def parse_price(self, price_text) -> float:
        """Парсит цену"""
        if price_text is None or price_text == '':
            return 0.0
        price_str = str(price_text).replace(' ', '').replace(',', '.')
        try:
            return float(price_str)
        except:
            return 0.0

    def _canon(self, s: str) -> str:
        """Канонизация строки"""
        s = s.strip().lower().replace("ё", "е")
        return re.sub(r"[^a-z0-9а-я]+", "", s)

    def parse_xls_file(self, file_path: str, city: str, shop: str, outlet_code: str) -> List[Dict]:
        """Парсит .xls файл через xlrd"""
        products = []

        try:
            wb = xlrd.open_workbook(file_path, formatting_info=True)
            ws = wb.sheet_by_index(0)
        except Exception as e:
            self.errors.append({
                "file": file_path,
                "error": f"Failed to read XLS: {e}",
                "time": datetime.now().isoformat()
            })
            return []

        # Ищем строку с заголовками
        header_row = None
        for r in range(min(20, ws.nrows)):
            for c in range(min(ws.ncols, 50)):
                try:
                    val = ws.cell_value(r, c)
                    if isinstance(val, str) and "наимен" in val.lower():
                        header_row = r
                        break
                except:
                    pass
            if header_row is not None:
                break

        if header_row is None:
            self.errors.append({
                "file": file_path,
                "error": "Header row not found",
                "time": datetime.now().isoformat()
            })
            return []

        # Определяем колонки
        name_col = None
        article_col = None
        barcode_col = None
        price_col = None
        quantity_col = None

        for c in range(ws.ncols):
            try:
                val = ws.cell_value(header_row, c)
                if not isinstance(val, str):
                    continue
                val_canon = self._canon(val)

                if "наимен" in val_canon or "name" in val_canon:
                    name_col = c
                elif "артикул" in val_canon or "код" in val_canon or "sku" in val_canon:
                    article_col = c
                elif "штрих" in val_canon or "barcode" in val_canon:
                    barcode_col = c
                elif "цена" in val_canon or "price" in val_canon:
                    price_col = c
                elif "количество" in val_canon or "наличие" in val_canon or "остаток" in val_canon:
                    quantity_col = c
            except:
                pass

        if name_col is None:
            self.errors.append({
                "file": file_path,
                "error": "Name column not found",
                "time": datetime.now().isoformat()
            })
            return []

        # Парсим товары
        current_brand_raw = None
        current_model_raw = None
        current_part_type_raw = None

        # Функция для определения типа строки по шрифту
        def get_font_size(row, col):
            try:
                xf = wb.format_map[ws.cell_xf_index(row, col)]
                font = wb.font_list[xf.font_index]
                return font.height // 20  # конвертируем в points
            except:
                return None

        for r in range(header_row + 1, ws.nrows):
            try:
                name_val = ws.cell_value(r, name_col)
                if not name_val or not isinstance(name_val, str):
                    continue
                name_val = name_val.strip()
                if not name_val:
                    continue

                # Определяем тип строки по font-size
                font_size = get_font_size(r, name_col)

                # Эвристика для определения категорий (если font-size не работает)
                # Проверяем артикул - если пустой, это категория
                article_val = ""
                if article_col is not None:
                    try:
                        article_val = ws.cell_value(r, article_col)
                        if article_val:
                            article_val = str(article_val).strip()
                    except:
                        pass

                # Если артикула нет и это похоже на категорию
                if not article_val:
                    # Это категория - определяем уровень
                    if name_val.startswith("1.") or name_val.startswith("2.") or name_val.startswith("3."):
                        current_brand_raw = name_val
                        current_model_raw = None
                        current_part_type_raw = None
                        continue
                    elif "ЗАПЧАСТИ ДЛЯ" in name_val.upper():
                        current_model_raw = name_val
                        current_part_type_raw = None
                        continue
                    else:
                        # Может быть тип запчасти
                        current_part_type_raw = name_val
                        continue

                # Это товар - сохраняем
                self.stats['total_parsed'] += 1

                article = article_val

                barcode = ""
                if barcode_col is not None:
                    try:
                        barcode_val = ws.cell_value(r, barcode_col)
                        if barcode_val:
                            barcode = str(barcode_val).strip()
                    except:
                        pass

                price = 0.0
                if price_col is not None:
                    try:
                        price = self.parse_price(ws.cell_value(r, price_col))
                    except:
                        pass

                in_stock = False
                if quantity_col is not None:
                    try:
                        qty_val = ws.cell_value(r, quantity_col)
                        if qty_val:
                            qty_str = str(qty_val).strip().lower()
                            in_stock = qty_str == '*' or 'наличи' in qty_str or qty_str not in ('', '0', 'нет')
                    except:
                        pass

                # Категория для отладки
                category_parts = [p for p in [current_brand_raw, current_model_raw, current_part_type_raw] if p]
                category = " / ".join(category_parts) if category_parts else ""

                products.append({
                    'article': article,
                    'barcode': barcode,
                    'name': name_val,
                    'price': price,
                    'in_stock': in_stock,
                    'brand': current_brand_raw or "",
                    'model': current_model_raw or "",
                    'part_type': current_part_type_raw or "",
                    'category': category,
                    'city': city,
                    'shop': shop,
                    'outlet_code': outlet_code,
                })

            except Exception as e:
                # Пропускаем проблемные строки
                pass

        return products

    def parse_single_outlet(self, price_list: Dict) -> int:
        """Парсит один прайс-лист"""
        url = price_list.get("url", "")
        city = price_list.get("city", "")
        shop = price_list.get("shop", "")
        outlet_code = price_list.get("outlet_code", "")

        if not outlet_code:
            filename = url.split("/")[-1].replace(".xls", "").replace(".xlsx", "")
            outlet_code = f"profi-{filename.lower().replace(' ', '-')}"

        print(f"  [{city}] {shop}...")

        file_path = self.download_price_list(url)
        if not file_path:
            print(f"    [SKIP] Не удалось скачать")
            return 0

        try:
            products = self.parse_xls_file(file_path, city, shop, outlet_code)
            self.products.extend(products)

            self.outlets_parsed.append({
                "city": city,
                "shop": shop,
                "outlet_code": outlet_code,
                "products_count": len(products)
            })

            print(f"    +{len(products)} товаров")
            return len(products)
        finally:
            try:
                os.unlink(file_path)
            except:
                pass

    def parse_all_outlets(self, use_dynamic: bool = False):
        """Парсит все прайс-листы"""
        print(f"\n{'='*60}")
        print(f"Парсер Profi - ЭТАП 1: Сбор СЫРЫХ данных (xlrd)")
        print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        if use_dynamic:
            print("[Режим] Динамическая загрузка списка с сайта\n")
            price_lists = fetch_price_lists()
            for pl in price_lists:
                filename = pl["url"].split("/")[-1].replace(".xls", "").replace(".xlsx", "")
                pl["outlet_code"] = f"profi-{filename.lower().replace(' ', '-').replace('%20', '-')}"
        else:
            print(f"[Режим] Статический список ({len(PRICE_LISTS)} прайс-листов)\n")
            price_lists = PRICE_LISTS

        total_products = 0
        for pl in price_lists:
            count = self.parse_single_outlet(pl)
            total_products += count

        print(f"\n{'='*60}")
        print(f"ИТОГО: {total_products} товаров из {len(self.outlets_parsed)} торговых точек")
        print(f"Ошибок: {len(self.errors)}")
        print(f"{'='*60}")

    def save_to_json(self, filename: str = None):
        """Сохраняет товары в JSON"""
        filename = filename or PRODUCTS_JSON

        data = {
            "source": "siriust.ru (Profi RAW)",
            "date": datetime.now().isoformat(),
            "total": len(self.products),
            "stats": self.stats,
            "outlets": self.outlets_parsed,
            "products": self.products,  # ВСЕ товары
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Сохранено в {filename}")


def save_to_db_all(products: List[Dict], outlets: List[Dict]):
    """Сохранение в profi_nomenclature_all"""
    if not products:
        print("Нет товаров для сохранения")
        return

    conn = get_db()
    cur = conn.cursor()
    try:
        print(f"\n[INFO] Пропускаем создание outlets (требуется shop_id)")

        inserted = 0
        updated = 0

        for p in products:
            article = p.get("article", "")
            if not article:
                continue

            cur.execute("""
                INSERT INTO profi_nomenclature_all (
                    article, barcode, name,
                    brand, model, part_type, category,
                    city, shop, outlet_code,
                    price, in_stock,
                    updated_at, processed
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), false)
                ON CONFLICT (article) DO UPDATE SET
                    name = EXCLUDED.name,
                    barcode = EXCLUDED.barcode,
                    brand = EXCLUDED.brand,
                    model = EXCLUDED.model,
                    part_type = EXCLUDED.part_type,
                    category = EXCLUDED.category,
                    city = EXCLUDED.city,
                    shop = EXCLUDED.shop,
                    outlet_code = EXCLUDED.outlet_code,
                    price = EXCLUDED.price,
                    in_stock = EXCLUDED.in_stock,
                    updated_at = NOW(),
                    processed = false
                RETURNING (xmax = 0) as is_insert
            """, (
                article,
                p.get("barcode", ""),
                p.get("name", ""),
                p.get("brand", ""),
                p.get("model", ""),
                p.get("part_type", ""),
                p.get("category", ""),
                p.get("city", ""),
                p.get("shop", ""),
                p.get("outlet_code", ""),
                p.get("price", 0),
                p.get("in_stock", False)
            ))

            row = cur.fetchone()
            if row and row[0]:
                inserted += 1
            else:
                updated += 1

        conn.commit()

        print(f"\n{'='*60}")
        print(f"СОХРАНЕНО В profi_nomenclature_all:")
        print(f"  +{inserted} новых товаров")
        print(f"  ~{updated} обновлено")

        cur.execute("SELECT COUNT(*) FROM profi_nomenclature_all")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM profi_nomenclature_all WHERE processed = false")
        unprocessed = cur.fetchone()[0]
        print(f"\nИтого в БД: {total} товаров ({unprocessed} не обработаны)")
        print(f"{'='*60}")

    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Парсер Profi - ЭТАП 1 (xlrd)')
    parser.add_argument('--all', action='store_true', help='Полный парсинг всех городов')
    parser.add_argument('--dynamic', action='store_true', help='Динамический список')
    parser.add_argument('--no-db', action='store_true', help='Не сохранять в БД')
    parser.add_argument('--city', '-c', type=str, help='Парсить только указанный город')
    parser.add_argument('--test', action='store_true', help='Тестовый режим: 1 город')
    args = parser.parse_args()

    profi_parser = ProfiParserXLRD()

    if args.test:
        price_lists = [pl for pl in PRICE_LISTS if 'москва' in pl["city"].lower()][:1]
        if price_lists:
            print(f"Тестовый режим: парсим {price_lists[0]['city']}")
            profi_parser.parse_single_outlet(price_lists[0])
    elif args.city:
        city_lower = args.city.lower()
        price_lists = [pl for pl in PRICE_LISTS if pl["city"].lower() == city_lower]
        if not price_lists:
            print(f"Город '{args.city}' не найден")
            return
        print(f"Парсинг города: {args.city}")
        for pl in price_lists:
            profi_parser.parse_single_outlet(pl)
    else:
        profi_parser.parse_all_outlets(use_dynamic=args.dynamic)

    profi_parser.save_to_json()

    if not args.no_db and profi_parser.products:
        save_to_db_all(profi_parser.products, profi_parser.outlets_parsed)

    print("\nПарсинг завершён!")
    print(f"\nСледующий шаг: запустить n8n Upload.json для нормализации")


if __name__ == "__main__":
    main()
