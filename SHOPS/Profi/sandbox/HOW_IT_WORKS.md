# Profi Sandbox — Как работает

Песочница нормализации магазина Profi (siriust.ru).
Автономный FastAPI сервер: парсинг Excel прайсов, предподготовка, rule-based сопоставление
с центральными справочниками zip_dict_*, AI-донормализация, экспорт в zip.

---

## Общая схема (pipeline)

```
Excel прайсы (43 outlet-а siriust.ru)
        │
        ▼
  ┌─────────────┐
  │  БЛОК 1     │  Скачивание + парсинг Excel
  │  Парсинг    │  Font-size → brand_raw / model_raw / part_type_raw
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  БЛОК 2     │  ProfiNormalizer (9 шагов из Normalize_v2.json)
  │  Предподго- │  brand_raw → brand (чистый)
  │  товка      │  part_type_raw → part_type (чистый)
  └──────┬──────┘  is_spare_part = true/false
         │
         ▼
  ┌─────────────┐
  │  БЛОК 3     │  brand → zip_dict_brands (exact match SQL)
  │  Rule-based │  part_type → PART_TYPE_MAPPING → zip_dict_part_types (exact match)
  │  сопоставле-│  Результат: zip_brand_id, zip_part_type_id
  │  ние        │  Что не нашлось → needs_ai = true
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  БЛОК 4     │  match_and_normalize_v3() — SQL функция
  │  AI норма-  │  4-агентный payload
  │  лизация    │  Результат: zip_nomenclature_id
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  БЛОК 5     │  profi_nomenclature → zip_nomenclature
  │  Экспорт    │  profi_prices → zip_current_prices
  │  в zip      │
  └─────────────┘
```

---

## БЛОК 1: Парсинг Excel

**Сервис:** `services/parser_service.py`
**Endpoints:** `POST /parse/all`, `POST /parse/outlet/{code}`, `POST /parse/dynamic`

### Источник данных

43 торговые точки Profi по всей России. Каждая точка — отдельный .xls файл
на siriust.ru. Список URL захардкожен в `price_lists_config.py`.

### Шаг 1.1: Скачивание

- `httpx.AsyncClient` скачивает .xls файл во временный файл
- Параллельно до 10 файлов (`asyncio.Semaphore`)
- Timeout: 60 секунд на файл

### Шаг 1.2: Определение структуры Excel

- `openpyxl.load_workbook()` открывает файл (через `asyncio.to_thread` — CPU-bound)
- Ищет строку заголовков: ячейка содержащая "наимен"
- Маппит колонки: наименование, артикул, цена

### Шаг 1.3: Определение категорий по размеру шрифта

Profi использует размер шрифта для иерархии категорий в Excel:

| Font size | Значение | Пример |
|-----------|----------|--------|
| **11** | Бренд (brand_raw) | `1. ЗАПЧАСТИ ДЛЯ APPLE` |
| **10** | Модель (model_raw) | `ЗАПЧАСТИ ДЛЯ APPLE IPHONE` |
| **9** | Тип запчасти (part_type_raw) | `ДИСПЛЕИ OLED` |
| другой | Строка товара | `Дисплей iPhone 14 Pro OLED GX черный` |

Парсер читает сверху вниз, запоминая текущий brand/model/part_type.
Каждая строка товара наследует категории от последних встреченных заголовков.

### Шаг 1.4: Извлечение данных товара

Для каждой строки товара извлекается:
- `article` — артикул
- `name` — наименование
- `brand_raw` — текущий бренд (font-size 11)
- `model_raw` — текущая модель (font-size 10)
- `part_type_raw` — текущий тип запчасти (font-size 9)
- `price` — цена (regex парсинг числа)
- `city`, `shop`, `outlet_code` — из конфига точки

### Шаг 1.5: Сохранение в БД

- `profi_nomenclature` — UPSERT по article (article, name, brand_raw, model_raw, part_type_raw)
- `profi_prices` — UPSERT по (article, outlet_code) (цена, город)

---

## БЛОК 2: Предподготовка (при парсинге)

**Логика:** `ProfiNormalizer` из `parser_clean.py`
**Когда:** Выполняется при парсинге, до сохранения в БД

