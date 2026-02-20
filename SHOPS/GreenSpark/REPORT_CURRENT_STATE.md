# GreenSpark Parser — Отчёт о текущем состоянии

**Дата:** 2026-02-16
**Парсер:** #20 (последний из стандартизации)

---

## 1. Общая информация

| Параметр | Значение |
|----------|----------|
| Папка | `SHOPS/GreenSpark/` |
| Источник | green-spark.ru (оптовый поставщик запчастей) |
| Тип парсинга | API JSON (`/local/api/catalog/products/`) |
| Города | 60 городов (мультигород) |
| Серверы | 4 шт. (server-a, server-b-ip1, server-b-ip2, server-c) |
| Защита сайта | Детекция headless, IP-баны (403), cookie-валидация |

---

## 2. Файлы в папке

### Основные (рабочие)

| Файл | Строк | Описание | Статус |
|------|-------|----------|--------|
| `parser.py` | 1708 | Старый парсер v1-v2 (через db_wrapper → Supabase) | Рабочий, есть save_staging + process_staging |
| `parser_v3.py` | 1483 | Основной парсер v3.5 (своя БД db_greenspark) | Рабочий, продакшн |
| `config.py` | 28 | Конфигурация URL, задержки, пути | OK |
| `coordinator.py` | 321 | Координатор серверов через PostgreSQL LISTEN/NOTIFY | Рабочий |
| `telegram_notifier.py` | 262 | Telegram уведомления о банах, прогрессе | Рабочий |
| `get_cookies.py` | ~150 | Получение cookies через Playwright | Рабочий |
| `stealth_cookies.py` | ~400 | Stealth-режим для cookies (Xvfb + non-headless) | Рабочий |
| `fill_articles.py` | ~100 | Массовое заполнение артикулов через HTML | Утилита |
| `setup_greenspark_in_zip.sql` | 192 | SQL инициализация в zip_shops/zip_outlets/zip_cities | Готов |
| `requirements.txt` | 3 | httpx, openpyxl, playwright | Неполный (нет psycopg2-binary) |
| `README.md` | 421 | Подробная документация | Актуальная |
| `deploy.sh` | ~150 | Скрипт деплоя на серверы | Утилита |

### Утилиты / тесты

| Файл | Описание |
|------|----------|
| `analyze_missing.py` | Анализ товаров без артикулов |
| `check_articles.py` | Проверка артикулов |
| `debug_api.py` | Отладка API запросов |
| `proxy_generator.py` | Генератор прокси |
| `reparse_articles_standalone.py` | Отдельный скрипт допарсинга артикулов |
| `recent_updates.py` | Последние обновления |
| `test_api.py`, `test_api2.py`, `test_api3.py` | Тесты API |
| `test_api_article.py` | Тест артикулов через API |

### Данные

| Файл | Описание |
|------|----------|
| `data/greenspark_cities.json` | 60 городов с set_city ID |
| `data/greenspark_outlets.sql` | SQL для outlets |
| `data/products.json`, `products.xlsx`, `products.csv` | Результаты парсинга |
| `data/categories.json` | Маппинг категорий |
| `data/sample_product.json` | Пример товара |
| `data/errors.json` | Лог ошибок |
| `proxies.txt` | 749 КБ — список прокси |
| `Города.json`, `карточка товара.json`, `Ответ Список товаров.json` | Сырые данные API (кириллические имена) |
| `no_article.xlsm`, `no_article_v2.xlsm` | Excel файлы товаров без артикулов |
| `n8n/` | 6 файлов n8n workflows |
| `migrations/001_parser_coordination.sql` | Миграция координатора |

---

## 3. Архитектура парсера

### Две версии парсера

#### parser.py (v1-v2, старый)
- **Класс:** `GreenSparkCatalogParser`
- **БД:** Supabase через `db_wrapper.get_db()` (маппинг таблиц)
- **Таблицы:** `staging` → `nomenclature` → `current_prices` (через db_wrapper маппит на Supabase)
- **Функции:** `save_staging()`, `process_staging()`, `save_to_db()` — **стандартные**
- **Особенности:** Поддержка прокси-ротации, координатора, мульти-IP

#### parser_v3.py (v3.5, основной / продакшн)
- **Класс:** `GreenSparkParser` + `IPRotator`
- **БД:** Напрямую `db_greenspark` на 85.198.98.104:5433 (НЕ Supabase)
- **Таблицы:** `greenspark_nomenclature` (UNIQUE по product_url), `greenspark_prices`, `outlets`
- **Функции:** `save_products_incremental()`, `save_products_to_db()` — **нестандартные**
- **Уже есть:** Флаг `--use-staging` для вызова `save_staging`/`process_staging` из parser.py

