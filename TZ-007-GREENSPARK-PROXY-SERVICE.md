# ТЗ-7: Переработка парсера GreenSpark — интеграция с proxy-service
Обновлено: 2026-02-18 19:30 (GMT+4)

## Контекст

### Текущее состояние парсера

`SHOPS/GreenSpark/parser_v3.py` (1483 строки) — production парсер green-spark.ru v3.5.

**Что он делает:**
- Парсит каталог комплектующих через API `green-spark.ru/local/api/catalog/products/`
- 60 городов, ~10-30 тыс. товаров на город, 2 типа цен (розница + грин 5)
- Рекурсивный обход категорий с пагинацией (100 товаров/страница)
- Допарсинг артикулов (API + HTML fallback)
- Инкрементальное сохранение каждые 200 товаров

**Система обхода блокировок (IPRotator):**
- 4 сервера (server-a: 85.198.98.104, server-b-ip1: 155.212.221.189, server-b-ip2: 217.114.14.17, server-c: 155.212.221.67)
- SSH SOCKS5 туннели между серверами (`ssh -D {port} -N user@host`)
- При бане → переключение на другой сервер через SSH туннель
- Если все забанены → ожидание 50-70 мин и повтор
- Cookies через Playwright + Xvfb на каждом сервере (обход headless-детекции)
- Telegram-уведомления о банах, переключениях, завершении

**БД:** отдельная `db_greenspark` на 85.198.98.104:5433 (НЕ Supabase, НЕ Homelab).

### Проблемы текущей версии

| # | Проблема | Последствия |
|---|----------|-------------|
| 1 | **Свой IPRotator** — 4 хардкод-сервера, SSH туннели, ручное управление | Сложно масштабировать, падает при недоступности сервера |
| 2 | **Своя БД** (db_greenspark на 85.198.98.104) | Изолирована от остальной платформы, не стандартизирована |
| 3 | **Нет staging** | Прямой UPSERT в nomenclature/prices, нет промежуточного этапа |
| 4 | **Cookies через Xvfb** на каждом сервере | Требует Playwright + Xvfb на всех 4 серверах |
| 5 | **Синхронный httpx** | Один запрос за раз, не использует возможности asyncio |
| 6 | **Не на Homelab** | Не вписывается в архитектуру ТЗ-6 (все парсеры → Homelab PostgreSQL) |
| 7 | **Coordinator на db_greenspark** | Координация между серверами через отдельную БД |

### Что уже есть

- **proxy-service** (порт 8110) — универсальный прокси-менеджер на Homelab:
  - `GET /proxy/get?protocol=http&for_site=greenspark` — выдаёт проверенный прокси с quick-test
  - `POST /proxy/report` — обратная связь (success/fail/banned_site)
  - Per-site бан-трекинг (прокси забаненный на greenspark не выдаётся для greenspark)
  - 34 источника, 4 протокола, ежедневный refresh
- **Homelab PostgreSQL** (213.108.170.194:5433) — целевая БД для всех парсеров (ТЗ-6)
- **Стандарт парсеров** (ТЗ-5) — save_staging → process_staging, db_wrapper

---

## Цель

Переписать GreenSpark парсер так, чтобы:

1. **Прокси** получал от proxy-service (вместо SSH-туннелей между серверами)
2. **БД** писал в Homelab PostgreSQL (вместо отдельной db_greenspark)
3. **Стандарт** — save_staging + process_staging (ТЗ-5)
4. **Cookies** — получал на Homelab (один сервер), через прокси при необходимости
5. **Запускался на Homelab** — один сервер вместо 4

---

## Архитектура (было → стало)

### Было

```
[server-a] ──SSH──> [server-b] ──SSH──> [server-c]
    │                    │                    │
    └── parser_v3.py     └── parser_v3.py     └── parser_v3.py
         │                    │                    │
         └── httpx            └── httpx            └── httpx
              │                    │                    │
              ▼                    ▼                    ▼
         green-spark.ru      green-spark.ru      green-spark.ru

         Координация через db_greenspark (LISTEN/NOTIFY)
         Cookies: Playwright + Xvfb на каждом сервере
```

### Стало

