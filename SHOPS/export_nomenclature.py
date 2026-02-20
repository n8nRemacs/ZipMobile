"""
Выгрузка уникальной номенклатуры из всех БД парсеров в Excel файлы.
"""
import psycopg2
import pandas as pd
from pathlib import Path
from datetime import datetime

# Параметры подключения
DB_CONFIG = {
    'host': '85.198.98.104',
    'port': 5433,
    'user': 'postgres',
    'password': 'Mi31415926pSss!'
}

# Список баз данных парсеров
DATABASES = [
    ('db_greenspark', 'GreenSpark'),
    ('db_taggsm', 'Taggsm'),
    ('db_memstech', 'MemsTech'),
    ('db_liberti', 'Liberti'),
    ('db_05gsm', '05GSM'),
    ('db_signal23', 'Signal23'),
    ('db_profi', 'Profi'),
    ('db_moba', 'Moba'),
    ('db_orizhka', 'Orizhka'),
    ('db_lcdstock', 'LCD-Stock'),
    ('db_moysklad', 'MoySklad'),
]

# Папка для выгрузки
OUTPUT_DIR = Path(__file__).parent / 'exports'
OUTPUT_DIR.mkdir(exist_ok=True)


def export_nomenclature(dbname: str, shop_name: str) -> int:
    """Выгружает номенклатуру из БД в Excel файл."""
    try:
        conn = psycopg2.connect(dbname=dbname, **DB_CONFIG)

        # SQL запрос для выгрузки номенклатуры
        query = """
            SELECT
                id,
                article,
                barcode,
                name,
                product_id,
                brand,
                model,
                part_type,
                category,
                device_type,
                first_seen_at,
                updated_at
            FROM nomenclature
            ORDER BY id
        """

        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty:
            print(f"  [{shop_name}] Нет данных в таблице nomenclature")
            return 0

        # Сохраняем в Excel
        output_file = OUTPUT_DIR / f"nomenclature_{shop_name.lower().replace('-', '_')}.xlsx"
        df.to_excel(output_file, index=False, engine='openpyxl')

        print(f"  [{shop_name}] Выгружено {len(df):,} записей -> {output_file.name}")
        return len(df)

    except psycopg2.OperationalError as e:
        print(f"  [{shop_name}] Ошибка подключения к {dbname}: {e}")
        return 0
    except Exception as e:
        print(f"  [{shop_name}] Ошибка: {e}")
        return 0


def main():
    print(f"=" * 60)
    print(f"Выгрузка номенклатуры из БД парсеров")
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"=" * 60)
    print()

    total_records = 0
    successful = 0

    for dbname, shop_name in DATABASES:
        count = export_nomenclature(dbname, shop_name)
        if count > 0:
            total_records += count
            successful += 1

    print()
    print(f"=" * 60)
    print(f"Итого: {successful}/{len(DATABASES)} магазинов, {total_records:,} записей")
    print(f"Файлы сохранены в: {OUTPUT_DIR}")
    print(f"=" * 60)


if __name__ == '__main__':
    main()
