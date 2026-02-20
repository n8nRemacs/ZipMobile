# Схема таблиц парсеров — Стандарт v1.0

> **Версия**: 1.0
> **Дата**: 2026-01-26
> **Статус**: Обязательный стандарт

---

## Обзор

Каждый парсер магазина должен иметь три типа таблиц в единой БД Supabase:

| Таблица | Назначение | Обязательность |
|---------|------------|----------------|
| `{shop}_nomenclature` | Уникальные товары | **Обязательно** |
| `{shop}_prices` | Цены по точкам | **Обязательно** |
| `{shop}_staging` | Временные данные | Опционально |

---

## 1. Таблица nomenclature

### DDL

```sql
CREATE TABLE {shop}_nomenclature (
    -- === ПЕРВИЧНЫЙ КЛЮЧ ===
    id SERIAL PRIMARY KEY,

    -- === ИДЕНТИФИКАЦИЯ (обязательно) ===
    article VARCHAR(100) NOT NULL,          -- Уникальный артикул
    name TEXT NOT NULL,                     -- Название товара

    -- === СЫРЫЕ ДАННЫЕ ИЗ ПАРСЕРА ===
    barcode VARCHAR(50),                    -- Штрихкод EAN-13/UPC
    brand_raw VARCHAR(200),                 -- Бренд как на сайте
    model_raw VARCHAR(200),                 -- Модель как на сайте
    part_type_raw VARCHAR(200),             -- Тип запчасти как на сайте
    category_raw TEXT,                      -- Полная категория (breadcrumbs)

    -- === НОРМАЛИЗОВАННЫЕ ДАННЫЕ ===
    brand VARCHAR(100),                     -- Бренд (Apple, Samsung)
    model VARCHAR(200),                     -- Модель (iPhone 14 Pro)
    part_type VARCHAR(100),                 -- Тип (Дисплей, АКБ)
    device_type VARCHAR(50),                -- Устройство (phone, tablet)
    product_id VARCHAR(255),                -- ID товара на сайте

    -- === СИНХРОНИЗАЦИЯ С ЦЕНТРАЛЬНОЙ БД ===
    zip_nomenclature_id UUID,               -- FK → zip_nomenclature.id
    zip_brand_id UUID,                      -- FK → zip_dict_brands.id
    zip_part_type_id INTEGER,               -- FK → zip_part_types.id
    zip_quality_id INTEGER,                 -- FK → zip_dict_qualities.id
    zip_color_id INTEGER,                   -- FK → zip_dict_colors.id
    normalized_at TIMESTAMPTZ,              -- Дата AI-нормализации

    -- === МЕТАДАННЫЕ ===
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- === ОГРАНИЧЕНИЯ ===
    CONSTRAINT {shop}_nomenclature_article_unique UNIQUE (article)
);

-- Индексы
CREATE INDEX idx_{shop}_nom_brand ON {shop}_nomenclature(brand);
CREATE INDEX idx_{shop}_nom_zip_id ON {shop}_nomenclature(zip_nomenclature_id);
CREATE INDEX idx_{shop}_nom_updated ON {shop}_nomenclature(updated_at);
```

### Описание полей

| Поле | Тип | Обязательно | Описание |
|------|-----|:-----------:|----------|
| `id` | SERIAL | ✅ | Первичный ключ |
| `article` | VARCHAR(100) | ✅ | Уникальный артикул товара (SKU) |
| `name` | TEXT | ✅ | Полное название товара |
| `barcode` | VARCHAR(50) | | Штрихкод EAN-13 или UPC |
| `brand_raw` | VARCHAR(200) | | Бренд как указан на сайте |
| `model_raw` | VARCHAR(200) | | Модель как указана на сайте |
| `part_type_raw` | VARCHAR(200) | | Тип запчасти как на сайте |
| `category_raw` | TEXT | | Полный путь категории (breadcrumbs) |
| `brand` | VARCHAR(100) | | Нормализованный бренд |
| `model` | VARCHAR(200) | | Нормализованная модель |
| `part_type` | VARCHAR(100) | | Нормализованный тип запчасти |
| `device_type` | VARCHAR(50) | | Тип устройства (phone/tablet/laptop) |
| `product_id` | VARCHAR(255) | | ID товара на сайте поставщика |
| `zip_nomenclature_id` | UUID | | Ссылка на центральную номенклатуру |
| `zip_brand_id` | UUID | | Ссылка на справочник брендов |
| `zip_part_type_id` | INTEGER | | Ссылка на справочник типов |
| `zip_quality_id` | INTEGER | | Ссылка на справочник качества |
| `zip_color_id` | INTEGER | | Ссылка на справочник цветов |
| `normalized_at` | TIMESTAMPTZ | | Дата AI-нормализации |
| `first_seen_at` | TIMESTAMPTZ | | Дата первого появления |
| `updated_at` | TIMESTAMPTZ | | Дата последнего обновления |

