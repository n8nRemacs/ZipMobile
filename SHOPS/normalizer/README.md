# ZipMobile Normalizer API

Микросервис нормализации товаров — связывает товары из магазинов (`{shop}_nomenclature`) с центральной номенклатурой (`zip_nomenclature`) через AI-классификацию, извлечение бренда/моделей и человеческую модерацию.

## Архитектура

```
Парсер магазина
    │
    ▼
{shop}_nomenclature (zip_nomenclature_id = NULL)
    │
    ▼
┌───────────────────────────────────────────────┐
│              Normalizer API (:8200)            │
│                                                │
│  Stage 0 (опц.)  AI-классификация             │
│       │          "это запчасть?"               │
│       ▼                                        │
│  Stage 1         AI-извлечение                 │
│       │          бренд + модели из имени        │
│       ▼                                        │
│  Stage 2         SQL exact match               │
│       │          → найдено: привязка            │
│       │          → не найдено: AI-валидация     │
│       │               → совпало: привязка       │
│       │               → новый: → модерация      │
│       ▼                                        │
│  zip_moderation_queue                          │
│       │                                        │
│  Модератор (Admin UI) разрешает                │
│       │                                        │
│  → создать/привязать в справочнике             │
└───────────────────────────────────────────────┘
    │
    ▼
zip_nomenclature (центральная номенклатура)
```

## Стек технологий

- **Python 3.11+**
- **FastAPI** — async HTTP framework
- **asyncpg** — async PostgreSQL driver (Supabase)
- **httpx** — async HTTP client (для n8n webhooks)
- **Pydantic v2** — валидация данных и настройки
- **n8n** — оркестрация AI-воркфлоу (классификация, извлечение, валидация)

## Структура файлов

```
normalizer/
├── __init__.py
├── main.py                     # FastAPI приложение, все эндпоинты, lifespan
├── config.py                   # Pydantic Settings (БД, n8n URL, пороги)
├── db.py                       # asyncpg connection pool
├── models.py                   # Pydantic-схемы запросов/ответов
├── tasks.py                    # Менеджер фоновых задач (normalizer_tasks)
├── n8n_client.py               # HTTP-клиент к n8n webhook'ам
├── moderation.py               # CRUD zip_moderation_queue
└── stages/
    ├── __init__.py
    ├── stage0_classify.py      # AI: классификация (запчасть или нет)
    ├── stage1_brand_models.py  # AI: извлечение бренда и моделей из названия
    └── stage2_merge.py         # SQL exact match → AI валидация → модерация
```

## Конфигурация

Все настройки через переменные окружения с префиксом `NORMALIZER_`:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `NORMALIZER_DB_HOST` | `aws-1-eu-west-3.pooler.supabase.com` | Хост PostgreSQL |
| `NORMALIZER_DB_PORT` | `5432` | Порт PostgreSQL |
| `NORMALIZER_DB_USER` | `postgres.griexhozxrqtepcilfnu` | Пользователь БД |
| `NORMALIZER_DB_PASSWORD` | `***` | Пароль БД |
| `NORMALIZER_DB_NAME` | `postgres` | Имя БД |
| `NORMALIZER_DB_POOL_MIN` | `2` | Мин. размер пула соединений |
| `NORMALIZER_DB_POOL_MAX` | `10` | Макс. размер пула соединений |
| `NORMALIZER_SERVER_PORT` | `8200` | Порт HTTP-сервера |
| `NORMALIZER_N8N_BASE_URL` | `http://localhost:5678` | Базовый URL n8n |
| `NORMALIZER_N8N_CLASSIFY_URL` | `/webhook/normalizer/classify` | Webhook классификации |
| `NORMALIZER_N8N_EXTRACT_BRAND_MODELS_URL` | `/webhook/normalizer/extract-brand-models` | Webhook извлечения бренда/моделей |
| `NORMALIZER_N8N_VALIDATE_BRAND_URL` | `/webhook/normalizer/validate-brand` | Webhook валидации бренда |
| `NORMALIZER_N8N_VALIDATE_MODELS_URL` | `/webhook/normalizer/validate-models` | Webhook валидации моделей |
| `NORMALIZER_CONFIDENCE_THRESHOLD` | `0.8` | Порог AI-уверенности (ниже → модерация) |
| `NORMALIZER_HTTP_TIMEOUT` | `60` | Таймаут HTTP-запросов (сек.) |

## API эндпоинты

