# ТЗ-6: Полный перенос обработки данных на Homelab
Обновлено: 2026-02-19 (GMT+4)

## Контекст

11 парсеров + AI-нормализация (n8n workers v7) работают с Supabase Cloud по сети. Каждый INSERT проходит через интернет (RTT 50-100ms, SSL, PgBouncer). При миллионах строк это создаёт:

- **Медленную запись:** batch=200 × тысячи батчей × 100ms
- **Нестабильность:** интернет/pooler timeout → парсеры встают
- **Ограничения pooler:** port 5432 — max 15 clients
- **Нормализация через сеть:** n8n workers тоже пишут в Cloud

### Решение (v2 — упрощённая архитектура)

**Homelab = рабочая БД:** полная копия всех таблиц. Парсинг и AI-нормализация — локально.
**Cloud = продакшен:** только финальные данные для API (каталог, цены, наличие, справочники).
**Синхронизация:** однонаправленная, Homelab → Cloud, только финальные таблицы.

### Почему Supabase, а не голый PostgreSQL

- Supabase self-hosted даёт PostgreSQL + PostgREST API + Auth + Storage + Realtime
- Может пригодиться для RAG (pgvector), dashboard, других проектов
- Парсеры пишут напрямую в PostgreSQL (psycopg2), не через PostgREST

### Допустимость потери данных

Homelab — не датацентр, может упасть. Но данные **не критичны:**
- **Staging** — промежуточные, пересоздаются при каждом парсинге
- **Nomenclature** — обновляется редко (дни/недели, при поступлении товара)
- **Нормализация** — можно перезапустить, результат идемпотентен
- Падение Homelab на 1-2 дня **ничего не ломает** — прод продолжает работать на Cloud

---

## Архитектура

```
HOMELAB (213.108.170.194)                         CLOUD (Supabase)
┌─────────────────────────────────────────┐       ┌──────────────────────────────┐
│                                         │       │  Supabase Cloud (ПРОД)       │
│  Парсеры (10 шт., cron 1/day)          │       │  griexhozxrqtepcilfnu        │
│  ↓                                      │       │                              │
│  PostgreSQL (Supabase self-hosted)      │       │  ФИНАЛЬНЫЕ ТАБЛИЦЫ:          │
│  localhost:5433                          │       │  ├── zip_nomenclature     ←─── sync
│  ├── {shop}_staging       (local only)  │       │  ├── zip_current_prices   ←─── sync
│  ├── {shop}_nomenclature               │       │  ├── zip_nomenclature_models←─ sync
│  ├── {shop}_parse_log                  │       │  └── zip_nomenclature_features← sync
│  │                                      │       │                              │
│  AI-нормализация (n8n workers v7)      │       │  СПРАВОЧНИКИ:               │
│  ├── zip_nomenclature_staging          │       │  ├── zip_dict_brands      ←─── sync
│  ├── zip_nomenclature                  │       │  ├── zip_dict_models      ←─── sync
│  ├── zip_current_prices               │       │  ├── zip_dict_colors      ←─── sync
│  └── zip_* (все центральные)           │       │  ├── zip_dict_part_types ←─── sync
│                                         │       │  └── zip_dict_features   ←─── sync
│  sync_to_cloud.py (cron, после обработки)│       │                              │
│                                         │       │  ИНФРАСТРУКТУРА (источник):  │
│  sync_from_cloud.py (cron, перед парсингом)│    │  ├── zip_shops ───────────→  │ sync
│                                         │       │  ├── zip_outlets ─────────→  │ sync
│                                         │       │  └── zip_cities ─────────→  │ sync
└─────────────────────────────────────────┘       │                              │
                                                   │  parts-api (port 8000)      │
                                                   │  frontend reads from here   │
                                                   └──────────────────────────────┘
```

### Что на Homelab (рабочая БД — полная копия)

- **Все таблицы** (~60) — полная копия облачной БД
- **Парсеры** — пишут staging/nomenclature/prices локально (<1ms)
- **AI-нормализация** (n8n workers) — работает с локальными таблицами
- **Staging** — никогда не покидает Homelab

### Что на Cloud (прод — только финальные данные)

После очистки на проде останутся **только** таблицы для API:

