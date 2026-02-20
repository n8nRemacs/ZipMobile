# Архитектура базы данных ZipMobile
Обновлено: 2026-02-20 (GMT+4)

## Обзор системы

**ZipMobile** — система мониторинга цен на запчасти для мобильных устройств с AI-нормализацией номенклатуры.

### Двухуровневая архитектура

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     HOMELAB (рабочая БД)                                    │
│              213.108.170.194 (Supabase self-hosted)                        │
│              PostgreSQL: port 5433 (direct) / 6543 (pooled)               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ВСЕ ТАБЛИЦЫ (79 шт.):                                                    │
│  • zip_* — центральные, справочники, номенклатура                          │
│  • {shop}_* — per-shop nomenclature, prices, staging                      │
│  • greenspark_* — parser internals                                         │
│  • Функции AI-нормализации (21 шт.)                                       │
│                                                                             │
│  Парсеры (10 шт.) → пишут сюда                                            │
│  AI-нормализация (n8n) → работает здесь                                    │
│                                                                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    │ sync_to_cloud.py (после нормализации)
                                    │ Только финальные zip_* таблицы
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CLOUD (production API)                                   │
│              Supabase Cloud: griexhozxrqtepcilfnu                          │
│              aws-1-eu-west-3.pooler.supabase.com:6543                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ТОЛЬКО финальные таблицы (~25 шт.):                                       │
│  • zip_nomenclature, zip_nomenclature_models, zip_nomenclature_features    │
│  • zip_current_prices                                                       │
│  • zip_dict_* справочники                                                  │
│  • zip_shops, zip_outlets, zip_cities, zip_timezones, zip_countries        │
│                                                                             │
│  parts-api → читает отсюда                                                 │
│  frontend → читает отсюда                                                  │
│                                                                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    │ sync_from_cloud.py (перед парсерами)
                                    │ Инфраструктурные таблицы
                                    ▼
                              HOMELAB (обратно)
```

### Инфраструктура

| Компонент | Значение |
|-----------|----------|
| **Homelab** | `213.108.170.194` (Supabase self-hosted) |
| Homelab PG (direct) | port **5433** |
| Homelab PG (pooled) | port **6543** |
| **Cloud** | Supabase Cloud, project `griexhozxrqtepcilfnu` |
| Cloud PG (pooled) | `aws-1-eu-west-3.pooler.supabase.com:6543` |
| Cloud Dashboard | https://supabase.com/dashboard/project/griexhozxrqtepcilfnu |
| n8n | http://213.108.170.194:5678 |
| SSH | `ssh homelab` |

### Строки подключения

```
# Homelab (рабочая БД — парсеры, нормализация)
postgresql://postgres:Mi31415926pSss!@213.108.170.194:5433/postgres     # direct
postgresql://postgres:Mi31415926pSss!@213.108.170.194:6543/postgres     # pooled