### Нормализация

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/normalize` | Нормализация одной записи (синхронно) |
| `POST` | `/normalize/batch` | Пакетная нормализация (фоновая задача) |
| `POST` | `/normalize/shop/{shop_code}` | Нормализация всех ненормализованных товаров магазина (фоновая задача) |
| `GET` | `/normalize/status` | Статистика нормализации по всем магазинам |

#### `POST /normalize`

Запрос:
```json
{
  "article": "TEST-001",
  "name": "Дисплей iPhone 14 Pro OLED GX черный",
  "shop_code": "profi",
  "url": "https://example.com/product/123",
  "classify": false
}
```

Ответ:
```json
{
  "article": "TEST-001",
  "status": "normalized",
  "brand_id": 1,
  "brand_name": "Apple",
  "model_ids": [42, 43],
  "model_names": ["iPhone 14 Pro"],
  "moderation_ids": [],
  "confidence": 0.95
}
```

Возможные `status`:
- `normalized` — бренд и модели успешно найдены в справочниках
- `needs_moderation` — AI не уверен или сущность не найдена, создана запись в `zip_moderation_queue`
- `not_spare_part` — AI-классификация определила что товар не является запчастью (только при `classify: true`)

#### `POST /normalize/batch`

Запрос:
```json
{
  "items": [
    {"article": "A1", "name": "Дисплей Samsung A52", "shop_code": "profi"},
    {"article": "A2", "name": "Стекло Xiaomi 12", "shop_code": "profi"}
  ]
}
```

Ответ:
```json
{"task_id": "550e8400-e29b-41d4-a716-446655440000"}
```

#### `POST /normalize/shop/{shop_code}`

Читает все записи из `{shop_code}_nomenclature` где `zip_nomenclature_id IS NULL` и нормализует их в фоне.

Ответ:
```json
{"task_id": "...", "total": 150}
```

### Модерация

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/moderate` | Список pending-записей (фильтры: `entity_type`, `shop_code`, `limit`, `offset`) |
| `GET` | `/moderate/stats` | Статистика: кол-во по типам и статусам |
| `GET` | `/moderate/{id}` | Детали одной записи |
| `POST` | `/moderate/{id}/resolve` | Разрешить запись: привязать к существующей сущности или создать новую |

#### `POST /moderate/{id}/resolve`

Привязка к существующему бренду:
```json
{"existing_id": 3}
```

Создание нового бренда:
```json
{"create_new": true, "new_name": "Tecno"}
```

Создание новой модели (с указанием бренда):
```json
{"create_new": true, "new_name": "Galaxy S24 Ultra", "new_data": {"brand_id": 2}}
```

### Справочники

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/dict/brands` | Все бренды (опц. `?q=` для поиска) |
| `GET` | `/dict/models` | Модели (опц. `?brand_id=`, `?q=`) |
| `GET` | `/dict/part_types` | Типы запчастей |
| `GET` | `/dict/colors` | Цвета |

### Задачи и инфраструктура

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/task/{task_id}` | Статус фоновой задачи |
| `GET` | `/health` | Проверка здоровья (БД) |
| `GET` | `/stats` | Общая статистика |

## Зависимые таблицы БД

### Создаются миграцией `024_normalizer_tables.sql`

- **`zip_moderation_queue`** — очередь модерации (brand/model/part_type/color). Статусы: `pending` → `resolved`
- **`zip_shop_price_types`** — маппинг типов цен по магазинам
- **`normalizer_tasks`** — фоновые задачи нормализатора (UUID PK, status, progress JSONB, result JSONB)

### Читаемые таблицы (уже существуют)

- `zip_dict_brands` — справочник брендов
- `zip_dict_models` — справочник моделей (+ `brand_id`)
- `zip_dict_part_types` — справочник типов запчастей
- `zip_dict_colors` — справочник цветов
- `zip_shops` — реестр магазинов
- `{shop}_nomenclature` — таблицы номенклатуры каждого магазина

## Pipeline нормализации (подробно)

### Stage 0: Классификация (опционально, `classify: true`)

Вызывает n8n webhook `/webhook/normalizer/classify` с `{name, article}`.
Ответ n8n: `{is_spare_part: bool, nomenclature_type: str, confidence: float}`.
Если `is_spare_part = false` — возвращаем `status: "not_spare_part"` и прекращаем.

### Stage 1: Извлечение бренда и моделей

