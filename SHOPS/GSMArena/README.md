# GSMArena Parser

Парсер моделей телефонов с характеристиками с сайта https://www.gsmarena.com/

## Текущий статус (2026-01-22)

| Бренд | Спарсено | Статус |
|-------|----------|--------|
| Samsung | 1446 | Done |
| vivo | 563 | Done |
| Huawei | 509 | Done |
| Xiaomi | 494 | Done |
| Oppo | 389 | Done |
| Honor | 296 | Done |
| Realme | 180 | Done |
| Apple | 143 | Done |
| OnePlus | 99 | Done |
| Tecno | 66 | Done |
| Google | 39 | Done |
| **ИТОГО** | **4224** | 11 брендов |

**Осталось:** Nokia, Motorola, Sony, LG, Asus, Lenovo, Meizu, ZTE

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        GSMArena.com                             │
│  makers.php3 → список брендов (126 шт)                         │
│  {brand}-phones-{id}.php → список моделей бренда               │
│  {brand}_{model}-{id}.php → характеристики модели              │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        parser.py                                │
│                                                                 │
│  1. GET BRANDS                                                  │
│     URL: /makers.php3                                          │
│     Результат: {slug, name, count} для каждого бренда          │
│                                                                 │
│  2. GET MODELS (для каждого бренда)                            │
│     URL: /{brand}-phones-{id}.php (страница 1)                 │
│     URL: /{brand}-phones-f-{id}-0-p{page}.php (страницы 2+)    │
│     Пагинация: 50 моделей на страницу                          │
│     Результат: [{name, url, image_url}, ...]                   │
│                                                                 │
│  3. GET SPECS (для каждой модели)                              │
│     URL: /{brand}_{model}-{id}.php                             │
│     HTML парсинг секций:                                       │
│     - Network, Launch, Body, Display, Platform                 │
│     - Memory, Main Camera, Selfie Camera, Sound                │
│     - Comms, Features, Battery, Misc                           │
│                                                                 │
│  4. NORMALIZE                                                   │
│     extract_year("Released 2025, January") → 2025              │
│     extract_battery_mah("5000 mAh") → 5000                     │
│     extract_weight_grams("227 g") → 227                        │
│     extract_display_inches("6.8 inches") → 6.8                 │
│                                                                 │
│  5. SAVE                                                        │
│     PostgreSQL: UPSERT в zip_gsmarena_raw                      │
│     JSON: output/{brand}_{date}.json                           │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL (port 5433)                       │
│                                                                 │
│  zip_gsmarena_raw:                                             │
│  - brand, model_name, model_url, image_url                     │
│  - announced, release_year, release_status                     │
│  - dimensions, weight, weight_grams, build, sim, ip_rating     │
│  - display_type, display_size, display_size_inches             │
│  - display_resolution, display_protection, refresh_rate        │
│  - os, chipset, cpu, gpu                                       │
│  - ram, storage, card_slot                                     │
│  - main_camera_mp, main_camera_setup, main_camera_video        │
│  - selfie_camera_mp, selfie_camera_setup, selfie_camera_video  │
│  - battery_capacity, battery_capacity_mah, battery_type        │
│  - charging_wired, charging_wireless                           │
│  - network_technology, network_2g/3g/4g/5g                     │
│  - wlan, bluetooth, nfc, gps, usb, radio                       │
│  - sensors, colors, price, price_eur                           │
│  - specs_json (полный JSON всех данных)                        │
│  - parsed_at, updated_at                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Использование

### Базовое использование

```bash
# Установка зависимостей
pip install requests beautifulsoup4 lxml psycopg2-binary playwright playwright-stealth
playwright install chromium

# Парсинг одного бренда
python parser.py --brand apple

# Парсинг с лимитом моделей
python parser.py --brand samsung --max 100

# Только вывод в JSON (без БД)
python parser.py --brand xiaomi --no-db

# Список доступных брендов
python parser.py --list-brands
```

### Парсинг с прокси (обход блокировок)

```bash
# 1. Генерация списка прокси (40,000+)
python proxy_generator.py

# 2. Парсинг с ротацией прокси
python parser.py --brand nokia --proxy --resume

# 3. Параллельный парсинг нескольких брендов
python parallel_parse.py --brands nokia motorola sony lg -t
```

### Resume mode (продолжение с места остановки)

```bash
# Парсинг пропускает уже спарсенные модели
python parser.py --brand vivo --proxy --resume
```

