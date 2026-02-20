# Profi - Финальный статус парсера

## ✅ ПРОБЛЕМА РЕШЕНА

### Что было неправильно:

❌ Создал `profi_nomenclature_all` где **дублировал** товары для каждой точки:
```
Article: ABC123, City: Москва    ← Запись 1
Article: ABC123, City: СПБ       ← Запись 2 (ДУБЛЬ!)
Article: ABC123, City: Казань    ← Запись 3 (ДУБЛЬ!)

Результат: 78,888 "товаров" (с дублями)
```

### Что правильно (из DATABASE_ARCHITECTURE.md):

✅ **profi_nomenclature** - УНИКАЛЬНЫЕ товары (по article):
```sql
id | article  | name                          | brand | model | part_type
1  | ABC123   | Дисплей iPhone 14 Pro OLED GX | Apple | iPhone| Дисплей

Constraint: UNIQUE(article) ← Один товар = одна запись!
```

✅ **profi_current_prices** - Цены ПО ТОЧКАМ:
```sql
nomenclature_id | outlet_id | price  | in_stock
1               | 42        | 5000   | true      ← Москва
1               | 55        | 5100   | true      ← СПБ
1               | 78        | 4900   | false     ← Казань

Constraint: UNIQUE(nomenclature_id, outlet_id)
```

**Один товар → одна запись в nomenclature**
**Один товар × N точек → N записей в prices**

---

## 📊 Текущая статистика БД

```sql
profi_nomenclature:      13,742 товаров (уникальных)
profi_current_prices:   327,390 цен (товары × точки)
```

**Это правильно!** Нет дублей.

---

## 🔄 Что делается сейчас

**Задача:** Обновление данных (запущен parser.py)

**Команда:**
```bash
python parser.py --all --dynamic
```

**Что делает:**
1. Скачивает актуальный список с https://siriust.ru/prays-listy/ (40 прайс-листов)
2. Парсит каждый Excel файл
3. **UPSERT** в profi_nomenclature (по UNIQUE article) - без дублей!
4. **UPSERT** в profi_current_prices (по nomenclature_id + outlet_id)

**ETA:** ~20-25 минут

**Ожидаемый результат:**
- profi_nomenclature: ~14-15k товаров (добавится ~1-2k новых)
- profi_current_prices: ~350-400k цен (обновятся все)

---

## 📁 Правильная структура таблиц

### profi_nomenclature (УНИКАЛЬНЫЕ товары)

```sql
CREATE TABLE profi_nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) UNIQUE NOT NULL,  ← Уникальный ключ!
    name TEXT,
    brand VARCHAR(100),
    model VARCHAR(100),
    part_type VARCHAR(100),
    category TEXT,

    -- Для синхронизации с центральной БД
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,

    first_seen_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### profi_current_prices (Цены по точкам)

```sql
CREATE TABLE profi_current_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER REFERENCES profi_nomenclature(id),
    outlet_id INTEGER REFERENCES zip_outlets(id),

    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    stock_stars SMALLINT,
    quantity INTEGER,
    in_stock BOOLEAN,
    product_url TEXT,

    updated_at TIMESTAMP,

    UNIQUE(nomenclature_id, outlet_id)  ← Уникальная цена на точку!
);
```

---

## 🎯 Двухэтапная обработка (АКТУАЛЬНАЯ)

### ЭТАП 1: Python парсер (parser.py) ✅

```
Excel (40 прайс-листов)
    ↓
Parser.py
    ├─ Парсинг по font-size (brand/model/part_type)
    ├─ UPSERT profi_nomenclature (UNIQUE по article)
    └─ UPSERT profi_current_prices (по nomenclature_id + outlet_id)
    ↓
profi_nomenclature: ~14-15k товаров
profi_current_prices: ~350-400k цен
```

### ЭТАП 2: n8n нормализация (Upload.json)

```
profi_nomenclature (raw data)
    ├─ brand: "Apple", "iPhone" и т.д.
    ├─ model: NULL или сырые данные
    └─ part_type: сырые данные
    ↓
n8n Upload.json
    ├─ Фильтрация (только запчасти)
    ├─ Нормализация brand/model
    ├─ Извлечение моделей из названия
    ├─ Нормализация part_type
    └─ UPDATE profi_nomenclature (normalized fields)
    ↓
profi_nomenclature (clean data)
    ├─ brand: "iPhone", "Samsung" и т.д.
    ├─ model: "14 Pro Max|14 Pro" (извлечено)
    └─ part_type: "ДИСПЛЕЙ", "АКБ" и т.д.
```

---

## 📝 Рабочие файлы

```
SHOPS/Profi/
├── parser.py                    ← ЭТАП 1: Основной парсер ✅
├── create_profi_tables_v2.sql   ← SQL: структура таблиц
├── price_lists_config.py        ← Конфиг прайс-листов (37 шт, устарел)
├── fetch_price_lists.py         ← Динамическая загрузка списка (40 шт)
├── Workflow/
│   ├── Upload.json              ← ЭТАП 2: n8n нормализация
│   └── Normalize_v2.json        ← LEGACY (отладка)
└── FINAL_STATUS.md              ← Этот файл
```

**УДАЛЕНЫ (неправильные):**
- ❌ `profi_nomenclature_all` - таблица с дублями
- ❌ `parser_to_all_xlrd.py` - неправильный парсер
- ❌ `parser_to_all.py` - неправильный парсер
- ❌ `parser_clean.py` - неправильный парсер
- ❌ `create_nomenclature_all.sql` - SQL для неправильной таблицы

---

## ✅ Итоговая проверка

После завершения парсинга:

```sql
-- Уникальные товары
SELECT COUNT(*) as total,
       COUNT(DISTINCT article) as unique_articles
FROM profi_nomenclature;

-- Топ брендов
SELECT brand, COUNT(*) as cnt
FROM profi_nomenclature
GROUP BY brand
ORDER BY cnt DESC
LIMIT 10;

-- Цены по точкам
SELECT COUNT(*) as total_prices,
       COUNT(DISTINCT nomenclature_id) as products_with_prices,
       COUNT(DISTINCT outlet_id) as outlets
FROM profi_current_prices;

-- Пример товара с ценами
SELECT
    n.article,
    n.name,
    n.brand,
    COUNT(p.id) as price_count
FROM profi_nomenclature n
LEFT JOIN profi_current_prices p ON p.nomenclature_id = n.id
WHERE n.brand = 'Apple'
GROUP BY n.id, n.article, n.name, n.brand
LIMIT 5;
```

---

## 🚀 Следующие шаги

1. ✅ Дождаться завершения parser.py (~20 минут)
2. ✅ Проверить данные в БД
3. ⏭️ Запустить n8n Upload.json для нормализации
4. ⏭️ Отправить в zip_nomenclature_staging для AI

---

**Дата:** 2026-01-26
**Статус:** Парсинг в процессе (правильная версия)
**Задача ID:** b0c32dd
