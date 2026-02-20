# Profi Sandbox — Схема БД и интеграция с zip

## Общая архитектура

Единая PostgreSQL 15 база данных на Supabase Cloud.
Два уровня таблиц:

```
┌─────────────────────────────────────────────────────┐
│                  zip_* (центральные)                │
│                                                     │
│  zip_nomenclature    — единый каталог запчастей     │
│  zip_current_prices  — актуальные цены из всех      │
│  zip_dict_brands     — справочник брендов           │
│  zip_dict_models     — справочник моделей           │
│  zip_dict_part_types — справочник типов запчастей   │
│  zip_dict_colors     — справочник цветов            │
│  zip_dict_features   — конфигурация AI-фич          │
│  zip_dict_qualities  — справочник качества           │
│  zip_outlets         — торговые точки (226 шт)      │
│  zip_nomenclature_staging — очередь AI обработки    │
│  zip_nomenclature_features — фичи товаров (M:N)     │
│  zip_nomenclature_models   — модели товаров (M:N)   │
└────────────────────────▲────────────────────────────┘
                         │
              экспорт (БЛОК 5)
                         │
┌────────────────────────┴────────────────────────────┐
│              profi_* (песочница Profi)               │
│                                                     │
│  profi_nomenclature  — номенклатура после парсинга  │
│  profi_prices        — цены по торговым точкам      │
│  profi_staging       — сырые данные парсера         │
│  profi_tasks         — фоновые задачи sandbox       │
└─────────────────────────────────────────────────────┘
```

Поток данных: profi_* → нормализация → zip_*. Обратный путь — только
`zip_nomenclature_id` записывается обратно в `profi_nomenclature`.

---

## Таблицы песочницы Profi

### profi_nomenclature

Основная таблица. Каждая строка — уникальный товар (артикул).

```
id                    SERIAL PRIMARY KEY
article               VARCHAR(100) UNIQUE NOT NULL   — артикул товара
barcode               VARCHAR(50)
name                  TEXT NOT NULL                   — наименование

── Сырые данные парсера (font-size из Excel) ──
brand_raw             VARCHAR(200)       — "1. ЗАПЧАСТИ ДЛЯ APPLE"
model_raw             VARCHAR(200)       — "ЗАПЧАСТИ ДЛЯ APPLE IPHONE"
part_type_raw         VARCHAR(200)       — "ДИСПЛЕИ OLED"
category              TEXT
product_url           TEXT

── Очищенные данные (после предподготовки, шаги 2.1–2.9) ──
brand                 VARCHAR(100)       — "iPhone"
model                 VARCHAR(200)       — NULL (перенесён в brand)
part_type             VARCHAR(100)       — "ДИСПЛЕЙ"

── Флаги нормализации ──
is_spare_part         BOOLEAN DEFAULT true    — false = не запчасть, пропускаем
needs_ai              BOOLEAN DEFAULT false   — true = rule-based не закрыл

── Результаты rule-based (БЛОК 3) ──
brand_normalized      VARCHAR(200)       — имя бренда из zip_dict_brands
part_type_normalized  VARCHAR(200)       — каноническая форма из PART_TYPE_MAPPING
zip_brand_id          INTEGER            — FK → zip_dict_brands.id
zip_part_type_id      INTEGER            — FK → zip_dict_part_types.id

── Результаты AI + экспорта (БЛОКИ 4–5) ──
zip_model_id          INTEGER            — FK → zip_dict_models.id
zip_color_id          INTEGER            — FK → zip_dict_colors.id
zip_nomenclature_id   INTEGER            — FK → zip_nomenclature.id (связь с центром)
normalized_at         TIMESTAMPTZ

── Метаданные ──
first_seen_at         TIMESTAMPTZ DEFAULT NOW()
updated_at            TIMESTAMPTZ DEFAULT NOW()
```

**Жизненный цикл записи:**

```
Парсинг:         article, name, brand_raw, model_raw, part_type_raw
                  ↓
Предподготовка:  brand, model, part_type, is_spare_part
                  ↓
Rule-based:      zip_brand_id, zip_part_type_id, brand_normalized, part_type_normalized
                  ↓  (если needs_ai=true)
AI:              zip_nomenclature_id
                  ↓
Экспорт:         zip_nomenclature_id (обратная ссылка из zip_nomenclature)
```

### profi_prices

Цены по торговым точкам. Одна строка = один артикул в одной точке.

