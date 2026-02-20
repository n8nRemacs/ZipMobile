"""
Массовая загрузка спарсенных данных в profi_nomenclature_all
Использует COPY для быстрой вставки большого объёма данных
"""

import json
import sys
import io
sys.path.insert(0, '..')
from db_wrapper import get_db

def load_bulk(json_file='data/products.json'):
    """Загрузка данных из JSON в БД"""

    print(f'[+] Читаем {json_file}...')
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Берём ВСЕ товары (не только первые 100)
    # Нужно перечитать полный JSON
    print(f'[!] ВНИМАНИЕ: JSON содержит только первые 100 товаров!')
    print(f'[!] Для загрузки всех товаров нужно пересохранить JSON без ограничения')

    products = data.get('products', [])
    total = data.get('total', len(products))

    print(f'[+] Товаров в JSON: {len(products)}')
    print(f'[+] Всего спарсено: {total}')

    if len(products) < total:
        print(f'\n[ERROR] В JSON только {len(products)} из {total} товаров!')
        print(f'[ERROR] Нужно пересохранить JSON полностью')
        return

    conn = get_db()
    cur = conn.cursor()

    try:
        # Метод 1: Используем execute_batch для быстрой вставки
        from psycopg2.extras import execute_batch

        print(f'\n[+] Загрузка {len(products)} товаров...')

        # Подготавливаем данные
        values = []
        for p in products:
            article = p.get('article', '')
            if not article:
                continue

            values.append((
                article,
                p.get('barcode', ''),
                p.get('name', ''),
                p.get('brand', ''),
                p.get('model', ''),
                p.get('part_type', ''),
                p.get('category', ''),
                p.get('city', ''),
                p.get('shop', ''),
                p.get('outlet_code', ''),
                p.get('price', 0),
                p.get('in_stock', False)
            ))

        print(f'[+] Подготовлено {len(values)} записей для вставки')

        # Вставляем батчами по 500
        sql = """
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
                brand = EXCLUDED.brand,
                model = EXCLUDED.model,
                part_type = EXCLUDED.part_type,
                updated_at = NOW(),
                processed = false
        """

        execute_batch(cur, sql, values, page_size=500)
        conn.commit()

        print(f'\n[OK] Данные загружены!')

        # Статистика
        cur.execute('SELECT COUNT(*) FROM profi_nomenclature_all')
        total_db = cur.fetchone()[0]

        cur.execute('SELECT COUNT(*) FROM profi_nomenclature_all WHERE processed = false')
        unprocessed = cur.fetchone()[0]

        print(f'\n[OK] Итого в БД:')
        print(f'  Всего товаров: {total_db}')
        print(f'  Не обработаны: {unprocessed}')

    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    load_bulk()
