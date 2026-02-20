# Orizhka.ru Parser

Парсер магазина запчастей для Apple **orizhka.ru**

## Особенности

- **API**: Tilda Store (`store.tildaapi.com`)
- **Категорий**: 41
- **Товаров**: ~2500
- **Город**: Санкт-Петербург
- **БД**: `db_orizhka`

## Структура

```
Orizhka/
├── parser.py           # Основной парсер
├── README.md
└── data/
    ├── products.json   # Результат (JSON)
    └── products.xlsx   # Результат (Excel)
```

## Запуск

```bash
# Полный парсинг с сохранением в БД (новая схема)
python3 parser.py

# Без сохранения в БД (только файлы)
python3 parser.py --no-db

# Использовать старую схему (products, stock)
python3 parser.py --old-schema

# Только инициализация БД
python3 parser.py --init-db
```

## Схема БД

### Новая схема (по умолчанию)

```sql
-- Торговые точки
outlets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,  -- 'orizhka-spb'
    city VARCHAR(100),
    name VARCHAR(200),
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- Номенклатура
orizhka_nomenclature (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    article VARCHAR(100) UNIQUE NOT NULL,  -- sku или uid из Tilda
    category VARCHAR(200),
    brand VARCHAR(100) DEFAULT 'Apple',
    first_seen_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- Цены и наличие
orizhka_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER REFERENCES orizhka_nomenclature(id),
    outlet_id INTEGER REFERENCES outlets(id),
    price NUMERIC(12,2),
    old_price NUMERIC(12,2),        -- старая цена (зачеркнутая)
    quantity INTEGER DEFAULT 0,      -- количество на складе
    in_stock BOOLEAN DEFAULT FALSE,
    product_url TEXT,               -- URL товара на сайте
    updated_at TIMESTAMP,
    UNIQUE (nomenclature_id, outlet_id)
)
```

### Старая схема (--old-schema)

```sql
-- Товары
products (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR(50) UNIQUE,  -- UID из Tilda
    sku VARCHAR(100),               -- Артикул
    name TEXT,                      -- Название
    price NUMERIC(10,2),            -- Цена
    old_price NUMERIC(10,2),        -- Старая цена
    availability INTEGER,           -- Количество
    category VARCHAR(200),          -- Категория
    brand VARCHAR(100),             -- Бренд (Apple)
    url TEXT,                       -- Ссылка
    city_id INTEGER,                -- ID города
    updated_at TIMESTAMP
)

-- Города
cities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),              -- Санкт-Петербург
    slug VARCHAR(100) UNIQUE,       -- spb
    region VARCHAR(200)
)
```

## API Tilda Store

```
GET https://store.tildaapi.com/api/getproductslist/
    ?storepartuid={category_id}
    &slice={page}
    &size={per_page}
    &getparts=true
    &getoptions=true
```

## Категории

| ID | Название |
|----|----------|
| 346541913282 | iPhone 7 |
| 776914721572 | iPhone 7 Plus |
| 553331889302 | iPhone 8 |
| ... | ... |
| 988341629032 | iPhone 16 Pro Max |

Полный список в `parser.py` → `CATEGORIES`

## Конфигурация

Переменные окружения:

```bash
DB_HOST=85.198.98.104
DB_PORT=5433
DB_NAME=db_orizhka
DB_USER=postgres
DB_PASSWORD=***
```