---

## 2. Таблица prices

### DDL

```sql
CREATE TABLE {shop}_prices (
    -- === ПЕРВИЧНЫЙ КЛЮЧ ===
    id SERIAL PRIMARY KEY,

    -- === СВЯЗИ (обязательно) ===
    nomenclature_id INTEGER NOT NULL
        REFERENCES {shop}_nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL
        REFERENCES zip_outlets(id),

    -- === ЦЕНЫ ===
    price NUMERIC(12,2),                    -- Розничная цена
    price_wholesale NUMERIC(12,2),          -- Оптовая цена

    -- === НАЛИЧИЕ ===
    in_stock BOOLEAN DEFAULT false,         -- Есть в наличии
    stock_stars SMALLINT,                   -- Уровень (1-5)
    quantity INTEGER,                       -- Точное количество

    -- === ДОПОЛНИТЕЛЬНО ===
    product_url TEXT,                       -- URL товара на сайте

    -- === МЕТАДАННЫЕ ===
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- === ОГРАНИЧЕНИЯ ===
    CONSTRAINT {shop}_prices_unique UNIQUE (nomenclature_id, outlet_id)
);

-- Индексы
CREATE INDEX idx_{shop}_prices_outlet ON {shop}_prices(outlet_id);
CREATE INDEX idx_{shop}_prices_in_stock ON {shop}_prices(in_stock);
CREATE INDEX idx_{shop}_prices_updated ON {shop}_prices(updated_at);
```

### Описание полей

| Поле | Тип | Обязательно | Описание |
|------|-----|:-----------:|----------|
| `id` | SERIAL | ✅ | Первичный ключ |
| `nomenclature_id` | INTEGER | ✅ | FK на товар |
| `outlet_id` | INTEGER | ✅ | FK на точку продаж |
| `price` | NUMERIC(12,2) | ✅ | Розничная цена |
| `price_wholesale` | NUMERIC(12,2) | | Оптовая цена |
| `in_stock` | BOOLEAN | ✅ | Наличие (true/false) |
| `stock_stars` | SMALLINT | | Уровень наличия (1-5) |
| `quantity` | INTEGER | | Точное количество |
| `product_url` | TEXT | | URL страницы товара |
| `updated_at` | TIMESTAMPTZ | | Дата обновления |

---

## 3. Таблица staging (опционально)

### DDL

```sql
CREATE TABLE {shop}_staging (
    -- === ПЕРВИЧНЫЙ КЛЮЧ ===
    id SERIAL PRIMARY KEY,

    -- === ИДЕНТИФИКАЦИЯ ===
    outlet_code VARCHAR(50),                -- Код точки продаж
    article VARCHAR(255),                   -- Артикул
    name TEXT,                              -- Название

    -- === СЫРЫЕ ДАННЫЕ ===
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,

    -- === ЦЕНЫ И НАЛИЧИЕ ===
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    in_stock BOOLEAN DEFAULT false,
    stock_level VARCHAR(50),                -- "много", "мало", "нет"
    quantity INTEGER,

    -- === URL ===
    product_url TEXT,

    -- === МЕТАДАННЫЕ ===
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);

-- Индексы
CREATE INDEX idx_{shop}_staging_article ON {shop}_staging(article);
CREATE INDEX idx_{shop}_staging_processed ON {shop}_staging(processed);
```

---

## 4. Список магазинов и их таблиц

