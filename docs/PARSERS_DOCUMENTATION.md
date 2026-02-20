# Система парсеров ZipMobile

## Обзор архитектуры

```
┌──────────────────────────────────────────────────────────────────┐
│              ЦЕНТРАЛЬНАЯ БД (postgres:5432)                      │
│              Supabase на 85.198.98.104                           │
├──────────────────────────────────────────────────────────────────┤
│  СПРАВОЧНИКИ (общие для всех):                                   │
│  ├── zip_cities       (117 городов)                              │
│  ├── zip_shops        (6 магазинов)                              │
│  └── zip_outlets      (226 торговых точек)                       │
│                                                                  │
│  ГЛОБАЛЬНАЯ НОМЕНКЛАТУРА:                                        │
│  └── zip_nomenclature (article UNIQUE глобально)                 │
│                                                                  │
│  ЦЕНЫ И ОСТАТКИ:                                                 │
│  ├── zip_current_prices   (актуальные цены)                      │
│  └── zip_price_history    (история цен)                          │
└──────────────────────────────────────────────────────────────────┘
                              ▲
                              │ sync_nomenclature_to_zip.py
                              │
┌─────────────────────────────┴────────────────────────────────────┐
│              ЛОКАЛЬНЫЕ БД ПАРСЕРОВ (postgres:5433)               │
├──────────────────────────────────────────────────────────────────┤
│  db_memstech / db_05gsm / db_greenspark / db_taggsm / db_profi   │
│                                                                  │
│  Каждая содержит:                                                │
│  ├── staging         (временные данные парсинга)                 │
│  ├── nomenclature    (article UNIQUE внутри магазина)            │
│  ├── current_prices  (актуальные цены по точкам)                 │
│  └── price_history   (история изменения цен)                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Структура баз данных

### Центральная БД (port 5432)

#### zip_shops
```sql
CREATE TABLE zip_shops (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,      -- 'memstech', '05gsm', etc.
    name VARCHAR(255) NOT NULL,
    website VARCHAR(255),
    shop_type VARCHAR(50),                 -- 'retailer', 'wholesale'
    company_name VARCHAR(255),
    parser_enabled BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### zip_cities
```sql
CREATE TABLE zip_cities (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,     -- 'moskva', 'spb', 'ekaterinburg'
    name VARCHAR(255) NOT NULL,            -- 'Москва', 'Санкт-Петербург'
    region_name VARCHAR(255),              -- 'Московская область'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### zip_outlets
```sql
CREATE TABLE zip_outlets (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES zip_shops(id),
    city_id INTEGER REFERENCES zip_cities(id),
    code VARCHAR(100) UNIQUE NOT NULL,     -- 'memstech-ekb', 'taggsm-moskva'
    name VARCHAR(255) NOT NULL,
    address TEXT,
    stock_mode VARCHAR(20) DEFAULT 'api',  -- 'local' или 'api'
    is_active BOOLEAN DEFAULT true,
    api_config JSONB,                      -- {"subdomain": "ekb"} или {"fias_id": "..."}
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### zip_nomenclature
```sql
CREATE TABLE zip_nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) UNIQUE NOT NULL,  -- глобально уникальный артикул
    name TEXT,
    category_raw TEXT,                     -- исходная категория
    category_normalized TEXT,              -- нормализованная категория
    product_type VARCHAR(100),
    brand VARCHAR(100),
    model VARCHAR(255),
    source_shop_code VARCHAR(50),          -- откуда впервые получен
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Локальные БД парсеров (port 5433)

> **Важно:** С версии 3.1 таблицы имеют префикс `{shop}_` (например, `profi_nomenclature`, `greenspark_prices`).
> Таблица `price_history` удалена — история хранится в центральной БД.
> Поле `product_url` перенесено из `nomenclature` в `prices`.

#### {shop}_staging (временная таблица)
```sql
CREATE TABLE {shop}_staging (
    id SERIAL PRIMARY KEY,
    outlet_code VARCHAR(100) NOT NULL,     -- ссылка на zip_outlets.code
    article VARCHAR(100),
    name TEXT,
    price NUMERIC(12, 2),
    quantity INTEGER DEFAULT 0,
    category_raw TEXT,
    product_url TEXT,
    product_id TEXT,
    parsed_at TIMESTAMP DEFAULT NOW()
);
```

#### {shop}_nomenclature (локальная номенклатура)
```sql
CREATE TABLE {shop}_nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT,
    category_raw TEXT,
    product_id TEXT,
    first_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### {shop}_prices (цены и остатки)
```sql
CREATE TABLE {shop}_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER REFERENCES {shop}_nomenclature(id),
    outlet_id INTEGER REFERENCES outlets(id),
    price NUMERIC(12, 2),
    in_stock BOOLEAN DEFAULT FALSE,
    quantity INTEGER DEFAULT 0,
    product_url TEXT,              -- URL товара на сайте
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(nomenclature_id, outlet_id)
);
```

> **Флаг `--old-schema`:** Все парсеры поддерживают флаг `--old-schema` для использования старой схемы БД (без префиксов). По умолчанию используется новая схема.

---

## Парсеры

### 1. MemsTech (15 городов)

**Расположение:** `SHOPS/memstech/parser.py`

**Особенности:**
- Использует поддомены для выбора города (ekb.memstech.ru, spb.memstech.ru)
- Парсит HTML-каталог с пагинацией
- Глубокий обход категорий

**Города:**
| Код | Поддомен | Город |
|-----|----------|-------|
| moskva | memstech.ru | Москва |
| ekaterinburg | ekb | Екатеринбург |
| spb | spb | Санкт-Петербург |
| kazan | kzn | Казань |
| krasnodar | krd | Краснодар |
| perm | perm | Пермь |
| ... | ... | ... |

**Запуск:**
```bash
cd /opt/parsers/memstech

# Один город
python3 parser.py --city москва

# Все города
python3 parser.py --all-cities --all

# Без сохранения в БД
python3 parser.py --all-cities --no-db
```

**Конфигурация outlet_code:** `memstech-{subdomain}`
- memstech-memstech.ru (Москва)
- memstech-ekb (Екатеринбург)
- memstech-spb (СПб)

---

### 2. 05GSM (1 точка)

**Расположение:** `SHOPS/05GSM/parser.py`

**Особенности:**
- Единственный магазин в Москве
- Парсит HTML-каталог
- Простая структура категорий

**Запуск:**
```bash
cd /opt/parsers/05gsm
python3 parser.py --all
```

**outlet_code:** `05gsm-moskva`

---

### 3. GreenSpark (60 городов)

**Расположение:** `SHOPS/GreenSpark/parser.py`

**Особенности:**
- Использует cookies для выбора города (magazine, global_magazine)
- API-based парсинг через JSON endpoints
- Требует свежие cookies для обхода JS-защиты
- Двухэтапный парсинг: сбор товаров + допарсинг артикулов

**Получение cookies:**
```bash
cd /opt/parsers/greenspark
python3 get_cookies.py --headless
```

**Запуск:**
```bash
# Все города
python3 parser.py --all-cities --all

# Один город
python3 parser.py --city астрахань --all
```

**Конфигурация:** Использует ID города из green-spark.ru
```python
CITIES = {
    "abakan": {"id": 289687, "name": "Абакан"},
    "adler": {"id": 289829, "name": "Адлер"},
    ...
}
```

**outlet_code:** `greenspark-{city_code}`

---

### 4. Taggsm (88 городов)

**Расположение:** `SHOPS/Taggsm/parser.py`

**Особенности:**
- Использует FIAS ID для выбора города
- API-based парсинг
- Большое количество городов

**Запуск:**
```bash
cd /opt/parsers/taggsm
python3 parser.py --all
```

**Конфигурация:** Использует fias_id
```python
CITIES = {
    "moskva": {"fias_id": "0c5b2444-...", "name": "Москва"},
    ...
}
```

**outlet_code:** `taggsm-{city_code}`

---

### 5. Profi (40 точек)

**Расположение:** `SHOPS/Profi/parse_profi.py`

**Особенности:**
- Парсит Excel прайс-листы с сайта siriust.ru
- Быстрый парсинг (секунды вместо минут)
- Множество точек в одном городе

**Запуск:**
```bash
cd /opt/parsers/profi
python3 parse_profi.py --all
```

**outlet_code:** `profi-{city}-{outlet_name}`
- profi-moskva-opt
- profi-moskva-savelovo
- profi-spb-nevsky
- ...

---

### 6. Naffas (МойСклад)

**Расположение:** `SHOPS/moysklad/Naffas/`

**Особенности:**
- Интеграция с API МойСклад
- Один онлайн-магазин

**outlet_code:** `naffas-online`

---

## Принцип работы парсера

### Этап 1: Сбор данных

```
1. Парсер получает список категорий
2. Для каждой категории:
   - Получает список товаров (с пагинацией)
   - Извлекает: article, name, price, quantity, category
   - Сохраняет в staging таблицу
```

### Этап 2: Обработка staging

```
1. Создание/обновление nomenclature:
   - UPSERT по article
   - Сохранение name, category_raw

2. Обновление current_prices:
   - UPSERT по (nomenclature_id, outlet_code)
   - Сохранение price, quantity

3. Запись price_history:
   - INSERT с ON CONFLICT DO NOTHING
   - Одна запись в день на товар/точку
```

### Этап 3: Синхронизация в центральную БД

```bash
python3 scripts/sync_nomenclature_to_zip.py --shop memstech
```

Скрипт:
1. Читает nomenclature из локальной БД
2. UPSERT в zip_nomenclature центральной БД
3. Обновляет только пустые поля (не перезаписывает существующие данные)

---

## Запуск на сервере

### Структура на сервере

```
/opt/parsers/
├── memstech/
│   ├── parser.py
│   ├── parse.log
│   └── data/
├── 05gsm/
│   ├── parser.py
│   └── ...
├── greenspark/
│   ├── parser.py
│   ├── get_cookies.py
│   ├── cookies.json
│   └── ...
├── taggsm/
│   └── ...
└── profi/
    ├── parse_profi.py
    └── ...
```

### Запуск в фоне

```bash
# MemsTech
cd /opt/parsers/memstech
PYTHONUNBUFFERED=1 nohup python3 parser.py --all-cities --all > parse.log 2>&1 &

# 05GSM
cd /opt/parsers/05gsm
nohup python3 parser.py --all > parse.log 2>&1 &

# GreenSpark (сначала cookies!)
cd /opt/parsers/greenspark
python3 get_cookies.py --headless
PYTHONUNBUFFERED=1 nohup python3 parser.py --all-cities --all > parse.log 2>&1 &

# Taggsm
cd /opt/parsers/taggsm
nohup python3 parser.py --all > parse.log 2>&1 &

# Profi
cd /opt/parsers/profi
nohup python3 parse_profi.py --all > parse.log 2>&1 &
```

### Мониторинг

```bash
# Проверка процессов
ps aux | grep parser.py | grep -v grep

# Просмотр логов
tail -f /opt/parsers/memstech/parse.log
tail -f /opt/parsers/greenspark/parse.log

# Статус по городам
grep -E 'ГОРОД:|ИТОГО:' /opt/parsers/memstech/parse.log | tail -20

# Количество товаров в БД
docker exec supabase-db psql -U postgres -d postgres -c "
SELECT 'memstech' as shop, COUNT(*) FROM db_memstech.nomenclature
UNION ALL SELECT 'taggsm', COUNT(*) FROM db_taggsm.nomenclature
"
```

---

## Настройка outlets (Setup SQL)

При добавлении нового магазина нужно:

1. Создать файл `setup_{shop}_in_zip.sql`
2. Выполнить на центральной БД

### Пример: setup_memstech_in_zip.sql

```sql
-- 1. Магазин
INSERT INTO zip_shops (code, name, website, shop_type, parser_enabled, is_active)
VALUES ('memstech', 'MemsTech', 'https://memstech.ru', 'retailer', true, true)
ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name;

-- 2. Города
INSERT INTO zip_cities (code, name, region_name, is_active) VALUES
    ('moskva', 'Москва', 'Москва', true),
    ('ekaterinburg', 'Екатеринбург', 'Свердловская область', true),
    ...
ON CONFLICT (code) DO NOTHING;

-- 3. Торговые точки
WITH shop AS (SELECT id FROM zip_shops WHERE code = 'memstech'),
     cities AS (SELECT code, id FROM zip_cities)
INSERT INTO zip_outlets (shop_id, city_id, code, name, stock_mode, is_active, api_config)
SELECT s.id, c.id, v.outlet_code, v.outlet_name, 'api', true, v.api_config::jsonb
FROM shop s
CROSS JOIN (VALUES
    ('moskva', 'memstech-memstech.ru', 'MemsTech Москва', '{"subdomain": "memstech.ru"}'),
    ('ekaterinburg', 'memstech-ekb', 'MemsTech Екатеринбург', '{"subdomain": "ekb"}'),
    ...
) AS v(city_code, outlet_code, outlet_name, api_config)
JOIN cities c ON c.code = v.city_code
ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, api_config = EXCLUDED.api_config;
```

### Выполнение на сервере

```bash
ssh root@85.198.98.104
docker exec -i supabase-db psql -U postgres -d postgres < setup_memstech_in_zip.sql
```

---

## Подключение к БД

### Центральная БД (Supabase)

```python
import psycopg2

conn = psycopg2.connect(
    host="85.198.98.104",
    port=5432,
    dbname="postgres",
    user="postgres",
    password="Mi31415926pSss!",
    sslmode="require"
)
```

### Локальные БД парсеров

```python
conn = psycopg2.connect(
    host="85.198.98.104",
    port=5433,
    dbname="db_memstech",  # или db_05gsm, db_greenspark, etc.
    user="postgres",
    password="Mi31415926pSss!",
    sslmode="require"
)
```

---

## Статистика (на момент создания документа)

| Магазин | Товаров | Городов | Точек |
|---------|---------|---------|-------|
| MemsTech | ~11,500 | 15 | 15 |
| 05GSM | 3,379 | 1 | 1 |
| GreenSpark | ~8,500 | 60 | 60 |
| Taggsm | 22,776 | 88 | 88 |
| Profi | 13,654 | - | 40 |
| Naffas | - | 1 | 1 |

**Всего outlets в zip_outlets:** 226

---

## Troubleshooting

### GreenSpark: 0 товаров

**Причина:** Истекли cookies

**Решение:**
```bash
cd /opt/parsers/greenspark
python3 get_cookies.py --headless
# Перезапустить парсер
```

### MemsTech: column "product_id" does not exist

**Причина:** Отсутствует колонка в staging

**Решение:**
```python
python3 -c "
import psycopg2
conn = psycopg2.connect(host='localhost', port=5433, dbname='db_memstech',
                        user='postgres', password='Mi31415926pSss!', sslmode='require')
cur = conn.cursor()
cur.execute('ALTER TABLE staging ADD COLUMN IF NOT EXISTS product_id TEXT')
conn.commit()
"
```

### Парсер завис / не пишет в лог

**Причина:** Буферизация stdout

**Решение:**
```bash
PYTHONUNBUFFERED=1 python3 parser.py --all
```

### Долгий парсинг GreenSpark

**Причина:** Этап допарсинга артикулов (3000+ товаров × индивидуальный запрос)

**Ожидание:** ~1 час на город

---

## Файловая структура проекта

```
ZipMobile/
├── SHOPS/
│   ├── memstech/
│   │   ├── parser.py
│   │   └── setup_memstech_in_zip.sql
│   ├── 05GSM/
│   │   ├── parser.py
│   │   └── setup_05gsm_in_zip.sql
│   ├── GreenSpark/
│   │   ├── parser.py
│   │   ├── get_cookies.py
│   │   ├── cookies.json
│   │   ├── greenspark_cities.json
│   │   └── setup_greenspark_in_zip.sql
│   ├── Taggsm/
│   │   ├── parser.py
│   │   └── setup_taggsm_in_zip.sql
│   ├── Profi/
│   │   ├── parse_profi.py
│   │   ├── fetch_price_lists.py
│   │   └── setup_profi_in_zip.sql
│   └── moysklad/
│       └── Naffas/
│           ├── parser.py
│           └── setup_naffas_in_zip.sql
├── scripts/
│   └── sync_nomenclature_to_zip.py
├── docs/
│   └── PARSERS_DOCUMENTATION.md
└── cities_export.csv
```

---

## Будущие улучшения

1. **Автоматический запуск** через cron/systemd
2. **Алерты** при ошибках парсинга
3. **Дашборд** для мониторинга статуса
4. **Параллельный парсинг** городов
5. **Кэширование** cookies GreenSpark
6. **Retry логика** при сетевых ошибках
