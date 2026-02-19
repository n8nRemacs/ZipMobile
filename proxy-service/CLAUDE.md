# proxy-service
Обновлено: 2026-02-19 21:30 (GMT+4)

## Назначение

Универсальный прокси-менеджер для всей платформы ZipMobile. Автономный микросервис, который:
- Собирает бесплатные прокси из 34 публичных источников (26 GitHub + 8 сайтов)
- Проверяет каждый прокси по 4 протоколам: HTTP, HTTPS, SOCKS4, SOCKS5
- Выдаёт проверенный прокси потребителю с **перепроверкой перед отдачей**
- Ведёт per-site бан-трекинг (прокси может быть забанен на greenspark, но работать на moba)
- **Получает и кэширует cookies** для сайтов через Playwright+Xvfb (поддерживает greenspark)
- Ежедневно обновляет пул по расписанию (cron 04:00 GMT+4)

Потребители: `orchestrator`, `parts-api`, любой сервис, которому нужен ротируемый прокси.

## Порт: 8110

## Структура файлов

```
proxy-service/
├── Dockerfile              Docker-образ (python:3.11-slim)
├── requirements.txt        8 зависимостей (+ playwright)
├── .env.example            Шаблон переменных окружения
├── CLAUDE.md               Эта документация
└── src/
    ├── __init__.py
    ├── main.py             FastAPI app, lifespan, 5 роутов
    ├── config.py            Pydantic BaseSettings из .env
    ├── database.py          asyncpg CRUD для proxy_pool + proxy_cookies (автосоздание таблиц)
    ├── scraper.py           Сбор прокси из 34 источников
    ├── checker.py           Мульти-протокольная проверка (aiohttp + aiohttp-socks)
    ├── pool.py              Менеджер пула: scrape → check → cookies → serve
    ├── cookie_fetcher.py    Playwright+Xvfb: получение cookies для сайтов через прокси
    └── scheduler.py         APScheduler: ежедневный refresh
```

---

## Размещение и запуск

### Вариант 1: Локально

```bash
cd proxy-service
cp .env.example .env        # при необходимости поправить значения
pip install -r requirements.txt
python -m src.main
```

Сервис стартует на `http://0.0.0.0:8110`.

### Вариант 2: Docker

```bash
cd proxy-service
docker build -t proxy-service .
docker run -d --name proxy-service -p 8110:8110 --env-file .env proxy-service
```

### Вариант 3: Docker Compose (в составе платформы)

Добавить в корневой `docker-compose.yml`:

```yaml
proxy-service:
  build: ./proxy-service
  ports:
    - "8110:8110"
  env_file: ./proxy-service/.env
  restart: unless-stopped
```

### Переменные окружения (.env)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `DATABASE_URL` | `postgresql://postgres:...@213.108.170.194:5433/postgres` | Homelab PostgreSQL direct |
| `HOST` | `0.0.0.0` | Bind-адрес FastAPI |
| `PORT` | `8110` | Порт сервиса |
| `LOG_LEVEL` | `info` | Уровень логов (debug/info/warning/error) |
| `CHECK_TIMEOUT` | `10` | Таймаут проверки одного прокси (секунды) |
| `CHECK_CONCURRENCY` | `100` | Макс. одновременных проверок (asyncio.Semaphore) |
| `DAILY_REFRESH_HOUR` | `4` | Час запуска ежедневного refresh (GMT+4) |
| `DAILY_REFRESH_MINUTE` | `0` | Минута запуска ежедневного refresh |
| `COOKIE_FETCH_CONCURRENCY` | `2` | Макс. одновременных Playwright-сессий |
| `COOKIE_MAX_AGE_HOURS` | `6` | TTL кэша cookies (часы) |
| `COOKIE_FETCH_LIMIT` | `20` | Макс. прокси для получения cookies за refresh |
| `COOKIE_FETCH_TIMEOUT` | `120` | Таймаут одного Playwright subprocess (секунды) |

### БД

Подключение к **Homelab PostgreSQL** (direct, порт 5433):
```
postgresql://postgres:Mi31415926pSss!@213.108.170.194:5433/postgres
```

Пул соединений: asyncpg, min=2, max=10, command_timeout=30s.

Таблица `proxy_pool` создаётся автоматически при старте сервиса (`_ensure_table`).

---

## API

Базовый URL: `http://<host>:8110`