Последовательность 7 шагов из Normalize_v2.json:

### Шаг 2.1: Фильтрация — только запчасти

Оставляем только:
- `brand_raw = '1. ЗАПЧАСТИ ДЛЯ APPLE'`
- `brand_raw = '2. ЗАПЧАСТИ ДЛЯ СОТОВЫХ'`
- `brand_raw = '3. АКСЕССУАРЫ'` + `model_raw = 'АКБ ДЛЯ МОБИЛЬНОЙ ТЕХНИКИ'`

Всё остальное (аксессуары, чехлы, стёкла) → `is_spare_part = false`, пропускаем.

### Шаг 2.2: Нормализация brand и model

| brand_raw | → brand |
|-----------|---------|
| `1. ЗАПЧАСТИ ДЛЯ APPLE` | `Apple` |
| `2. ЗАПЧАСТИ ДЛЯ СОТОВЫХ` | `Android` |
| `3. АКСЕССУАРЫ` | `АКБ` |

| model_raw | → model |
|-----------|---------|
| `ЗАПЧАСТИ ДЛЯ APPLE IPHONE` | `iPhone` |
| `ЗАПЧАСТИ ДЛЯ APPLE IPAD` | `iPad` |
| `ЗАПЧАСТИ ДЛЯ APPLE WATCH` | `Apple Watch` |
| `ЗАПЧАСТИ ДЛЯ APPLE MACBOOK` | `MacBook` |
| `ЗАПЧАСТИ ДЛЯ APPLE AIRPODS` | `AirPods` |
| Остальное | Убираем префикс `ЗАПЧАСТИ ДЛЯ` |

### Шаг 2.3: Обрезка part_type для iPhone

Для iPhone обрезаем part_type до первого слова "ДЛЯ":
- `ДИСПЛЕИ ДЛЯ IPHONE 14` → `ДИСПЛЕИ`
- `КАМЕРЫ ДЛЯ IPHONE 15 PRO` → `КАМЕРЫ`

### Шаг 2.4: Перенос model → brand

После шага 2.2 в model лежит фактический бренд. Переносим:
- `brand='Apple', model='iPhone'` → `brand='iPhone', model=NULL`
- `brand='Android', model='SAMSUNG'` → `brand='SAMSUNG', model=NULL`

### Шаг 2.6: АКБ для мобильной техники

Для `model_raw = 'АКБ ДЛЯ МОБИЛЬНОЙ ТЕХНИКИ'`:
- `part_type_raw = 'АКБ XIAOMI'` → `brand='XIAOMI', part_type='АКБ'`
- `part_type_raw = 'АКБ ДЛЯ SAMSUNG'` → `brand='SAMSUNG', part_type='АКБ'`

### Шаг 2.7: Нормализация УНИВЕРСАЛЬНЫЙ

- `УНИВЕРСАЛЬНЫЕ ЗАПЧАСТИ` → `УНИВЕРСАЛЬНЫЙ`
- Любое `*универсал*` → `УНИВЕРСАЛЬНЫЙ`

### Шаг 2.9: Приведение part_type к единому виду

37 маппингов множественного числа и вариаций к канонической форме:

| Из прайса | → Каноническая форма |
|-----------|---------------------|
| ДИСПЛЕИ, ДИСПЛЕИ INCELL, ДИСПЛЕИ OLED, ... | ДИСПЛЕЙ |
| КАМЕРЫ | КАМЕРА |
| ЗАДНИЕ КРЫШКИ, ЗАДНЯЯ КРЫШКИ | КРЫШКА ЗАДНЯЯ |
| КНОПКИ, КНОПКИ ВКЛЮЧЕНИЯ | КНОПКА |
| ШЛЕЙФА, ШЛЕЙФЫ, ШЛЕЙФА ДЛЯ IPAD | ШЛЕЙФ |
| РАЗЪЕМЫ ДЛЯ ЗАРЯДКИ, РАЗЪЕМЫ ЗАРЯДКИ | РАЗЪЕМ ЗАРЯДКИ |
| ... | ... |

**Результат предподготовки:** в `profi_nomenclature` лежат чистые `brand`, `model`,
`part_type` — но это всё ещё "профи-шные" значения, не привязанные к zip.

