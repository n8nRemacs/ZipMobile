# Profi Parser - Техническая документация

## Обзор

Парсер прайс-листов сети магазинов **Профи** (siriust.ru) - оптовый поставщик запчастей для мобильных устройств с точками продаж по всей России.

**Двухэтапная обработка:**
1. **ЭТАП 1:** Python парсер (parser.py) - извлечение сырых данных из Excel
2. **ЭТАП 2:** n8n workflow (Upload.json) - нормализация и обогащение данных

---

## Источник данных

### Страница прайс-листов
```
https://siriust.ru/prays-listy/
```

Содержит ссылки на XLS-файлы для каждой торговой точки.

### Формат URL прайс-листов
```
https://www.siriust.ru/club/price/{CityName}.xls
https://www.siriust.ru/club/price/{CityName}-%20{N}.xls
```

**Примеры:**
- `Astraxan.xls` - Астрахань
- `Kazan-%201.xls` - Казань точка 1
- `Sankt-peterburg-%207.xls` - СПб точка 7

### ВАЖНО: URL меняются!

Сайт периодически:
- Добавляет новые города
- Удаляет закрытые точки
- Меняет нумерацию точек
- Меняет транслитерацию

**Решение:** Используйте `--dynamic` флаг для автоматического получения актуального списка URL.

---

## Формат XLS-файлов

### Структура прайс-листа

| Строка | Содержимое |
|--------|------------|
| 1-13 | Шапка (логотип, контакты) |
| 14 | **Заголовок таблицы** |
| 15+ | Данные (иерархия + товары) |

### Колонки

| Колонка | Название | Тип |
|---------|----------|-----|
| A | № п/п | Число |
| B | Фото | Ссылка |
| C | **Артикул** | Текст (М0944559) |
| D | **Штрихкод** | Число (13 цифр) |
| E | **Наименование** | Текст |
| F | **Наличие** | Число (1-5 звезд) |
| G | **Цена** | Число (руб.) |

### Иерархия по размеру шрифта

**Ключевая особенность!** Категории определяются по размеру шрифта ячейки "Наименование":

| Размер шрифта | Уровень | Пример |
|---------------|---------|--------|
| **11pt** (220 twips) | Бренд | `1. ЗАПЧАСТИ ДЛЯ APPLE` |
| **10pt** (200 twips) | Модель | `ЗАПЧАСТИ ДЛЯ APPLE IPHONE` |
| **9pt** (180 twips) | Тип запчасти | `АКБ ДЛЯ IPHONE` |
| **8pt** и меньше | Товар | `Дисплей iPhone 14 Pro OLED GX` |

```python
# Код определения уровня
fsize = font.height / 20  # twips → points

if fsize >= 10.5:      # ~11pt
    current_brand = name_val
elif 9.5 <= fsize < 10.5:  # ~10pt
    current_model = name_val
elif 8.5 <= fsize < 9.5:   # ~9pt
    current_type = name_val
else:
    # Это товар
```

### Наличие (stock_stars)

| Значение | Описание |
|----------|----------|
| 1 | Мало |
| 2 | Немного |
| 3 | Достаточно |
| 4 | Много |
| 5 | Очень много |

---

## Архитектура базы данных

### ПРАВИЛЬНАЯ структура (без дублей!)

#### profi_nomenclature - Уникальные товары

```sql
CREATE TABLE profi_nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) UNIQUE NOT NULL,  -- ← Уникальный ключ!
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

**Принцип:** Один товар = одна запись. Уникальность по `article`.

#### profi_current_prices - Цены по точкам

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

    UNIQUE(nomenclature_id, outlet_id)  -- ← Уникальная цена на точку!
);
```

**Принцип:** Один товар × N точек = N записей. Уникальность по `(nomenclature_id, outlet_id)`.

### Пример данных

**profi_nomenclature:**
```
id | article  | name                          | brand | model  | part_type
1  | ABC123   | Дисплей iPhone 14 Pro OLED GX | Apple | iPhone | Дисплей
```

**profi_current_prices:**
```
nomenclature_id | outlet_id | price  | in_stock
1               | 42        | 5000   | true      ← Москва
1               | 55        | 5100   | true      ← СПБ
1               | 78        | 4900   | false     ← Казань
```

**Один товар → одна запись в nomenclature**
**Один товар × N точек → N записей в prices**

---

## Двухэтапная обработка

### ЭТАП 1: Python парсер (parser.py)

