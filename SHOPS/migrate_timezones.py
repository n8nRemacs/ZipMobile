"""
Обновление таймзон в regions (захардкожено)
"""
import psycopg2

DATABASES = [
    'db_greenspark', 'db_taggsm', 'db_memstech', 'db_liberti',
    'db_05gsm', 'db_signal23', 'db_profi', 'db_moba',
    'db_orizhka', 'db_lcdstock', 'db_moysklad', 'db_zip'
]

# Маппинг регион -> таймзона (из update_timezones.sql)
REGION_TIMEZONE = {
    # Калининградское время (UTC+2)
    '39': 'Europe/Kaliningrad',

    # Московское время (UTC+3)
    '77': 'Europe/Moscow', '78': 'Europe/Moscow',
    '01': 'Europe/Moscow', '05': 'Europe/Moscow', '06': 'Europe/Moscow',
    '07': 'Europe/Moscow', '08': 'Europe/Moscow', '09': 'Europe/Moscow',
    '10': 'Europe/Moscow', '11': 'Europe/Moscow', '12': 'Europe/Moscow',
    '13': 'Europe/Moscow', '15': 'Europe/Moscow', '16': 'Europe/Moscow',
    '20': 'Europe/Moscow', '21': 'Europe/Moscow', '23': 'Europe/Moscow',
    '26': 'Europe/Moscow', '29': 'Europe/Moscow', '31': 'Europe/Moscow',
    '32': 'Europe/Moscow', '33': 'Europe/Moscow', '34': 'Europe/Moscow',
    '35': 'Europe/Moscow', '36': 'Europe/Moscow', '37': 'Europe/Moscow',
    '40': 'Europe/Moscow', '43': 'Europe/Moscow', '44': 'Europe/Moscow',
    '46': 'Europe/Moscow', '47': 'Europe/Moscow', '48': 'Europe/Moscow',
    '50': 'Europe/Moscow', '51': 'Europe/Moscow', '52': 'Europe/Moscow',
    '53': 'Europe/Moscow', '57': 'Europe/Moscow', '58': 'Europe/Moscow',
    '60': 'Europe/Moscow', '61': 'Europe/Moscow', '62': 'Europe/Moscow',
    '67': 'Europe/Moscow', '68': 'Europe/Moscow', '69': 'Europe/Moscow',
    '71': 'Europe/Moscow', '76': 'Europe/Moscow', '83': 'Europe/Moscow',
    '90': 'Europe/Moscow', '91': 'Europe/Moscow', '92': 'Europe/Moscow',
    '93': 'Europe/Moscow', '94': 'Europe/Moscow', '95': 'Europe/Moscow',

    # Самарское время (UTC+4)
    '18': 'Europe/Samara', '30': 'Europe/Samara',
    '63': 'Europe/Samara', '64': 'Europe/Samara', '73': 'Europe/Samara',

    # Екатеринбургское время (UTC+5)
    '02': 'Asia/Yekaterinburg', '45': 'Asia/Yekaterinburg',
    '56': 'Asia/Yekaterinburg', '59': 'Asia/Yekaterinburg',
    '66': 'Asia/Yekaterinburg', '72': 'Asia/Yekaterinburg',
    '74': 'Asia/Yekaterinburg', '86': 'Asia/Yekaterinburg',
    '89': 'Asia/Yekaterinburg',

    # Омское время (UTC+6)
    '55': 'Asia/Omsk',

    # Красноярское время (UTC+7)
    '04': 'Asia/Barnaul', '17': 'Asia/Krasnoyarsk',
    '19': 'Asia/Krasnoyarsk', '22': 'Asia/Barnaul',
    '24': 'Asia/Krasnoyarsk', '42': 'Asia/Krasnoyarsk',
    '54': 'Asia/Krasnoyarsk', '70': 'Asia/Krasnoyarsk',

    # Иркутское время (UTC+8)
    '03': 'Asia/Irkutsk', '38': 'Asia/Irkutsk',

    # Якутское время (UTC+9)
    '14': 'Asia/Yakutsk', '28': 'Asia/Yakutsk', '75': 'Asia/Yakutsk',

    # Владивостокское время (UTC+10)
    '25': 'Asia/Vladivostok', '27': 'Asia/Vladivostok',
    '65': 'Asia/Vladivostok', '79': 'Asia/Vladivostok',

    # Магаданское время (UTC+11)
    '49': 'Asia/Magadan', '87': 'Asia/Magadan',

    # Камчатское время (UTC+12)
    '41': 'Asia/Kamchatka',
}