### Ключевые различия v3 от стандарта

| Аспект | Стандарт (PARSER_STANDARD.md) | parser_v3.py (текущий) |
|--------|-------------------------------|------------------------|
| БД | Supabase Cloud | Локальная db_greenspark (85.198.98.104:5433) |
| Подключение | `db_wrapper.get_db()` | Свой `get_db()` с psycopg2 напрямую |
| Уникальность товара | По `article` (UNIQUE) | По `product_url` (UNIQUE) |
| Staging | TRUNCATE → INSERT → UPSERT | Нет staging, прямой UPSERT каждые 200 товаров |
| Поля nomenclature | article, name, brand_raw, model_raw, part_type_raw, category_raw, barcode, zip_nomenclature_id | name, product_url, article, category |
| Таблица outlets | `zip_outlets` (центральная) | `outlets` (локальная, код `greenspark-{city_id}`) |
| IP ротация | Нет | SSH SOCKS5 туннели, 4 сервера |
| Координация | Нет | PostgreSQL LISTEN/NOTIFY между серверами |
| Telegram | Нет | Полная интеграция (баны, прогресс, завершение) |

---

## 4. Подключение к БД

### parser.py (старый) — через db_wrapper
```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db  # → Supabase Cloud
```
Маппинг в `db_wrapper.py`:
- `parser_progress` → `greenspark_parser_progress`
- `parser_queue` → `greenspark_parser_queue`
- `parser_servers` → `greenspark_parser_servers`
- `outlets` → `zip_outlets`
- **НЕТ маппинга** для `staging`, `nomenclature`, `current_prices` на `greenspark_*`

### parser_v3.py (основной) — прямое подключение
```python
DB_HOST = "85.198.98.104"
DB_PORT = 5433
DB_NAME = "db_greenspark"
DB_USER = "postgres"
DB_PASSWORD = "Mi31415926pSss!"
```

### coordinator.py — прямое подключение
```python
DB_HOST = "85.198.98.104"
DB_PORT = 5433
DB_NAME = "db_greenspark"
```

---

## 5. Схема БД (db_greenspark, локальная)

### greenspark_nomenclature
```sql
CREATE TABLE greenspark_nomenclature (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    product_url TEXT NOT NULL UNIQUE,  -- URL = уникальный идентификатор
    article VARCHAR(50),               -- NULL если ещё не допарсен
    category TEXT,
    first_seen_at TIMESTAMP,
    updated_at TIMESTAMP
);
```
**Отличия от стандарта:**
- Нет `brand_raw`, `model_raw`, `part_type_raw`, `barcode`, `product_id`
- Нет `zip_nomenclature_id`, `zip_brand_id`, `normalized_at`
- UNIQUE по `product_url` вместо `article` (артикул может быть NULL)
- `article` опционален (допарсивается отдельным этапом)

### greenspark_prices
```sql
CREATE TABLE greenspark_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INT REFERENCES greenspark_nomenclature(id),
    outlet_id INT REFERENCES outlets(id),
    price NUMERIC,
    price_wholesale NUMERIC,
    in_stock BOOLEAN,
    updated_at TIMESTAMP,
    UNIQUE(nomenclature_id, outlet_id)
);
```
**Отличия от стандарта:**
- Нет `product_url` в prices (есть в v3, но не во всех путях)
- Нет `stock_stars`, `quantity`

### outlets (локальная)
```sql
CREATE TABLE outlets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE,  -- greenspark-{city_id}
    city VARCHAR(100),
    name VARCHAR(200),
    is_active BOOLEAN
);
```
**По стандарту должна быть:** `zip_outlets` (центральная, через Supabase)

---

## 6. Статус по стандарту PARSER_STANDARD.md

### Чеклист