### GET /health

Healthcheck.

**Ответ:**
```json
{"status": "ok", "service": "proxy-service"}
```

---

### GET /proxy/get

Выдать один проверенный рабочий прокси. **Перед отдачей делает quick-test** (до 3 попыток).

**Query-параметры:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `protocol` | string | `http` | Протокол: `http`, `https`, `socks4`, `socks5` |
| `for_site` | string | null | Ключ сайта для фильтрации банов: `greenspark`, `moba`, `memstech` |

**Успешный ответ (200):**
```json
{
  "host": "103.42.180.5",
  "port": 1080,
  "protocol": "socks5",
  "response_time_ms": 245.31,
  "cookies": {"magazine": "1008", "global_magazine": "1008", "catalog-per-page": "100", "...": "..."}
}
```

Поле `cookies` присутствует только если `for_site` указан и в БД есть свежие cookies (TTL: `COOKIE_MAX_AGE_HOURS`).
Если cookies нет — поле отсутствует (парсер должен обработать оба варианта через fallback).

**Если нет рабочих прокси (404):**
```json
{"detail": "No working proxies available"}
```

**Алгоритм выдачи:**
1. SELECT до 10 кандидатов из `proxy_pool` WHERE `status='working'` AND `{protocol}=TRUE` AND NOT banned для `for_site`
2. Сортировка: `last_used_at ASC NULLS FIRST, success_count DESC` (LRU + надёжные первыми)
3. Для каждого кандидата (макс. 3 попытки):
   - Quick-test по запрошенному протоколу (timeout 5с)
   - Если OK → вернуть, обновить `last_used_at`
   - Если FAIL → пометить `status='dead'`, взять следующего
4. Если все 3 fail → 404

---

### POST /proxy/report

Потребитель сообщает результат использования прокси. Позволяет системе обучаться: успешные прокси получают приоритет, проблемные — банятся или убиваются.

**Тело запроса (JSON):**

| Поле | Тип | Обязательно | Описание |
|------|-----|------------|----------|
| `host` | string | да | IP-адрес прокси |
| `port` | int | да | Порт прокси |
| `success` | bool | да | Успешно ли сработал |
| `response_time` | float | нет | Время ответа (мс) |
| `banned_site` | string | нет | Сайт, на котором забанен (`greenspark`, `moba`) |

**Пример — успех:**
```json
{"host": "103.42.180.5", "port": 8080, "success": true, "response_time": 312.5}
```

**Пример — бан на сайте:**
```json
{"host": "103.42.180.5", "port": 8080, "success": false, "banned_site": "greenspark"}
```

**Пример — общий fail:**
```json
{"host": "103.42.180.5", "port": 8080, "success": false}
```

**Логика обработки:**
- `success=true` → `success_count += 1`, `fail_count = 0`, обновить `response_time_ms`
- `success=false` + `banned_site` → добавить сайт в `banned_sites[]` (без дублей)
- `success=false` без `banned_site` → `fail_count += 1`. Если `fail_count > 5` → `status = 'dead'`

**Ответ:**
```json
{"status": "ok"}
```

---

### POST /proxy/refresh

Запустить полный цикл обновления пула (в фоне).

**Тело:** не требуется.

**Ответ (мгновенный):**
```json
{"status": "started", "message": "Refresh running in background"}
```

Если refresh уже запущен, повторный вызов пропускается (asyncio.Lock).

**Что происходит в фоне:**
1. **Scrape** — обход 34 источников, сбор IP:port, дедупликация
2. **Upsert** — вставка новых в БД как `status='raw'` (ON CONFLICT DO NOTHING)
3. **Check raw** — проверка до 500 `raw` прокси по 4 протоколам → `working` или `dead`
4. **Recheck working** — перепроверка до 500 `working` (могли умереть за сутки)
5. **Cookie fetch** — получение свежих cookies для SOCKS5-прокси через Playwright+Xvfb (до 20 прокси, сайт: greenspark, TTL 6ч)
6. **Cleanup** — удаление `dead` старше 48 часов

**Cookie fetch детали:**
- Целевые сайты: `greenspark` (green-spark.ru)
- Методика: Playwright headless браузер через SOCKS5-прокси, Xvfb virtual display
- Успешность: обычно 80-90% (зависит от доступности прокси и сайта)
- Возврат: JSONB словарь с name→value парами (13-15 cookies на green-spark.ru)