# Cloud (production API)
postgresql://postgres.griexhozxrqtepcilfnu:PASSWORD@aws-1-eu-west-3.pooler.supabase.com:6543/postgres
```

> **ВАЖНО**: Парсеры и AI-нормализация работают ТОЛЬКО с Homelab. Cloud используется только для production API. Синхронизация финальных данных — через `sync_to_cloud.py`.

---

## Статистика БД

### Homelab (полная БД)

| Параметр | Значение |
|----------|----------|
| Всего таблиц | **79** |
| Функций | **21** |
| Парсеров | **10** (все протестированы 2026-02-18) |

### Данные парсеров (v10, 2026-02-20)

| # | Магазин | Nomenclature (+ price) | Product URLs | Тип парсера | URL тип |
|---|---------|------------------------|--------------|-------------|---------|
| 1 | TagGSM | 22,838 | ~22,838 | HTML | single |
| 2 | Liberti | 16,927 | ~16,927 | Excel | single |
| 3 | Profi | 13,583 | ~13,583 | Excel | single |
| 4 | Moba | 13,083 | ~13,083 | HTML (Playwright) | **multi** |
| 5 | MemsTech | 11,844 | ~16,893 | HTML | **multi** |
| 6 | 05GSM | 3,509 | ~3,509 | HTML | single |
| 7 | Signal23 | 3,133 | ~3,133 | HTML | single |
| 8 | Orizhka | 2,607 | ~2,607 | Tilda API | single |
| 9 | NAFFAS | 1,276 | 0 (нет URL) | MoySklad API | single |
| 10 | LCD-Stock | 1,195 | ~1,195 | HTML | single |
| | **ИТОГО** | **~90,000** | **~97,000** | | |

### Справочники

| Параметр | Значение |
|----------|----------|
| Моделей устройств | 5,936 |
| Брендов | 33 |
| Цветов | 18 |
| Типов запчастей | 13 |
| Характеристик (features) | 12 |
| Точек продаж (outlets) | 226 |
| Городов | 117 |

---

## Таблицы магазинов

### Список магазинов и их таблиц

| # | Магазин | Префикс | Nomenclature (+ price) | Product URLs | Staging | URL тип |
|---|---------|---------|------------------------|--------------|---------|---------|
| 1 | Профи | `profi_` | `profi_nomenclature` | `profi_product_urls` | `profi_staging` | single |
| 2 | GreenSpark | `greenspark_` | `greenspark_nomenclature` | `greenspark_product_urls` | `greenspark_staging` | single |
| 3 | TAGGSM | `taggsm_` | `taggsm_nomenclature` | `taggsm_product_urls` | `taggsm_staging` | single |
| 4 | MemsTech | `memstech_` | `memstech_nomenclature` | `memstech_product_urls` | `memstech_staging` | **multi** |
| 5 | Liberti | `liberti_` | `liberti_nomenclature` | `liberti_product_urls` | `liberti_staging` | single |
| 6 | 05GSM | `_05gsm_` | `_05gsm_nomenclature` | `_05gsm_product_urls` | `_05gsm_staging` | single |
| 7 | Signal23 | `signal23_` | `signal23_nomenclature` | `signal23_product_urls` | — | single |
| 8 | Moba | `moba_` | `moba_nomenclature` | `moba_product_urls` | `moba_staging` | **multi** |
| 9 | Orizhka | `orizhka_` | `orizhka_nomenclature` | `orizhka_product_urls` | `orizhka_staging` | single |
| 10 | LCD-Stock | `lcdstock_` | `lcdstock_nomenclature` | `lcdstock_product_urls` | `lcdstock_staging` | single |
| 11 | NAFFAS | `moysklad_naffas_` | `moysklad_naffas_nomenclature` | `moysklad_naffas_product_urls` | `moysklad_naffas_staging` | single |

---

## Стандартная схема таблиц

### {shop}_nomenclature (v10: + price)

```sql
CREATE TABLE {shop}_nomenclature (
    -- ИДЕНТИФИКАЦИЯ
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) UNIQUE NOT NULL,
    barcode VARCHAR(50),
    name TEXT NOT NULL,
    product_id VARCHAR(255),

    -- ДАННЫЕ ПАРСЕРА
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    color VARCHAR(100),
    quality VARCHAR(100),
    category VARCHAR(200),
    device_type VARCHAR(50),

    -- СПРАВОЧНАЯ ЦЕНА (v10: перенесено из _prices)
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),

    -- СВЯЗЬ С ЦЕНТРАЛЬНОЙ БД (zip_*)
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    zip_category_id INTEGER,
    normalized_at TIMESTAMPTZ,

    -- МЕТАДАННЫЕ
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### {shop}_product_urls (v10: заменяет {shop}_prices)

```sql
CREATE TABLE {shop}_product_urls (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL FK,
    outlet_id UUID,                       -- NULL = единый URL, UUID = per-city URL (multi-URL магазины)
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT {shop}_product_urls_url_unique UNIQUE (url)
);
-- Single-URL (9 магазинов): outlet_id = NULL, 1 строка на товар
-- Multi-URL (MemsTech, Moba): outlet_id = UUID, N строк на товар (разные поддомены)
```

### {shop}_staging (без изменений)

