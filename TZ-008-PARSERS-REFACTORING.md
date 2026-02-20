# ТЗ-8: Рефакторинг парсеров
Обновлено: 2026-02-19 (GMT+4)

## Контекст

После миграции v9.0 (удалены stock поля) и стандартизации v1 (TZ-005) парсеры работают,
но накопились технические долги: legacy файлы, незакрытые дыры в db_wrapper, дублирование
~2400 строк одинакового кода.

**Что НЕ трогаем:** логику парсинга (HTTP/HTML/API), proxy-service интеграцию, GreenSpark v4.

---

## Проблемы

### Критические (могут ломать парсеры)

**P1. db_wrapper.py — неполный TABLE_MAPPING**

5 магазинов используют generic имена таблиц (`staging`, `nomenclature`, `current_prices`),
но их маппинга нет в `db_wrapper.TABLE_MAPPING`. Это значит SQL-запросы могут падать
или писать не в те таблицы.

Отсутствуют маппинги для: `Profi`, `Taggsm`, `signal23`, `Liberti`, `memstech`.

**P2. signal23/parser.py — неверное имя staging таблицы**

```python
# СЕЙЧАС (неверно):
INSERT INTO staging (...)       # generic — в db_wrapper нет маппинга для signal23

# ДОЛЖНО БЫТЬ:
INSERT INTO signal23_staging (...)
```

**P3. Orizhka/parser.py — двойные INSERT**

Парсер пишет одновременно в старые таблицы (`products`, `outlets`, `cities`)
и в правильные (`orizhka_nomenclature`, `orizhka_prices`, `zip_outlets`).
Старые таблицы скорее всего не существуют → ошибки.

### Высокие (мусор и путаница)