---

### GET /proxy/stats

Статистика пула.

**Ответ:**
```json
{
  "raw": 1523,
  "working": 342,
  "dead": 4210,
  "checking": 0,
  "total": 6075,
  "banned_by_site": {
    "greenspark": 45,
    "moba": 12
  }
}
```

---

## Принципы работы

### Жизненный цикл прокси

```
[Источник] → scrape → INSERT(raw) → check → working/dead
                                         ↓
                                    [Cookies fetch]
                                    Playwright получает cookies для greenspark
                                         ↓
                                    [Потребитель]
                                    GET /proxy/get?for_site=greenspark
                                         ↓
                                    quick-test OK? → выдача с cookies (если есть) → report(success/fail)
                                    quick-test FAIL? → dead, следующий кандидат

                                    GET /proxy/get БЕЗ for_site
                                         ↓
                                    quick-test OK? → выдача БЕЗ cookies → report(success/fail)
```

**Статусы прокси:**

| Статус | Значение |
|--------|---------|
| `raw` | Только что scraped, ещё не проверен |
| `checking` | Зарезервировано (не используется в текущей версии) |
| `working` | Прошёл проверку хотя бы по одному протоколу |
| `dead` | Не ответил ни по одному протоколу / набрал >5 fail_count |
| `banned` | Зарезервировано (баны отслеживаются через `banned_sites[]`) |

### Мульти-протокольная проверка

Каждый прокси проверяется по **4 протоколам одновременно** (asyncio.gather):

| Протокол | Метод | Тестовый URL |
|----------|-------|-------------|
| HTTP | `aiohttp` + `proxy=http://host:port` | `http://httpbin.org/ip` |
| HTTPS | `aiohttp` + `proxy=http://host:port` | `https://httpbin.org/ip` |
| SOCKS4 | `aiohttp_socks.ProxyConnector(SOCKS4)` | `http://httpbin.org/ip` |
| SOCKS5 | `aiohttp_socks.ProxyConnector(SOCKS5)` | `http://httpbin.org/ip` |

Результат записывается в 4 boolean колонки. Один прокси может поддерживать `http=TRUE, socks5=TRUE` одновременно.

`response_time_ms` — среднее по всем успешным протоколам.

### Per-site бан-трекинг

Потребители через `POST /proxy/report` сообщают `banned_site`. Это добавляет сайт в массив `banned_sites[]`.

При `GET /proxy/get?for_site=greenspark` — фильтр `NOT (banned_sites @> ARRAY['greenspark'])`.

Прокси забаненный на greenspark продолжает работать для moba и других сайтов.

**Известные ключи сайтов для проверки:**

| Ключ | URL | Назначение |
|------|-----|-----------|
| `greenspark` | `https://green-spark.ru/` | Поставщик запчастей |
| `moba` | `https://moba.ru/` | Поставщик запчастей |
| `memstech` | `https://memstech.ru/` | Поставщик запчастей |

Индикаторы блокировки: `captcha`, `smartcaptcha`, `blocked`, `access denied`, `403 forbidden`, `challenge`, `cf-browser-verification`, `just a moment`, `checking your browser`.

### Получение и кэширование cookies (Cookie Fetching)

**Назначение:** Получить и закэшировать cookies сайта через прокси, чтобы парсеры могли использовать их без дополнительного Playwright.

**Процесс:**
1. При каждом `POST /proxy/refresh` на шаге 5 запускается `_fetch_missing_cookies(site_key="greenspark")`
2. Выбираются SOCKS5-прокси БЕЗ свежих cookies (TTL истёк или отсутствуют)
3. Для каждого прокси:
   - `CookieFetcher.fetch_cookies()` запускает Playwright в subprocess с Xvfb display
   - Браузер открывает URL сайта через прокси
   - Ждёт загрузки страницы и поиска маркера "COOKIES:" в stdout
   - Парсит JSONB cookies и сохраняет в БД
4. Результаты кэшируются в `proxy_cookies` таблице с TTL

**Параметры:**
```
COOKIE_FETCH_CONCURRENCY = 2        # макс. одновременные Playwright-сессии
COOKIE_FETCH_LIMIT = 20             # макс. прокси за один refresh
COOKIE_FETCH_TIMEOUT = 120          # таймаут subprocess (сек)
COOKIE_MAX_AGE_HOURS = 6            # TTL кэша
```

