# Архитектура парсеров ZipMobile

> **См. также:** [PARSER_GUIDE.md](./PARSER_GUIDE.md) — пошаговое руководство по созданию новых парсеров

## Общие принципы

### 1. Изоляция данных по источникам

Каждый магазин/источник имеет **отдельную базу данных**:
- `db_profi` — Профи (siriust.ru)
- `db_greenspark` — GreenSpark (green-spark.ru)
- `db_taggsm` — TAGGSM (taggsm.ru)
- `db_05gsm` — 05GSM (05gsm.ru)
- `db_moysklad` — МойСклад (Naffas и другие)
- `db_memstech` — MemsTech
- `db_zip` — Унифицированная поисковая база

### 2. Минимальный набор таблиц для каждого источника

В каждой базе данных (db_profi, db_greenspark, etc.) таблицы **без префикса**:

```
staging              # Сырые данные парсинга (временные)
outlets              # Торговые точки/города
nomenclature         # Уникальные товары по артикулу
unique_nomenclature  # Для нормализации и матчинга
current_prices       # Текущие цены по точкам
price_history        # История цен (опционально)
```

### 3. Поток данных

```
Источник (API/XLS/HTML)
         ↓
    staging              # Сырые данные, TRUNCATE перед парсингом
         ↓ UPSERT
    nomenclature         # Уникальные товары (по артикулу)
         ↓
    current_prices       # Текущие цены по точкам
         ↓
    price_history        # История изменения цен
         ↓ (после нормализации)
    unique_nomenclature  # Для матчинга с ZIP
         ↓
    db_zip.nomenclature  # Каноничная номенклатура (UUID)
```

---

## Структура таблиц

> **Примечание:** Все таблицы создаются в отдельной базе данных для каждого источника (db_profi, db_greenspark, etc.) **без префикса**.

### 1. staging

Временная таблица для сырых данных парсинга.

```sql
CREATE TABLE staging (
    id SERIAL PRIMARY KEY,
    outlet_code VARCHAR(50) NOT NULL,      -- Код точки

    -- Сырые данные
    name TEXT NOT NULL,                     -- Название товара
    article VARCHAR(100),                   -- Артикул/SKU
    barcode VARCHAR(50),                    -- Штрихкод

    -- Иерархия (сырая)
    brand_raw TEXT,                         -- Бренд (как в источнике)
    model_raw TEXT,                         -- Модель (как в источнике)
    part_type_raw TEXT,                     -- Тип запчасти (как в источнике)
    category_raw TEXT,                      -- Категория (как в источнике)

    -- Цены и остатки
    price NUMERIC(12,2),                    -- Цена
    price_wholesale NUMERIC(12,2),          -- Оптовая цена (если есть)
    stock_level INTEGER,                    -- Уровень остатка (1-5 звёзд)
    in_stock BOOLEAN DEFAULT FALSE,         -- Есть в наличии

    -- Метаданные
    url TEXT,                               -- URL товара
    loaded_at TIMESTAMP DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_staging_outlet ON staging(outlet_code);
CREATE INDEX idx_staging_article ON staging(article);
```

### 2. outlets

Торговые точки/города источника.

```sql
CREATE TABLE outlets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,      -- Уникальный код (например: profi-moskva-opt)
    city VARCHAR(100) NOT NULL,             -- Город
    name VARCHAR(255) NOT NULL,             -- Название точки
    address TEXT,                           -- Адрес
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 3. nomenclature

Уникальные товары источника (дедупликация по артикулу).

```sql
CREATE TABLE nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) NOT NULL UNIQUE,   -- Артикул (уникальный ключ)
    barcode VARCHAR(50),                    -- Штрихкод
    name TEXT NOT NULL,                     -- Название

    -- Сырые атрибуты (как пришли из источника)
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,

    -- Нормализованные атрибуты (заполняются после обработки)
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),

    first_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_nom_brand ON nomenclature(brand);
CREATE INDEX idx_nom_model ON nomenclature(model);
```

### 4. unique_nomenclature

Таблица для нормализации и матчинга с ZIP.

```sql
CREATE TABLE unique_nomenclature (
    id SERIAL PRIMARY KEY,

    -- Канонические данные
    canonical_name TEXT NOT NULL,
    canonical_article VARCHAR(100),

    -- Связь с источником
    nomenclature_id INTEGER REFERENCES nomenclature(id),

    -- Связь с ZIP (заполняется после матчинга)
    zip_nomenclature_id UUID,               -- FK на zip_nomenclature

    -- Нормализованные атрибуты
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),

    -- Статус
    is_processed BOOLEAN DEFAULT FALSE,
    confidence NUMERIC(3,2),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 5. current_prices