```
[Homelab 213.108.170.194]
    │
    ├── proxy-service (:8110)
    │   └── GET /proxy/get?protocol=http&for_site=greenspark
    │       → Проверенный прокси из пула 5000+ IP
    │
    ├── greenspark parser (новый)
    │   └── httpx + прокси от proxy-service
    │       → green-spark.ru
    │
    └── PostgreSQL (:5433)
        ├── greenspark_staging     (промежуточные)
        ├── greenspark_nomenclature (товары)
        └── greenspark_prices      (цены по городам)

    Cookies: Playwright + Xvfb на Homelab (один раз)
    Без SSH-туннелей, без координатора, без мультисерверности
```

---

## Что создаём / меняем

### Новый файл: `SHOPS/GreenSpark/parser_v4.py`

Полная переработка parser_v3.py. Старый файл НЕ удаляем (оставляем как fallback).

### Структура нового парсера

```python
# parser_v4.py — GreenSpark парсер v4 (proxy-service + Homelab DB + staging)

class ProxyClient:
    """Получение и ротация прокси через proxy-service."""
    PROXY_SERVICE_URL = "http://localhost:8110"  # или 213.108.170.194:8110

    async def get_proxy(self) -> dict           # GET /proxy/get?protocol=http&for_site=greenspark
    async def report(self, proxy, success, ...) # POST /proxy/report
    def format_proxy_url(self, proxy) -> str    # → "http://host:port"

class CookieManager:
    """Получение cookies через Playwright (локально на Homelab)."""
    async def get_cookies(self, proxy_url=None) -> dict
    def load_cookies(self) -> dict
    def save_cookies(self, cookies: dict)

class GreenSparkParser:
    """Парсер каталога."""
    # Ядро парсинга — ТА ЖЕ логика что в v3:
    # - crawl_category() рекурсия
    # - extract_product_info()
    # - extract_article / fetch_article_from_page
    # - multi-city loop
    #
    # НО:
    # - httpx Client создаётся с proxy=ProxyClient.get_proxy()
    # - При бане → ProxyClient.report(banned_site='greenspark') → новый прокси
    # - Нет IPRotator, нет SSH туннелей
    # - Нет Coordinator

def save_staging(products, city_id=None):
    """Стандартная save_staging (ТЗ-5)."""
    # INSERT INTO greenspark_staging

def process_staging():
    """Стандартная process_staging (ТЗ-5)."""
    # staging → greenspark_nomenclature (UPSERT по product_url)
    # staging → greenspark_prices (UPSERT по nomenclature_id + outlet_id)

def main():
    # argparse: --all-cities, --city, --skip-parsed, --process, --no-db
```

---

## Детали реализации

### 1. ProxyClient — интеграция с proxy-service

```python
import httpx

class ProxyClient:
    """Интеграция с proxy-service для получения прокси."""

    def __init__(self, base_url: str = "http://localhost:8110"):
        self.base_url = base_url
        self.current_proxy = None
        self._client = httpx.Client(timeout=10)

    def get_proxy(self) -> dict:
        """Получить проверенный прокси для greenspark."""
        resp = self._client.get(f"{self.base_url}/proxy/get", params={
            "protocol": "http",
            "for_site": "greenspark",
        })
        if resp.status_code == 200:
            self.current_proxy = resp.json()
            return self.current_proxy
        return None

    def report_success(self, response_time: float = None):
        """Сообщить об успешном использовании."""
        if not self.current_proxy:
            return
        self._client.post(f"{self.base_url}/proxy/report", json={
            "host": self.current_proxy["host"],
            "port": self.current_proxy["port"],
            "success": True,
            "response_time": response_time,
        })

    def report_failure(self, banned: bool = False):
        """Сообщить о неудаче (бан или timeout)."""
        if not self.current_proxy:
            return
        payload = {
            "host": self.current_proxy["host"],
            "port": self.current_proxy["port"],
            "success": False,
        }
        if banned:
            payload["banned_site"] = "greenspark"
        self._client.post(f"{self.base_url}/proxy/report", json=payload)

    @property
    def proxy_url(self) -> str:
        """Текущий прокси в формате для httpx."""
        if self.current_proxy:
            return f"http://{self.current_proxy['host']}:{self.current_proxy['port']}"
        return None
```

### 2. Обработка блокировок (вместо IPRotator)

**Было (v3):** бан → SSH-туннель к другому серверу → cookies через Xvfb там → продолжить.

**Стало (v4):**
```
бан → report_failure(banned=True) → get_proxy() (новый прокси из пула)
    → пересоздать httpx.Client с новым proxy → продолжить

Если proxy-service вернул 404 (нет прокси):
    → ожидание 5 мин → повтор (proxy-service мог обновить пул)
    → максимум 3 попытки → завершение с сохранением прогресса
```