**Обработка ошибок:**
- Если `fetch_cookies()` не найдёт маркер "COOKIES:" → возвращает None
- Ошибки неcritical — refresh продолжается, счётчик `cookies_fetched` отражает успехи
- Парсеры могут использовать fallback (собственный CookieManager)

**Пример cookies для green-spark.ru (13 параметров):**
```json
{
  "__jua_": "Mozilla%2F5.0%20...",      // User-Agent маркер
  "__hash_": "65cfe49619d1200537...",   // Хеш сессии
  "__js_p_": "510,3600,0,0,0",          // JS вычисления
  "__jhash_": "480",                    // JS хеш
  "__lhash_": "9ba9c227fac68020...",    // Локальный хеш
  "magazine": "1008",                   // ID магазина
  "global_magazine": "1008",            // Глобальный магазин
  "catalog-per-page": "100",            // Товаров на странице
  "catalog-sort": "{...}",              // JSON сортировки
  "catalog-horizontal": "false",        // Ориентация
  "PHPSESSID": "8m2241o7cvooku2...",   // PHP session
  "_nav_token": "a712d9c2-22e8-...",   // Навигационный token
  "BITRIX_SM_SALE_UID": "272092920"    // Bitrix UID
}
```

**Интеграция с парсерами:**
- Парсер запрашивает: `GET /proxy/get?protocol=socks5&for_site=greenspark`
- Если cookies в cache и свежие (TTL OK) → возвращаются в поле `cookies`
- Парсер использует: `httpx.Client(..., cookies=response['cookies'])`
- Если cookies отсутствуют → парсер работает с fallback механизмом

### Ротация (LRU)

Выборка прокси сортируется:
1. `last_used_at ASC NULLS FIRST` — давно не использовавшиеся первыми
2. `success_count DESC` — при равном времени — надёжные первыми

Это обеспечивает равномерную ротацию и минимизирует повторное использование одного прокси.

### Scheduler

APScheduler с AsyncIOScheduler. Задача `daily_refresh`:
- Запускается ежедневно в **04:00** (настраивается через `DAILY_REFRESH_HOUR`, `DAILY_REFRESH_MINUTE`)
- Выполняет тот же цикл, что и `POST /proxy/refresh`
- Защита от дублирования через `asyncio.Lock` в `ProxyPool`

### Concurrency

- Scraping: до 20 одновременных HTTP-запросов к источникам (`TCPConnector(limit=20)`)
- Checking: Semaphore на `CHECK_CONCURRENCY` (по умолчанию 100) одновременных проверок
- DB pool: asyncpg min=2, max=10 соединений

---

## База данных

### Таблица: `proxy_pool`

Создаётся автоматически при старте сервиса. База: Homelab PostgreSQL (`213.108.170.194:5433`).

| Колонка | Тип | Default | Описание |
|---------|-----|---------|----------|
| `id` | SERIAL | auto | PK |
| `host` | VARCHAR(45) | NOT NULL | IP-адрес прокси |
| `port` | INTEGER | NOT NULL | Порт прокси |
| `http` | BOOLEAN | FALSE | Поддерживает HTTP |
| `https` | BOOLEAN | FALSE | Поддерживает HTTPS |
| `socks4` | BOOLEAN | FALSE | Поддерживает SOCKS4 |
| `socks5` | BOOLEAN | FALSE | Поддерживает SOCKS5 |
| `response_time_ms` | FLOAT | NULL | Среднее время ответа (мс) по рабочим протоколам |
| `success_count` | INTEGER | 0 | Кол-во успешных использований (из report) |
| `fail_count` | INTEGER | 0 | Кол-во неудачных использований (сбрасывается при success) |
| `status` | VARCHAR(20) | 'raw' | Статус: `raw`, `working`, `dead` |
| `banned_sites` | TEXT[] | '{}' | Массив сайтов, на которых забанен |
| `source` | VARCHAR(80) | NULL | Домен источника (github.com, proxyscrape.com, ...) |
| `created_at` | TIMESTAMP | NOW() | Когда добавлен |
| `last_checked_at` | TIMESTAMP | NULL | Последняя проверка checker'ом |
| `last_used_at` | TIMESTAMP | NULL | Последняя выдача потребителю |

**Constraint:** `UNIQUE(host, port)` — один прокси = одна запись, протоколы хранятся в boolean колонках.

