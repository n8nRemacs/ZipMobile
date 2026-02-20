# Стандарт разработки парсеров ZipMobile

> **Версия**: 1.0
> **Дата**: 2026-01-26
> **Обязателен для всех новых парсеров**

---

## Содержание

1. [Обзор архитектуры](#1-обзор-архитектуры)
2. [Структура папки парсера](#2-структура-папки-парсера)
3. [Схема базы данных](#3-схема-базы-данных)
4. [Подключение к БД](#4-подключение-к-бд)
5. [Обязательные поля данных](#5-обязательные-поля-данных)
6. [Шаблон парсера](#6-шаблон-парсера)
7. [SQL миграции](#7-sql-миграции)
8. [Требования к коду](#8-требования-к-коду)
9. [Чеклист перед релизом](#9-чеклист-перед-релизом)
10. [Примеры](#10-примеры)

---

## 1. Обзор архитектуры

### Общая схема

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ЕДИНАЯ БД (Supabase Cloud)                           │
│                 aws-1-eu-west-3.pooler.supabase.com:5432                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ЦЕНТРАЛЬНЫЕ ТАБЛИЦЫ (zip_*)              ТАБЛИЦЫ МАГАЗИНОВ ({shop}_*)      │
│  ════════════════════════════             ══════════════════════════════    │
│  zip_shops                                {shop}_nomenclature               │
│  zip_outlets                              {shop}_prices                     │
│  zip_cities                               {shop}_staging (опционально)      │
│  zip_dict_brands                                                            │
│  zip_dict_models                                                            │
│  zip_nomenclature                                                           │
│  zip_nomenclature_staging                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Поток данных

```
Парсер                    БД магазина           Центральная БД (AI)
───────                   ───────────           ─────────────────────
1. Сбор данных ─────────► {shop}_nomenclature
                          {shop}_prices
                                │
                                │ MCP /load (only_new: true)
                                ▼
                          zip_nomenclature_staging
                                │
                                │ AI-нормализация (n8n workers)
                                ▼
                          zip_nomenclature
                          zip_nomenclature_models
                          zip_nomenclature_features
                                │
                                │ sync_back_to_shops.py
                                ▼
                          {shop}_nomenclature.zip_nomenclature_id = UUID
```

---

## 2. Структура папки парсера

### Обязательные файлы

```
SHOPS/{ShopName}/
├── parser.py              # Главный файл парсера (CLI + класс)
├── config.py              # Конфигурация (URL, задержки, пути)
├── requirements.txt       # Python зависимости
├── setup_{shop}_in_zip.sql # SQL инициализация магазина и outlets
├── README.md              # Документация парсера
└── data/                  # Директория для выходных данных
    └── .gitkeep
```

### Опциональные файлы

```
SHOPS/{ShopName}/
├── n8n/                   # n8n workflows (если нужна автоматизация)
│   ├── parse_all.json
│   └── check_prices.json
├── migrations/            # Дополнительные миграции
│   └── 001_create_tables.sql
└── tests/                 # Тесты
    └── test_parser.py
```

### Правила именования

| Элемент | Формат | Пример |
|---------|--------|--------|
| Папка парсера | PascalCase или lowercase | `GreenSpark`, `signal23` |
| Код магазина | lowercase, без пробелов | `greenspark`, `signal23` |
| Префикс таблиц | lowercase + `_` | `greenspark_`, `signal23_` |
| Код outlet | `{shop}-{city}[-{number}]` | `profi-msk-1`, `taggsm-moskva` |

---

## 3. Схема базы данных

### 3.1 Таблица `{shop}_nomenclature`

Хранит уникальные товары магазина. **Один товар = одна запись**.

```sql
CREATE TABLE {shop}_nomenclature (
    -- Первичный ключ
    id SERIAL PRIMARY KEY,

    -- === ОБЯЗАТЕЛЬНЫЕ ПОЛЯ ===
    article VARCHAR(100) NOT NULL,         -- Уникальный артикул товара
    name TEXT NOT NULL,                    -- Название товара

    -- === КЛАССИФИКАЦИЯ (сырые данные) ===
    brand_raw VARCHAR(200),                -- Бренд как на сайте
    model_raw VARCHAR(200),                -- Модель как на сайте
    part_type_raw VARCHAR(200),            -- Тип запчасти как на сайте
    category_raw TEXT,                     -- Полная категория (breadcrumbs)

    -- === КЛАССИФИКАЦИЯ (нормализованные) ===
    brand VARCHAR(100),                    -- Нормализованный бренд
    model VARCHAR(200),                    -- Нормализованная модель
    part_type VARCHAR(100),                -- Нормализованный тип
    device_type VARCHAR(50),               -- Тип устройства (phone, tablet, laptop)

    -- === ДОПОЛНИТЕЛЬНЫЕ ДАННЫЕ ===
    barcode VARCHAR(50),                   -- Штрихкод EAN/UPC
    product_id VARCHAR(255),               -- ID товара на сайте поставщика

    -- === СИНХРОНИЗАЦИЯ С ЦЕНТРАЛЬНОЙ БД ===
    zip_nomenclature_id UUID,              -- FK → zip_nomenclature.id
    zip_brand_id UUID,                     -- FK → zip_dict_brands.id
    zip_part_type_id INTEGER,              -- FK → zip_part_types.id
    zip_quality_id INTEGER,                -- FK → zip_dict_qualities.id
    zip_color_id INTEGER,                  -- FK → zip_dict_colors.id
    normalized_at TIMESTAMPTZ,             -- Дата AI-нормализации

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

### 3.2 Таблица `{shop}_prices`

Хранит цены по точкам продаж. **Одна цена = одна комбинация товар + точка**.

```sql
CREATE TABLE {shop}_prices (
    -- Первичный ключ
    id SERIAL PRIMARY KEY,

    -- === СВЯЗИ ===
    nomenclature_id INTEGER NOT NULL
        REFERENCES {shop}_nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL
        REFERENCES zip_outlets(id),

    -- === ЦЕНЫ ===
    price NUMERIC(12,2),                   -- Розничная цена
    price_wholesale NUMERIC(12,2),         -- Оптовая цена (если есть)

    -- === НАЛИЧИЕ ===
    in_stock BOOLEAN DEFAULT false,        -- Есть в наличии
    stock_stars SMALLINT,                  -- Уровень наличия (1-5)
    quantity INTEGER,                      -- Точное количество (если известно)

    -- === ДОПОЛНИТЕЛЬНО ===
    product_url TEXT,                      -- URL товара на сайте для этой точки

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

### 3.3 Таблица `{shop}_staging` (опционально)

Временная таблица для пакетной загрузки.

```sql
CREATE TABLE {shop}_staging (
    id SERIAL PRIMARY KEY,

    -- Идентификация
    outlet_code VARCHAR(50),
    article VARCHAR(100),

    -- Данные
    name TEXT,
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    barcode VARCHAR(50),

    -- Цены и наличие
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    in_stock BOOLEAN,
    quantity INTEGER,

    -- URL
    product_url TEXT,

    -- Метаданные
    loaded_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. Подключение к БД

### 4.1 Использование db_wrapper

**ОБЯЗАТЕЛЬНО** использовать `db_wrapper.py` для подключения:

```python
# В начале парсера
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db

# Использование
conn = get_db()
cur = conn.cursor()
try:
    cur.execute("SELECT * FROM nomenclature")  # Автоматически → {shop}_nomenclature
    # ...
    conn.commit()
finally:
    cur.close()
    conn.close()
```

### 4.2 Регистрация префикса

Добавить префикс в `SHOPS/db_config.py`:

```python
TABLE_PREFIXES = {
    # ... существующие
    "newshop": "newshop",  # ← добавить
}
```

### 4.3 Маппинг таблиц (если нужно)

Если используются нестандартные имена таблиц, добавить в `SHOPS/db_wrapper.py`:

```python
TABLE_MAPPING = {
    # ... существующие
    "my_custom_table": "newshop_nomenclature",  # ← добавить
}
```

---

## 5. Обязательные поля данных

### 5.1 Поля товара (nomenclature)

| Поле | Обязательно | Описание | Источник |
|------|-------------|----------|----------|
| `article` | **ДА** | Уникальный идентификатор товара | SKU, артикул, product_id |
| `name` | **ДА** | Полное название товара | Заголовок страницы |
| `category_raw` | Желательно | Категория из breadcrumbs | Навигация сайта |
| `brand_raw` | Желательно | Бренд как на сайте | Характеристики / название |
| `model_raw` | Желательно | Модель как на сайте | Характеристики / название |
| `part_type_raw` | Желательно | Тип запчасти | Категория / название |
| `barcode` | Опционально | Штрихкод EAN-13 | Характеристики |
| `product_id` | Опционально | ID на сайте поставщика | URL / скрытые поля |

### 5.2 Поля цены (prices)

| Поле | Обязательно | Описание | Источник |
|------|-------------|----------|----------|
| `nomenclature_id` | **ДА** | FK на товар | После UPSERT |
| `outlet_id` | **ДА** | FK на точку | Из zip_outlets |
| `price` | **ДА** | Розничная цена | Страница товара |
| `in_stock` | **ДА** | Наличие (true/false) | Статус / кнопка купить |
| `price_wholesale` | Опционально | Оптовая цена | Если есть |
| `stock_stars` | Опционально | Уровень наличия 1-5 | Визуальный индикатор |
| `quantity` | Опционально | Точное количество | Если показывается |
| `product_url` | Желательно | URL товара | Для проверки |

### 5.3 Генерация article

Если артикул не найден на сайте, генерировать по схеме:

```python
def generate_article(url: str, prefix: str = "XX") -> str:
    """
    Генерация артикула из URL

    Args:
        url: URL товара
        prefix: 2-3 буквы кода магазина (GS, TG, LB, S23)

    Returns:
        Артикул в формате: {PREFIX}-{slug}
    """
    from urllib.parse import urlparse
    path = urlparse(url).path
    slug = path.rstrip('/').split('/')[-1]
    slug = slug.replace('.html', '').replace('.htm', '')
    return f"{prefix}-{slug[:50]}"

# Примеры:
# https://signal23.ru/products/display-iphone-14.html → S23-display-iphone-14
# https://greenspark.ru/p/12345 → GS-12345
```

---

## 6. Шаблон парсера

### 6.1 Минимальный шаблон parser.py

```python
"""
Парсер {ShopName} - {описание}

База данных: {shop}_nomenclature, {shop}_prices
Тип парсинга: HTML / API / Excel
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import argparse
from datetime import datetime
from typing import Optional, List, Dict

# === КОНФИГУРАЦИЯ БД ===
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db

# === КОНСТАНТЫ МАГАЗИНА ===
SHOP_CODE = "{shop}"           # Код магазина (lowercase)
SHOP_NAME = "{ShopName}"       # Название для логов
SHOP_PREFIX = "{XX}"           # Префикс для артикулов (2-3 буквы)

# === ИМПОРТ КОНФИГУРАЦИИ ===
from config import (
    BASE_URL,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    USER_AGENT,
    DATA_DIR,
)


class {ShopName}Parser:
    """Парсер каталога {ShopName}"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })
        self.products: List[Dict] = []
        self.errors: List[Dict] = []
        self.last_request_time = 0

        os.makedirs(DATA_DIR, exist_ok=True)

    def _delay(self):
        """Задержка между запросами"""
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, url: str, retries: int = MAX_RETRIES) -> Optional[requests.Response]:
        """HTTP запрос с повторами и exponential backoff"""
        self._delay()

        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # 1, 2, 4 сек
                else:
                    self.errors.append({
                        "url": url,
                        "error": str(e),
                        "time": datetime.now().isoformat()
                    })
        return None

    def parse_all(self, limit: int = None) -> List[Dict]:
        """
        Основной метод парсинга

        Args:
            limit: Максимальное количество товаров (для тестов)

        Returns:
            Список товаров
        """
        print(f"{'='*60}")
        print(f"Парсинг {SHOP_NAME}")
        print(f"{'='*60}\n")

        # TODO: Реализовать логику парсинга
        # 1. Получить список категорий/страниц
        # 2. Обойти каждую категорию
        # 3. Спарсить товары
        # 4. Добавить в self.products

        print(f"\nИтого: {len(self.products)} товаров, {len(self.errors)} ошибок")
        return self.products

    def _parse_product(self, url: str) -> Optional[Dict]:
        """
        Парсинг страницы товара

        Returns:
            Dict с полями: article, name, price, in_stock, category_raw,
                          brand_raw, model_raw, part_type_raw, barcode, url
        """
        response = self._make_request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        try:
            product = {
                "url": url,
                "parsed_at": datetime.now().isoformat(),
            }

            # 1. Название (ОБЯЗАТЕЛЬНО)
            h1 = soup.find('h1')
            product["name"] = h1.get_text(strip=True) if h1 else ""

            # 2. Артикул (ОБЯЗАТЕЛЬНО)
            # TODO: Найти артикул на странице
            product["article"] = self._extract_article(soup, url)

            # 3. Цена (ОБЯЗАТЕЛЬНО)
            product["price"] = self._extract_price(soup)

            # 4. Наличие (ОБЯЗАТЕЛЬНО)
            product["in_stock"] = self._extract_stock(soup)

            # 5. Категория (breadcrumbs)
            product["category_raw"] = self._extract_category(soup)

            # 6. Бренд, модель, тип (опционально)
            product["brand_raw"] = self._extract_brand(soup)
            product["model_raw"] = self._extract_model(soup)
            product["part_type_raw"] = self._extract_part_type(soup)

            # 7. Штрихкод (опционально)
            product["barcode"] = self._extract_barcode(soup)

            # Валидация обязательных полей
            if not product["name"] or not product["article"]:
                return None

            return product

        except Exception as e:
            self.errors.append({
                "url": url,
                "error": str(e),
                "time": datetime.now().isoformat()
            })
            return None

    def _extract_article(self, soup: BeautifulSoup, url: str) -> str:
        """Извлечение артикула"""
        # TODO: Реализовать для конкретного сайта
        # Пример: ищем в мета-тегах, таблице характеристик, тексте
        return f"{SHOP_PREFIX}-unknown"

    def _extract_price(self, soup: BeautifulSoup) -> float:
        """Извлечение цены"""
        # TODO: Реализовать для конкретного сайта
        return 0.0

    def _extract_stock(self, soup: BeautifulSoup) -> bool:
        """Извлечение наличия"""
        # TODO: Реализовать для конкретного сайта
        return False

    def _extract_category(self, soup: BeautifulSoup) -> str:
        """Извлечение категории из breadcrumbs"""
        breadcrumbs = soup.select('.breadcrumb a, .breadcrumb li')
        if breadcrumbs:
            return ' / '.join([b.get_text(strip=True) for b in breadcrumbs[1:]])
        return ""

    def _extract_brand(self, soup: BeautifulSoup) -> str:
        """Извлечение бренда"""
        return ""

    def _extract_model(self, soup: BeautifulSoup) -> str:
        """Извлечение модели"""
        return ""

    def _extract_part_type(self, soup: BeautifulSoup) -> str:
        """Извлечение типа запчасти"""
        return ""

    def _extract_barcode(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение штрихкода"""
        return None

    # === СОХРАНЕНИЕ ===

    def save_to_json(self, filename: str = None):
        """Сохранить в JSON"""
        filename = filename or f"{DATA_DIR}/products.json"
        data = {
            "source": SHOP_NAME,
            "url": BASE_URL,
            "date": datetime.now().isoformat(),
            "total": len(self.products),
            "products": self.products,
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Сохранено: {filename}")

    def save_to_csv(self, filename: str = None):
        """Сохранить в CSV"""
        import csv
        filename = filename or f"{DATA_DIR}/products.csv"
        if not self.products:
            return

        fieldnames = ["article", "name", "price", "in_stock", "category_raw", "url"]
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.products)
        print(f"Сохранено: {filename}")


# === ФУНКЦИИ РАБОТЫ С БД ===

def ensure_outlet(outlet_code: str, city: str, name: str):
    """Создаёт outlet если не существует"""
    conn = get_db()
    cur = conn.cursor()
    try:
        # Получаем shop_id
        cur.execute("SELECT id FROM zip_shops WHERE code = %s", (SHOP_CODE,))
        shop_row = cur.fetchone()
        if not shop_row:
            print(f"WARN: Магазин {SHOP_CODE} не найден в zip_shops!")
            return
        shop_id = shop_row[0]

        # Получаем city_id (или создаём)
        cur.execute("SELECT id FROM zip_cities WHERE name ILIKE %s", (city,))
        city_row = cur.fetchone()
        city_id = city_row[0] if city_row else None

        # Создаём outlet
        cur.execute("""
            INSERT INTO zip_outlets (shop_id, city_id, code, name, is_active)
            VALUES (%s, %s, %s, %s, true)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                is_active = true
        """, (shop_id, city_id, outlet_code, name))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def save_to_db(products: List[Dict], outlet_code: str):
    """
    Сохранение в БД: {shop}_nomenclature + {shop}_prices

    Args:
        products: Список товаров
        outlet_code: Код торговой точки
    """
    if not products:
        print("Нет товаров для сохранения")
        return

    conn = get_db()
    cur = conn.cursor()
    try:
        # Получаем outlet_id
        cur.execute("SELECT id FROM zip_outlets WHERE code = %s", (outlet_code,))
        outlet_row = cur.fetchone()
        if not outlet_row:
            print(f"ERROR: outlet {outlet_code} не найден!")
            return
        outlet_id = outlet_row[0]

        saved_nom = 0
        saved_prices = 0

        for p in products:
            article = p.get("article", "").strip()
            name = p.get("name", "").strip()

            if not article or not name:
                continue

            # UPSERT в nomenclature
            cur.execute(f"""
                INSERT INTO {SHOP_CODE}_nomenclature (
                    article, name, barcode,
                    brand_raw, model_raw, part_type_raw, category_raw,
                    first_seen_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (article) DO UPDATE SET
                    name = EXCLUDED.name,
                    barcode = COALESCE(EXCLUDED.barcode, {SHOP_CODE}_nomenclature.barcode),
                    brand_raw = COALESCE(EXCLUDED.brand_raw, {SHOP_CODE}_nomenclature.brand_raw),
                    model_raw = COALESCE(EXCLUDED.model_raw, {SHOP_CODE}_nomenclature.model_raw),
                    part_type_raw = COALESCE(EXCLUDED.part_type_raw, {SHOP_CODE}_nomenclature.part_type_raw),
                    category_raw = EXCLUDED.category_raw,
                    updated_at = NOW()
                RETURNING id
            """, (
                article,
                name,
                p.get("barcode"),
                p.get("brand_raw"),
                p.get("model_raw"),
                p.get("part_type_raw"),
                p.get("category_raw"),
            ))

            nom_row = cur.fetchone()
            if not nom_row:
                continue
            nom_id = nom_row[0]
            saved_nom += 1

            # UPSERT в prices
            cur.execute(f"""
                INSERT INTO {SHOP_CODE}_prices (
                    nomenclature_id, outlet_id,
                    price, price_wholesale, in_stock, quantity,
                    product_url, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
                    price = EXCLUDED.price,
                    price_wholesale = EXCLUDED.price_wholesale,
                    in_stock = EXCLUDED.in_stock,
                    quantity = EXCLUDED.quantity,
                    product_url = EXCLUDED.product_url,
                    updated_at = NOW()
            """, (
                nom_id,
                outlet_id,
                p.get("price", 0),
                p.get("price_wholesale"),
                p.get("in_stock", False),
                p.get("quantity"),
                p.get("url"),
            ))
            saved_prices += 1

        conn.commit()

        print(f"\n=== Сохранено в БД ===")
        print(f"{SHOP_CODE}_nomenclature: {saved_nom}")
        print(f"{SHOP_CODE}_prices: {saved_prices}")

    finally:
        cur.close()
        conn.close()


# === MAIN ===

def main():
    arg_parser = argparse.ArgumentParser(description=f'Парсер {SHOP_NAME}')
    arg_parser.add_argument('--all', action='store_true', help='Полный парсинг')
    arg_parser.add_argument('--no-db', action='store_true', help='Не сохранять в БД')
    arg_parser.add_argument('--limit', '-l', type=int, help='Лимит товаров')
    arg_parser.add_argument('--outlet', type=str, default=f'{SHOP_CODE}-online',
                          help='Код торговой точки')
    args = arg_parser.parse_args()

    parser = {ShopName}Parser()
    parser.parse_all(limit=args.limit)

    # Сохранение локально
    parser.save_to_json()
    parser.save_to_csv()

    # Сохранение в БД
    if not args.no_db:
        save_to_db(parser.products, args.outlet)

    print("\nГотово!")


if __name__ == "__main__":
    main()
```

### 6.2 Шаблон config.py

```python
"""
Конфигурация парсера {ShopName}
"""

import os

# === URL ===
BASE_URL = "https://example.com"

# === СТАРТОВЫЕ КАТЕГОРИИ ===
START_CATEGORIES = [
    "/catalog/zapchasti-dlya-telefonov",
    "/catalog/akkumulyatory",
]

# === НАСТРОЙКИ ЗАПРОСОВ ===
REQUEST_DELAY = 0.5          # Секунд между запросами
REQUEST_TIMEOUT = 30         # Таймаут запроса
MAX_RETRIES = 3              # Максимум повторов
ITEMS_PER_PAGE = 100         # Товаров на страницу (для API)

# === USER AGENT ===
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# === ПУТИ К ФАЙЛАМ ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

PRODUCTS_JSON = os.path.join(DATA_DIR, "products.json")
PRODUCTS_CSV = os.path.join(DATA_DIR, "products.csv")
CATEGORIES_JSON = os.path.join(DATA_DIR, "categories.json")
ERRORS_LOG = os.path.join(DATA_DIR, "errors.json")
```

### 6.3 Шаблон requirements.txt

```
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
psycopg2-binary>=2.9.0
openpyxl>=3.0.0
```

---

## 7. SQL миграции

### 7.1 Файл setup_{shop}_in_zip.sql

```sql
-- Инициализация магазина {ShopName} в архитектуре zip_*
-- Выполнить ОДИН РАЗ перед первым запуском парсера

-- ============================================
-- 1. МАГАЗИН (zip_shops)
-- ============================================

INSERT INTO zip_shops (code, name, website, shop_type, parser_enabled, is_active)
VALUES (
    '{shop}',
    '{ShopName}',
    'https://example.com',
    'retailer',  -- или 'wholesale', 'distributor'
    true,
    true
)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    website = EXCLUDED.website,
    parser_enabled = EXCLUDED.parser_enabled;

-- ============================================
-- 2. ТОРГОВЫЕ ТОЧКИ (zip_outlets)
-- ============================================

WITH shop AS (
    SELECT id FROM zip_shops WHERE code = '{shop}'
),
cities AS (
    SELECT code, id FROM zip_cities
)
INSERT INTO zip_outlets (shop_id, city_id, code, name, stock_mode, is_active)
SELECT
    s.id,
    c.id,
    v.outlet_code,
    v.outlet_name,
    'parse',
    true
FROM shop s
CROSS JOIN (VALUES
    ('moskva', '{shop}-msk', '{ShopName} Москва'),
    ('spb', '{shop}-spb', '{ShopName} СПб')
    -- Добавить остальные точки
) AS v(city_code, outlet_code, outlet_name)
LEFT JOIN cities c ON c.code = v.city_code
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    is_active = EXCLUDED.is_active;

-- ============================================
-- 3. ТАБЛИЦЫ МАГАЗИНА
-- ============================================

-- Номенклатура
CREATE TABLE IF NOT EXISTS {shop}_nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    product_id VARCHAR(255),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT {shop}_nomenclature_article_unique UNIQUE (article)
);

-- Цены
CREATE TABLE IF NOT EXISTS {shop}_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES {shop}_nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL REFERENCES zip_outlets(id),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    in_stock BOOLEAN DEFAULT false,
    stock_stars SMALLINT,
    quantity INTEGER,
    product_url TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT {shop}_prices_unique UNIQUE (nomenclature_id, outlet_id)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_{shop}_nom_brand ON {shop}_nomenclature(brand);
CREATE INDEX IF NOT EXISTS idx_{shop}_nom_zip_id ON {shop}_nomenclature(zip_nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_{shop}_nom_updated ON {shop}_nomenclature(updated_at);
CREATE INDEX IF NOT EXISTS idx_{shop}_prices_outlet ON {shop}_prices(outlet_id);
CREATE INDEX IF NOT EXISTS idx_{shop}_prices_in_stock ON {shop}_prices(in_stock);

-- ============================================
-- 4. ПРОВЕРКА
-- ============================================

SELECT
    s.code AS shop,
    o.code AS outlet,
    c.name AS city
FROM zip_outlets o
JOIN zip_shops s ON o.shop_id = s.id
LEFT JOIN zip_cities c ON o.city_id = c.id
WHERE s.code = '{shop}'
ORDER BY c.name;
```

---

## 8. Требования к коду

### 8.1 Обязательные требования

| # | Требование | Причина |
|---|------------|---------|
| 1 | Использовать `db_wrapper.get_db()` | Единообразие, маппинг таблиц |
| 2 | Задержка между запросами ≥ 0.3 сек | Защита от блокировки |
| 3 | Exponential backoff при ошибках | Устойчивость к сбоям |
| 4 | Логирование ошибок в errors.json | Отладка и мониторинг |
| 5 | UPSERT по article (не INSERT) | Идемпотентность |
| 6 | Обрабатывать исключения | Не ломать весь парсинг из-за одного товара |
| 7 | CLI с аргументами (--all, --limit) | Удобство запуска |
| 8 | Сохранять в JSON и CSV | Резервные копии |

### 8.2 Рекомендации

```python
# ✅ ХОРОШО: UPSERT
cur.execute("""
    INSERT INTO nomenclature (article, name, ...)
    VALUES (%s, %s, ...)
    ON CONFLICT (article) DO UPDATE SET
        name = EXCLUDED.name,
        updated_at = NOW()
""", (article, name, ...))

# ❌ ПЛОХО: INSERT без ON CONFLICT
cur.execute("INSERT INTO nomenclature ...", ...)


# ✅ ХОРОШО: Параметризованные запросы
cur.execute("SELECT * FROM t WHERE id = %s", (id,))

# ❌ ПЛОХО: f-строки в SQL
cur.execute(f"SELECT * FROM t WHERE id = {id}")


# ✅ ХОРОШО: Context manager
with get_db() as conn:
    cur = conn.cursor()
    ...

# ❌ ПЛОХО: Без закрытия соединения
conn = get_db()
cur = conn.cursor()
# забыли conn.close()


# ✅ ХОРОШО: Обработка ошибок
try:
    product = self._parse_product(url)
except Exception as e:
    self.errors.append({"url": url, "error": str(e)})
    continue

# ❌ ПЛОХО: Падение на первой ошибке
product = self._parse_product(url)  # упадёт весь парсер
```

### 8.3 Форматирование кода

- Python 3.9+
- PEP 8 стиль
- Type hints для публичных методов
- Docstrings для классов и методов

---

## 9. Чеклист перед релизом

### Структура

- [ ] Папка `SHOPS/{ShopName}/` создана
- [ ] `parser.py` — главный файл
- [ ] `config.py` — конфигурация
- [ ] `requirements.txt` — зависимости
- [ ] `setup_{shop}_in_zip.sql` — миграция
- [ ] `README.md` — документация
- [ ] `data/` — директория для данных

### Конфигурация БД

- [ ] Префикс добавлен в `db_config.py` → `TABLE_PREFIXES`
- [ ] Маппинг добавлен в `db_wrapper.py` (если нужно)
- [ ] SQL миграция выполнена на Supabase
- [ ] Магазин добавлен в `zip_shops`
- [ ] Торговые точки добавлены в `zip_outlets`

### Код парсера

- [ ] Использует `from db_wrapper import get_db`
- [ ] Задержка между запросами ≥ 0.3 сек
- [ ] Exponential backoff при ошибках
- [ ] Логирование ошибок
- [ ] UPSERT вместо INSERT
- [ ] CLI аргументы (--all, --limit, --no-db)
- [ ] Сохранение в JSON и CSV

### Данные

- [ ] Поле `article` — уникальный идентификатор
- [ ] Поле `name` — заполнено
- [ ] Поле `price` — числовое
- [ ] Поле `in_stock` — boolean
- [ ] Поле `category_raw` — breadcrumbs

### Тестирование

- [ ] Парсер запускается без ошибок
- [ ] `--limit 10` работает
- [ ] `--no-db` работает
- [ ] Данные корректно сохраняются в БД
- [ ] UPSERT работает (повторный запуск не дублирует)

---

## 10. Примеры

### Существующие парсеры (эталоны)

| Парсер | Тип | Особенности |
|--------|-----|-------------|
| `signal23` | HTML | Простой, OpenCart, хороший пример |
| `Orizhka` | API | Tilda Store API, JSON |
| `Liberti` | Excel | Парсинг прайс-листов |
| `GreenSpark` | Distributed | Координация через PostgreSQL |
| `Profi` | Excel | Много городов, нормализация |

### Команды запуска

```bash
# Тестовый запуск (10 товаров, без БД)
python parser.py --limit 10 --no-db

# Полный парсинг
python parser.py --all

# Парсинг для конкретной точки
python parser.py --all --outlet myshop-msk

# Только обработка staging (если используется)
python parser.py --process
```

### Проверка данных в БД

```sql
-- Статистика по магазину
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE zip_nomenclature_id IS NOT NULL) AS normalized,
    MAX(updated_at) AS last_update
FROM {shop}_nomenclature;

-- Товары без нормализации (для AI)
SELECT article, name, category_raw
FROM {shop}_nomenclature
WHERE zip_nomenclature_id IS NULL
LIMIT 100;

-- Цены по точкам
SELECT
    o.code AS outlet,
    COUNT(*) AS products,
    COUNT(*) FILTER (WHERE p.in_stock) AS in_stock,
    AVG(p.price) AS avg_price
FROM {shop}_prices p
JOIN zip_outlets o ON o.id = p.outlet_id
GROUP BY o.code;
```

---

## Приложение: Типы парсеров

### A. HTML парсер (BeautifulSoup)

Для обычных сайтов с серверным рендерингом.

```python
soup = BeautifulSoup(response.text, 'html.parser')
name = soup.select_one('h1').get_text(strip=True)
price = soup.select_one('.price').get_text()
```

### B. API парсер (JSON)

Для сайтов с REST API (Tilda, OpenCart API, etc.)

```python
response = self.session.get(f"{API_URL}/products", params={"limit": 100})
data = response.json()
for item in data["products"]:
    product = {
        "article": item["sku"],
        "name": item["title"],
        "price": item["price"],
    }
```

### C. Excel парсер (openpyxl)

Для прайс-листов в формате Excel.

```python
from openpyxl import load_workbook

wb = load_workbook(filename)
ws = wb.active

for row in ws.iter_rows(min_row=2, values_only=True):
    product = {
        "article": row[0],
        "name": row[1],
        "price": row[2],
    }
```

### D. Защищённый парсер (Playwright/CDP)

Для сайтов с защитой от ботов.

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(url)
    # ... парсинг через page.query_selector()
```

---

**Автор**: AI Assistant
**Проект**: ZipMobile
**Лицензия**: Internal Use Only