## Защита от бана (429 Too Many Requests)

GSMArena агрессивно блокирует парсеры. Реализованы следующие механизмы:

### 1. Ротация прокси

```
proxies.txt → 40,816 прокси из GitHub списков
                │
                ▼
       ┌────────────────┐
       │   Request 1    │ → proxy #1
       │   Request 2    │ → proxy #1
       │   429 Error    │
       └────────────────┘
                │
                ▼
       ┌────────────────┐
       │   Switch       │ → proxy #2
       │   Request 3    │ → proxy #2
       │   ...          │
       └────────────────┘
```

### 2. Обновление Cookies (Playwright Stealth)

Каждые 10 смен прокси обновляются cookies через headless браузер:

```
proxy switch #10, #20, #30...
         │
         ▼
┌─────────────────────────────┐
│   Playwright (headless)     │
│   1. Открыть gsmarena.com   │
│   2. Имитация скролла       │
│   3. Получить cookies       │
│   4. Новый User-Agent       │
└─────────────────────────────┘
```

### 3. Resume Mode

- Парсер проверяет БД перед началом
- Пропускает уже спарсенные модели
- Позволяет продолжить после блокировки

## Файлы

```
SHOPS/GSMArena/
├── parser.py              # Основной парсер с proxy/resume
├── proxy_generator.py     # Генератор списка прокси (40k+)
├── parallel_parse.py      # Параллельный парсинг брендов
├── stealth_cookies.py     # Playwright stealth для cookies
├── proxies.txt            # Список прокси (генерируется)
├── cookies.json           # Текущие cookies
├── requirements.txt       # Зависимости
├── README.md             # Эта документация
└── output/               # JSON выгрузки
    ├── apple_20260122.json
    ├── samsung_20260122.json
    └── ...
```

## Источники прокси

| Источник | Прокси |
|----------|--------|
| TheSpeedX/PROXY-List | ~40,000 |
| monosans/proxy-list | ~1,000 |
| clarketm/proxy-list | ~400 |
| sslproxies.org | ~100 |
| free-proxy-list.net | ~300 |
| **ИТОГО** | **~41,000** |

**Важно:** Большинство бесплатных прокси - низкого качества (CDN, сломанные). Реально работает ~5-10%.

## Конфигурация

```python
# Задержка между запросами (защита от бана)
DELAY_MIN = 3.0  # секунд (без прокси)
DELAY_MAX = 6.0  # секунд (без прокси)
# С прокси задержка делится на 2

# Целевые бренды (20 штук)
TARGET_BRANDS = [
    'apple', 'samsung', 'xiaomi', 'huawei', 'honor',
    'oppo', 'vivo', 'realme', 'oneplus', 'google',
    'motorola', 'nokia', 'sony', 'lg', 'asus',
    'nothing', 'zte', 'meizu', 'lenovo', 'poco'
]

# База данных
DB_CONFIG = {
    'host': '85.198.98.104',
    'port': 5433,
    'database': 'postgres'
}
```

## UPSERT логика

Парсер использует `ON CONFLICT DO UPDATE`:
- Если модель существует → обновляет все поля
- Если модели нет → создаёт новую запись
- Ключ уникальности: `(brand, model_name)`

```sql
INSERT INTO zip_gsmarena_raw (brand, model_name, ...)
VALUES (...)
ON CONFLICT (brand, model_name)
DO UPDATE SET
    model_url = EXCLUDED.model_url,
    specs_json = EXCLUDED.specs_json,
    updated_at = NOW();
```

## Синхронизация со справочниками

После парсинга, данные синхронизируются с основными справочниками:

```sql
-- Синхронизация брендов и моделей
SELECT * FROM sync_all_gsmarena();

-- Привязка URL к моделям
SELECT link_gsmarena_urls();
```

## Проблемы и решения

| Проблема | Решение |
|----------|---------|
| 429 Too Many Requests | Ротация прокси + cookies refresh |
| Прокси не работает | Автоматическое переключение на следующий |
| Блокировка IP | Использование 40k+ прокси пула |
| Потеря прогресса | Resume mode из БД |
| Медленный парсинг | Параллельный запуск (parallel_parse.py) |

## Миграции БД

- `sql/migrations/018_create_gsmarena_raw.sql` — создание таблицы
- `sql/migrations/019_sync_gsmarena_to_dicts.sql` — функции синхронизации
