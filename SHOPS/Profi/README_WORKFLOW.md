# Profi - Двухэтапная обработка прайс-листов

## Архитектура

```
ЭТАП 1: Python парсер
├── Скачивает Excel с siriust.ru
├── Парсит по font-size (11=бренд, 10=модель, 9=тип)
├── Сохраняет СЫРЫЕ данные
└── → profi_nomenclature_all

ЭТАП 2: n8n Upload.json
├── Читает из profi_nomenclature_all
├── Применяет нормализацию (SQL)
├── Сохраняет очищенные данные
└── → profi_nomenclature + profi_current_prices
```

---

## Таблицы

### 1. profi_nomenclature_all (СЫРЫЕ данные)

**ЭТАП 1** - Python парсер пишет сюда:

```sql
profi_nomenclature_all
├── article (UNIQUE)
├── name, barcode
├── brand_raw: "1. ЗАПЧАСТИ ДЛЯ APPLE"      ← КАК ЕСТЬ из Excel
├── model_raw: "ЗАПЧАСТИ ДЛЯ APPLE IPHONE"  ← КАК ЕСТЬ
├── part_type_raw: "Дисплеи для iPhone 14"  ← КАК ЕСТЬ
├── category_raw: полный путь
├── city, shop, outlet_code
├── price, in_stock
├── processed: false → true после n8n
└── updated_at
```

### 2. profi_nomenclature (ФИНАЛЬНАЯ)

**ЭТАП 2** - n8n Upload.json пишет сюда:

```sql
profi_nomenclature
├── article (UNIQUE)
├── name, barcode
├── brand: "iPhone"                    ← НОРМАЛИЗОВАНО
├── model: "14 Pro Max|14 Pro"         ← ИЗВЛЕЧЕНО из названия
├── part_type: "ДИСПЛЕЙ"               ← НОРМАЛИЗОВАНО
├── brand_raw, model_raw, part_type_raw  ← для истории
└── zip_nomenclature_id                ← NULL = не отправлен в AI
```

### 3. profi_current_prices

Цены по точкам продаж:

```sql
profi_current_prices
├── nomenclature_id → profi_nomenclature.id
├── outlet_id → zip_outlets.id
├── price, stock_stars, in_stock
└── product_url
```

---

## Запуск

### ЭТАП 1: Парсинг Excel

```bash
cd SHOPS/Profi

# 1. Создать таблицу (один раз)
psql -h aws-1-eu-west-3.pooler.supabase.com -p 5432 -U postgres.griexhozxrqtepcilfnu -d postgres -f create_nomenclature_all.sql

# 2. Парсинг всех городов
python parser_to_all.py --all

# 3. Парсинг одного города (тест)
python parser_to_all.py --city "Москва"

# 4. Тестовый режим (1 прайс-лист)
python parser_to_all.py --test
```

**Результат:** Данные в `profi_nomenclature_all`, `processed=false`

---

### ЭТАП 2: Нормализация в n8n

```bash
# 1. Открыть n8n
http://85.198.98.104:5678

# 2. Импортировать workflow
SHOPS/Profi/Workflow/Upload.json

# 3. Настроить credentials
PostgreSQL: Supabase Cloud
- Host: aws-1-eu-west-3.pooler.supabase.com
- Port: 5432
- Database: postgres
- User: postgres.griexhozxrqtepcilfnu
- Password: Mi31415926pSss!

# 4. Запустить workflow
Кликнуть "Execute Workflow"
```

**Результат:** Данные в `profi_nomenclature` + `profi_current_prices`

---

## Проверка результатов

```sql
-- Статистика ЭТАП 1
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE processed = false) as pending,
    COUNT(*) FILTER (WHERE processed = true) as completed
FROM profi_nomenclature_all;

-- Статистика ЭТАП 2
SELECT
    COUNT(*) as total_products
FROM profi_nomenclature;

SELECT
    COUNT(*) as total_prices,
    COUNT(*) FILTER (WHERE in_stock = true) as in_stock
FROM profi_current_prices;

-- Топ брендов (после нормализации)
SELECT brand, COUNT(*) as cnt
FROM profi_nomenclature
GROUP BY brand
ORDER BY cnt DESC
LIMIT 10;
```

---

## Очистка устаревших данных

После удаления товаров из `profi_nomenclature` нужно почистить связанные цены:

```bash
# Удалить цены и историю для удалённых товаров
psql -h aws-1-eu-west-3.pooler.supabase.com -p 5432 -U postgres.griexhozxrqtepcilfnu -d postgres -f cleanup_orphaned_data.sql
```

---

## Обновление данных

### Вариант 1: Полная перезагрузка

```bash
# 1. Очистить profi_nomenclature_all
psql -c "TRUNCATE profi_nomenclature_all CASCADE;"

# 2. Запустить парсер
python parser_to_all.py --all

# 3. Запустить n8n Upload.json
```

### Вариант 2: Обновление (UPSERT)

```bash
# 1. Парсер обновит существующие товары (ON CONFLICT DO UPDATE)
python parser_to_all.py --all

# 2. n8n обработает только новые (processed=false)
```

---

## Структура файлов

```
SHOPS/Profi/
├── parser_to_all.py                  ← ЭТАП 1: Python парсер
├── create_nomenclature_all.sql       ← SQL: создание таблицы
├── cleanup_orphaned_data.sql         ← SQL: очистка устаревших данных
├── Workflow/
│   └── Upload.json                   ← ЭТАП 2: n8n нормализация
├── config.py                         ← Конфигурация
├── price_lists_config.py             ← Список прайс-листов
└── README_WORKFLOW.md                ← Эта документация
```

---

## Отличия от старой версии

| Параметр | Старая | Новая (двухэтапная) |
|----------|--------|---------------------|
| Парсер | parser.py | parser_to_all.py |
| Нормализация | В Python | В n8n |
| Таблица сырых данных | - | profi_nomenclature_all |
| Таблица финала | profi_nomenclature | profi_nomenclature |
| Разделение этапов | Нет | Да (парсинг / нормализация) |

---

## Преимущества двухэтапной обработки

✅ **Разделение ответственности:**
- Python - парсинг и сбор данных
- n8n - бизнес-логика нормализации

✅ **Гибкость:**
- Можно изменить нормализацию без переписывания парсера
- Можно запускать парсинг и нормализацию независимо

✅ **Отладка:**
- Видим СЫРЫЕ данные до нормализации
- Можем повторно нормализовать без повторного парсинга

✅ **История:**
- Сохраняются и сырые (brand_raw), и нормализованные (brand) данные

---

## Следующий шаг: AI-нормализация

После ЭТАПА 2 данные из `profi_nomenclature` загружаются в `zip_nomenclature_staging` для AI-обработки (V7 воркеры).
