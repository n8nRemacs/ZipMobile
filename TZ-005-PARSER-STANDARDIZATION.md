# ТЗ-5: Стандартизация парсеров
Обновлено: 2026-02-19 (GMT+4)

## Контекст

11 парсеров поставщиков запчастей. 7 из 11 уже стандартизированы (подключены к Supabase через db_wrapper, имеют save_staging + process_staging). 4 парсера требуют доработки.

**БД:** Единая Supabase `griexhozxrqtepcilfnu` (PostgreSQL)
**Подключение:** `SHOPS/db_config.py` + `SHOPS/db_wrapper.py`
**Код парсеров:** `SHOPS/` (каждый магазин в своей папке)
**Сервер парсеров:** 85.198.98.104 (путь: /opt/parsers или /root/SHOPS)

---

## Стандарт (эталон)

Эталонные парсеры: **05GSM**, **memstech**, **signal23**, **Taggsm**, **Liberti**

### Структура парсера:
```
SHOPS/{Shop}/
├── config.py          # Конфигурация (BASE_URL, категории, города)
├── parser.py          # Основной парсер
├── requirements.txt   # Зависимости
├── data/              # JSON/CSV выгрузки
└── n8n/               # n8n workflow файлы
```

### Обязательные функции в parser.py:

```python
# 1. Класс парсера
class {Shop}Parser:
    def parse_all(self) -> List[Dict]:
        """Парсинг всех товаров/городов"""
        ...

# 2. Сохранение сырых данных
def save_staging(products: List[Dict]):
    """TRUNCATE staging → INSERT сырые данные"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE staging")  # db_wrapper маппит на {shop}_staging
    for p in products:
        cur.execute("INSERT INTO staging (...) VALUES (...)", (...))
    conn.commit()

# 3. Обработка staging → nomenclature + current_prices
def process_staging():
    """
    1. UPSERT staging → nomenclature (по article)
    2. UPSERT → current_prices (nomenclature_id + outlet_id)
    3. INSERT → price_history (на текущую дату)
    """
    conn = get_db()
    cur = conn.cursor()

    # staging → nomenclature
    cur.execute("""
        INSERT INTO nomenclature (article, name, brand_raw, model_raw, ...)
        SELECT DISTINCT ON (article) article, name, ...
        FROM staging WHERE article IS NOT NULL
        ON CONFLICT (article) DO UPDATE SET
            name = EXCLUDED.name, updated_at = NOW()
    """)

    # staging → current_prices
    cur.execute("""
        INSERT INTO current_prices (nomenclature_id, outlet_id, price, price_wholesale, product_url, updated_at)
        SELECT n.id, o.id, s.price, s.price_wholesale, s.url, NOW()
        FROM staging s
        JOIN nomenclature n ON n.article = s.article
        JOIN outlets o ON o.code = s.outlet_code
        ON CONFLICT (nomenclature_id, outlet_id) DO UPDATE SET
            price = EXCLUDED.price, price_wholesale = EXCLUDED.price_wholesale,
            product_url = EXCLUDED.product_url, updated_at = NOW()
    """)

    conn.commit()

# 4. Точка входа
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--process', action='store_true')
    parser.add_argument('--no-db', action='store_true')
    args = parser.parse_args()

    if args.process:
        process_staging()
        return

    p = {Shop}Parser()
    p.parse_all()

    if not args.no_db:
        save_staging(p.products)
        if args.all:
            process_staging()
```