**Ключевое отличие:** Пул proxy-service содержит тысячи IP. Смена прокси — мгновенная (~100мс), без SSH, без ожидания разбана. Если один прокси забанен — берём следующий.

### 3. Cookies

**Было:** Playwright + Xvfb на каждом из 4 серверов.

**Стало:** Playwright + Xvfb **только на Homelab**. Cookies не привязаны к IP (cookies = сессия сайта, а не IP). Прокси меняется, cookies остаются.

```python
class CookieManager:
    COOKIES_FILE = "cookies.json"

    def get_cookies(self, shop_id: str = "16344") -> dict:
        """Получить cookies через Playwright (локально)."""
        # Запуск xvfb-run python get_cookies_inline.py
        # Тот же скрипт что в v3, но БЕЗ SSH к другим серверам
        ...

    def load_cookies(self) -> dict:
        """Загрузить из файла."""
        ...

    def are_valid(self, cookies: dict) -> bool:
        """Проверить что cookies ещё действительны (тестовый запрос)."""
        ...
```

**Когда обновлять cookies:**
- При старте парсера (если файл старше 12ч или отсутствует)
- При получении не-JSON ответа (SmartCaptcha, redirect на капчу)
- Каждые 3000 товаров (профилактика, как в v3)

### 4. БД — Homelab PostgreSQL

**Подключение:**
```python
# Через db_config.py (стандарт ТЗ-6)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import get_local_config

def get_db():
    config = get_local_config()
    return psycopg2.connect(**config)
```

Или напрямую:
```
postgresql://postgres:Mi31415926pSss!@213.108.170.194:5433/postgres
```

### 5. Таблицы (Homelab PostgreSQL)

Используются существующие таблицы. Если их нет — создать при первом запуске.

#### greenspark_staging (промежуточная, TRUNCATE перед каждым городом)

```sql
CREATE TABLE IF NOT EXISTS greenspark_staging (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    product_url     TEXT NOT NULL,
    article         TEXT,
    category        TEXT,
    price           NUMERIC(10,2) DEFAULT 0,
    price_wholesale NUMERIC(10,2) DEFAULT 0,
    in_stock        BOOLEAN DEFAULT FALSE,
    city_id         INTEGER,
    city_name       TEXT,
    outlet_code     TEXT,                     -- 'greenspark-{city_id}'
    created_at      TIMESTAMP DEFAULT NOW()
);
```

#### greenspark_nomenclature (уникальные товары, UPSERT по product_url)

```sql
-- Уже существует, ключевые поля:
-- id, name, product_url (UNIQUE), article, category,
-- first_seen_at, updated_at
```

#### greenspark_prices (цены по городам, UPSERT по nomenclature_id + outlet_id)

```sql
-- Уже существует, ключевые поля:
-- id, nomenclature_id, outlet_id, price, price_wholesale,
-- in_stock, updated_at
```

### 6. save_staging / process_staging (стандарт ТЗ-5)

```python
def save_staging(products: List[Dict], city_id: int = None):
    """Сохранить сырые данные в staging."""
    conn = get_db()
    cur = conn.cursor()

    # TRUNCATE только данные этого города (не весь staging)
    if city_id:
        cur.execute("DELETE FROM greenspark_staging WHERE city_id = %s", (city_id,))
    else:
        cur.execute("TRUNCATE TABLE greenspark_staging")

    for p in products:
        outlet_code = f"greenspark-{p.get('city_id')}" if p.get('city_id') else 'greenspark-online'
        cur.execute("""
            INSERT INTO greenspark_staging
                (name, product_url, article, category, price, price_wholesale,
                 in_stock, city_id, city_name, outlet_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            p["name"], p["url"], p.get("article"), p.get("category"),
            p.get("price", 0), p.get("price_wholesale", 0),
            p.get("in_stock", False), p.get("city_id"), p.get("city_name"),
            outlet_code,
        ))

    conn.commit()
    cur.close()
    conn.close()


def process_staging():
    """Обработать staging → nomenclature + prices."""
    conn = get_db()
    cur = conn.cursor()

    # 1. staging → greenspark_nomenclature (по product_url)
    cur.execute("""
        INSERT INTO greenspark_nomenclature (name, product_url, article, category, first_seen_at, updated_at)
        SELECT DISTINCT ON (product_url)
            name, product_url, article, category, NOW(), NOW()
        FROM greenspark_staging
        WHERE product_url IS NOT NULL AND product_url != ''
        ON CONFLICT (product_url) DO UPDATE SET
            name = EXCLUDED.name,
            article = COALESCE(EXCLUDED.article, greenspark_nomenclature.article),
            category = EXCLUDED.category,
            updated_at = NOW()
    """)

    # 2. staging → greenspark_prices (по nomenclature_id + outlet_id)
    cur.execute("""
        INSERT INTO greenspark_prices (nomenclature_id, outlet_id, price, price_wholesale, in_stock, updated_at)
        SELECT n.id, o.id, s.price, s.price_wholesale, s.in_stock, NOW()
        FROM greenspark_staging s
        JOIN greenspark_nomenclature n ON n.product_url = s.product_url
        JOIN outlets o ON o.code = s.outlet_code
        WHERE s.product_url IS NOT NULL
        ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
            price = EXCLUDED.price,
            price_wholesale = EXCLUDED.price_wholesale,
            in_stock = EXCLUDED.in_stock,
            updated_at = NOW()
    """)

    conn.commit()
    cur.close()
    conn.close()
```

