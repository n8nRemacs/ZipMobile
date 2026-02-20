# Руководство по созданию парсеров ZipMobile

## Содержание

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Создание нового парсера](#создание-нового-парсера)
3. [Структура базы данных](#структура-базы-данных)
4. [Стандартные функции](#стандартные-функции)
5. [CLI интерфейс](#cli-интерфейс)
6. [Тестирование](#тестирование)
7. [Деплой на сервер](#деплой-на-сервер)
8. [Интеграция с ZIP](#интеграция-с-zip)

---

## Обзор архитектуры

### Принципы

1. **Изоляция данных** — каждый магазин имеет отдельную базу данных
2. **Унифицированная структура** — все парсеры используют одинаковые таблицы
3. **Двухэтапная обработка** — сначала staging, потом нормализация
4. **Идемпотентность** — повторный запуск не создаёт дубликатов

### Поток данных

```
┌─────────────────┐
│  Источник       │  API / HTML / XLS / Sitemap
└────────┬────────┘
         ↓
┌─────────────────┐
│  Парсер         │  parse_source() → List[Dict]
└────────┬────────┘
         ↓
┌─────────────────┐
│  staging        │  TRUNCATE + INSERT (сырые данные)
└────────┬────────┘
         ↓ process_staging()
┌─────────────────┐
│  nomenclature   │  UPSERT по article (уникальные товары)
└────────┬────────┘
         ↓
┌─────────────────┐
│  current_prices │  UPSERT (текущие цены по точкам)
└────────┬────────┘
         ↓
┌─────────────────┐
│  price_history  │  INSERT per day (история цен)
└─────────────────┘
```

### Существующие парсеры

| Источник | База | Формат | Папка |
|----------|------|--------|-------|
| Profi (siriust.ru) | db_profi | XLS | `SHOPS/Profi/` |
| GreenSpark | db_greenspark | API JSON | `SHOPS/GreenSpark/` |
| TAGGSM | db_taggsm | HTML | `SHOPS/Taggsm/` |
| 05GSM | db_05gsm | HTML/Sitemap | `SHOPS/05GSM/` |
| MoySklad/Naffas | db_moysklad | API JSON | `SHOPS/moysklad/Naffas/` |
| MemsTech | db_memstech | HTML | `SHOPS/memstech/` |

---

## Создание нового парсера

### Шаг 1: Структура папок

```
SHOPS/
└── НовыйМагазин/
    ├── __init__.py       # Пустой файл
    ├── config.py         # Конфигурация (URL, параметры)
    ├── parser.py         # Основной парсер
    ├── cookies.json      # Cookies (если нужна авторизация)
    └── data/             # Выходные файлы (products.json, etc.)
```

### Шаг 2: Конфигурация (config.py)

```python
"""
Конфигурация парсера НовыйМагазин
"""

# URL источника
BASE_URL = "https://example-shop.ru"
API_URL = f"{BASE_URL}/api/v1"
CATALOG_URL = f"{BASE_URL}/catalog"

# Параметры запросов
REQUEST_DELAY = 0.5          # Задержка между запросами (сек)
REQUEST_TIMEOUT = 30         # Таймаут запроса (сек)
MAX_RETRIES = 3              # Количество повторов
ITEMS_PER_PAGE = 100         # Товаров на странице

# User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Выходные файлы
DATA_DIR = "data"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
ERRORS_LOG = f"{DATA_DIR}/errors.json"

# Категории (если статичные)
CATEGORIES = {
    "category-1": "Дисплеи",
    "category-2": "Аккумуляторы",
    # ...
}
```

### Шаг 3: Основной парсер (parser.py)

```python
"""
Парсер НовыйМагазин - описание источника

База данных: db_newshop
Таблицы: staging, outlets, nomenclature, current_prices, price_history
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import psycopg2
import argparse
from datetime import datetime
from typing import Optional, List, Dict

from config import (
    BASE_URL, API_URL, REQUEST_DELAY, REQUEST_TIMEOUT,
    USER_AGENT, DATA_DIR, PRODUCTS_JSON, PRODUCTS_CSV
)

# ============================================================
# КОНФИГУРАЦИЯ БД
# ============================================================

DB_HOST = os.environ.get("DB_HOST", "85.198.98.104")
DB_PORT = int(os.environ.get("DB_PORT", 5433))
DB_NAME = os.environ.get("DB_NAME", "db_newshop")  # <-- Изменить!
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mi31415926pSss!")

# Код магазина для outlets
SHOP_CODE = "newshop-online"  # <-- Изменить!
SHOP_NAME = "НовыйМагазин"    # <-- Изменить!
SHOP_CITY = "Москва"          # <-- Изменить!


def get_db():
    """Подключение к БД"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"
    )


# ============================================================
# КЛАСС ПАРСЕРА
# ============================================================

class NewShopParser:
    """Парсер каталога НовыйМагазин"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self.products: List[Dict] = []
        self.errors: List[Dict] = []

        os.makedirs(DATA_DIR, exist_ok=True)

    def parse_all(self) -> List[Dict]:
        """
        Основной метод парсинга.
        Возвращает список товаров в унифицированном формате.
        """
        print(f"Парсинг {SHOP_NAME}...")

        # TODO: Реализовать логику парсинга
        # - Обход категорий
        # - Сбор товаров
        # - Обработка пагинации

        return self.products

    def parse_product(self, raw_data: dict) -> Optional[Dict]:
        """
        Преобразует сырые данные товара в унифицированный формат.

        Обязательные поля:
        - name: str - название товара
        - article: str - артикул (уникальный идентификатор)
        - price: float - цена
        - in_stock: bool - наличие

        Опциональные поля:
        - category: str - категория
        - brand: str - бренд
        - model: str - модель устройства
        - url: str - URL товара
        - barcode: str - штрихкод
        """
        try:
            return {
                "name": raw_data.get("title", ""),
                "article": raw_data.get("sku", ""),
                "price": float(raw_data.get("price", 0)),
                "in_stock": raw_data.get("available", False),
                "category": raw_data.get("category", ""),
                "url": raw_data.get("url", ""),
            }
        except Exception as e:
            self.errors.append({
                "data": str(raw_data)[:200],
                "error": str(e),
                "time": datetime.now().isoformat()
            })
            return None

    def save_to_json(self, filename: str = None):
        """Сохранить в JSON"""
        filename = filename or PRODUCTS_JSON
        data = {
            "source": SHOP_NAME,
            "date": datetime.now().isoformat(),
            "total": len(self.products),
            "products": self.products,
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Сохранено в {filename}: {len(self.products)} товаров")

    def save_to_csv(self, filename: str = None):
        """Сохранить в CSV"""
        import csv
        filename = filename or PRODUCTS_CSV
        if not self.products:
            return

        fieldnames = ["article", "name", "price", "in_stock", "category", "url"]
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.products)
        print(f"Сохранено в {filename}")


# ============================================================
# ФУНКЦИИ РАБОТЫ С БД
# ============================================================

def ensure_outlet():
    """Создаёт outlet если не существует"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO outlets (code, city, name, is_active)
            VALUES (%s, %s, %s, true)
            ON CONFLICT (code) DO NOTHING
        """, (SHOP_CODE, SHOP_CITY, SHOP_NAME))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def save_staging(products: List[Dict]):
    """Сохранение товаров в staging таблицу"""
    if not products:
        print("Нет товаров для сохранения в staging")
        return

    conn = get_db()
    cur = conn.cursor()
    try:
        # Очищаем staging
        cur.execute("TRUNCATE TABLE staging")

        # Вставляем товары
        insert_sql = """
            INSERT INTO staging (
                outlet_code, name, article, category_raw,
                price, in_stock, url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        for p in products:
            cur.execute(insert_sql, (
                SHOP_CODE,
                p.get("name", ""),
                p.get("article", ""),
                p.get("category", ""),
                p.get("price", 0),
                p.get("in_stock", False),
                p.get("url", ""),
            ))

        conn.commit()
        print(f"Сохранено в staging: {len(products)} товаров")
    finally:
        cur.close()
        conn.close()


def process_staging():
    """Обработка staging: UPSERT в nomenclature и current_prices"""
    conn = get_db()
    cur = conn.cursor()
    try:
        ensure_outlet()

        # 1. UPSERT в nomenclature
        cur.execute("""
            INSERT INTO nomenclature (article, name, category_raw, first_seen_at, updated_at)
            SELECT DISTINCT ON (article)
                article, name, category_raw, NOW(), NOW()
            FROM staging
            WHERE article IS NOT NULL AND article != ''
            ON CONFLICT (article) DO UPDATE SET
                name = EXCLUDED.name,
                category_raw = EXCLUDED.category_raw,
                updated_at = NOW()
        """)
        nom_count = cur.rowcount
        print(f"Nomenclature: {nom_count} записей")

        # 2. UPSERT в current_prices
        cur.execute("""
            INSERT INTO current_prices (nomenclature_id, outlet_id, price, in_stock, updated_at)
            SELECT DISTINCT ON (n.id, o.id)
                n.id, o.id, s.price, s.in_stock, NOW()
            FROM staging s
            JOIN nomenclature n ON n.article = s.article
            JOIN outlets o ON o.code = s.outlet_code
            WHERE s.article IS NOT NULL AND s.article != ''
            ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
                price = EXCLUDED.price,
                in_stock = EXCLUDED.in_stock,
                updated_at = NOW()
        """)
        price_count = cur.rowcount
        print(f"Current prices: {price_count} записей")

        # 3. INSERT в price_history
        cur.execute("""
            INSERT INTO price_history (nomenclature_id, outlet_id, price, recorded_date)
            SELECT DISTINCT ON (n.id, o.id)
                n.id, o.id, s.price, CURRENT_DATE
            FROM staging s
            JOIN nomenclature n ON n.article = s.article
            JOIN outlets o ON o.code = s.outlet_code
            WHERE s.article IS NOT NULL AND s.article != ''
            ON CONFLICT (nomenclature_id, outlet_id, recorded_date) DO UPDATE SET
                price = EXCLUDED.price
        """)
        hist_count = cur.rowcount
        print(f"Price history: {hist_count} записей")

        conn.commit()

        # Статистика
        cur.execute("SELECT COUNT(*) FROM nomenclature")
        total_nom = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM current_prices WHERE in_stock = true")
        in_stock = cur.fetchone()[0]

        print(f"\n=== Итого в БД ===")
        print(f"Номенклатура: {total_nom}")
        print(f"В наличии: {in_stock}")

    finally:
        cur.close()
        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():
    arg_parser = argparse.ArgumentParser(description=f'Парсер {SHOP_NAME}')
    arg_parser.add_argument('--all', action='store_true',
                           help='Полный парсинг: сбор + БД + обработка')
    arg_parser.add_argument('--process', action='store_true',
                           help='Только обработка staging')
    arg_parser.add_argument('--no-db', action='store_true',
                           help='Не сохранять в БД')
    args = arg_parser.parse_args()

    # Только обработка
    if args.process:
        print("Обработка staging...")
        process_staging()
        return

    # Парсинг
    parser = NewShopParser()
    parser.parse_all()
    parser.save_to_json()
    parser.save_to_csv()

    # Сохранение в БД
    if not args.no_db:
        save_staging(parser.products)
        if args.all:
            process_staging()

    print("\nГотово!")


if __name__ == "__main__":
    main()
```

---

## Структура базы данных

### Создание базы данных

```bash
# На сервере
ssh root@85.198.98.104

# Создание БД
docker exec supabase-db psql -U postgres -c "CREATE DATABASE db_newshop;"
```

### Создание таблиц

```sql
-- Выполнить в db_newshop

-- 1. Outlets (торговые точки)
CREATE TABLE outlets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    city VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Staging (сырые данные)
CREATE TABLE staging (
    id SERIAL PRIMARY KEY,
    outlet_code VARCHAR(50) NOT NULL,
    name TEXT NOT NULL,
    article VARCHAR(100),
    barcode VARCHAR(50),
    brand_raw TEXT,
    model_raw TEXT,
    part_type_raw TEXT,
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    stock_level INTEGER,
    in_stock BOOLEAN DEFAULT FALSE,
    url TEXT,
    loaded_at TIMESTAMP DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_staging_outlet ON staging(outlet_code);
CREATE INDEX idx_staging_article ON staging(article);

-- 3. Nomenclature (уникальные товары)
CREATE TABLE nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) NOT NULL UNIQUE,
    barcode VARCHAR(50),
    name TEXT NOT NULL,
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    first_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_nom_brand ON nomenclature(brand);
CREATE INDEX idx_nom_model ON nomenclature(model);

-- 4. Unique nomenclature (для нормализации)
CREATE TABLE unique_nomenclature (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    canonical_article VARCHAR(100),
    nomenclature_id INTEGER REFERENCES nomenclature(id),
    zip_nomenclature_id UUID,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    is_processed BOOLEAN DEFAULT FALSE,
    confidence NUMERIC(3,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 5. Current prices (текущие цены)
CREATE TABLE current_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL REFERENCES outlets(id) ON DELETE CASCADE,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    stock_stars SMALLINT,
    in_stock BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(nomenclature_id, outlet_id)
);
CREATE INDEX idx_prices_nom ON current_prices(nomenclature_id);
CREATE INDEX idx_prices_outlet ON current_prices(outlet_id);

-- 6. Price history (история цен)
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

### Скрипт создания таблиц

```bash
# Одной командой на сервере
ssh root@85.198.98.104 'docker exec supabase-db psql -U postgres -d db_newshop -c "
CREATE TABLE IF NOT EXISTS outlets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    city VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS staging (
    id SERIAL PRIMARY KEY,
    outlet_code VARCHAR(50) NOT NULL,
    name TEXT NOT NULL,
    article VARCHAR(100),
    barcode VARCHAR(50),
    brand_raw TEXT,
    model_raw TEXT,
    part_type_raw TEXT,
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    stock_level INTEGER,
    in_stock BOOLEAN DEFAULT FALSE,
    url TEXT,
    loaded_at TIMESTAMP DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_staging_outlet ON staging(outlet_code);
CREATE INDEX IF NOT EXISTS idx_staging_article ON staging(article);
CREATE TABLE IF NOT EXISTS nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) NOT NULL UNIQUE,
    barcode VARCHAR(50),
    name TEXT NOT NULL,
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    first_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_nom_brand ON nomenclature(brand);
CREATE INDEX IF NOT EXISTS idx_nom_model ON nomenclature(model);
CREATE TABLE IF NOT EXISTS unique_nomenclature (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    canonical_article VARCHAR(100),
    nomenclature_id INTEGER REFERENCES nomenclature(id),
    zip_nomenclature_id UUID,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    is_processed BOOLEAN DEFAULT FALSE,
    confidence NUMERIC(3,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS current_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL REFERENCES outlets(id) ON DELETE CASCADE,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    stock_stars SMALLINT,
    in_stock BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(nomenclature_id, outlet_id)
);
CREATE INDEX IF NOT EXISTS idx_prices_nom ON current_prices(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_prices_outlet ON current_prices(outlet_id);
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL REFERENCES outlets(id) ON DELETE CASCADE,
    price NUMERIC(12,2),
    stock_stars SMALLINT,
    recorded_date DATE DEFAULT CURRENT_DATE,
    recorded_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(nomenclature_id, outlet_id, recorded_date)
);
CREATE INDEX IF NOT EXISTS idx_history_date ON price_history(recorded_date);
"'
```

---

## Стандартные функции

### Обязательные функции

| Функция | Описание |
|---------|----------|
| `get_db()` | Возвращает psycopg2 connection |
| `ensure_outlet()` | Создаёт outlet если не существует |
| `save_staging(products)` | TRUNCATE + INSERT в staging |
| `process_staging()` | UPSERT в nomenclature и current_prices |
| `main()` | CLI интерфейс с argparse |

### Рекомендуемые функции класса парсера

| Функция | Описание |
|---------|----------|
| `parse_all()` | Основной метод парсинга |
| `parse_product(raw)` | Преобразование сырых данных в унифицированный формат |
| `save_to_json()` | Сохранение в JSON |
| `save_to_csv()` | Сохранение в CSV |

### Унифицированный формат товара

```python
{
    # Обязательные
    "name": "Дисплей iPhone 12 Pro Max",    # Название
    "article": "GS-00012345",               # Артикул (уникальный!)
    "price": 5500.00,                       # Цена
    "in_stock": True,                       # Наличие

    # Опциональные
    "category": "Дисплеи / Apple / iPhone 12",
    "brand": "Apple",
    "model": "iPhone 12 Pro Max",
    "part_type": "Дисплей",
    "url": "https://shop.ru/product/12345",
    "barcode": "4680012345678",
    "price_wholesale": 4800.00,             # Оптовая цена
    "stock_level": 3,                       # Уровень остатка (1-5)
}
```

---

## CLI интерфейс

### Стандартные аргументы

```python
arg_parser = argparse.ArgumentParser(description='Парсер МагазинX')

# Режимы работы
arg_parser.add_argument('--all', action='store_true',
                       help='Полный парсинг: сбор + БД + обработка')
arg_parser.add_argument('--process', action='store_true',
                       help='Только обработка staging (без парсинга)')
arg_parser.add_argument('--no-db', action='store_true',
                       help='Не сохранять в БД (только файлы)')

# Опциональные (зависят от источника)
arg_parser.add_argument('--city', '-c', type=str,
                       help='Город для фильтрации')
arg_parser.add_argument('--category', type=str,
                       help='Категория для парсинга')
arg_parser.add_argument('--limit', '-l', type=int,
                       help='Лимит товаров')
arg_parser.add_argument('--parallel', '-p', action='store_true',
                       help='Параллельный парсинг')
```

### Примеры использования

```bash
# Полный парсинг с сохранением в БД
python parser.py --all

# Только парсинг без БД (для тестирования)
python parser.py --no-db

# Только обработка staging
python parser.py --process

# С ограничением количества
python parser.py --limit 100 --no-db

# Параллельный парсинг
python parser.py --parallel --all
```

---

## Тестирование

### Локальное тестирование

```bash
# 1. Проверка парсинга (без БД)
cd SHOPS/НовыйМагазин
python parser.py --limit 10 --no-db

# 2. Проверка JSON вывода
cat data/products.json | python -m json.tool | head -50

# 3. Проверка подключения к БД
python -c "
import psycopg2
conn = psycopg2.connect(
    host='85.198.98.104',
    port=5433,
    dbname='db_newshop',
    user='postgres',
    password='Mi31415926pSss!',
    sslmode='require'
)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM staging')
print(f'Staging: {cur.fetchone()[0]} rows')
conn.close()
"

# 4. Полный тест
python parser.py --all
```

### Проверка данных в БД

```sql
-- Статистика
SELECT
    (SELECT COUNT(*) FROM staging) as staging,
    (SELECT COUNT(*) FROM nomenclature) as nomenclature,
    (SELECT COUNT(*) FROM current_prices) as prices,
    (SELECT COUNT(*) FROM current_prices WHERE in_stock) as in_stock;

-- Примеры товаров
SELECT article, name, price FROM nomenclature LIMIT 10;

-- Проверка дубликатов
SELECT article, COUNT(*)
FROM nomenclature
GROUP BY article
HAVING COUNT(*) > 1;
```

---

## Деплой на сервер

### Шаг 1: Копирование файлов

```bash
# С локальной машины
scp -r SHOPS/НовыйМагазин root@85.198.98.104:/opt/parsers/newshop/
```

### Шаг 2: Установка зависимостей

```bash
ssh root@85.198.98.104

cd /opt/parsers/newshop
pip3 install -r requirements.txt
# Или отдельно:
pip3 install requests beautifulsoup4 lxml psycopg2-binary openpyxl httpx
```

### Шаг 3: Создание базы данных

```bash
docker exec supabase-db psql -U postgres -c "CREATE DATABASE db_newshop;"

# Создать таблицы (см. выше)
```

### Шаг 4: Тестовый запуск

```bash
cd /opt/parsers/newshop
python3 parser.py --limit 10 --all
```

### Шаг 5: Настройка cron

```bash
# Редактировать crontab
crontab -e

# Добавить задание (каждый день в 3:00)
0 3 * * * cd /opt/parsers/newshop && python3 parser.py --all >> /var/log/parser-newshop.log 2>&1
```

### Структура на сервере

```
/opt/parsers/
├── profi/
│   └── parse_profi.py
├── greenspark/
│   └── parser.py
├── taggsm/
│   └── parser.py
├── 05gsm/
│   └── parser.py
├── moysklad/
│   └── naffas/
│       └── parser.py
└── newshop/          # <-- Новый парсер
    ├── config.py
    ├── parser.py
    └── data/
```

---

## Интеграция с ZIP

### Регистрация источника

```sql
-- В db_zip
INSERT INTO sources (code, name, url, database_name, is_active)
VALUES ('newshop', 'НовыйМагазин', 'https://newshop.ru', 'db_newshop', true);
```

### Миграция номенклатуры в ZIP

```sql
-- 1. Создать записи в zip.nomenclature
INSERT INTO db_zip.nomenclature (article, name, brand_id, part_type_id)
SELECT
    un.canonical_article,
    un.canonical_name,
    b.id,
    pt.id
FROM db_newshop.unique_nomenclature un
LEFT JOIN db_zip.brands b ON b.normalized_name = un.brand
LEFT JOIN db_zip.part_types pt ON pt.normalized_name = un.part_type
WHERE un.is_processed = true
  AND un.zip_nomenclature_id IS NULL;

-- 2. Обновить связь
UPDATE db_newshop.unique_nomenclature un
SET zip_nomenclature_id = zn.id
FROM db_zip.nomenclature zn
WHERE zn.article = un.canonical_article
  AND un.zip_nomenclature_id IS NULL;

-- 3. Перенести цены
INSERT INTO db_zip.current_prices (nomenclature_id, outlet_id, price, in_stock)
SELECT
    un.zip_nomenclature_id,
    zo.id,
    cp.price,
    cp.in_stock
FROM db_newshop.current_prices cp
JOIN db_newshop.nomenclature n ON n.id = cp.nomenclature_id
JOIN db_newshop.unique_nomenclature un ON un.nomenclature_id = n.id
JOIN db_zip.outlets zo ON zo.source_outlet_id = cp.outlet_id
                      AND zo.source_id = (SELECT id FROM db_zip.sources WHERE code = 'newshop')
WHERE un.zip_nomenclature_id IS NOT NULL
ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
    price = EXCLUDED.price,
    in_stock = EXCLUDED.in_stock,
    updated_at = NOW();
```

### Скрипт синхронизации

Создать файл `sync_to_zip.py`:

```python
"""
Синхронизация данных из db_newshop в db_zip
"""

import psycopg2
from datetime import datetime

DB_HOST = "85.198.98.104"
DB_PORT = 5433
DB_USER = "postgres"
DB_PASSWORD = "Mi31415926pSss!"

def sync_to_zip():
    # TODO: Реализовать синхронизацию
    pass

if __name__ == "__main__":
    sync_to_zip()
```

---

## Чеклист создания парсера

- [ ] Создать папку `SHOPS/НовыйМагазин/`
- [ ] Создать `config.py` с настройками
- [ ] Создать `parser.py` с классом парсера
- [ ] Реализовать `parse_all()` для сбора товаров
- [ ] Добавить `save_staging()` и `process_staging()`
- [ ] Добавить CLI с argparse
- [ ] Создать базу данных на сервере
- [ ] Создать таблицы в БД
- [ ] Протестировать локально (`--limit 10 --no-db`)
- [ ] Протестировать с БД (`--limit 10 --all`)
- [ ] Скопировать на сервер
- [ ] Запустить полный парсинг
- [ ] Добавить в cron
- [ ] Зарегистрировать в db_zip.sources
- [ ] Обновить документацию

---

## Troubleshooting

### Ошибка подключения к БД

```
psycopg2.OperationalError: connection refused
```

Проверить:
- IP сервера: 85.198.98.104
- Порт: 5433 (не 5432!)
- sslmode: require

### Дубликаты в nomenclature

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint
```

Использовать `DISTINCT ON (article)` в INSERT:

```sql
INSERT INTO nomenclature (article, name, ...)
SELECT DISTINCT ON (article) article, name, ...
FROM staging
ON CONFLICT (article) DO UPDATE SET ...
```

### Пустой staging после парсинга

Проверить:
1. Правильность article (не пустой?)
2. Правильность outlet_code
3. Наличие outlet в таблице outlets

### Нет данных в current_prices

Проверить JOIN:
```sql
-- Должен возвращать данные
SELECT s.article, n.id, o.id
FROM staging s
JOIN nomenclature n ON n.article = s.article
JOIN outlets o ON o.code = s.outlet_code
LIMIT 10;
```

---

## Контакты

- Сервер: 85.198.98.104
- SSH: `ssh root@85.198.98.104`
- Пароль: `Mi31415926pSss!`
- PostgreSQL порт: 5433 (SSL)