| Группа | Таблицы | Назначение |
|--------|---------|-----------|
| Каталог | `zip_nomenclature`, `zip_nomenclature_models`, `zip_nomenclature_features` | Унифицированные товары |
| Цены | `zip_current_prices` | Текущие цены |
| Справочники | `zip_dict_brands`, `zip_dict_models`, `zip_dict_colors`, `zip_dict_qualities`, `zip_dict_part_types`, `zip_dict_features`, `zip_dict_device_types`, `zip_dict_categories`, `zip_dict_price_types` | Фильтры и отображение |
| Инфраструктура | `zip_shops`, `zip_outlets`, `zip_cities`, `zip_timezones`, `zip_countries` | Магазины и точки |
| Классификация | `zip_product_types`, `zip_nomenclature_types`, `zip_accessory_types`, `zip_equipment_types` | Типы товаров |
| GSMArena | `zip_gsmarena_phones`, `zip_gsmarena_raw` | Справочник устройств |
| Служебные | `zip_shop_price_types`, `zip_brand_part_type_features` | Конфигурация |

**Не нужны на проде:**
- `{shop}_nomenclature` (×11) — per-shop breakdown, нужен только для работы
- `{shop}_prices` (×11) — per-shop цены
- `{shop}_staging` (×11) — промежуточные данные
- `{shop}_parse_log` (×11) — логи парсеров
- `zip_nomenclature_staging` — staging AI-обработки
- `zip_price_history`, `zip_stock_history` — история (считается из данных)
- `master_unified_nomenclature` — рабочая таблица
- `greenspark_*` — пока не работает

---

## Этап 1: Supabase Self-Hosted (ВЫПОЛНЕН)

Supabase развёрнут на Homelab:
- IP: 213.108.170.194
- PostgreSQL порт: 5433 (direct), 6543 (pooled)
- PostgreSQL пароль: настроен
- 13 сервисов: Studio, Kong, PostgreSQL, Supavisor, PostgREST, GoTrue, Realtime, Storage, Edge Functions, Analytics, Imgproxy, Vector, Meta
- pg_hba.conf: trust для Docker network 172.16.0.0/12

---

## Этап 2: Начальная миграция данных (pg_dump)

### 2.1 Полный дамп из Cloud

Вместо поштучного Python-скрипта — полный pg_dump. Быстрее и надёжнее.

```bash
# На Homelab — дамп всей базы из Cloud
pg_dump "postgresql://postgres.griexhozxrqtepcilfnu:PASSWORD@aws-1-eu-west-3.pooler.supabase.com:5432/postgres?sslmode=require" \
    --no-owner --no-privileges --no-comments \
    --exclude-schema=auth --exclude-schema=storage \
    --exclude-schema=realtime --exclude-schema=supabase_functions \
    --exclude-schema=extensions --exclude-schema=graphql \
    --exclude-schema=graphql_public --exclude-schema=pgbouncer \
    --exclude-schema=pgsodium --exclude-schema=vault \
    --exclude-schema=supabase_migrations \
    -f /tmp/cloud_dump.sql

# Размер: ожидается ~100-500MB (зависит от данных)
```

### 2.2 Восстановление на Homelab

```bash
# Восстановить в локальную БД
psql "postgresql://postgres:PASSWORD@localhost:5433/postgres" < /tmp/cloud_dump.sql
```

### 2.3 Проверка

```bash
# Подсчитать таблицы
psql ... -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"

# Проверить данные
psql ... -c "SELECT COUNT(*) FROM zip_outlets"
psql ... -c "SELECT COUNT(*) FROM moba_nomenclature"
```

---

## Этап 3: Код — db_config.py и sync-скрипты (ВЫПОЛНЕН)

### 3.1 db_config.py — уже обновлён

Парсеры по умолчанию пишут в `DB_TARGET=local`:
- `get_local_config()` → localhost:5433
- `get_cloud_config()` → aws-1-eu-west-3.pooler.supabase.com:5432

### 3.2 Файлы синхронизации

| Файл | Направление | Назначение |
|------|-------------|-----------|
| `sync_to_cloud.py` | Homelab → Cloud | Финальные таблицы (каталог + справочники) |
| `sync_from_cloud.py` | Cloud → Homelab | Инфраструктура (outlets, shops, cities) |

### 3.3 sync_to_cloud.py — новая версия

Синхронизирует **только финальные данные**, не per-shop таблицы:

```python
# Таблицы для синхронизации в Cloud (Homelab → Cloud)
SYNC_TABLES = {
    # Каталог (результат нормализации)
    "zip_nomenclature": "id",
    "zip_nomenclature_models": None,  # composite key
    "zip_nomenclature_features": None,

    # Цены (агрегированные)
    "zip_current_prices": None,

    # Справочники (AI может создавать новые записи)
    "zip_dict_brands": "id",
    "zip_dict_models": "id",
    "zip_dict_colors": "id",
    "zip_dict_qualities": "id",
    "zip_dict_part_types": "id",
    "zip_dict_features": "id",
    "zip_dict_device_types": "id",
    "zip_dict_categories": "id",
    "zip_dict_price_types": "id",
}
```