```sql
CREATE TABLE {shop}_staging (
    id SERIAL PRIMARY KEY,
    outlet_code VARCHAR(100),
    name TEXT,
    article VARCHAR(255),
    category TEXT,
    brand VARCHAR(200),
    model VARCHAR(500),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    url TEXT,
    processed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Центральные таблицы (zip_*)

### Группа 1: Инфраструктура (5 таблиц)

| # | Таблица | Записей | Описание |
|---|---------|---------|----------|
| 1 | `zip_shops` | 6 | Магазины/поставщики |
| 2 | `zip_outlets` | 226 | Торговые точки |
| 3 | `zip_cities` | 117 | Города |
| 4 | `zip_timezones` | 12 | Часовые пояса |
| 5 | `zip_countries` | 5 | Страны |

### Группа 2: Справочники (8+ таблиц)

| # | Таблица | Записей | Описание |
|---|---------|---------|----------|
| 6 | `zip_dict_brands` | 33 | Бренды |
| 7 | `zip_dict_device_types` | 4 | Типы устройств |
| 8 | `zip_dict_models` | 5,936 | Модели устройств |
| 9 | `zip_dict_colors` | 18 | Цвета |
| 10 | `zip_dict_qualities` | 20 | Качество |
| 11 | `zip_dict_features` | 12 | Характеристики для AI |
| 12 | `zip_dict_part_types` | 13 | Типы запчастей |
| 13 | `zip_dict_price_types` | 6 | Типы цен |
| 14 | `zip_dict_categories` | 0 | Иерархический справочник |

### Группа 3: Классификация (4 таблицы)

| # | Таблица | Описание |
|---|---------|----------|
| 15 | `zip_product_types` | Верхний уровень (запчасть/аксессуар/оборудование) |
| 16 | `zip_nomenclature_types` | Типы номенклатуры |
| 17 | `zip_accessory_types` | Типы аксессуаров |
| 18 | `zip_equipment_types` | Типы оборудования |

### Группа 4: Номенклатура (3 таблицы)

| # | Таблица | Записей | Описание |
|---|---------|---------|----------|
| 19 | `zip_nomenclature` | 211 | Унифицированные товары (UUID) |
| 20 | `zip_nomenclature_models` | 0 | Связь товар ↔ модели (M:N) |
| 21 | `zip_nomenclature_features` | 0 | Значения характеристик (M:N) |

### Группа 5: AI-нормализация (2 таблицы)

| # | Таблица | Записей | Описание |
|---|---------|---------|----------|
| 22 | `zip_brand_part_type_features` | 0 | Конфигурация AI для бренд+тип |
| 23 | `zip_nomenclature_staging` | 1,000 | Staging для AI обработки |

### Группа 6: Цены (3 таблицы)

| # | Таблица | Описание |
|---|---------|----------|
| 24 | `zip_current_prices` | Текущие цены (snapshot) |
| 25 | `zip_price_history` | История цен |
| 26 | `zip_shop_price_types` | Связь магазин ↔ типы цен |

### Группа 7: GSMArena (2 таблицы)

| # | Таблица | Записей | Описание |
|---|---------|---------|----------|
| 29 | `zip_gsmarena_raw` | 9,101 | Сырые данные телефонов |
| 30 | `zip_gsmarena_phones` | 0 | Нормализованные телефоны |

---

## Поток данных (Data Flow)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ИСТОЧНИКИ ДАННЫХ (10 парсеров)                        │
│                                                                              │
│   HTML парсеры:                    Другие типы:                             │
│   • TagGSM     (HTML)              • Профи     (Excel)                     │
│   • MemsTech   (HTML)              • Liberti   (Excel)                     │
│   • 05GSM      (HTML)              • NAFFAS    (MoySklad API)              │
│   • Signal23   (HTML/OpenCart)      • Orizhka   (Tilda API)                │
│   • LCD-Stock  (HTML)              • Moba      (HTML + Playwright)         │
│   • GreenSpark (API/JSON)                                                   │
│                                                                              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼ Все парсеры пишут на Homelab
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЭТАП 1: ПАРСИНГ → {shop}_nomenclature + {shop}_product_urls (Homelab)       │
│                                                                              │
│  Парсер сохраняет:                                                          │
│  • {shop}_nomenclature: article, name, brand, model, category, price        │
│  • {shop}_product_urls: url, outlet_id (NULL для single-URL)                │
│  • zip_nomenclature_id = NULL (пока не нормализован)                        │
│                                                                              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │ WHERE zip_nomenclature_id IS NULL
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЭТАП 2: AI-НОРМАЛИЗАЦИЯ → zip_nomenclature_staging (Homelab)               │
│                                                                              │
│  n8n workflows (AI Workers v7):                                             │
│  • brand-worker → zip_brand_id                                              │
│  • model-worker → zip_dict_models                                           │
│  • part-type-worker → zip_part_type_id                                      │
│  • features-worker → характеристики                                         │
│  • color-worker → zip_color_id                                              │
│  • quality-worker → zip_quality_id                                          │
│  • price-sync → синхронизация цен                                           │
│                                                                              │
│  Статус: НЕ НАСТРОЕН (следующий этап)                                       │
│                                                                              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │ После AI-нормализации
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЭТАП 3: SYNC TO CLOUD → sync_to_cloud.py                                   │
│                                                                              │
│  Синхронизирует ТОЛЬКО финальные таблицы:                                   │
│  • DICT_TABLES → zip_dict_* (UPSERT)                                       │
│  • CATALOG_TABLES → zip_nomenclature, _models, _features (UPSERT/REPLACE) │
│  • PRICE_TABLES → zip_current_prices (TRUNCATE+INSERT)                     │
│                                                                              │
│  Статус: ГОТОВ, но не запускался (ждёт нормализацию)                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Подключение парсеров к БД

### Конфигурация (SHOPS/db_config.py)

Поддерживает два режима: `local` (Homelab) и `cloud` (Supabase Cloud).

```python
# SHOPS/db_config.py
DB_TARGET = os.getenv("DB_TARGET", "local")  # "local" | "cloud"