---

## БЛОК 3: Rule-based сопоставление с zip_dict_*

**Сервис:** `services/normalizer_service.py`
**Endpoint:** `POST /normalize/rules`

Задача: сопоставить чистые значения из предподготовки с центральными справочниками.

### Почему exact match, а не fuzzy

В Profi бренды чёткие — после предподготовки они совпадают 1:1 с `zip_dict_brands`.
Нет склонений, альтернативного написания или опечаток. iPhone это iPhone,
SAMSUNG это SAMSUNG.

Типы запчастей — тоже конечный набор после маппинга. ДИСПЛЕЙ это ДИСПЛЕЙ.

### Шаг 3.1: Бренды — один SQL запрос

```sql
UPDATE profi_nomenclature pn
SET zip_brand_id = zb.id, brand_normalized = zb.name
FROM zip_dict_brands zb
WHERE LOWER(TRIM(pn.brand)) = LOWER(TRIM(zb.name))
  AND pn.zip_brand_id IS NULL
  AND pn.is_spare_part = true
```

Один запрос, без циклов, закрывает ~95% записей по бренду.

### Шаг 3.2: Типы запчастей — PART_TYPE_MAPPING + SQL

1. Python-маппинг: `PART_TYPE_MAPPING[part_type.upper()]` → каноническая форма
   (убирает множественное число, склонения, вариации)
2. Записываем в `part_type_normalized`
3. SQL exact match:

```sql
UPDATE profi_nomenclature pn
SET zip_part_type_id = zpt.id
FROM zip_dict_part_types zpt
WHERE LOWER(TRIM(pn.part_type_normalized)) = LOWER(TRIM(zpt.name))
```

### Шаг 3.3: Расстановка флагов

- `zip_brand_id IS NOT NULL AND zip_part_type_id IS NOT NULL` → `needs_ai = false` (готово)
- Иначе → `needs_ai = true` (отправится в AI)

### Ожидаемый результат

Rule-based закрывает ~95%+ записей Profi. В AI уходят только краевые случаи:
нестандартные типы запчастей, новые бренды которых нет в справочнике.

---

## БЛОК 4: AI нормализация

**Сервис:** `services/normalizer_service.py`
**Endpoint:** `POST /normalize/ai`

Только для записей с `needs_ai = true`. Батчами по 50 штук.

### Формат payload (4-агентный)

SQL функция `match_and_normalize_v3()` ожидает результаты работы 4 AI-агентов:

```json
{
  "article": "ART-001",
  "name": "Дисплей iPhone 14 Pro OLED GX черный",
  "shop_code": "profi",

  "agent1": {
    "brand_raw": "iPhone",
    "part_type_raw": "ДИСПЛЕЙ",
    "confidence": 0.7
  },
  "agent2": {
    "models": [{"name": "iPhone 14 Pro", "is_new": false}],
    "confidence": 0.9
  },
  "agent3": {
    "features": {"technology": "OLED", "originality": "Копия"},
    "confidence": 0.85
  },
  "agent4": {
    "manufacturer": {"value": "GX", "is_new": false},
    "color": {"value": "Черный", "is_new": false},
    "confidence": 0.9
  }
}
```

| Агент | Что определяет | Откуда данные для Profi |
|-------|---------------|----------------------|
| Agent 1 | Бренд, тип запчасти | hints из предподготовки (confidence 0.7) |
| Agent 2 | Модели устройства | AI определяет из name |
| Agent 3 | Характеристики (технология, привязка, оригинальность) | AI определяет из name |
| Agent 4 | Производитель копии, цвет | AI определяет из name |

### Что делает match_and_normalize_v3 (12 шагов)

1. Парсит JSONB payload
2. `match_or_create_brand()` — ищет/создаёт бренд в `brands`
3. Exact + fuzzy match `part_type` в `part_types`
4. `match_or_create_models()` — ищет/создаёт модели (M:N)
5. `match_or_add_manufacturer()` — производитель копии
6. `match_or_create_color()` — цвет
7. Quality из `originality` feature
8. UPSERT в `zip_nomenclature`
9. Синхронизация `nomenclature_models` (M:N связь)
10. Сохранение features в `nomenclature_features`
11. Обновление staging статуса
12. Возвращает `{success, nomenclature_id}`

