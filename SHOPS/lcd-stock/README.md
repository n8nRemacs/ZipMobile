# LCD-Stock.ru Parser

Парсер магазина дисплеев и запчастей **lcd-stock.ru**

## Особенности

- **Тип**: HTML парсер
- **Категорий**: 6
- **Товаров**: ~1100
- **Город**: Москва
- **БД**: `db_lcdstock`

## Структура

```
lcd-stock/
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

# Без сохранения в БД
python3 parser.py --no-db

# Использовать старую схему (products, stock)
python3 parser.py --old-schema

# Только одна категория
python3 parser.py --category displei

# Только инициализация БД
python3 parser.py --init-db
```

## Категории

| Slug | Название | Товаров |
|------|----------|---------|
| `displei` | Дисплеи | ~800 |
| `zadnie-kryshki` | Задние крышки | ~140 |
| `akkumulyatory` | Аккумуляторы | ~120 |
| `aksessuary` | Аксессуары | 0 |
| `shlejfy-platy` | Платы зарядки | ~90 |
| `smart-chasy` | Смарт-часы | 0 |

## Схема БД

### Новая схема (по умолчанию)

```sql
-- Торговые точки
outlets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,  -- 'lcd-savelovskiy', 'lcd-gorbushka'
    city VARCHAR(100),
    name VARCHAR(200),
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- Номенклатура
lcd_nomenclature (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    article VARCHAR(255) UNIQUE NOT NULL,  -- sku или product_id
    category VARCHAR(200),
    brand VARCHAR(100),
    color VARCHAR(100),                     -- цвет товара
    first_seen_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- Цены и наличие по магазинам
lcd_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER REFERENCES lcd_nomenclature(id),
    outlet_id INTEGER REFERENCES outlets(id),
    price NUMERIC(12,2),
    old_price NUMERIC(12,2),
    stock_status VARCHAR(50),              -- "много", "мало", "нет в наличии"
    in_stock BOOLEAN DEFAULT FALSE,
    product_url TEXT,
    updated_at TIMESTAMP,
    UNIQUE (nomenclature_id, outlet_id)
)
```

### Старая схема (--old-schema)

```sql
-- Товары
products (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR(255) UNIQUE,  -- slug из URL
    sku VARCHAR(100),                -- Артикул
    name TEXT,
    price NUMERIC(10,2),
    old_price NUMERIC(10,2),
    category VARCHAR(200),
    brand VARCHAR(100),              -- Apple, Samsung, Xiaomi...
    color VARCHAR(100),              -- Цвет товара
    url TEXT,
    updated_at TIMESTAMP
)

-- Магазины
outlets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    slug VARCHAR(100) UNIQUE,
    address TEXT
)

-- Наличие по магазинам
stock (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR(255),
    outlet_id INTEGER REFERENCES outlets(id),
    status VARCHAR(50),              -- много/мало/нет в наличии
    quantity INTEGER,                -- 0/1/2
    updated_at TIMESTAMP,
    UNIQUE(product_id, outlet_id)
)
```

## Магазины

| Slug | Название |
|------|----------|
| `savelovskiy` | ТК Савеловский |
| `sklad-savelovskiy` | Склад Савеловский |
| `mitinskiy` | ТЦ Митинский радиорынок |
| `gorbushka` | ТЦ Горбушкин Двор |
| `megaberezka` | ТРЦ Мегаберезка |

## Структура сайта

- Пагинация: `?page=N`
- Товары: `.card-product`
- Название: `.card-product_title`
- Цена: `.product-price`