### 3.4 sync_from_cloud.py (бывший sync_outlets.py)

```python
# Таблицы для синхронизации из Cloud (Cloud → Homelab)
SYNC_TABLES = [
    "zip_shops",
    "zip_outlets",
    "zip_cities",
    "zip_timezones",
    "zip_countries",
]
```

---

## Этап 4: Очистка Cloud после миграции

После успешной миграции и проверки — удалить ненужные таблицы из Cloud.

### 4.1 Таблицы для удаления из Cloud

```sql
-- Per-shop таблицы (данные есть только на Homelab)
-- Для каждого из 11 магазинов:
DROP TABLE IF EXISTS {shop}_staging CASCADE;
DROP TABLE IF EXISTS {shop}_nomenclature CASCADE;
DROP TABLE IF EXISTS {shop}_prices CASCADE;
DROP TABLE IF EXISTS {shop}_parse_log CASCADE;

-- Конкретный список:
DROP TABLE IF EXISTS _05gsm_staging, _05gsm_nomenclature, _05gsm_prices, _05gsm_parse_log CASCADE;
DROP TABLE IF EXISTS memstech_staging, memstech_nomenclature, memstech_prices, memstech_parse_log CASCADE;
DROP TABLE IF EXISTS signal23_staging, signal23_nomenclature, signal23_prices, signal23_parse_log CASCADE;
DROP TABLE IF EXISTS taggsm_staging, taggsm_nomenclature, taggsm_prices, taggsm_parse_log CASCADE;
DROP TABLE IF EXISTS liberti_staging, liberti_nomenclature, liberti_prices, liberti_parse_log CASCADE;
DROP TABLE IF EXISTS profi_staging, profi_nomenclature, profi_prices, profi_current_prices CASCADE;
DROP TABLE IF EXISTS lcdstock_staging, lcdstock_nomenclature_v2, lcdstock_prices_v2 CASCADE;
DROP TABLE IF EXISTS orizhka_staging, orizhka_nomenclature, orizhka_prices CASCADE;
DROP TABLE IF EXISTS moysklad_naffas_staging, moysklad_naffas_nomenclature, moysklad_naffas_prices CASCADE;
DROP TABLE IF EXISTS moba_staging, moba_nomenclature, moba_prices CASCADE;
DROP TABLE IF EXISTS greenspark_staging, greenspark_nomenclature, greenspark_prices, greenspark_parser_progress CASCADE;

-- Рабочие таблицы AI
DROP TABLE IF EXISTS zip_nomenclature_staging CASCADE;

-- История (можно вычислить, не нужна на проде)
DROP TABLE IF EXISTS zip_price_history, zip_stock_history CASCADE;

-- Прочие рабочие
DROP TABLE IF EXISTS master_unified_nomenclature CASCADE;
DROP TABLE IF EXISTS moysklad_naffas_price_history CASCADE;
```

### 4.2 Что остаётся на Cloud

~25 таблиц:

```
zip_nomenclature, zip_nomenclature_models, zip_nomenclature_features
zip_current_prices
zip_dict_brands, zip_dict_models, zip_dict_colors, zip_dict_qualities
zip_dict_part_types, zip_dict_features, zip_dict_device_types
zip_dict_categories, zip_dict_price_types
zip_shops, zip_outlets, zip_cities, zip_timezones, zip_countries
zip_product_types, zip_nomenclature_types, zip_accessory_types, zip_equipment_types
zip_shop_price_types, zip_brand_part_type_features
zip_gsmarena_phones, zip_gsmarena_raw
```

---

## Этап 5: Cron расписание

```cron
# /etc/cron.d/zipmobile (Homelab)

# 1. Синхронизировать инфраструктуру из облака (перед парсингом)
0 2 * * *   root   cd /mnt/projects/repos/ZipMobile/SHOPS && python3 sync_from_cloud.py

# 2. Парсеры (ночью)
10 2 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/05GSM && python3 parser.py --all
15 2 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/signal23 && python3 parser.py --all
20 2 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/Orizhka && python3 parser.py --all
25 2 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/moysklad/Naffas && python3 parser.py --all
30 2 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/lcd-stock && python3 parser.py --all
0  3 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/memstech && python3 parser.py --all
30 3 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/Profi && python3 parser.py --all
0  4 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/Liberti && python3 parser.py --all
30 4 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/Moba && python3 moba_playwright_parser.py
35 4 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/Moba && python3 write_to_db.py
0  5 * * *  root   cd /mnt/projects/repos/ZipMobile/SHOPS/Taggsm && python3 parser.py --all

# 3. AI-нормализация (n8n запускается автоматически по триггеру или webhook)

# 4. Синхронизация финальных данных в прод (после парсинга + нормализации)
0 7 * * *   root   cd /mnt/projects/repos/ZipMobile/SHOPS && python3 sync_to_cloud.py
```