### Подключение к БД:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db  # Маппит старые имена таблиц на {shop}_*
```

### Таблицы в Supabase (для каждого магазина):
- `{shop}_staging` — сырые данные (TRUNCATE перед каждым парсингом). Без stock полей.
- `{shop}_nomenclature` — уникальные товары (UPSERT по article)
- `{shop}_prices` — текущие цены по точкам (UPSERT по nomenclature_id + outlet_id). Без in_stock, stock_stars, quantity.
- Общая таблица `zip_outlets` (или `outlets` через db_wrapper)

---

---

## v1 DONE — Задачи выполнены (Moba, lcd-stock, Orizhka, GreenSpark стандартизированы)

## v2 — Убрать stock из всей архитектуры

**Контекст v2:** Остатки не хранятся в БД. Данные быстро устаревают, парсеры не дают точных остатков.
В будущем — per-product парсер реального времени (цена + наличие по запросу).

### Что убрать (v2)

**Из {shop}_prices:**
- `in_stock BOOLEAN` — удалить
- `stock_stars SMALLINT` — удалить
- `quantity INTEGER` — удалить

**Из {shop}_staging:**
- `in_stock BOOLEAN` — удалить
- `stock_level VARCHAR(50)` — удалить

**Из zip_outlets:**
- `stock_mode` — удалить (разделение local/api/parse больше не нужно)

**Центральные таблицы (DROP):**
- `zip_current_stock` — удалить
- `zip_stock_history` — удалить

### SQL миграция (Homelab)

```sql
-- 1. Удалить центральные stock таблицы
DROP TABLE IF EXISTS zip_current_stock CASCADE;
DROP TABLE IF EXISTS zip_stock_history CASCADE;

-- 2. Убрать stock_mode из zip_outlets
ALTER TABLE zip_outlets DROP COLUMN IF EXISTS stock_mode;

-- 3. Для каждого {shop} — убрать stock поля из prices
-- (11 магазинов: _05gsm, greenspark, taggsm, memstech, liberti, profi,
--  lcdstock, lcdstock_v2, orizhka, moba, moysklad_naffas, signal23)
ALTER TABLE {shop}_prices DROP COLUMN IF EXISTS in_stock;
ALTER TABLE {shop}_prices DROP COLUMN IF EXISTS stock_stars;
ALTER TABLE {shop}_prices DROP COLUMN IF EXISTS quantity;