### 7. Что сохраняем из v3 (без изменений)

| Компонент | Файл/Метод | Комментарий |
|-----------|-----------|-------------|
| Логика обхода каталога | `crawl_category()` | Рекурсия по подкатегориям, пагинация |
| Извлечение данных товара | `extract_product_info()` | Парсинг JSON ответа API |
| Извлечение артикула | `extract_article()`, `fetch_article_from_api()`, `fetch_article_from_page()` | Regex из URL картинки + API + HTML fallback |
| Мульти-город | `parse_city()`, `load_cities()`, `set_city()` | 60 городов, cookie `magazine` |
| Инкрементальное сохранение | `_maybe_save_incremental()` | Каждые 200 товаров → staging |
| Telegram-уведомления | `telegram_notifier.py` | Без изменений |
| config.py | Все константы | Без изменений |
| data/greenspark_cities.json | 60 городов | Без изменений |

### 8. Что удаляем / не переносим

| Компонент | Причина удаления |
|-----------|-----------------|
| `IPRotator` (250 строк) | Заменён на ProxyClient (50 строк) |
| `ServerEndpoint` dataclass | Не нужен — нет серверов |
| SSH-туннели (`start_ssh_tunnel`, `stop_ssh_tunnel`) | Прокси от proxy-service |
| Coordinator (`coordinator.py`) | Один сервер — нет координации |
| `get_cookies_via_xvfb()` с SSH к другим серверам | Cookies только локально |
| `handle_ban()` с wait 50-70 мин | Мгновенная смена прокси |
| `_wait_and_retry()` | Не нужен — пул тысяч IP |
| Хардкод серверов (ENDPOINTS) | Нет серверов |
| `db_greenspark` connection | Пишем в Homelab PostgreSQL |

### 9. Обработка бана — новая логика

```python
# В GreenSparkParser.get_category_data():

def get_category_data(self, path_parts, page=1):
    self._rate_limit()
    url = f"{API_URL}{PRODUCTS_ENDPOINT}?..."

    for attempt in range(3):  # до 3 попыток с разными прокси
        try:
            response = self.client.get(url)

            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                # Блокировка (SmartCaptcha/redirect)
                self.proxy_client.report_failure(banned=True)
                self._switch_proxy()
                continue

            if response.status_code == 403:
                self.proxy_client.report_failure(banned=True)
                self._switch_proxy()
                continue

            # Успех
            self.proxy_client.report_success(response.elapsed.total_seconds() * 1000)
            return response.json()

        except (httpx.TimeoutException, httpx.ConnectError):
            self.proxy_client.report_failure(banned=False)
            self._switch_proxy()
            continue

    return None  # Все 3 попытки провалились

def _switch_proxy(self):
    """Получить новый прокси и пересоздать клиент."""
    proxy = self.proxy_client.get_proxy()
    if proxy:
        self.client = httpx.Client(
            timeout=REQUEST_TIMEOUT,
            proxy=self.proxy_client.proxy_url,
            cookies=self.cookies,
            headers=self.headers,
            follow_redirects=True,
        )
        print(f"[PROXY] Переключение на {proxy['host']}:{proxy['port']}")
    else:
        print("[PROXY] Нет доступных прокси, ожидание 5 мин...")
        time.sleep(300)
```