---

## Этап 6: Тестирование

### 6.1 Порядок

1. **pg_dump / restore** — проверить что все таблицы на месте
2. **Запустить 05GSM** (лёгкий парсер) → проверить запись в локальную БД
3. **sync_to_cloud.py --dry-run** → проверить что таблицы для синхронизации определяются
4. **sync_to_cloud.py** → проверить что данные появились в Cloud
5. **parts-api** → проверить что API читает из Cloud нормально
6. **Полный цикл** — все 10 парсеров → нормализация → sync → проверка

### 6.2 Критерии успеха

- [ ] Все таблицы (~60) восстановлены на Homelab из pg_dump
- [ ] 10 парсеров пишут в локальную БД без ошибок
- [ ] AI-нормализация (n8n) работает с локальной БД
- [ ] sync_to_cloud.py переносит финальные данные в Cloud
- [ ] parts-api читает актуальные данные из Cloud
- [ ] Скорость записи парсеров значительно выросла
- [ ] Парсеры работают при отключённом интернете

---

## Порядок выполнения

| # | Задача | Время | Статус |
|---|--------|-------|--------|
| 1 | Установить Supabase self-hosted | 30 мин | DONE |
| 2 | Настроить порты, пароли, pg_hba.conf | 15 мин | DONE |
| 3 | Обновить db_config.py (local/cloud) | 10 мин | DONE |
| 4 | Создать init_local_db.sql (31 таблица) | 20 мин | DONE (заменён pg_dump) |
| 5 | pg_dump Cloud → restore Homelab | 30 мин | TODO |
| 6 | Тест: 05GSM → локальная БД | 5 мин | TODO |
| 7 | Переписать sync_to_cloud.py (финальные таблицы) | 30 мин | DONE |
| 8 | Переписать sync_from_cloud.py (инфраструктура) | 15 мин | DONE |
| 9 | Тест: sync → Cloud | 5 мин | TODO |
| 10 | Полный цикл всех 10 парсеров | 60 мин | TODO |
| 11 | Настроить n8n на локальную БД | 30 мин | TODO |
| 12 | Настроить cron | 10 мин | TODO |
| 13 | Очистить ненужные таблицы в Cloud | 5 мин | TODO |

---

## Файлы

### Новые
| Файл | Назначение |
|------|-----------|
| `SHOPS/init_local_db.sql` | SQL-схема (устарел — заменён pg_dump) |
| `SHOPS/sync_to_cloud.py` | Homelab → Cloud: финальные таблицы |
| `SHOPS/sync_from_cloud.py` | Cloud → Homelab: инфраструктура |

### Изменённые
| Файл | Что менялось |
|------|-------------|
| `SHOPS/db_config.py` | local/cloud конфигурация, DB_TARGET |
| `SHOPS/Moba/write_to_db.py` | Убран хардкод порта 6543 |

### Удалённые / устаревшие
| Файл | Причина |
|------|---------|
| `SHOPS/seed_local_from_cloud.py` | Заменён на pg_dump |
| `SHOPS/sync_outlets.py` | Заменён на sync_from_cloud.py |

---

## Риски и митигация

| Риск | Митигация |
|------|----------|
| Homelab упал | Данные не критичны, прод продолжает работать на Cloud |
| Диск Homelab умер | Финальные данные есть в Cloud, pg_dump повторить |
| pg_dump timeout | Разбить на `--table` по группам, или direct connection |
| sync_to_cloud теряет данные | UPSERT идемпотентен, можно перезапустить |
| n8n не подключается к local DB | Настроить connection string в n8n на localhost:5433 |

---

## Будущее

- **RAG из Supabase:** pgvector extension для embeddings
- **Orchestrator:** FastAPI (port 8100) управляет парсерами + sync через API
- **Per-product парсер (облако):** On-demand проверка цены + наличия по запросу клиента. Результат НЕ сохраняется в БД — возвращается сразу клиенту.
- **Мониторинг:** Grafana / n8n алерты при ошибках парсинга