Текущие цены по точкам.

```sql
CREATE TABLE current_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL REFERENCES outlets(id) ON DELETE CASCADE,

    price NUMERIC(12,2),                    -- Розничная цена
    price_wholesale NUMERIC(12,2),          -- Оптовая цена
    stock_stars SMALLINT,                   -- Уровень остатка (1-5)
    in_stock BOOLEAN DEFAULT FALSE,

    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(nomenclature_id, outlet_id)
);

CREATE INDEX idx_prices_nom ON current_prices(nomenclature_id);
CREATE INDEX idx_prices_outlet ON current_prices(outlet_id);
```

### 6. price_history (опционально)

История цен для аналитики.

```sql
CREATE TABLE price_history (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL REFERENCES outlets(id) ON DELETE CASCADE,

    price NUMERIC(12,2),
    stock_stars SMALLINT,
    recorded_date DATE DEFAULT CURRENT_DATE,
    recorded_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(nomenclature_id, outlet_id, recorded_date)
);

CREATE INDEX idx_history_date ON price_history(recorded_date);
```

---

## Структура парсера

### Файлы

```
SHOPS/{Source}/
├── config.py           # Конфигурация (URL, параметры)
├── parser.py           # Основной парсер (или parse_{source}.py)
├── fetch_*.py          # Получение списка прайсов/категорий (если динамически)
└── cookies.json        # Cookies для авторизации (если нужно)
```

### Основные функции парсера

```python
# Конфигурация БД
DB_HOST = os.environ.get("DB_HOST", "85.198.98.104")
DB_PORT = int(os.environ.get("DB_PORT", 5433))
DB_NAME = os.environ.get("DB_NAME", "db_source")  # Отдельная БД для источника
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mi31415926pSss!")

# 1. Подключение к БД
def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, sslmode="require"
    )

# 2. Создание/обновление точек
def ensure_outlet():
    """Создать outlet если не существует"""
    pass

# 3. Парсинг данных
def parse_source() -> list:
    """Парсинг источника, возвращает список товаров"""
    # Для XLS: скачать файл, разобрать по колонкам
    # Для API: обойти категории, собрать товары
    # Для HTML: парсить страницы через BeautifulSoup
    pass

# 4. Сохранение в staging
def save_staging(products: list):
    """TRUNCATE и INSERT в staging"""
    pass

# 5. Обработка staging
def process_staging():
    """
    1. UPSERT в nomenclature
    2. UPSERT в current_prices
    3. INSERT в price_history
    4. Вывод статистики
    """
    pass

# 6. Главная функция
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--process", action="store_true")
    parser.add_argument("--no-db", action="store_true")
    args = parser.parse_args()

    if args.process:
        process_staging()
    else:
        products = parse_source()
        if not args.no_db:
            save_staging(products)
            if args.all:
                process_staging()
```

---

## Миграция в ZIP

После нормализации данных в `unique_nomenclature` (в базе источника):

```sql
-- Выполняется из базы db_zip

-- 1. Создаём записи в db_zip.nomenclature
INSERT INTO nomenclature (article, name, brand_id, part_type_id)
SELECT un.canonical_article, un.canonical_name, b.id, pt.id
FROM dblink('dbname=db_source', 'SELECT * FROM unique_nomenclature WHERE is_processed')
    AS un(id int, canonical_name text, canonical_article varchar, ...)
LEFT JOIN brands b ON b.normalized_name = un.brand
LEFT JOIN part_types pt ON pt.normalized_name = un.part_type
WHERE un.zip_nomenclature_id IS NULL;

-- 2. Обновляем связь в базе источника
-- (через dblink или отдельный скрипт)

-- 3. Переносим цены
INSERT INTO current_prices (nomenclature_id, outlet_id, price, in_stock)
SELECT
    sn.zip_nomenclature_id,
    o.id,
    cp.price,
    cp.in_stock
FROM source_nomenclature sn
JOIN outlets o ON o.source_id = sn.source_id AND o.source_outlet_id = cp.outlet_id
WHERE sn.zip_nomenclature_id IS NOT NULL
ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
    price = EXCLUDED.price,
    in_stock = EXCLUDED.in_stock,
    updated_at = NOW();
```