| Магазин | Код | nomenclature | prices | staging |
|---------|-----|--------------|--------|---------|
| 05GSM | `_05gsm` | `_05gsm_nomenclature` | `_05gsm_prices` | `_05gsm_staging` |
| GreenSpark | `greenspark` | `greenspark_nomenclature` | `greenspark_prices` | `greenspark_staging` |
| LCD-Stock | `lcdstock` | `lcdstock_nomenclature_v2` | `lcdstock_prices_v2` | `lcdstock_staging` |
| Liberti | `liberti` | `liberti_nomenclature` | `liberti_prices` | `liberti_staging` |
| MemsTech | `memstech` | `memstech_nomenclature` | `memstech_prices` | `memstech_staging` |
| Moba | `moba` | `moba_nomenclature` | `moba_prices` | `moba_staging` |
| NAFFAS | `moysklad_naffas` | `moysklad_naffas_nomenclature` | `moysklad_naffas_prices` | `moysklad_naffas_staging` |
| Orizhka | `orizhka` | `orizhka_nomenclature` | `orizhka_prices` | `orizhka_staging` |
| Profi | `profi` | `profi_nomenclature` | `profi_prices` | `profi_staging` |
| Signal23 | `signal23` | `signal23_nomenclature` | `signal23_prices` | `signal23_staging` |
| TAGGSM | `taggsm` | `taggsm_nomenclature` | `taggsm_prices` | `taggsm_staging` |

---

## 5. Связи между таблицами

```
                    ┌─────────────────────────────────────────────┐
                    │          zip_nomenclature (центр)           │
                    │  id (UUID), article, name, brand_id, ...    │
                    └─────────────────────────────────────────────┘
                                          ▲
                                          │ zip_nomenclature_id
                                          │
┌─────────────────────────────────────────┴─────────────────────────────────────────┐
│                            {shop}_nomenclature                                     │
│  id, article (UNIQUE), name, brand_raw, model_raw, part_type_raw, category_raw    │
│  brand, model, part_type, device_type                                             │
│  zip_nomenclature_id, zip_brand_id, zip_part_type_id, ...                        │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                                          │ nomenclature_id
                                          ▼
┌─────────────────────────────────────────┴─────────────────────────────────────────┐
│                              {shop}_prices                                         │
│  id, nomenclature_id (FK), outlet_id (FK → zip_outlets)                           │
│  price, price_wholesale, in_stock, stock_stars, quantity, product_url             │
└───────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ outlet_id
                                          ▼
                    ┌─────────────────────────────────────────────┐
                    │              zip_outlets                     │
                    │  id, shop_id (FK), city_id (FK), code, name │
                    └─────────────────────────────────────────────┘
```

---

## 6. Применение миграции

### Шаг 1: Проверить текущее состояние

```bash
cd ZipMobile
python scripts/verify_parser_tables_standard.py
```

### Шаг 2: Посмотреть SQL для исправления

```bash
python scripts/verify_parser_tables_standard.py --fix
```

### Шаг 3: Применить миграцию

```bash
# Dry run (без изменений)
python scripts/apply_standardization_migration.py

# Применить
python scripts/apply_standardization_migration.py --apply
```

### Шаг 4: Проверить результат

```bash
python scripts/verify_parser_tables_standard.py
```

---

## 7. Работа с данными

### Добавление товара (UPSERT)

```sql
INSERT INTO {shop}_nomenclature (
    article, name, barcode,
    brand_raw, model_raw, part_type_raw, category_raw,
    first_seen_at, updated_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
ON CONFLICT (article) DO UPDATE SET
    name = EXCLUDED.name,
    barcode = COALESCE(EXCLUDED.barcode, {shop}_nomenclature.barcode),
    brand_raw = EXCLUDED.brand_raw,
    model_raw = EXCLUDED.model_raw,
    part_type_raw = EXCLUDED.part_type_raw,
    category_raw = EXCLUDED.category_raw,
    updated_at = NOW()
RETURNING id;
```

### Добавление цены (UPSERT)

```sql
INSERT INTO {shop}_prices (
    nomenclature_id, outlet_id,
    price, price_wholesale, in_stock, quantity,
    product_url, updated_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
    price = EXCLUDED.price,
    price_wholesale = EXCLUDED.price_wholesale,
    in_stock = EXCLUDED.in_stock,
    quantity = EXCLUDED.quantity,
    product_url = EXCLUDED.product_url,
    updated_at = NOW();
```

### Выборка товаров без нормализации

```sql
SELECT article, name, category_raw, brand_raw
FROM {shop}_nomenclature
WHERE zip_nomenclature_id IS NULL
ORDER BY updated_at DESC
LIMIT 100;
```

### Статистика по магазину

```sql
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE zip_nomenclature_id IS NOT NULL) AS normalized,
    COUNT(*) FILTER (WHERE zip_nomenclature_id IS NULL) AS pending,
    MAX(updated_at) AS last_update
FROM {shop}_nomenclature;
```

---

## История изменений

| Версия | Дата | Описание |
|--------|------|----------|
| 1.0 | 2026-01-26 | Первая версия стандарта |

---

**Автор**: ZipMobile Team
