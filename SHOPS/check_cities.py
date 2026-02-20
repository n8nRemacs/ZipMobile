import psycopg2

def get_conn(db):
    return psycopg2.connect(
        host='85.198.98.104',
        port=5433,
        dbname=db,
        user='postgres',
        password='Mi31415926pSss!'
    )

# 1. Структура cities в db_zip
print('=== cities в db_zip ===')
conn = get_conn('db_zip')
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'cities' ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f'{row[0]}: {row[1]}')

cur.execute('SELECT * FROM cities LIMIT 10')
print('\nПримеры:')
cols = [desc[0] for desc in cur.description]
print(cols)
for row in cur.fetchall():
    print(row)

cur.execute('SELECT COUNT(*) FROM cities')
print(f'\nВсего городов: {cur.fetchone()[0]}')

# Уникальные города из outlets парсеров
print('\n=== Уникальные города из всех парсеров ===')
all_cities = set()
for db in ['db_greenspark', 'db_taggsm', 'db_memstech', 'db_liberti', 'db_05gsm', 'db_signal23', 'db_profi', 'db_moba']:
    try:
        c = get_conn(db)
        cur2 = c.cursor()
        cur2.execute('SELECT DISTINCT city FROM outlets WHERE city IS NOT NULL')
        cities = [r[0] for r in cur2.fetchall()]
        all_cities.update(cities)
        print(f'{db}: {len(cities)} городов')
        c.close()
    except Exception as e:
        print(f'{db}: ERROR - {e}')

print(f'\nВсего уникальных городов: {len(all_cities)}')
print('Примеры:', sorted(list(all_cities))[:20])
conn.close()