### 10. CLI (main)

```python
def main():
    parser = argparse.ArgumentParser(description='GreenSpark парсер v4')
    parser.add_argument('--all-cities', action='store_true', help='Все 60 городов')
    parser.add_argument('--city', type=str, help='Конкретный город')
    parser.add_argument('--skip-parsed', action='store_true', help='Пропуск спарсенных')
    parser.add_argument('--category', type=str, help='Стартовая категория')
    parser.add_argument('--no-reparse', action='store_true', help='Без допарсинга артикулов')
    parser.add_argument('--no-db', action='store_true', help='Без БД')
    parser.add_argument('--process', action='store_true', help='Только process_staging')
    parser.add_argument('--all', action='store_true', help='parse + staging + process (стандарт ТЗ-5)')
    parser.add_argument('--proxy-service', type=str, default='http://localhost:8110',
                        help='URL proxy-service')
    args = parser.parse_args()

    if args.process:
        process_staging()
        return

    proxy_client = ProxyClient(base_url=args.proxy_service)
    cookie_mgr = CookieManager()
    cookies = cookie_mgr.get_or_refresh()

    gs = GreenSparkParser(proxy_client=proxy_client, cookies=cookies)

    if args.all_cities or args.city:
        # Мультигородской цикл (та же логика что v3)
        cities = gs.load_cities()
        if args.city:
            cities = [c for c in cities if c["name"].lower() == args.city.lower()]
        ...
        for city in cities:
            products = gs.parse_city(city["set_city"], city["name"], ...)
            if not args.no_db:
                save_staging(products, city_id=city["set_city"])
                if args.all:
                    process_staging()
    else:
        gs.parse_catalog(...)
        if not args.no_db:
            save_staging(gs.products)
            if args.all:
                process_staging()
```

---

## Файлы

### Создаём

| Файл | Описание |
|------|----------|
| `SHOPS/GreenSpark/parser_v4.py` | Новый парсер (proxy-service + Homelab DB + staging) |

### Не трогаем

| Файл | Причина |
|------|---------|
| `parser_v3.py` | Оставляем как fallback, рабочий |
| `parser.py` | Legacy (db_wrapper + Supabase) |
| `config.py` | Используется как есть |
| `telegram_notifier.py` | Используется как есть |
| `data/greenspark_cities.json` | Используется как есть |
| `get_cookies.py`, `stealth_cookies.py` | Cookie-утилиты |
| `coordinator.py` | Не используется в v4, но не удаляем |

### Обновляем

| Файл | Что меняем |
|------|-----------|
| `SHOPS/GreenSpark/CLAUDE.md` | Добавить описание v4, proxy-service, Homelab DB |

---

## Миграция данных

### Из db_greenspark → Homelab PostgreSQL

Если таблицы `greenspark_nomenclature` и `greenspark_prices` уже существуют в Homelab (из pg_dump по ТЗ-6), данные уже на месте.

Если нет — мигрировать:

```bash
# Дамп из db_greenspark (85.198.98.104:5433)
pg_dump "postgresql://postgres:Mi31415926pSss!@85.198.98.104:5433/db_greenspark" \
    --no-owner --no-privileges \
    -t greenspark_nomenclature -t greenspark_prices -t outlets \
    -f /tmp/greenspark_dump.sql

# Восстановить в Homelab
psql "postgresql://postgres:Mi31415926pSss!@213.108.170.194:5433/postgres" \
    < /tmp/greenspark_dump.sql
```

### Создать greenspark_staging (если не существует)