-- 4. Для каждого {shop} — убрать stock поля из staging
ALTER TABLE {shop}_staging DROP COLUMN IF EXISTS in_stock;
ALTER TABLE {shop}_staging DROP COLUMN IF EXISTS stock_level;
```

### Статус v2 задач

| Файл | Статус |
|------|--------|
| SQL миграция Homelab | TODO |
| SHOPS/init_local_db.sql | TODO |
| SHOPS/sync_to_cloud.py | TODO |
| SHOPS/GreenSpark/parser_v4.py | TODO |
| Все 12 парсеров (убрать in_stock) | TODO |

---

## Задачи по каждому парсеру (v1)

### 1. Moba — ❌ Не мигрирован на Supabase

**Файл:** `SHOPS/Moba/moba_parser.py`
**Проблема:** Подключается к локальной БД на 85.198.98.104:5433 (db_moba), а не к Supabase.

**Что сделать:**
1. Заменить локальный `get_db()` на импорт из `db_wrapper`:
   ```python
   # УДАЛИТЬ:
   DB_HOST = os.environ.get("DB_HOST", "85.198.98.104")
   DB_PORT = int(os.environ.get("DB_PORT", 5433))
   DB_NAME = os.environ.get("DB_NAME", "db_moba")
   ...
   def get_db(): ...

   # ЗАМЕНИТЬ НА:
   import sys, os
   sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
   from db_wrapper import get_db
   ```
2. Добавить маппинг таблиц в `SHOPS/db_wrapper.py` (если отсутствует):
   ```python
   TABLE_MAPPING = {
       ...
       "staging": "moba_staging",
       "nomenclature": "moba_nomenclature",
       "current_prices": "moba_prices",
       "outlets": "zip_outlets",
   }
   ```
   **Внимание:** db_wrapper маппит по контексту вызова. Проверить что moba_parser.py использует generic имена таблиц (staging, nomenclature, current_prices), а db_wrapper корректно маппит их на moba_*.
3. Убедиться что таблицы `moba_staging`, `moba_nomenclature`, `moba_prices` существуют в Supabase.
4. Проверить что `save_staging` и `process_staging` работают с Supabase.

**Дополнительно:** Moba использует `curl_cffi` для обхода Yandex SmartCaptcha (в `moba_full_parser.py`). Основной парсер — `moba_parser.py`, его и стандартизировать. `moba_full_parser.py` — для сложных случаев, оставить как есть.

---

### 2. lcd-stock — ⚠️ Использует db_config вместо db_wrapper

**Файл:** `SHOPS/lcd-stock/parser.py`
**Проблема:** Подключается через `db_config` напрямую. Таблицы с суффиксом `_v2` (lcdstock_nomenclature_v2, lcdstock_prices_v2). Нет стандартных save_staging / process_staging.

**Что сделать:**
1. Заменить импорт:
   ```python
   # УДАЛИТЬ:
   from db_config import get_db_config, get_table_name
   SHOP_PREFIX = "lcdstock"
   TABLE_NOMENCLATURE = get_table_name(SHOP_PREFIX, "nomenclature_v2")
   ...

   # ЗАМЕНИТЬ НА:
   import sys, os
   sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
   from db_wrapper import get_db
   ```
2. Добавить маппинг `_v2` таблиц в `db_wrapper.py`:
   ```python
   TABLE_MAPPING = {
       ...
       "nomenclature": "lcdstock_nomenclature_v2",
       "current_prices": "lcdstock_prices_v2",
       "staging": "lcdstock_staging",
   }
   ```
   **Или** переименовать таблицы в Supabase, убрав `_v2` (lcdstock_nomenclature, lcdstock_prices). Решение — на усмотрение исполнителя, но задокументировать.
3. Добавить функции `save_staging()` и `process_staging()` по эталону.
4. Обновить `main()` с аргументами `--all`, `--process`, `--no-db`.

---

### 3. Orizhka — ⚠️ Нет save_staging / process_staging

**Файл:** `SHOPS/Orizhka/parser.py`
**Проблема:** Уже подключена через `db_wrapper`. Имеет `save_to_new_schema()` которая напрямую UPSERT-ит в orizhka_nomenclature + orizhka_prices. Нет промежуточного staging и стандартных функций.

**Что сделать:**
1. Добавить `save_staging(products)`:
   - TRUNCATE orizhka_staging
   - INSERT сырые данные из products
2. Добавить `process_staging()`:
   - staging → orizhka_nomenclature (UPSERT по article)
   - staging → orizhka_prices (UPSERT по nomenclature_id + outlet_id)
3. Оставить `save_to_new_schema()` как fallback с флагом `--direct`.
4. Обновить `main()`:
   - По умолчанию: parse → save_staging
   - `--all`: parse → save_staging → process_staging
   - `--direct`: parse → save_to_new_schema (старый режим)
   - `--process`: только process_staging
   - `--no-db`: без БД

---

### 4. GreenSpark — ⚠️ Своя структура

**Файл:** `SHOPS/GreenSpark/parser_v3.py` (основной), `parser.py` (старый)
**Проблема:** parser_v3.py использует `save_products_to_db()` — напрямую UPSERT в greenspark_nomenclature + greenspark_prices. Нет staging. Сложная логика ротации IP, координатор серверов.

**Что сделать:**
1. **НЕ переписывать parser_v3.py** — он работает, сложная логика ротации IP.
2. В `parser.py` (старый) уже есть `save_staging()` + `process_staging()` — они стандартные.
3. Добавить в `parser_v3.py` вызов save_staging/process_staging из parser.py:
   ```python
   # В конце save_products_to_db или как альтернативный режим:
   from parser import save_staging, process_staging

   # Или добавить флаг --use-staging
   if args.use_staging:
       save_staging(parser.products)
       process_staging()
   else:
       save_products_to_db(parser.products)
   ```
4. Убедиться что `greenspark_staging` таблица существует и используется.

---

### 5. Profi — ⚠️ Много legacy файлов

**Файл:** `SHOPS/Profi/parser.py` (основной)
**Проблема:** В папке 10+ файлов парсеров (parse_profi.py, parse_profi_v2.py, parser_clean.py, parser_to_all.py, load_to_db_bulk.py...). Основной parser.py уже имеет save_staging + process_staging и подключен через db_wrapper.

**Что сделать:**
1. **parser.py уже стандартный** — ничего менять не нужно.
2. Удалить или переместить legacy файлы в подпапку `_legacy/`:
   ```
   SHOPS/Profi/_legacy/
   ├── parse_profi.py
   ├── parse_profi (2).py
   ├── parse_profi (3).py
   ├── parse_profi_v2.py
   ├── parse_profi_to_zip.py
   ├── parse_profi_zip.py
   ├── parser_clean.py
   ├── parser_to_all.py
   ├── parser_to_all_xlrd.py
   └── load_to_db_bulk.py
   ```
3. Оставить только:
   ```
   SHOPS/Profi/
   ├── config.py
   ├── parser.py          # Основной (уже стандартный)
   ├── requirements.txt
   ├── data/
   └── n8n/
   ```

---

## Общие задачи

### 6. Проверить db_wrapper.py

`db_wrapper.py` маппит старые имена таблиц на новые. Проблема: маппинг зависит от контекста — если Moba вызывает `INSERT INTO staging`, db_wrapper должен знать что это `moba_staging`, а не `lcdstock_staging`.

**Текущая реализация:** маппинг статический, одинаковый для всех. Это значит что `staging` → `lcdstock_staging` для ВСЕХ парсеров, что неправильно.

**Варианты решения:**
A) Каждый парсер использует полные имена таблиц (`moba_staging`, `moba_nomenclature`) — тогда db_wrapper не нужен
B) Каждый парсер передаёт свой shop_code в db_wrapper
C) Оставить как есть — парсеры уже используют нужные имена через маппинг

**Рекомендация:** Вариант A — все парсеры используют полные имена таблиц напрямую. `db_wrapper` оставить для обратной совместимости, но новый код пишет полные имена. Это проще, понятнее, нет магии.

### 7. Проверить таблицы в Supabase

Подключиться к Supabase и проверить что для каждого магазина существуют все 3 таблицы:

```sql
-- Подключение:
-- psql "postgresql://postgres.griexhozxrqtepcilfnu:Mi31415926pSss!@aws-1-eu-west-3.pooler.supabase.com:5432/postgres?sslmode=require"

