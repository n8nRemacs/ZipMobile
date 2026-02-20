# Стандарт магазинов ZipMobile

## Стандарт таблиц

Каждый магазин (`{shop}`) должен иметь следующие таблицы:

### `{shop}_nomenclature`
Основная таблица товаров магазина.

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL PK | Локальный ID |
| article | VARCHAR(100) UNIQUE | Артикул магазина |
| name | TEXT | Наименование товара |
| url | TEXT | Ссылка на товар |
| zip_nomenclature_id | INTEGER FK → zip_nomenclature(id) | Связь с центральной номенклатурой (NULL = не нормализован) |
| brand_id | INTEGER FK → zip_dict_brands(id) | Бренд |
| model_ids | INTEGER[] | Массив моделей |
| part_type_id | INTEGER FK → zip_dict_part_types(id) | Тип запчасти |
| color_id | INTEGER FK → zip_dict_colors(id) | Цвет |
| needs_ai | BOOLEAN DEFAULT false | Требует AI-нормализации |
| is_active | BOOLEAN DEFAULT true | Активен ли товар |
| created_at | TIMESTAMPTZ DEFAULT NOW() | Дата создания |
| updated_at | TIMESTAMPTZ DEFAULT NOW() | Дата обновления |

### `{shop}_prices`
Цены товаров.

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL PK | |
| nomenclature_id | INTEGER FK → {shop}_nomenclature(id) | |
| price_type_id | INTEGER FK → price_types(id) | Тип цены (розница, опт, и т.д.) |
| price | NUMERIC(12,2) | Цена |
| currency | VARCHAR(10) DEFAULT 'RUB' | Валюта |
| is_active | BOOLEAN DEFAULT true | |
| updated_at | TIMESTAMPTZ DEFAULT NOW() | |

### `{shop}_staging`
Промежуточная таблица для парсинга.

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL PK | |
| raw_data | JSONB | Сырые данные от парсера |
| status | VARCHAR(20) DEFAULT 'new' | new / processed / error |
| error | TEXT | Ошибка обработки |
| created_at | TIMESTAMPTZ DEFAULT NOW() | |

### `{shop}_parse_log`
Лог парсингов.

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL PK | |
| task_id | UUID | ID задачи |
| status | VARCHAR(20) | pending / running / completed / failed |
| stats | JSONB | Статистика: total, new, updated, errors |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |
| error | TEXT | |

---

## Стандарт API парсера

Каждый парсер-сервис должен реализовывать следующие эндпоинты:

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/parse/all` | Запуск полного парсинга (background task) |
| POST | `/parse/outlet/{code}` | Парсинг конкретной точки |
| GET | `/parse/task/{id}` | Статус задачи парсинга |
| GET | `/health` | Проверка здоровья сервиса |
| GET | `/stats` | Статистика: всего товаров, последний парсинг |
| GET | `/outlets` | Список точек/источников магазина |

---

## Маппинг типов цен

Таблица `zip_shop_price_types` связывает магазины с типами цен:

```
shop_id → zip_shops(id)
price_type_id → price_types(id)
is_default — флаг цены по умолчанию
```

---

## Поток нормализации новых товаров

```
Парсер → {shop}_nomenclature (zip_nomenclature_id=NULL)
       → Normalizer API (extract brand + models via AI)
       → SQL exact match в zip_dict_brands / zip_dict_models
       → Совпадение найдено: привязка к zip_nomenclature
       → Совпадение НЕ найдено: AI-валидация → модерация (zip_moderation_queue)
       → Модератор разрешает → создание/привязка в справочнике → zip_nomenclature
```

---

## Обнаружение новых outlet'ов

При парсинге, если обнаружен новый outlet (точка продаж), который отсутствует в БД:
1. Автоматическое создание записи с `status='pending_review'`
2. Запись попадает в очередь модерации
3. Модератор подтверждает / редактирует / отклоняет