def get_local_config():
    return {
        "host": "localhost",
        "port": 5433,
        "user": "postgres",
        "password": "...",
        "dbname": "postgres",
    }

def get_cloud_config():
    return {
        "host": "aws-1-eu-west-3.pooler.supabase.com",
        "port": 6543,
        "user": "postgres.griexhozxrqtepcilfnu",
        "password": "...",
        "dbname": "postgres",
        "sslmode": "require",
    }

def get_db_config(target=None):
    target = target or DB_TARGET
    if target == "cloud":
        return get_cloud_config()
    return get_local_config()
```

### Обёртка с маппингом таблиц (SHOPS/db_wrapper.py)

Прозрачно переименовывает таблицы через regex перезапись SQL:

```python
TABLE_MAPPING = {
    "outlets": "zip_outlets",
    "cities": "zip_cities",
    "products": "lcdstock_products",
    "stock": "lcdstock_stock",
    "lcd_nomenclature": "lcdstock_nomenclature",
    "lcd_prices": "lcdstock_prices",
    "gsm05_nomenclature": "_05gsm_nomenclature",
    "gsm05_prices": "_05gsm_prices",
    "gsm05_staging": "_05gsm_staging",
    # ... и другие маппинги
}

# Дополнительные методы SupabaseCursor:
# cur.batch_insert(sql, values, page_size=1000) — execute_values wrapper
# cur.set_timeout(seconds) — SET statement_timeout
```

### Использование в парсерах

```python
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db

