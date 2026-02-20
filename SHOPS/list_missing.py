# -*- coding: utf-8 -*-
import psycopg2
import sys
sys.stdout.reconfigure(encoding='utf-8')

DATABASES = [
    'db_greenspark', 'db_taggsm', 'db_memstech', 'db_liberti',
    'db_05gsm', 'db_signal23', 'db_profi', 'db_moba',
    'db_orizhka', 'db_lcdstock', 'db_moysklad'
]

def get_conn(db):
    return psycopg2.connect(
        host='85.198.98.104',
        port=5433,
        dbname=db,
        user='postgres',
        password='Mi31415926pSss!'
    )

all_missing = set()

for db in DATABASES:
    try:
        conn = get_conn(db)
        cur = conn.cursor()
        cur.execute("SELECT name FROM cities WHERE region_id IS NULL")
        missing = [r[0] for r in cur.fetchall()]
        if missing:
            all_missing.update(missing)
        conn.close()
    except Exception as e:
        print(f'{db}: ERROR - {e}')

print('Города без региона:')
for city in sorted(all_missing):
    print(f"    '{city}': '',")