**Что делает:**
1. Скачивает прайс-листы с siriust.ru
2. Парсит Excel файлы (через xlrd)
3. Определяет иерархию brand/model/part_type по font-size
4. UPSERT в `profi_nomenclature` (по UNIQUE article)
5. UPSERT в `profi_current_prices` (по nomenclature_id + outlet_id)

**Результат:**
- Сырые данные в БД
- Без дублей товаров
- С ценами по каждой точке

**Запуск:**
```bash
cd SHOPS/Profi
python parser.py --all --dynamic
```

### ЭТАП 2: n8n нормализация (Upload.json)

**Что делает:**
1. Читает данные из `profi_nomenclature`
2. Фильтрует (только запчасти, не аксессуары)
3. Нормализует brand/model/part_type через SQL
4. Извлекает модели из названия (regex)
5. Обогащает данными из справочников
6. UPDATE `profi_nomenclature` (нормализованные поля)

**Результат:**
- Нормализованные бренды: "iPhone", "Samsung", "Xiaomi"
- Извлеченные модели: "14 Pro Max|14 Pro"
- Классифицированные типы запчастей: "ДИСПЛЕЙ", "АКБ"

**Запуск:**
- Импортировать `Workflow/Upload.json` в n8n
- Настроить подключение к БД
- Запустить workflow

---

## Запуск парсера

### Полный парсинг (все города, динамический список)

```bash
python parser.py --all --dynamic
```

**Результат:**
- ~40 прайс-листов
- ~14-15k товаров в profi_nomenclature
- ~350-400k цен в profi_current_prices
- ETA: ~20-25 минут

### Тестовый режим (1 город)

```bash
python parser.py --test
```

**Результат:**
- Парсит только Москву
- ~4-5k товаров
- ETA: ~30 секунд

### Конкретный город

```bash
python parser.py --city "Москва"
```

### Без загрузки в БД (только JSON)

```bash
python parser.py --all --no-db
```

**Результат:**
- Сохраняет в `data/products.json`
- Не записывает в БД

---

## Структура файлов

```
SHOPS/Profi/
├── parser.py                    ← ЭТАП 1: Основной парсер ✅
├── price_lists_config.py        ← Статический конфиг (37 шт, для fallback)
├── fetch_price_lists.py         ← Динамическая загрузка списка (40 шт)
├── create_profi_tables_v2.sql   ← SQL: структура таблиц
├── cleanup_orphaned_data.sql    ← SQL: очистка orphaned prices
├── config.py                    ← Конфигурация (пути, БД)
├── Workflow/
│   ├── Upload.json              ← ЭТАП 2: n8n нормализация ✅
│   └── Normalize_v2.json        ← LEGACY (только для отладки)
├── data/
│   └── products.json            ← Результат парсинга (JSON)
├── README.md                    ← Этот файл
├── FINAL_STATUS.md              ← Финальный статус (2026-01-26)
└── STATUS.md                    ← Предыдущий статус (архив)
```

### УСТАРЕВШИЕ файлы (не используются):

- `parse_profi.py`, `parse_profi_v2.py` - старые версии парсера
- `parser_to_all.py`, `parser_to_all_xlrd.py` - парсеры с ошибочной архитектурой
- `parser_clean.py` - неправильная версия
- `create_nomenclature_all.sql` - таблица с дублями (удалена)

---

## Статистика БД (актуальная на 2026-01-26)

```sql
profi_nomenclature:      13,742 товаров (уникальных)
profi_current_prices:   327,390 цен (товары × точки)
```

**Это правильно!** Нет дублей.

### Топ брендов

```sql
SELECT brand, COUNT(*) as cnt
FROM profi_nomenclature
WHERE brand IS NOT NULL
GROUP BY brand
ORDER BY cnt DESC
LIMIT 10;
```

### Проверка структуры