> **См. также:** [PARSER_GUIDE.md](./PARSER_GUIDE.md#интеграция-с-zip) — подробная инструкция по интеграции с ZIP

---

## Источники и базы данных

| Источник | База данных | Формат | Статус |
|----------|------------|--------|--------|
| Profi (siriust.ru) | `db_profi` | XLS | ✅ Готов |
| GreenSpark (green-spark.ru) | `db_greenspark` | API JSON | ✅ Готов |
| TAGGSM (taggsm.ru) | `db_taggsm` | HTML | ✅ Готов |
| 05GSM (05gsm.ru) | `db_05gsm` | HTML/Sitemap | ✅ Готов |
| MoySklad/Naffas | `db_moysklad` | API JSON | ✅ Готов |
| MemsTech | `db_memstech` | HTML | ✅ Готов |
| **ZIP (поисковая)** | `db_zip` | — | ✅ Таблицы созданы |

---

## Особенности источников

### Profi (siriust.ru)
- **База**: `db_profi`
- **Формат**: XLS файлы
- **Иерархия**: Определяется по размеру шрифта (11pt=бренд, 10pt=модель, 9pt=тип)
- **Точки**: 40+ городов, динамически обновляются с сайта
- **Цены**: Розничные

### GreenSpark (green-spark.ru)
- **База**: `db_greenspark`
- **Формат**: API JSON (`/local/api/catalog/products/`)
- **Иерархия**: Категории из breadcrumbs
- **Точки**: Один магазин (shop_id), несколько городов доставки
- **Цены**: Розничные + тариф "Грин 5"
- **Особенности**: Требует cookies для авторизации, артикул из URL картинки

### TAGGSM (taggsm.ru)
- **База**: `db_taggsm`
- **Формат**: HTML парсинг
- **Иерархия**: Категории из URL path
- **Точки**: Астрахань, Таганрог, Москва, Ростов-на-Дону
- **Цены**: Зависят от города (fias_id)
- **Особенности**: Наличие показывается по городам

### 05GSM (05gsm.ru)
- **База**: `db_05gsm`
- **Формат**: HTML парсинг через sitemap
- **Иерархия**: Категории из breadcrumbs
- **Точки**: Одна (онлайн-магазин)
- **Цены**: Розничные
- **Особенности**: Параллельный парсинг, кеширование sitemap

### MoySklad (b2b.moysklad.ru)
- **База**: `db_moysklad`
- **Формат**: API JSON (`/desktop-api/public/{CATALOG_ID}/products.json`)
- **Магазины внутри**: Naffas + другие
- **Точки**: По магазинам
- **Цены**: B2B цены
- **Особенности**: SaaS платформа, каждый магазин имеет свой CATALOG_ID

### MemsTech
- **База**: `db_memstech`
- **Формат**: HTML
- **Точки**: 15 городов
- **Особенности**: Использует поддомены для выбора города (ekb.memstech.ru, spb.memstech.ru)

---

## Команды запуска

```bash
# Profi
cd /opt/parsers/profi
python3 parse_profi.py --all          # Полный парсинг
python3 parse_profi.py --process      # Только обработка staging

# GreenSpark
cd /opt/parsers/greenspark
python3 parser.py --all               # Полный парсинг
python3 parser.py --no-db             # Только файлы (без БД)

# TAGGSM
cd /opt/parsers/taggsm
python3 parser.py --city "Москва" --all  # С фильтром по городу
python3 parser.py --all                   # Все города

# 05GSM
cd /opt/parsers/05gsm
python3 parser.py --parallel --all    # Параллельный парсинг
python3 parser.py --limit 100 --no-db # Тестовый запуск

# MoySklad (Naffas)
cd /opt/parsers/moysklad/naffas
python3 parser.py --all

# MemsTech
cd /opt/parsers/memstech
python3 parser.py --city москва         # Один город
python3 parser.py --all-cities --all    # Все города
```

---

## Мониторинг

```bash
# Подключение к конкретной БД
ssh root@85.198.98.104
docker exec -it supabase-db psql -U postgres -d db_profi
```

```sql
-- Статистика по источнику (выполнять в нужной БД)
SELECT
    (SELECT COUNT(*) FROM nomenclature) as nomenclature,
    (SELECT COUNT(*) FROM current_prices) as prices,
    (SELECT COUNT(*) FROM current_prices WHERE in_stock) as in_stock,
    (SELECT COUNT(*) FROM outlets) as outlets;

-- Последние обновления
SELECT article, name, updated_at
FROM nomenclature
ORDER BY updated_at DESC
LIMIT 10;

-- Проверка всех баз
\l db_*
```