conn = get_db()          # Подключение к Homelab (по умолчанию)
conn = get_db("cloud")   # Подключение к Cloud
cur = conn.cursor()
cur.execute("SELECT * FROM outlets")  # → SELECT * FROM zip_outlets
```

---

## Скрипты синхронизации

### sync_from_cloud.py (Cloud → Homelab)

Запускается **перед парсерами**. Синхронизирует инфраструктурные таблицы, которые управляются из админки:

```
zip_shops, zip_outlets, zip_cities, zip_timezones, zip_countries
```

```bash
python3 sync_from_cloud.py             # все таблицы
python3 sync_from_cloud.py --dry-run   # только подсчёт
python3 sync_from_cloud.py --table zip_outlets  # одна таблица
```

### sync_to_cloud.py (Homelab → Cloud)

Запускается **после нормализации**. Синхронизирует финальные данные для production API:

```
# Справочники (UPSERT): zip_dict_brands, zip_dict_models, zip_dict_colors, ...
# Каталог (UPSERT): zip_nomenclature, zip_nomenclature_models, zip_nomenclature_features
# Цены (TRUNCATE+INSERT): zip_current_prices
```

```bash
python3 sync_to_cloud.py                   # все таблицы
python3 sync_to_cloud.py --dry-run         # только подсчёт
python3 sync_to_cloud.py --only-catalog    # только каталог
python3 sync_to_cloud.py --only-prices     # только цены
python3 sync_to_cloud.py --only-dicts      # только справочники
python3 sync_to_cloud.py --table zip_dict_brands  # одна таблица
```

---

## V7 SQL Функции (Homelab)

| Функция | Описание |
|---------|----------|
| `get_features_for_agents(brand_id, part_type_id)` | Конфигурация features для агентов AI |
| `get_features_no_match(brand_id, part_type_id)` | Features без матчинга |
| `get_features_with_match(brand_id, part_type_id)` | Features с матчингом |
| `match_or_create_brand(brand_raw)` | Fuzzy match бренда |
| `match_or_create_model(brand_id, model_name)` | Fuzzy match модели |
| `match_or_create_color(color_raw)` | Fuzzy match цвета |
| `match_or_create_models(brand_id, models_jsonb)` | Batch обработка моделей |
| `add_dynamic_value(brand_id, part_type_id, feature_code, value)` | Новое значение в DYNAMIC_LIST |
| `match_or_create_category(category_raw)` | Fuzzy match категории |
| `match_and_normalize_v3(data_jsonb)` | Главная функция нормализации V7 |

---

## Важные ограничения

| Параметр | Значение |
|----------|----------|
| Batch INSERT limit | ~300 rows per execute_values (500 hangs) |
| Безопасный BATCH_SIZE | **200** |
| Cloud port 5432 | Session mode, max ~15 clients |
| Cloud port 6543 | Transaction mode, рекомендуется |
| При подключении к port 6543 | `cfg.pop("options", None)` обязательно |
| zip_outlets.id | UUID, не integer |
| Cloud direct (db.*.supabase.co) | Только IPv6, у homelab нет IPv6 |

---

## Версионирование

| Версия | Дата | Описание |
|--------|------|----------|
| 1.0 | 2024-01 | Начальная схема (5 таблиц) |
| 2.0 | 2024-06 | Расширение до 18 таблиц |
| 3.0 | 2026-01-19 | AI-нормализация: +4 таблицы |
| 4.0 | 2026-01-19 | V7: Мульти-агентная архитектура, 29 таблиц, 9 функций |
| 5.0 | 2026-01-24 | Миграция на Supabase Cloud: единая БД с префиксами |
| 6.0 | 2026-01-27 | Стандартизация 100% таблиц парсеров |
| 7.0 | 2026-01-29 | Унификация: удалены _raw поля, VIEW нормализации |
| 8.0 | 2026-02-18 | Двухуровневая архитектура: Homelab (79 таблиц) + Cloud (финальные). pg_dump миграция. Все 10 парсеров протестированы на Homelab. |
| 9.0 | 2026-02-19 | Удалены остатки: zip_current_stock, zip_stock_history, поля in_stock/stock_stars/quantity/stock_level/stock_mode из всех таблиц. GreenSpark: однопроходный парсинг + автосинхронизация точек. |
| **10.0** | **2026-02-20** | **{shop}_prices → {shop}_product_urls. price/price_wholesale перенесены в {shop}_nomenclature. product_urls: связь номенклатура→URL (outlet_id nullable). Single-URL (9 магазинов): outlet_id=NULL. Multi-URL (MemsTech, Moba): outlet_id=UUID. TagGSM: 2M строк → ~23K. Старые _prices переименованы в _prices_deprecated.** |

---

## Контакты

| Ресурс | URL |
|--------|-----|
| Homelab SSH | `ssh homelab` (213.108.170.194) |
| Supabase Dashboard | https://supabase.com/dashboard/project/griexhozxrqtepcilfnu |
| n8n | http://213.108.170.194:5678 |
| Репозиторий | https://github.com/n8nRemacs/ZipMobile |