```sql
-- Уникальные товары
SELECT COUNT(*) as total,
       COUNT(DISTINCT article) as unique_articles
FROM profi_nomenclature;

-- Должно быть: total = unique_articles

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

## Известные проблемы и решения

### 1. URL прайс-листов меняются

**Проблема:** Статический конфиг `price_lists_config.py` содержит 37 URL, из которых 17 возвращают 404.

**Причина:** Сайт обновляет структуру прайс-листов (добавляет/удаляет точки, меняет нумерацию).

**Решение:** Используйте `--dynamic` флаг:
```bash
python parser.py --all --dynamic
```

Парсер получит актуальный список с сайта (40 прайс-листов).

### 2. Дубликаты товаров

**Проблема:** Ранее использовались таблицы типа `profi_nomenclature_all`, где товары дублировались для каждой точки.

**Результат:** 78,888 "товаров" вместо реальных ~14,000 уникальных.

**Решение:** Текущая архитектура правильная:
- `profi_nomenclature` - UNIQUE по article
- `profi_current_prices` - цены по точкам (связь через nomenclature_id)

### 3. Orphaned prices

**Проблема:** После удаления товаров из nomenclature остаются цены без связи.

**Решение:** Запустить очистку:
```sql
-- См. cleanup_orphaned_data.sql
DELETE FROM profi_current_prices
WHERE nomenclature_id NOT IN (
    SELECT id FROM profi_nomenclature
);
```

### 4. Иерархия не определяется

**Проблема:** Некоторые XLS файлы без форматирования шрифтов.

**Решение:** xlrd требует `formatting_info=True`. Файлы должны быть .xls (не .xlsx).

### 5. Пустые цены

**Проблема:** В некоторых товарах `price = 0.00`

**Причина:**
- Колонка "Цена" не найдена в Excel
- Формат цены не распознан

**Решение:** Проверить эвристику определения колонок в `_resolve_columns()` (parser.py:161-175)

---

## Зависимости

```bash
pip install httpx xlrd psycopg2-binary openpyxl
```

**Версии:**
- httpx >= 0.24.0 (HTTP клиент)
- xlrd == 1.2.0 (парсинг .xls с formatting_info)
- psycopg2-binary >= 2.9.0 (PostgreSQL драйвер)
- openpyxl >= 3.0.0 (парсинг .xlsx, fallback)

**Важно:** xlrd >= 2.0 не поддерживает .xlsx файлы с форматированием.

---

## База данных (Supabase Cloud)

### Подключение

```python
from db_wrapper import get_db

conn = get_db()
cur = conn.cursor()
```

### Конфигурация

См. `db_wrapper.py` в корне проекта.

**Структура:**
- Единая БД на Supabase Cloud (AWS EU-West-3)
- Префиксы таблиц: `profi_`, `alltime_`, `zipmobile_`, `mobilcentre_`
- PostgreSQL 15

---

## Нормализация данных (ЭТАП 2)

### Бренды (brand)

| Исходное (brand_raw) | Нормализованное (brand) |
|----------------------|------------------------|
| `1. ЗАПЧАСТИ ДЛЯ APPLE` | `iPhone` |
| `2. ЗАПЧАСТИ ДЛЯ СОТОВЫХ` | `Samsung`, `Xiaomi` и т.д. |
| `3. АКСЕССУАРЫ` | `null` (фильтруется) |

### Модели (model)

Извлекаются из названия товара через regex:

| Название | Извлеченная модель |
|----------|-------------------|
| `Дисплей iPhone 14 Pro OLED GX` | `14 Pro` |
| `АКБ Samsung Galaxy A52 4500mAh` | `A52` |

### Типы запчастей (part_type)

| Исходное (part_type_raw) | Нормализованное (part_type) |
|--------------------------|----------------------------|
| `АКБ ДЛЯ IPHONE` | `ДИСПЛЕЙ` |
| `Дисплеи` | `ДИСПЛЕЙ` |
| `Задние крышки` | `ЗАДНЯЯ КРЫШКА` |

---

## Следующие шаги

1. ✅ Дождаться завершения parser.py (запущен 2026-01-26)
2. ✅ Проверить данные в БД (должно быть ~14-15k товаров)
3. ⏭️ Запустить n8n Upload.json для нормализации
4. ⏭️ Отправить в zip_nomenclature_staging для AI-обработки

---

## TODO / Доработки

- [ ] Автоматическое обновление по расписанию (cron или n8n schedule)
- [ ] Уведомления об изменениях цен (Telegram bot)
- [ ] История цен (сохранение изменений в profi_price_history)
- [ ] Интеграция с основной номенклатурой (zip_nomenclature)
- [ ] API для поиска товаров по артикулу
- [ ] Retry логика при ошибках скачивания (httpx retry)
- [ ] Логирование в файл (не только stdout)

---

## Контакты и доступы

### База данных (Supabase)
- Host: aws-1-eu-west-3.pooler.supabase.com
- Port: 6543
- Database: postgres
- User: postgres.griexhozxrqtepcilfnu

### n8n
- URL: http://85.198.98.104:5678
- Login: dk.remacs@gmail.com

### Документация
- DATABASE_ARCHITECTURE.md - Архитектура БД
- NORMALIZATION_PIPELINE_V7.md - Процесс нормализации
- INFRASTRUCTURE.md - Инфраструктура проекта

---

**Дата обновления:** 2026-01-26
**Версия:** 2.0 (правильная архитектура без дублей)
**Автор:** Claude Code + EloWork