Вызывает n8n webhook `/webhook/normalizer/extract-brand-models` с `{name}`.
AI извлекает из строки вида `"Дисплей iPhone 14 Pro OLED GX черный"`:
```json
{"brand": "Apple", "models": ["iPhone 14 Pro"], "confidence": 0.95}
```

### Stage 2: Merge и валидация

**2a. SQL exact match бренда:**
```sql
SELECT id, name FROM zip_dict_brands WHERE LOWER(TRIM(name)) = LOWER(TRIM($1))
```

**2b. Если не найден — AI-валидация:**
Загружаем все бренды из `zip_dict_brands`, отправляем в n8n `/webhook/normalizer/validate-brand`.
AI ищет похожий бренд (опечатки, альтернативные написания).
- Нашёл совпадение → используем `match_id`
- Новый бренд → создаём запись в `zip_moderation_queue` с `entity_type='brand'`

**2c. Аналогично для моделей:**
SQL exact match по `zip_dict_models WHERE brand_id = $1` → AI-валидация → модерация.

**2d. Результат:**
- Все найдено → `status: "normalized"`, возвращаем `brand_id`, `model_ids`
- Что-то не найдено → `status: "needs_moderation"`, возвращаем `moderation_ids`

## n8n Webhooks

Нормализатор ожидает 4 webhook'а в n8n:

### 1. `/webhook/normalizer/classify`
**Вход:** `{name: str, article: str}`
**Выход:** `{is_spare_part: bool, nomenclature_type: str | null, confidence: float}`

### 2. `/webhook/normalizer/extract-brand-models`
**Вход:** `{name: str}`
**Выход:** `{brand: str | null, models: [str], confidence: float}`

### 3. `/webhook/normalizer/validate-brand`
**Вход:** `{brand_raw: str, all_brands: [{id, name}]}`
**Выход:** `{is_new: bool, match_id: int | null, match: str | null, confidence: float, reasoning: str}`

### 4. `/webhook/normalizer/validate-models`
**Вход:** `{models_raw: [str], brand_id: int, all_models: [{id, name}]}`
**Выход:** `{matches: [{model: str, is_new: bool, match_id: int | null, match: str | null, confidence: float, reasoning: str}]}`

## Запуск

```bash
# 1. Применить миграцию
psql $DATABASE_URL -f sql/migrations/024_normalizer_tables.sql

# 2. Запуск (из корня проекта)
cd SHOPS/normalizer
uvicorn main:app --host 0.0.0.0 --port 8200 --reload

# Или через Python
python -m SHOPS.normalizer.main
```

## Примеры curl

```bash
# Нормализация одного товара
curl -X POST http://localhost:8200/normalize \
  -H "Content-Type: application/json" \
  -d '{"article":"TEST-001","name":"Дисплей iPhone 14 Pro OLED GX черный","shop_code":"profi"}'

# С классификацией
curl -X POST http://localhost:8200/normalize \
  -d '{"article":"TEST-002","name":"Чехол iPhone 14","shop_code":"test","classify":true}'

# Нормализация всех ненормализованных товаров Profi
curl -X POST http://localhost:8200/normalize/shop/profi

# Статус задачи
curl http://localhost:8200/task/550e8400-e29b-41d4-a716-446655440000

# Список записей на модерацию
curl "http://localhost:8200/moderate?entity_type=brand&limit=10"

# Разрешить модерацию — использовать существующий бренд
curl -X POST http://localhost:8200/moderate/1/resolve \
  -H "Content-Type: application/json" \
  -d '{"existing_id": 3}'

# Разрешить модерацию — создать новый бренд
curl -X POST http://localhost:8200/moderate/1/resolve \
  -H "Content-Type: application/json" \
  -d '{"create_new": true, "new_name": "Tecno"}'

# Справочник брендов с поиском
curl "http://localhost:8200/dict/brands?q=app"

# Модели бренда
curl "http://localhost:8200/dict/models?brand_id=1"

# Статистика модерации
curl http://localhost:8200/moderate/stats

# Статистика нормализации по магазинам
curl http://localhost:8200/normalize/status

# Health check
curl http://localhost:8200/health
```

## Связь с другими сервисами

- **Profi Sandbox** (`:8100`) — парсер Profi, заполняет `profi_nomenclature`
- **Admin UI** (`:3000`) — React SPA для модерации и управления справочниками
- **n8n** (`:5678`) — AI-воркфлоу для классификации/извлечения/валидации
- **Supabase PostgreSQL** — единая БД для всех сервисов
