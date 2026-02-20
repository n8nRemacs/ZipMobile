# Pipeline нормализации v7.0 — Микросервисная архитектура воркеров

## Обзор

Pipeline v7 реализован как набор **независимых воркеров** (n8n workflows), каждый из которых:
- Имеет свой webhook endpoint
- Отвечает за одну задачу
- Сохраняет результат в `zip_nomenclature_staging`
- Возвращает JSON с результатом

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ВХОДНЫЕ ДАННЫЕ                                   │
│  zip_nomenclature_staging WHERE status = 'pending'                       │
│  name: "Дисплей iPhone 14 Pro Max OLED GX черный с привязкой"           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   WORKER 1    │           │   WORKER 3    │           │   WORKER 5    │
│    Brand      │           │   Part Type   │           │    Color      │
│  (GPT-4o)     │           │  (GPT-4o)     │           │  (Fuzzy)      │
│               │           │               │           │               │
│ → brand_id    │           │ → part_type_id│           │ → color_id    │
└───────┬───────┘           └───────┬───────┘           └───────┬───────┘
        │                           │                           │
        │           ┌───────────────┴───────────────┐           │
        │           │                               │           │
        ▼           ▼                               ▼           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   WORKER 2    │           │   WORKER 4    │           │   WORKER 6    │
│    Model      │           │   Features    │           │   Quality     │
│  (QWen 72B)   │           │  (GPT-4o)     │           │   (Fuzzy)     │
│               │           │               │           │               │
│ → models[]    │           │ → features{}  │           │ → quality_id  │
│  (needs brand)│           │ (needs brand  │           │               │
│               │           │  + part_type) │           │               │
└───────┬───────┘           └───────┬───────┘           └───────┬───────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │          WORKER 7             │
                    │         Price Sync            │
                    │                               │
                    │ 1. Читает staging             │
                    │ 2. UPSERT nomenclature        │
                    │ 3. INSERT model links         │
                    │ 4. UPSERT prices              │
                    │ 5. UPSERT stock               │
                    │ 6. status = 'completed'       │
                    └───────────────────────────────┘
