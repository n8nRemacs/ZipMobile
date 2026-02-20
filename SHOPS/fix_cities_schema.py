"""
Исправление схемы cities в db_orizhka, db_lcdstock, db_zip
Добавляем region_id вместо region
"""
import psycopg2

DATABASES = ['db_orizhka', 'db_lcdstock', 'db_zip']

def get_conn(db):
    return psycopg2.connect(
        host='85.198.98.104',
        port=5433,
        dbname=db,
        user='postgres',
        password='Mi31415926pSss!'
    )

def fix_cities(db_name):
    print(f'\n=== {db_name} ===')
    conn = get_conn(db_name)
    cur = conn.cursor()

    # Проверяем структуру cities
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'cities'
    """)
    columns = [r[0] for r in cur.fetchall()]
    print(f'  Колонки cities: {columns}')

    # Добавляем region_id если его нет
    if 'region_id' not in columns:
        cur.execute("""
            ALTER TABLE cities ADD COLUMN region_id INTEGER REFERENCES regions(id)
        """)
        conn.commit()
        print('  + Добавлен region_id')

    # Миграция данных из region (если есть)
    if 'region' in columns:
        # Обновляем region_id на основе region (название региона)
        cur.execute("""
            UPDATE cities c
            SET region_id = r.id
            FROM regions r
            WHERE c.region = r.name AND c.region_id IS NULL
        """)
        updated = cur.rowcount
        conn.commit()
        print(f'  Обновлено {updated} записей по имени региона')

    # Проверяем outlets - нужно ли добавить city
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'outlets'
    """)
    outlet_columns = [r[0] for r in cur.fetchall()]
    print(f'  Колонки outlets: {outlet_columns}')

    # Добавляем city в outlets если нет
    if 'city' not in outlet_columns and 'outlets' in [r[0] for r in cur.execute("""
        SELECT table_name FROM information_schema.tables WHERE table_name = 'outlets'
    """) or []]:
        cur.execute("""
            ALTER TABLE outlets ADD COLUMN city VARCHAR(200)
        """)
        conn.commit()
        print('  + Добавлен city в outlets')

    # Добавляем city_id в outlets если нет
    if 'city_id' not in outlet_columns:
        try:
            cur.execute("""
                ALTER TABLE outlets ADD COLUMN city_id INTEGER REFERENCES cities(id)
            """)
            conn.commit()
            print('  + Добавлен city_id в outlets')
        except Exception as e:
            print(f'  city_id: {e}')

    conn.close()


if __name__ == '__main__':
    print('Исправление схемы cities')
    print('='*50)

    for db in DATABASES:
        try:
            fix_cities(db)
        except Exception as e:
            print(f'  ERROR: {e}')

    print('\nГотово!')