```
id                    SERIAL PRIMARY KEY
article               VARCHAR(100) NOT NULL           — FK к profi_nomenclature.article
outlet_code           VARCHAR(100) NOT NULL           — код точки ("profi-msk-savelovo")
city                  VARCHAR(100)                    — город
price                 NUMERIC(12,2)                   — розничная цена
updated_at            TIMESTAMPTZ DEFAULT NOW()

UNIQUE (article, outlet_code)
```

### profi_tasks

Фоновые задачи sandbox. Создаётся при вызове POST endpoints.

```
id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY
task_type             VARCHAR(50) NOT NULL    — "parse_all", "normalize_rules", "export_full"
status                VARCHAR(20) DEFAULT 'pending'   — pending → running → completed/failed
params                JSONB                   — параметры запуска {"outlet_code": "..."}
progress              JSONB                   — {"current": 10, "total": 37, "message": "..."}
result                JSONB                   — итоговый результат
error                 TEXT                    — stack trace при failed
created_at            TIMESTAMPTZ DEFAULT NOW()
started_at            TIMESTAMPTZ
completed_at          TIMESTAMPTZ
```

---

## Центральные справочники (zip_dict_*)

Sandbox читает их для сопоставления в БЛОКЕ 3.

### zip_dict_brands (~33 записи)

```
id          UUID PRIMARY KEY
code        VARCHAR(50) UNIQUE     — "apple", "samsung"
name        VARCHAR(100) NOT NULL  — "Apple", "Samsung"
aliases     JSONB DEFAULT '[]'     — альтернативные написания
is_active   BOOLEAN DEFAULT true
```

### zip_dict_models (~5936 записей)

```
id              UUID PRIMARY KEY
brand_id        UUID → zip_dict_brands.id
device_type_id  UUID → zip_dict_device_types.id
code            VARCHAR(100) UNIQUE
name            VARCHAR(200) NOT NULL    — "iPhone 14 Pro", "Galaxy S23"
aliases         JSONB DEFAULT '[]'
release_year    INTEGER
is_active       BOOLEAN DEFAULT true
```

### zip_dict_part_types (13 записей)

```
id          SERIAL PRIMARY KEY
code        VARCHAR(50) UNIQUE     — "display", "battery"
name        VARCHAR(100) NOT NULL  — "Дисплей", "Аккумулятор"
is_active   BOOLEAN DEFAULT true
```

Типы: Дисплей, Аккумулятор, Корпус, Кнопка, Камера, Динамик, Микрофон,
Разъем, Шлейф, Тачскрин, Рамка, Стекло камеры, SIM-лоток, и др.

### zip_dict_colors (18 записей)

```
id          SERIAL PRIMARY KEY
code        VARCHAR(50) UNIQUE
name        VARCHAR(100) NOT NULL  — "Черный", "Белый", "Золотой"
is_active   BOOLEAN DEFAULT true
```

### zip_dict_features (7+ записей)

Конфигурация AI-фич для агентов 3 и 4.

```
id              SERIAL PRIMARY KEY
code            VARCHAR(50) UNIQUE       — "binding", "technology", "manufacturer"
name            VARCHAR(100) NOT NULL    — "Привязка", "Технология"
feature_type    VARCHAR(30) NOT NULL     — "BOOLEAN", "STATIC_LIST", "DYNAMIC_LIST", "COLOR"
possible_values JSONB
is_active       BOOLEAN DEFAULT true
```

### zip_dict_qualities

```
id          SERIAL PRIMARY KEY
code        VARCHAR(50) UNIQUE
name        VARCHAR(100) NOT NULL  — "Оригинал", "Копия", "Премиум"
is_active   BOOLEAN DEFAULT true
```

---

## Центральные таблицы данных (zip_*)

Sandbox экспортирует сюда в БЛОКЕ 5.

### zip_nomenclature

Единый каталог запчастей из всех магазинов.

```
id                UUID PRIMARY KEY
article           VARCHAR(100) UNIQUE
name              TEXT NOT NULL

── Ссылки на справочники ──
brand_id          UUID → zip_dict_brands.id
part_type_id      INTEGER → zip_dict_part_types.id
color_id          INTEGER → zip_dict_colors.id
quality_id        INTEGER → zip_dict_qualities.id

── AI метаданные ──
manufacturer      VARCHAR(200)     — производитель копии (GX, ZY, ...)
confidence        NUMERIC(3,2)     — средняя уверенность 4 агентов
parsed_by         VARCHAR(50)      — "multi-agent-v7"
parsed_at         TIMESTAMPTZ

── Цены / остатки ──
current_price     NUMERIC(12,2)
current_stock     INTEGER DEFAULT 0

── Timestamps ──
created_at        TIMESTAMPTZ DEFAULT NOW()
updated_at        TIMESTAMPTZ DEFAULT NOW()
```