```sql
-- На Homelab PostgreSQL (213.108.170.194:5433)
CREATE TABLE IF NOT EXISTS greenspark_staging (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    product_url     TEXT NOT NULL,
    article         TEXT,
    category        TEXT,
    price           NUMERIC(10,2) DEFAULT 0,
    price_wholesale NUMERIC(10,2) DEFAULT 0,
    in_stock        BOOLEAN DEFAULT FALSE,
    city_id         INTEGER,
    city_name       TEXT,
    outlet_code     TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

---

## Порядок выполнения

| # | Задача | Время | Зависимость |
|---|--------|-------|-------------|
| 1 | Проверить что proxy-service работает и имеет прокси для greenspark | 5 мин | proxy-service задеплоен |
| 2 | Проверить/создать таблицы на Homelab (staging, nomenclature, prices, outlets) | 10 мин | ТЗ-6 этап 2 |
| 3 | Написать `parser_v4.py`: ProxyClient + CookieManager | 20 мин | — |
| 4 | Перенести логику парсинга из v3 (crawl, extract, articles) | 30 мин | #3 |
| 5 | Реализовать save_staging + process_staging | 15 мин | #4 |
| 6 | Реализовать обработку банов (proxy switch) | 15 мин | #3 |
| 7 | Тест: `--no-db --city Москва` (парсинг без БД) | 10 мин | #4 |
| 8 | Тест: `--city Москва` (один город в staging) | 10 мин | #5, #2 |
| 9 | Тест: `--all-cities --skip-parsed` (полный прогон) | 60 мин | #6, #8 |
| 10 | Обновить CLAUDE.md | 5 мин | #9 |

**Итого: ~3 часа** (включая полный тестовый прогон).

---

## Тестирование

### 1. Проверка proxy-service

```bash
# Есть ли рабочие прокси для greenspark?
curl http://localhost:8110/proxy/get?protocol=http&for_site=greenspark

# Ожидаемый ответ:
# {"host": "x.x.x.x", "port": 8080, "protocol": "http", "response_time_ms": 245}

# Если 404 — сначала POST /proxy/refresh и подождать
curl -X POST http://localhost:8110/proxy/refresh
```

### 2. Парсинг без БД

```bash
cd SHOPS/GreenSpark
python3 parser_v4.py --no-db --city Москва --proxy-service http://localhost:8110
# Ожидание: парсит ~5000-10000 товаров, выводит в консоль, без сохранения
```

### 3. Один город

```bash
python3 parser_v4.py --city Москва --all
# Ожидание: парсит → save_staging → process_staging
# Проверка:
psql ... -c "SELECT COUNT(*) FROM greenspark_staging WHERE city_name = 'Москва'"
psql ... -c "SELECT COUNT(*) FROM greenspark_nomenclature"
psql ... -c "SELECT COUNT(*) FROM greenspark_prices"
```

### 4. Полный прогон

```bash
python3 parser_v4.py --all-cities --all --skip-parsed
# 60 городов, ~10-30 мин на город (зависит от прокси)
# С --skip-parsed — продолжает с неспарсенных
```

### 5. Проверка обработки банов

```bash
# Мониторить логи:
# - "[PROXY] Переключение на x.x.x.x:port" — нормальная ротация
# - "[PROXY] Нет доступных прокси" — критическая ситуация

# Проверить что proxy-service получает отчёты:
curl http://localhost:8110/proxy/stats
# banned_by_site.greenspark > 0 = отчёты приходят
```

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|------------|----------|
| Прокси из пула быстро банятся на greenspark | Средняя | proxy-service пул 5000+ IP, ежедневный refresh. Можно увеличить CHECK_CONCURRENCY |
| Cookies протухают чаще чем в v3 | Низкая | Тот же механизм refresh (каждые 3000 товаров или при не-JSON ответе) |
| Homelab PostgreSQL медленнее db_greenspark | Очень низкая | Homelab = localhost для парсера, <1ms RTT |
| proxy-service упал | Низкая | Fallback: запуск с `--no-proxy` (без прокси, прямое подключение с IP Homelab) |
| Не хватает HTTP прокси для greenspark | Средняя | Можно добавить `protocol=socks5` как fallback. proxy-service поддерживает все 4 протокола |

---

## Cron (после внедрения)

Добавить в расписание ТЗ-6:

```cron
# GreenSpark — долгий парсер, отдельный запуск
0  1 * * *  root  cd /mnt/projects/repos/ZipMobile/SHOPS/GreenSpark && python3 parser_v4.py --all-cities --all --skip-parsed >> /var/log/greenspark.log 2>&1
```

---

## Метрики успеха

- [ ] parser_v4.py запускается на Homelab и парсит через proxy-service
- [ ] Прокси ротируются автоматически при банах (без SSH-туннелей)
- [ ] Данные пишутся в Homelab PostgreSQL (не в db_greenspark)
- [ ] save_staging + process_staging работают по стандарту ТЗ-5
- [ ] 60 городов парсятся за один прогон (<24ч)
- [ ] Telegram-уведомления работают
- [ ] proxy-service получает отчёты и трекает баны для greenspark