| # | Требование | Статус | Комментарий |
|---|------------|--------|-------------|
| 1 | Папка `SHOPS/GreenSpark/` | ✅ | Существует |
| 2 | `parser.py` — главный файл | ⚠️ | Есть, но основной — parser_v3.py |
| 3 | `config.py` — конфигурация | ✅ | Есть |
| 4 | `requirements.txt` | ⚠️ | Неполный: нет psycopg2-binary, playwright-stealth |
| 5 | `setup_greenspark_in_zip.sql` | ✅ | Есть, 60 городов, zip_outlets |
| 6 | `README.md` | ✅ | Подробный |
| 7 | `data/` директория | ✅ | Есть |
| 8 | Использует `db_wrapper.get_db()` | ❌ | parser_v3.py — свой get_db() напрямую |
| 9 | Задержка между запросами | ✅ | 1.5 сек (config.py) |
| 10 | UPSERT по article | ⚠️ | UPSERT по product_url (article может быть NULL) |
| 11 | Стандартные CLI аргументы | ⚠️ | Есть --all-cities, --no-db, но нет --all, --limit |
| 12 | save_staging() | ⚠️ | Есть в parser.py, нет в parser_v3.py (есть --use-staging) |
| 13 | process_staging() | ⚠️ | Есть в parser.py, нет в parser_v3.py |
| 14 | Поля: brand_raw, model_raw, part_type_raw | ❌ | Не извлекаются |
| 15 | zip_nomenclature_id | ❌ | Нет в таблице |
| 16 | greenspark_staging таблица | ❓ | Не проверено (нет доступа к БД) |

---

## 7. Маппинг в db_wrapper.py

Текущие маппинги для GreenSpark:
```python
TABLE_MAPPING = {
    "parser_progress": "greenspark_parser_progress",
    "parser_queue": "greenspark_parser_queue",
    "parser_request_log": "greenspark_parser_request_log",
    "parser_servers": "greenspark_parser_servers",
    "product_lookup": "greenspark_product_lookup",
    "shop_cookies": "greenspark_shop_cookies",
    "shop_parser_configs": "greenspark_shop_parser_configs",
}
```

**Отсутствуют маппинги:**
- `staging` → `greenspark_staging`
- `nomenclature` → `greenspark_nomenclature`
- `current_prices` → `greenspark_prices`

**Проблема:** parser.py использует `staging`, `nomenclature`, `current_prices` — без маппинга они НЕ будут переписаны на `greenspark_*`. Это значит parser.py пишет в несуществующие таблицы или в чужие таблицы.

---

## 8. Префикс в db_config.py

```python
TABLE_PREFIXES = {
    "greenspark": "greenspark",  # ✅ Зарегистрирован
}
```

---

## 9. Что работает сейчас

### В продакшне (parser_v3.py):
1. Парсинг всех 60 городов с IP ротацией через SSH туннели
2. Инкрементальное сохранение каждые 200 товаров в `greenspark_nomenclature` + `greenspark_prices`
3. Допарсинг артикулов (batch из БД + HTTP fallback)
4. Telegram уведомления
5. Автоматическое получение cookies через Xvfb
6. Координатор для эстафеты между серверами

### Статистика (из README):
- ~11,155 товаров в номенклатуре
- 96.3% товаров с артикулами (10,739/11,155)
- 60 городов с разными ценами

---

## 10. Проблемы и несоответствия

### Критичные
1. **Двойная БД** — parser_v3.py пишет в локальную db_greenspark (85.198.98.104:5433), а стандарт требует Supabase Cloud
2. **Нет маппинга staging/nomenclature/current_prices** в db_wrapper → parser.py (старый) скорее всего сломан при работе с Supabase
3. **UNIQUE по product_url vs article** — стандарт требует UNIQUE по article, но у GreenSpark ~4% товаров без артикула

### Средние
4. **Нет полей классификации** — brand_raw, model_raw, part_type_raw не извлекаются (API не предоставляет)
5. **Нет zip_nomenclature_id** — не подключен к центральной номенклатуре
6. **requirements.txt неполный** — нет psycopg2-binary, socksio, playwright-stealth

### Мелкие
7. **Файловый мусор** — кириллические JSON файлы, .xlsm файлы, тестовые скрипты
8. **Двойные outlet-таблицы** — `outlets` (локальная) и `zip_outlets` (Supabase) не синхронизированы
9. **setup_greenspark_in_zip.sql** — готов, но неясно выполнялся ли

---

## 11. Рекомендации по ТЗ-5

Согласно ТЗ-5 (раздел 4. GreenSpark):

> 1. **НЕ переписывать parser_v3.py** — он работает, сложная логика ротации IP
> 2. В parser.py уже есть save_staging + process_staging
> 3. Добавить в parser_v3.py вызов через --use-staging (уже частично есть)
> 4. Убедиться что greenspark_staging существует

**Фактически `--use-staging` в parser_v3.py уже реализован** (строки 1440-1443, 1466-1469).

**Что ещё можно сделать:**
- Добавить маппинг в db_wrapper для staging/nomenclature/current_prices
- Проверить/создать greenspark_staging в Supabase
- Добавить недостающие поля (brand_raw, etc.) в greenspark_nomenclature
- Навести порядок в файлах (переместить тестовые/кириллические в _legacy/)
- Дополнить requirements.txt
