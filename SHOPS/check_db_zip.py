import psycopg2

conn = psycopg2.connect(
    host='85.198.98.104',
    port=5433,
    dbname='db_zip',
    user='postgres',
    password='Mi31415926pSss!'
)
cur = conn.cursor()

# Список всех таблиц
print('=== Таблицы в db_zip ===')
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' ORDER BY table_name
""")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = cur.fetchone()[0]
    print(f'  {t}: {cnt} записей')

# Проверяем есть ли regions
if 'regions' in tables:
    print('\n=== regions ===')
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'regions' ORDER BY ordinal_position
    """)
    for row in cur.fetchall():
        print(f'  {row[0]}: {row[1]}')

    cur.execute('SELECT * FROM regions LIMIT 10')
    print('\nПримеры:')
    for row in cur.fetchall():
        print(f'  {row}')

# Проверяем cities
if 'cities' in tables:
    print('\n=== cities ===')
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'cities' ORDER BY ordinal_position
    """)
    for row in cur.fetchall():
        print(f'  {row[0]}: {row[1]}')

    cur.execute('SELECT * FROM cities LIMIT 10')
    print('\nПримеры:')
    for row in cur.fetchall():
        print(f'  {row}')

conn.close()