### Индексы (proxy_pool)

| Имя | Колонки | Назначение |
|-----|---------|-----------|
| `idx_proxy_pool_status` | `status` | Быстрый SELECT по статусу |
| `idx_proxy_pool_protocols` | `http, https, socks4, socks5` | Фильтрация по протоколу |

### Таблица: `proxy_cookies`

Кэш cookies для пар (прокси, сайт). Создаётся автоматически при старте.

| Колонка | Тип | Default | Описание |
|---------|-----|---------|----------|
| `id` | SERIAL | auto | PK |
| `host` | VARCHAR(45) | NOT NULL | IP-адрес прокси |
| `port` | INTEGER | NOT NULL | Порт прокси |
| `site_key` | VARCHAR(50) | NOT NULL | Ключ сайта: `greenspark` |
| `cookies` | JSONB | NOT NULL | Словарь name→value |
| `fetched_at` | TIMESTAMP | NOW() | Когда получены |

**Constraint:** `UNIQUE(host, port, site_key)` — одна запись на пару прокси+сайт.
**TTL:** `COOKIE_MAX_AGE_HOURS` (по умолчанию 6 часов). При истечении — запись остаётся, но считается протухшей.

### Индексы (proxy_cookies)

| Имя | Колонки | Назначение |
|-----|---------|-----------|
| `idx_proxy_cookies_site` | `site_key` | Фильтрация по сайту |

### SQL создания

```sql
CREATE TABLE IF NOT EXISTS proxy_pool (
    id              SERIAL PRIMARY KEY,
    host            VARCHAR(45) NOT NULL,
    port            INTEGER NOT NULL,
    http            BOOLEAN DEFAULT FALSE,
    https           BOOLEAN DEFAULT FALSE,
    socks4          BOOLEAN DEFAULT FALSE,
    socks5          BOOLEAN DEFAULT FALSE,
    response_time_ms FLOAT,
    success_count   INTEGER DEFAULT 0,
    fail_count      INTEGER DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'raw',
    banned_sites    TEXT[] DEFAULT '{}',
    source          VARCHAR(80),
    created_at      TIMESTAMP DEFAULT NOW(),
    last_checked_at TIMESTAMP,
    last_used_at    TIMESTAMP,
    UNIQUE(host, port)
);

CREATE INDEX idx_proxy_pool_status ON proxy_pool(status);
CREATE INDEX idx_proxy_pool_protocols ON proxy_pool(http, https, socks4, socks5);

CREATE TABLE IF NOT EXISTS proxy_cookies (
    id           SERIAL PRIMARY KEY,
    host         VARCHAR(45) NOT NULL,
    port         INTEGER NOT NULL,
    site_key     VARCHAR(50) NOT NULL,
    cookies      JSONB NOT NULL,
    fetched_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE(host, port, site_key)
);

CREATE INDEX idx_proxy_cookies_site ON proxy_cookies(site_key);
```

### Ключевые запросы

**Выборка кандидатов (пример для HTTP, с фильтром бана):**
```sql
SELECT host, port FROM proxy_pool
WHERE status = 'working'
  AND http = TRUE
  AND NOT (banned_sites @> ARRAY['greenspark']::text[])
ORDER BY last_used_at ASC NULLS FIRST, success_count DESC
LIMIT 10;
```

**Upsert при scrape (батчами по 500):**
```sql
INSERT INTO proxy_pool (host, port, source, status)
VALUES ($1, $2, $3, 'raw')
ON CONFLICT (host, port) DO NOTHING;
```

**Обновление после проверки:**
```sql
UPDATE proxy_pool SET
    status = $3, http = $4, https = $5, socks4 = $6, socks5 = $7,
    response_time_ms = COALESCE($8, response_time_ms),
    last_checked_at = NOW()
WHERE host = $1 AND port = $2;
```

**Cleanup dead старше 48ч:**
```sql
DELETE FROM proxy_pool
WHERE status = 'dead' AND last_checked_at < NOW() - INTERVAL '48 hours';
```

---

## Источники прокси (scraper)

34 источника, все — публичные plain-text списки `IP:PORT`.

### GitHub (26 источников)