-- Проверка:
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND (
    table_name LIKE '%_staging'
    OR table_name LIKE '%_nomenclature%'
    OR table_name LIKE '%_prices%'
)
ORDER BY table_name;
```

Если каких-то таблиц нет — создать по стандарту из PARSER_TABLES_SCHEMA.md.

### 8. Унифицировать config.py

Не все парсеры имеют отдельный config.py. У некоторых конфигурация прямо в parser.py.

**Правило:** Если парсер простой (1 город, мало настроек) — config внутри parser.py допустим. Если много городов/категорий — выносить в config.py.

---

## Порядок выполнения

1. **Profi** — просто навести порядок (удалить legacy) → 5 минут
2. **Orizhka** — добавить save_staging + process_staging → 15 минут
3. **lcd-stock** — переключить на db_wrapper + добавить staging → 15 минут
4. **Moba** — мигрировать на Supabase → 15 минут
5. **GreenSpark** — добавить staging режим → 10 минут
6. **Проверить таблицы** в Supabase → 10 минут
7. **Тестовый запуск** каждого парсера с `--no-db` → 30 минут

---

## Тестирование

Для каждого парсера после стандартизации:

```bash
# 1. Проверить что парсер запускается
cd SHOPS/{Shop}
python3 parser.py --no-db

# 2. Проверить staging
python3 parser.py  # без --all, только staging

# 3. Проверить полный цикл
python3 parser.py --all

# 4. Проверить данные в Supabase
psql "postgresql://postgres.griexhozxrqtepcilfnu:...@aws-1-eu-west-3.pooler.supabase.com:5432/postgres?sslmode=require" \
  -c "SELECT COUNT(*) FROM {shop}_nomenclature; SELECT COUNT(*) FROM {shop}_prices;"
```

---

## Результат

После выполнения все 11 парсеров:
- Подключены к единой Supabase через db_wrapper или напрямую
- Имеют стандартные функции: save_staging, process_staging
- Запускаются одинаково: `python3 parser.py --all`
- Папки чистые, без legacy файлов
- Таблицы в Supabase существуют и заполняются
