# -*- coding: utf-8 -*-
"""
Финальный маппинг оставшихся городов
"""
import psycopg2

DATABASES = [
    'db_greenspark', 'db_taggsm', 'db_memstech', 'db_liberti',
    'db_05gsm', 'db_signal23', 'db_profi', 'db_moba',
    'db_orizhka', 'db_lcdstock', 'db_moysklad'
]

# Финальный маппинг
CITY_REGION_MAP = {
    'Биробиджан': '79',  # Еврейская АО
    'Буденновск': '26',  # Ставропольский край
    'Джанкой': '91',     # Крым
    'Димитровград': '73', # Ульяновская область
    'Донецк (ДНР)': '93', # ДНР
    'Донецк (Рост.)': '61', # Ростовская область
    'Дубна': '50',       # Московская область
    'Ейск': '23',        # Краснодарский край
    'Ессентуки': '26',   # Ставропольский край
    'Запорожье': '90',   # Запорожская область
    'Керчь': '91',       # Крым
    'Котлас': '29',      # Архангельская область
    'Луганск': '94',     # ЛНР
    'Мариуполь': '93',   # ДНР
    'Мелитополь': '90',  # Запорожская область
    'Орел': '57',        # Орловская область (без ё)
    'Орёл': '57',        # Орловская область (с ё)
    'Херсон': '95',      # Херсонская область
    # Интернет-магазины - не города, оставляем без региона
}

def get_conn(db):
    return psycopg2.connect(
        host='85.198.98.104',
        port=5433,
        dbname=db,
        user='postgres',
        password='Mi31415926pSss!'
    )

def fix_cities(db_name):
    conn = get_conn(db_name)
    cur = conn.cursor()

    updated = 0
    for city_name, region_code in CITY_REGION_MAP.items():
        cur.execute("""
            UPDATE cities c SET region_id = r.id
            FROM regions r
            WHERE c.name = %s AND r.code = %s AND c.region_id IS NULL
        """, (city_name, region_code))
        updated += cur.rowcount

    conn.commit()

    # Проверяем
    cur.execute("SELECT name FROM cities WHERE region_id IS NULL")
    missing = [r[0] for r in cur.fetchall()]

    if updated > 0 or missing:
        print(f'{db_name}: +{updated}, осталось: {missing}')

    conn.close()


if __name__ == '__main__':
    print('Финальный маппинг городов')
    print('='*50)

    for db in DATABASES:
        try:
            fix_cities(db)
        except Exception as e:
            print(f'{db}: ERROR - {e}')

    print('\nГотово!')