### zip_current_prices

Актуальные цены из всех магазинов и точек.

```
id                SERIAL PRIMARY KEY
nomenclature_id   UUID → zip_nomenclature.id
outlet_id         INTEGER → zip_outlets.id

price             NUMERIC(12,2)
price_wholesale   NUMERIC(12,2)
in_stock          BOOLEAN DEFAULT false
quantity          INTEGER

updated_at        TIMESTAMPTZ DEFAULT NOW()

UNIQUE (nomenclature_id, outlet_id)
```

### zip_nomenclature_models (M:N)

Один товар может подходить к нескольким моделям устройств.

```
nomenclature_id   UUID → zip_nomenclature.id
model_id          UUID → zip_dict_models.id

UNIQUE (nomenclature_id, model_id)
```

### zip_nomenclature_features (M:N)

Характеристики товара, извлечённые AI.

```
nomenclature_id   UUID → zip_nomenclature.id
feature_id        INTEGER → zip_dict_features.id
value             VARCHAR(100)       — "OLED", "С привязкой", "GX"
confidence        NUMERIC(3,2)

UNIQUE (nomenclature_id, feature_id)
```

---

## SQL функции нормализации (v7)

Sandbox вызывает эти функции в БЛОКЕ 4 (AI нормализация).

### match_and_normalize_v3(p_data JSONB)

Главная функция. Принимает 4-агентный payload, возвращает `{success, nomenclature_id}`.

Внутри вызывает:

| Функция | Что делает | Логика поиска |
|---------|-----------|---------------|
| `match_or_create_brand(text)` | Найти/создать бренд | exact → code → fuzzy(0.6) → aliases → create |
| `match_or_create_model(uuid, text)` | Найти/создать модель | exact within brand → fuzzy(0.7) → create |
| `match_or_create_models(uuid, jsonb)` | Батч моделей | вызывает match_or_create_model для каждой |
| `match_or_create_color(text)` | Найти/создать цвет | exact → fuzzy(0.7) → create |
| `match_or_add_manufacturer(uuid, int, text, bool)` | Производитель | exact → fuzzy(0.7) → add if is_new |
| `get_features_for_agents(uuid, int)` | Конфиг AI-фич | по brand_id + part_type_id |

---

## Связь profi_nomenclature → zip_nomenclature

```
profi_nomenclature                          zip_nomenclature
┌──────────────────┐                       ┌──────────────────┐
│ article          │───── экспорт ────────▶│ article          │
│ name             │                       │ name             │
│                  │                       │                  │
│ zip_brand_id ────┼──────────────────────▶│ brand_id         │
│ zip_part_type_id ┼──────────────────────▶│ part_type_id     │
│ zip_color_id ────┼──────────────────────▶│ color_id         │
│                  │                       │                  │
│ zip_nomenclature_id ◀───── обратная ────│ id               │
│                  │         ссылка        │                  │
└──────────────────┘                       └──────────────────┘

profi_prices                                zip_current_prices
┌──────────────────┐                       ┌──────────────────┐
│ article          │                       │ nomenclature_id ─┼─▶ zip_nomenclature.id
│ outlet_code      │───── экспорт ────────▶│ outlet_id        │
│ price            │                       │ price            │
└──────────────────┘                       └──────────────────┘
```

---

## Индексы (миграция 023)

```sql
-- profi_tasks
idx_profi_tasks_status     ON profi_tasks(status)
idx_profi_tasks_type       ON profi_tasks(task_type)

-- profi_nomenclature (расширение)
idx_profi_nom_needs_ai     ON profi_nomenclature(needs_ai) WHERE needs_ai = true
idx_profi_nom_spare        ON profi_nomenclature(is_spare_part)
idx_profi_nom_zip_brand    ON profi_nomenclature(zip_brand_id)
```

---

## Статистика БД

| Метрика | Значение |
|---------|----------|
| Магазинов | 12 |
| Торговых точек (zip_outlets) | 226 |
| Городов | 117 |
| Брендов (zip_dict_brands) | 33 |
| Моделей (zip_dict_models) | 5 936 |
| Типов запчастей | 13 |
| Цветов | 18 |
| Точек Profi | 43 |