### Результат

Запись в `profi_nomenclature` получает `zip_nomenclature_id` → связь с центральной
номенклатурой. `needs_ai = false`.

---

## БЛОК 5: Экспорт в zip

**Сервис:** `services/export_service.py`
**Endpoints:** `POST /export/nomenclature`, `POST /export/prices`, `POST /export/full`

### Шаг 5.1: Экспорт номенклатуры

```
profi_nomenclature (zip_brand_id + zip_part_type_id заполнены)
    → UPSERT zip_nomenclature (article, name, brand_id, part_type_id, color_id, source_shop='profi')
    → Получаем zip_nomenclature.id
    → Записываем обратно в profi_nomenclature.zip_nomenclature_id
```

### Шаг 5.2: Экспорт цен

```
profi_prices JOIN profi_nomenclature (zip_nomenclature_id IS NOT NULL)
    → UPSERT zip_current_prices (nomenclature_id, outlet_code, city, price, source_shop='profi')
```

### Превью перед экспортом

`GET /export/preview` показывает без выполнения:
- Сколько записей готово к экспорту
- Сколько новых (ещё нет в zip)
- Сколько цен готово

---

## Дополнительные блоки

### Справочники (dict_service)

`POST /dict/sync` — загружает `zip_dict_brands`, `zip_dict_models`, `zip_dict_part_types`,
`zip_dict_colors` в оперативную память. Используется для быстрого поиска в rule-based.

### Real-time проверка цен (price_service)

`POST /prices/check {"articles": ["ART-001"]}` — скачивает все 43 Excel файла параллельно,
фильтрует только запрошенные артикулы, возвращает актуальные цены из всех точек.
Обновляет `profi_prices`.

### Фоновые задачи (tasks)

Долгие операции (парсинг, нормализация, экспорт) выполняются в фоне:
1. `POST` endpoint создаёт запись в `profi_tasks` со статусом `pending`
2. Возвращает `{task_id}`
3. `asyncio.create_task()` запускает работу, статус → `running`
4. По ходу обновляется `progress` ({"current": 10, "total": 37, "message": "..."})
5. По завершении → `completed` или `failed`
6. Клиент поллит `GET /parse/task/{task_id}`

---

## Специфика песочницы Profi

Каждый магазин имеет свою песочницу нормализации, потому что у каждого свои стартовые данные:

**Profi (эта песочница):**
- Богатые стартовые данные: бренд, модель, тип запчасти уже разложены по font-size
- Бренды чёткие, без склонений — exact match закрывает почти всё
- Типы запчастей — конечный набор, нужен только маппинг множественного числа
- Rule-based закрывает ~95%, AI нужен для единичных случаев

**Другой магазин (гипотетический):**
- Может быть только name одной строкой, без разбивки на brand/model/part_type
- Может не быть артикулов
- Может быть другая система именования
- Rule-based правила совсем другие, AI нужен больше

Именно поэтому песочницы раздельные: правила маппинга настраиваются один раз
под конкретный магазин, а не пытаются быть универсальными.

---

## Запуск

```bash
cd SHOPS/Profi/sandbox
uvicorn main:app --port 8100 --reload
```

## Типичный рабочий цикл

```bash
# 1. Проверить здоровье
curl http://localhost:8100/health

# 2. Загрузить справочники в память
curl -X POST http://localhost:8100/dict/sync

# 3. Распарсить один outlet (тест)
curl -X POST http://localhost:8100/parse/outlet/profi-msk-savelovo
# → {"task_id": "..."}

# 4. Подождать завершения
curl http://localhost:8100/parse/task/{task_id}

# 5. Посмотреть статистику
curl http://localhost:8100/stats

# 6. Rule-based нормализация
curl -X POST http://localhost:8100/normalize/rules

# 7. Посмотреть статус нормализации
curl http://localhost:8100/normalize/status

# 8. AI для оставшихся
curl -X POST http://localhost:8100/normalize/ai

# 9. Превью экспорта
curl http://localhost:8100/export/preview

# 10. Экспорт в zip
curl -X POST http://localhost:8100/export/full
```