**P4. Лишние файлы в GreenSpark/**

Активный парсер — только `parser_v4.py`. Остальные создают путаницу:
- `parser.py` — v3, deprecated
- `parser_v3.py` — устарел
- `reparse_articles_standalone.py` — заменён логикой в v4
- 18 test/debug файлов в корне папки: `test_api*.py`, `debug_api.py`, `analyze_missing.py`, `check_articles.py`, `recent_updates.py`, `fill_articles.py`

**P5. Лишние файлы в Moba/**

Активный парсер — `moba_parser.py` + `write_to_db.py` (нужен для cron).
Остальное — незадокументированные варианты и утилиты cookies:
- Варианты: `moba_full_parser.py`, `moba_multicity_parser.py`, `moba_playwright_parser.py`
- Утилиты: `get_cookies_*.py` (×4), `capture_moba.py`, `parse_cookies.py`, `auto_cookies.py`, `cdp_browser.py`
- Тесты: `test_access.py`, `test_moba.py`, `test_mobile.py`

**P6. Лишние файлы в Profi/** (вне `_legacy/`)

- `parse_price.py`, `parse_price_n8n.py` — отношение к `parser.py` не документировано
- `parser_server.py` — назначение не документировано
- `check_akb.py` — отладочный скрипт

### Средние (дублирование кода)

**P7. ~2400 строк одинакового boilerplate**

Все 12 парсеров содержат идентичный код:
- `save_staging()` — TRUNCATE + INSERT в staging (~30 строк × 12 = 360 строк)
- `process_staging()` — UPSERT staging → nomenclature + prices (~50 строк × 12 = 600 строк)
- CLI-флаги `--all`, `--process`, `--no-db` (~15 строк × 12 = 180 строк)
- `ensure_outlet()` — INSERT outlet ON CONFLICT DO NOTHING (~10 строк × 12 = 120 строк)
- Connection cleanup в `try/finally` — везде одинаково

---

## Решение

### Часть 1: Критические баги (приоритет — сейчас)

#### 1.1 Дополнить db_wrapper.TABLE_MAPPING

```python
# SHOPS/db_wrapper.py — добавить маппинги:
TABLE_MAPPING = {
    # ... существующие ...

    # Profi
    "profi_staging": "profi_staging",
    "profi_nomenclature": "profi_nomenclature",
    "profi_prices": "profi_prices",
    "profi_current_prices": "profi_prices",  # алиас

    # Taggsm
    "taggsm_staging": "taggsm_staging",
    "taggsm_nomenclature": "taggsm_nomenclature",
    "taggsm_prices": "taggsm_prices",

    # signal23
    "signal23_staging": "signal23_staging",
    "signal23_nomenclature": "signal23_nomenclature",
    "signal23_prices": "signal23_prices",

    # Liberti
    "liberti_staging": "liberti_staging",
    "liberti_nomenclature": "liberti_nomenclature",
    "liberti_prices": "liberti_prices",

    # memstech
    "memstech_staging": "memstech_staging",
    "memstech_nomenclature": "memstech_nomenclature",
    "memstech_prices": "memstech_prices",
}
```

Дополнительно — проверить что каждый из этих парсеров использует полные имена таблиц,
а не generic (`staging`, `nomenclature`, `current_prices`).

#### 1.2 Исправить signal23/parser.py

Заменить `INSERT INTO staging` → `INSERT INTO signal23_staging` во всём файле.
Аналогично проверить `nomenclature` → `signal23_nomenclature`, `current_prices` → `signal23_prices`.

#### 1.3 Исправить Orizhka/parser.py

Найти и удалить все INSERT в старые таблицы: `products`, `outlets`, `cities`.
Оставить только INSERT в `orizhka_nomenclature`, `orizhka_prices`, `orizhka_staging`, `zip_outlets`.

---

### Часть 2: Очистка файлов

#### 2.1 GreenSpark/ — переместить в _legacy/ или удалить

Создать `GreenSpark/_legacy/` если нет, переместить:
- `parser.py` → `_legacy/`
- `parser_v3.py` → `_legacy/`
- `reparse_articles_standalone.py` → `_legacy/`

Удалить тест/дебаг файлы (не используются в production):
- `test_api.py`, `test_api2.py`, `test_api3.py`, `test_api_article.py`
- `test_protocols.py`, `test_socks5_noverify.py`
- `debug_api.py`, `check_articles.py`, `recent_updates.py`, `analyze_missing.py`
- `fill_articles.py`

Оставить (используются в production):
- `parser_v4.py`, `config.py`, `telegram_notifier.py`
- `proxy_generator.py`, `coordinator.py` — если используются, иначе тоже в _legacy/
- `get_cookies.py`, `stealth_cookies.py` — если используются

#### 2.2 Moba/ — задокументировать назначение файлов

**Активные в cron:**
- `moba_parser.py` — основной парсер
- `write_to_db.py` — запись в БД (вызывается отдельно)
- `moba_playwright_parser.py` — Playwright-вариант (тоже в cron)

**Переместить в Moba/_legacy/ или удалить:**
- `moba_full_parser.py` — дублирует moba_parser или устарел?
- `moba_multicity_parser.py` — дублирует moba_parser или устарел?
- Утилиты cookies: `get_cookies_cdp.py`, `get_cookies_frida.py`, `get_cookies_http.py`, `get_cookies_ws.py`
- `capture_moba.py`, `cdp_browser.py`, `parse_cookies.py`
- Тесты: `test_access.py`, `test_moba.py`, `test_mobile.py`

Для каждого файла — либо добавить комментарий назначения в шапку, либо удалить.

#### 2.3 Profi/ — задокументировать

**Активен:** `parser.py`

**Задокументировать или перенести в _legacy/:**
- `parse_price.py` — если это альтернативный режим парсинга, добавить в шапку описание
- `parse_price_n8n.py` — n8n интеграция, явно помечена ли как deprecated?
- `parser_server.py` — server-mode, добавить описание в шапку
- `check_akb.py` — отладочный, переместить в `_legacy/` или удалить

---

### Часть 3: Выделение общего кода (DRY)

> **Приоритет: низкий.** Делать ТОЛЬКО после того, как Части 1 и 2 выполнены и протестированы.

Создать `SHOPS/parser_base.py`:

```python
# SHOPS/parser_base.py
"""Общие утилиты для всех парсеров."""

import argparse
import psycopg2
from typing import List, Dict, Optional


def add_standard_args(parser: argparse.ArgumentParser):
    """Стандартные CLI флаги для всех парсеров."""
    parser.add_argument('--all', action='store_true', help='Парсинг + process_staging')
    parser.add_argument('--process', action='store_true', help='Только process_staging')
    parser.add_argument('--no-db', action='store_true', help='Без записи в БД')
    parser.add_argument('--no-staging', action='store_true', help='Пропустить staging, сразу в prices')


def save_staging_generic(conn, staging_table: str, products: List[Dict], fields: List[str]):
    """Очистить staging таблицу и записать новые данные.

    fields — список колонок (кроме id, created_at, processed).
    products — список dict с этими ключами.
    """
    cur = conn.cursor()
    try:
        cur.execute(f"TRUNCATE TABLE {staging_table}")
        if products:
            cols = ", ".join(fields)
            placeholders = ", ".join(["%s"] * len(fields))
            sql = f"INSERT INTO {staging_table} ({cols}, processed) VALUES ({placeholders}, false)"
            for p in products:
                cur.execute(sql, tuple(p.get(f) for f in fields))
        conn.commit()
        return len(products)
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close()


def process_staging_generic(
    conn,
    staging_table: str,
    nom_table: str,
    prices_table: str,
    outlet_code: str,
    nom_conflict_col: str = "article",
):
    """Перенести данные из staging → nomenclature + prices.

    Стандартный UPSERT: staging → nomenclature по article, prices по (nom_id, outlet_id).
    """
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM zip_outlets WHERE code = %s", (outlet_code,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Outlet '{outlet_code}' не найден в zip_outlets")
        outlet_id = row[0]

        # staging → nomenclature
        cur.execute(f"""
            INSERT INTO {nom_table} (article, name, category, updated_at)
            SELECT DISTINCT ON (article) article, name, category, NOW()
            FROM {staging_table}
            WHERE article IS NOT NULL AND processed = false
            ON CONFLICT ({nom_conflict_col}) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                updated_at = NOW()
        """)

        # staging → prices
        cur.execute(f"""
            INSERT INTO {prices_table} (nomenclature_id, outlet_id, price, price_wholesale, product_url, updated_at)
            SELECT n.id, %s, s.price, s.price_wholesale, s.url, NOW()
            FROM {staging_table} s
            JOIN {nom_table} n ON n.article = s.article
            WHERE s.processed = false
            ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
                price = EXCLUDED.price,
                price_wholesale = EXCLUDED.price_wholesale,
                product_url = EXCLUDED.product_url,
                updated_at = NOW()
        """, (outlet_id,))

        cur.execute(f"UPDATE {staging_table} SET processed = true WHERE processed = false")
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close()
```

**Миграция парсеров на parser_base.py:**

Делать постепенно, по одному парсеру. Начинать с самых простых (05GSM, signal23).
Каждый раз: тест `--no-db`, тест `--process`, проверить данные в БД.

**Этот этап — опциональный.** Если текущий код работает стабильно, можно отложить.

---

## Порядок выполнения

| # | Задача | Файлы | Приоритет |
|---|--------|-------|-----------|
| 1 | Исправить signal23 staging → signal23_staging | signal23/parser.py | **Критический** |
| 2 | Исправить Orizhka двойные INSERT | Orizhka/parser.py | **Критический** |
| 3 | Дополнить TABLE_MAPPING в db_wrapper | db_wrapper.py | **Высокий** |
| 4 | GreenSpark: переместить legacy + удалить тесты | GreenSpark/ | Средний |
| 5 | Moba: задокументировать/очистить варианты | Moba/ | Средний |
| 6 | Profi: задокументировать parse_price*.py | Profi/ | Низкий |
| 7 | Создать parser_base.py + мигрировать 2-3 парсера | SHOPS/ | Низкий |

---

## Верификация

```bash
# P1: db_wrapper покрывает все магазины
# Для каждого парсера убедиться что SQL INSERT использует полные имена таблиц

# P2: signal23 staging
grep -n "INSERT INTO staging" SHOPS/signal23/parser.py  # должно быть 0

# P3: Orizhka нет старых таблиц
grep -n "INTO products\|INTO outlets\|INTO cities" SHOPS/Orizhka/parser.py  # 0

# P4-P6: нет лишних файлов
ls SHOPS/GreenSpark/*.py | grep -v parser_v4 | grep -v config | grep -v telegram | grep -v proxy  # только _legacy/

# Тест каждого парсера после изменений
python3 parser.py --no-db   # запускается без ошибок
```

---

## Что НЕ входит в этот ТЗ

- Логика парсинга (HTTP-запросы, HTML-парсинг) — не трогать
- GreenSpark parser_v4.py — уже переписан, не рефакторить
- proxy-service интеграция — отдельный компонент
- RealTime/parser.py — будущий per-product парсер, отдельный контекст
- n8n воркеры — отдельный проект