```

---

## Воркеры

### Worker 1: Brand (AI)

**Endpoint:** `POST /worker/brand`

**Модель:** GPT-4o-mini (быстрый, дешевый)

**Задача:** Определить бренд устройства из названия

**Логика:**
1. AI анализирует название
2. Match в `zip_dict_brands` или CREATE новый
3. UPDATE staging SET `normalized_brand_id`, `normalized_brand`

**Маппинг брендов:**
```
iPhone, Айфон → Apple
Galaxy, Самсунг → Samsung
Redmi, Xiaomi → Xiaomi
Honor, Хонор → Honor
Huawei, Хуавей → Huawei
Realme, Реалми → Realme
Poco, Поко → Poco
и т.д.
```

---

### Worker 2: Model (AI)

**Endpoint:** `POST /worker/model`

**Модель:** QWen 2.5 72B (лучше для списков моделей)

**Задача:** Найти ВСЕ модели устройств, с которыми совместима запчасть

**Важно:** Одна запчасть может подходить к НЕСКОЛЬКИМ моделям!

**Примеры:**
- "iPhone 14/14 Pro" → ["iPhone 14", "iPhone 14 Pro"]
- "S21/S21+/S21 Ultra" → ["Galaxy S21", "Galaxy S21+", "Galaxy S21 Ultra"]

**Логика:**
1. Получить список моделей бренда из `zip_dict_models`
2. AI извлекает все модели из названия
3. Fuzzy match каждой модели
4. UPDATE staging SET `normalized_models` (JSONB массив)

**Формат normalized_models:**
```json
[
  {"id": "uuid-1", "name": "iPhone 14 Pro", "is_new": false},
  {"id": "uuid-2", "name": "iPhone 14 Pro Max", "is_new": false}
]
```

**Альтернатива — раздельные воркеры:**
- **Worker 2.1** — только AI извлечение
- **Worker 2.2** — только матчинг и сохранение

---

### Worker 3: Part Type (AI)

**Endpoint:** `POST /worker/part-type`

**Модель:** GPT-4o-mini

**Задача:** Определить тип запчасти из 34 категорий

**Категории (из zip_dict_part_types):**
| ID | Название |
|----|----------|
| 1 | Шлейфы межплатные |
| 2 | Шлейфы на вспышку |
| 3 | Шлейфы на динамики |
| 4 | Шлейфы на дисплей |
| 5 | Шлейфы на зарядку |
| 6 | Шлейфы на кнопки |
| 7 | Шлейфы на прочие |
| 8 | Аккумуляторы |
| 9 | Дисплеи |
| 10 | Задние крышки |
| 11 | Звонки/Динамики |
| 12 | Камеры основные |
| 13 | Камеры фронтальные |
| 14 | Клавиатуры |
| 15 | Коннекторы зарядки |
| 16 | Коннекторы шлейфов |
| 17 | Контейнеры SIM-карт |
| 18 | Корпуса |
| 19 | Средние части корпуса |
| 20 | Микросхемы |
| 21 | Микрофоны |
| 22 | Монтажные наклейки |
| 23 | Скотчи АКБ |
| 24 | Проклейки дисплея |
| 25 | Отражатели подсветки на дисплей |
| 26 | Пленки OCA |
| 27 | Сенсоры дисплея |
| 28 | Стекла дисплеев для переклейки |
| 29 | Стекло на камеру |
| 30 | Шурупы, винты |
| 31 | Аккумуляторы (банки без контроллера) |
| 32 | Платы основные материнские и части |
| 33 | Платы зарядки |
| 34 | Прочее |

**Логика:**
1. AI определяет тип из названия
2. Match в `zip_dict_part_types` (similarity)
3. UPDATE staging SET `normalized_part_type_id`, `normalized_part_type`

---

### Worker 4: Features (AI)

**Endpoint:** `POST /worker/features`

**Модель:** GPT-4o-mini

**Задача:** Извлечь характеристики запчасти

**Характеристики для дисплеев:**
- `technology` — OLED, Hard OLED, Soft OLED, LCD, TFT, Incell
- `manufacturer` — GX, ZY, JK, Tianma, BOE
- `with_frame` — с рамкой / без рамки
- `with_touchscreen` — с тачскрином
- `binding` — требуется привязка

**Логика:**
1. Получить конфигурацию для brand+part_type из `zip_brand_part_type_features`
2. AI извлекает значения характеристик
3. UPDATE staging SET `normalized_features` (JSONB)

**Формат normalized_features:**
```json
{
  "technology": "OLED",
  "manufacturer": "GX",
  "with_frame": true,
  "binding": null
}
```

---

### Worker 5: Color (Fuzzy)

**Endpoint:** `POST /worker/color`

**Без AI** — fuzzy match по справочнику

**Маппинг:**
```javascript
{
  'черн': 'Черный', 'black': 'Черный', 'midnight': 'Черный', 'graphite': 'Черный',
  'бел': 'Белый', 'white': 'Белый', 'starlight': 'Белый', 'silver': 'Белый',
  'золот': 'Золотой', 'gold': 'Золотой',
  'син': 'Синий', 'blue': 'Синий',
  'красн': 'Красный', 'red': 'Красный',
  'зелен': 'Зеленый', 'green': 'Зеленый',
  'фиолет': 'Фиолетовый', 'purple': 'Фиолетовый',
  'розов': 'Розовый', 'pink': 'Розовый',
  'сер': 'Серый', 'gray': 'Серый', 'grey': 'Серый',
  'титан': 'Титановый', 'titanium': 'Титановый',
  // ... и т.д.
}
```

**Логика:**
1. Поиск паттерна цвета в названии
2. Match в `zip_dict_colors`
3. UPDATE staging SET `normalized_color_id`, `normalized_color`

---

### Worker 6: Quality (Fuzzy)

**Endpoint:** `POST /worker/quality`

**Без AI** — fuzzy match по справочнику

**Маппинг (по приоритету):**
```javascript
[
  { patterns: ['ориг', 'original'], quality: 'Оригинал' },
  { patterns: ['service pack', 'сервис пак'], quality: 'Service Pack' },
  { patterns: ['oem'], quality: 'OEM' },
  { patterns: ['hard oled'], quality: 'Hard OLED' },
  { patterns: ['soft oled'], quality: 'Soft OLED' },
  { patterns: ['oled'], quality: 'OLED' },
  { patterns: ['incell'], quality: 'Incell' },
  { patterns: ['tft'], quality: 'TFT' },
  { patterns: ['aaa'], quality: 'Копия AAA' },
  { patterns: [' aa', 'aa '], quality: 'Копия AA' },
  { patterns: ['копия', 'copy'], quality: 'Копия' },
  { patterns: [' gx', 'gx '], quality: 'GX' },
  { patterns: [' zy', 'zy '], quality: 'ZY' },
  { patterns: [' jk', 'jk '], quality: 'JK' },
  { patterns: ['tianma'], quality: 'Tianma' },
]
```

**Логика:**
1. Поиск паттерна качества в названии (первый match по приоритету)
2. Match в `zip_dict_qualities`
3. UPDATE staging SET `normalized_quality_id`, `normalized_quality`

---

### Worker 7: Price Sync

**Endpoint:** `POST /worker/price-sync`

**Задача:** Финализация — создание записей в основных таблицах

**Логика:**
1. SELECT из staging (со всеми normalized_* полями)
2. UPSERT в `zip_nomenclature` → получить nomenclature_id
3. INSERT в `zip_nomenclature_models` (связи M:N из normalized_models)
4. UPSERT в `zip_outlets` → получить outlet_id
5. UPSERT в `zip_current_prices`
6. UPSERT в `zip_current_stock`
7. UPDATE staging SET `status='completed'`, `normalized_nomenclature_id`

---

## Структура staging таблицы

Полная структура после миграции `020_extend_staging_for_workers_v7.sql`:

```sql
zip_nomenclature_staging (
  -- Основные поля
  id INTEGER PRIMARY KEY,
  shop_code VARCHAR,              -- код магазина (greenspark, taggsm, etc.)
  outlet_code VARCHAR,            -- код точки продаж
  article VARCHAR,                -- артикул товара
  name TEXT,                      -- оригинальное название
  price NUMERIC,                  -- цена
  price_wholesale NUMERIC,        -- оптовая цена
  stock_quantity INTEGER,         -- количество
  in_stock BOOLEAN,               -- наличие

  -- Статус обработки
  status VARCHAR,                 -- pending → processing → completed/failed
  retry_count INTEGER,            -- счетчик попыток
  error_message TEXT,             -- описание ошибки
  ai_response JSONB,              -- сырой ответ AI
  confidence NUMERIC,             -- уверенность (0.0-1.0)

  -- FK колонки (заполняются воркерами 1,3,5,6,7)
  normalized_brand_id UUID,       -- → zip_dict_brands
  normalized_part_type_id INTEGER,-- → zip_dict_part_types
  normalized_color_id INTEGER,    -- → zip_dict_colors
  normalized_quality_id INTEGER,  -- → zip_dict_qualities
  normalized_nomenclature_id UUID,-- → zip_nomenclature (финал)

  -- Текстовые копии (для отладки)
  normalized_brand VARCHAR(100),
  normalized_part_type VARCHAR(100),
  normalized_color VARCHAR(50),
  normalized_quality VARCHAR(50),

  -- JSONB данные
  normalized_models JSONB DEFAULT '[]',   -- [{id, name, is_new}]
  normalized_features JSONB DEFAULT '{}', -- {technology, manufacturer, ...}

  -- Timestamps
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

**Вспомогательные объекты:**
- `v_staging_normalized` — view с расшифрованными значениями
- `get_staging_stats()` — функция статистики по статусам

---

## Порядок вызова воркеров

### Последовательный (простой)

```
1. Worker 1 (brand)
2. Worker 2 (model)     ← needs brand_id
3. Worker 3 (part_type)
4. Worker 4 (features)  ← needs brand_id + part_type_id
5. Worker 5 (color)
6. Worker 6 (quality)
7. Worker 7 (price-sync)
```

### Параллельный (оптимальный)

```
Группа 1 (параллельно):
├── Worker 1 (brand)
├── Worker 3 (part_type)
├── Worker 5 (color)
└── Worker 6 (quality)
        │
        ▼ (ждём brand_id и part_type_id)

Группа 2 (параллельно):
├── Worker 2 (model)    ← needs brand_id
└── Worker 4 (features) ← needs brand_id + part_type_id
        │
        ▼

Финал:
└── Worker 7 (price-sync)
```

---

## Стоимость и производительность

### Стоимость AI (на 1000 записей)

| Воркер | Модель | Tokens | Стоимость |
|--------|--------|--------|-----------|
| Worker 1 | GPT-4o-mini | ~150 | $0.02 |
| Worker 2 | QWen 72B | ~300 | $0.01 |
| Worker 3 | GPT-4o-mini | ~200 | $0.03 |
| Worker 4 | GPT-4o-mini | ~200 | $0.03 |
| **ИТОГО** | | | **$0.09** |

Workers 5, 6, 7 — без AI (бесплатно)

### Время обработки (на 1 запись)

| Режим | Время |
|-------|-------|
| Последовательный | ~3-4 сек |
| Параллельный | ~1.5-2 сек |

---

## Файлы воркеров

```
n8n/workers/
├── worker-1-brand.json
├── worker-2-model.json
├── worker-2.1-model-extract.json
├── worker-2.2-model-match.json
├── worker-3-part-type.json
├── worker-4-features.json
├── worker-5-color.json
├── worker-6-quality.json
├── worker-7-price-sync.json
└── README.md
```

---

## Отличия от предыдущих версий

| Параметр | v6 | v7 (воркеры) |
|----------|-----|--------------|
| Архитектура | Монолитный workflow | Микросервисы |
| Агентов | 2 | 7 воркеров |
| Параллелизм | Ограниченный | Полный |
| Масштабирование | Сложно | Легко (запуск N инстансов) |
| Отладка | Сложно | Просто (каждый воркер отдельно) |
| Изменения | Риск сломать всё | Изолированные изменения |
| Тестирование | Только интеграционное | Unit + интеграционное |

---

## Следующие шаги

1. ✅ Воркеры 1-7 созданы
2. ✅ Миграция staging (`020_extend_staging_for_workers_v7.sql`) — применена
3. ⬜ Orchestrator workflow (координация воркеров)
4. ⬜ Тестирование на 100 записях
5. ⬜ Мониторинг и алерты