| Репозиторий | Протоколы |
|-------------|-----------|
| TheSpeedX/PROXY-List | http, socks4, socks5 |
| monosans/proxy-list | http, socks4, socks5 |
| hookzof/socks5_list | socks5 |
| ShiftyTR/Proxy-List | http, socks4, socks5 |
| mmpx12/proxy-list | http, https, socks4, socks5 |
| roosterkid/openproxylist | http, socks4, socks5 |
| prxchk/proxy-list | http, socks4, socks5 |
| MuRongPIG/Proxy-Master | http, socks4, socks5 |
| zloi-user/hideip.me | http, socks4, socks5 |

### Сайты (8 источников)

| Сайт | Протоколы |
|------|-----------|
| proxyscrape.com | http, socks4, socks5 |
| proxy-list.download | http, https, socks4, socks5 |
| openproxylist.xyz | http |

Парсинг через regex: `(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})`.
Дедупликация по паре `(host, port)`.

---

## Зависимости

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| fastapi | >=0.115.0 | HTTP framework |
| uvicorn | >=0.30.0 | ASGI server |
| asyncpg | >=0.30.0 | PostgreSQL async driver |
| aiohttp | >=3.9.0 | HTTP client для scrape и check |
| aiohttp-socks | >=0.9.0 | SOCKS4/SOCKS5 через aiohttp |
| apscheduler | >=3.10.0 | Cron scheduler |
| pydantic-settings | >=2.0.0 | Config из .env |
| playwright | >=1.40.0 | Headless браузер для cookie fetching |

---

## Отличия от orchestrator/src/proxy/

| Аспект | orchestrator (старый) | proxy-service (новый) |
|--------|----------------------|----------------------|
| Идентификация | `proxy` (строка `IP:PORT`) | `host` + `port` (раздельно) |
| Протоколы | `type` (одна колонка, один протокол) | `http`, `https`, `socks4`, `socks5` (4 boolean) |
| БД | Supabase Cloud (griexhozxrqtepcilfnu) | Homelab PostgreSQL (213.108.170.194:5433) |
| Соединение | Одно asyncpg connection | asyncpg Pool (2-10) |
| Перепроверка | Нет | quick-test перед каждой выдачей |
| HTTP API | Нет (библиотека) | FastAPI на порту 8110 |
| Scheduler | Нет | APScheduler cron 04:00 |
| Dockerfile | Нет | Есть |
| Dead cleanup | 24ч | 48ч |
| SOCKS проверка | Только формат URL | aiohttp_socks.ProxyConnector |
| Cookie fetching | Нет | Playwright+Xvfb для greenspark |
| Cookie кэш | Нет | proxy_cookies JSONB таблица |

---

## Тестирование и известные проблемы

### End-to-End тестирование (19.02.2026)

Проведено полное тестирование интеграции cookies:
- ✅ Refresh получает cookies через Playwright+Xvfb
- ✅ Cookies сохраняются в proxy_cookies с TTL 6ч
- ✅ GET /proxy/get?for_site=greenspark возвращает cookies
- ✅ GET /proxy/get БЕЗ for_site НЕ возвращает cookies
- ✅ Fallback работает (без cookies → парсер использует Playwright)

### Исправленные баги

**BUG (19.02.2026):** `database.py:248` — ошибка при десериализации cookies
```python
# Было (НЕПРАВИЛЬНО):
return dict(val) if val else None  # ValueError: dictionary update sequence...

# Стало (ИСПРАВЛЕНО):
return val if val else None         # asyncpg уже возвращает dict из JSONB
```

**Статус:** Исправлено и протестировано на продакшене.

### Рекомендации по развёртыванию

1. **Playwright installation:** Убедитесь, что `playwright` установлен и `xvfb-run` доступен на сервере
   ```bash
   pip install playwright
   playwright install chromium
   which xvfb-run  # должна быть на Linux
   ```

2. **Мониторинг cookies:** Проверяйте логи на сообщения вида:
   ```
   [CookieFetcher] OK: greenspark через 68.71.243.14:4145, 13 cookies
   Cookie fetch done: 9/11 succeeded for greenspark
   ```

3. **TTL cookies:** Если green-spark часто меняет cookies (blocklists, новые anti-bot), уменьшьте `COOKIE_MAX_AGE_HOURS` с 6 до 3-4 часов

4. **Параллелизм cookie fetching:** Если нужно быстрее получать cookies, увеличьте `COOKIE_FETCH_CONCURRENCY` (но не более 5, так как Playwright тяжелый)