# Дополнительные города
CITY_REGION_MAP_EXTRA = {
    'Ангарск': '38', 'Братск': '38', 'Березники': '59',
    'Сургут': '86', 'Нижневартовск': '86', 'Ноябрьск': '89',
    'Грозный': '20', 'Элиста': '08', 'Владикавказ': '15',
    'Нальчик': '07', 'Черкесск': '09', 'Назрань': '06',
    'Махачкала': '05', 'Миасс': '74', 'Магнитогорск': '74',
    'Златоуст': '74', 'Бердск': '54', 'Кемерово': '42',
    'Новокузнецк': '42', 'Бийск': '22', 'Благовещенск': '28',
    'Орёл': '57', 'Кострома': '44', 'Калуга': '40',
    'Великий Новгород': '53', 'Курган': '45', 'Симферополь': '91',
    'Чита': '75', 'Южно-Сахалинск': '65', 'Петропавловск-Камчатский': '41',
    'Якутск': '14', 'Находка': '25', 'Уссурийск': '25',
    'Владивосток': '25', 'Хабаровск': '27', 'Комсомольск-на-Амуре': '27',
    'Магадан': '49', 'Москва (мосб.)': '50', 'Москва (МОП)': '50',
    'Питер': '78', 'СПб': '78', 'Санкт Петербург': '78',
    'Ростов': '61', 'Н.Новгород': '52', 'Нижний': '52',
    'Махачкала': '05',
}

def get_conn(db):
    return psycopg2.connect(
        host='85.198.98.104',
        port=5433,
        dbname=db,
        user='postgres',
        password='Mi31415926pSss!'
    )

def update_timezones(db_name):
    """Обновление таймзон в regions"""
    print(f'\n=== {db_name} ===')
    conn = get_conn(db_name)
    cur = conn.cursor()

    # Обновляем timezone в regions
    for region_code, tz_code in REGION_TIMEZONE.items():
        cur.execute("""
            UPDATE regions SET timezone = %s WHERE code = %s
        """, (tz_code, region_code))
    conn.commit()

    # Статистика
    cur.execute("SELECT COUNT(*) FROM regions WHERE timezone IS NOT NULL")
    with_tz = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM regions")
    total = cur.fetchone()[0]
    print(f'  regions с timezone: {with_tz}/{total}')

    # Дополняем города
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables WHERE table_name = 'cities'
        )
    """)
    if cur.fetchone()[0]:
        for city_name, region_code in CITY_REGION_MAP_EXTRA.items():
            cur.execute("""
                UPDATE cities c SET region_id = r.id
                FROM regions r
                WHERE c.name = %s AND r.code = %s AND c.region_id IS NULL
            """, (city_name, region_code))
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM cities WHERE region_id IS NULL")
        no_region = cur.fetchone()[0]
        if no_region > 0:
            cur.execute("SELECT name FROM cities WHERE region_id IS NULL LIMIT 10")
            names = [r[0] for r in cur.fetchall()]
            print(f'  Города без региона ({no_region}): {names}')

    conn.close()


if __name__ == '__main__':
    print('Обновление таймзон')
    print('='*50)

    for db in DATABASES:
        try:
            update_timezones(db)
        except Exception as e:
            print(f'  ERROR: {e}')

    print('\nГотово!')
