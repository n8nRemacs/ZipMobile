# RealTime Parser - Универсальный парсер цен в реальном времени

## Назначение

MCP-сервер для парсинга актуальных цен и наличия товаров по URL. Конфигурация парсинга хранится в БД, что позволяет добавлять новые магазины без изменения кода.

## Архитектура

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   MCP Client    │────▶│   MCP Server     │────▶│  Target Shop    │
│  (Claude, n8n)  │     │  (mcp_server.py) │     │  (green-spark)  │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                        ┌────────▼─────────┐
                        │  PostgreSQL DB   │
                        │ shop_parser_configs│
                        └──────────────────┘
```

## Структура файлов

```
SHOPS/RealTime/
├── mcp_server.py       # MCP сервер с инструментами
├── parser.py           # Универсальный парсер (CLI + библиотека)
├── config_loader.py    # Загрузка конфигов из БД
├── extractors/
│   ├── api_json.py     # Извлечение данных из JSON API
│   └── html.py         # Извлечение данных из HTML
├── schema.sql          # Схема таблиц БД
├── apply_schema.py     # Применение схемы к БД
├── requirements.txt    # Python зависимости
└── greenspark/
    └── cookies.json    # Cookies для GreenSpark
```

## Установка

```bash
cd SHOPS/RealTime
pip install -r requirements.txt

# Применить схему к БД (если ещё не применена)
python apply_schema.py
```

## Запуск MCP сервера

```bash
# STDIO транспорт (для Claude Code)
python mcp_server.py

# SSE транспорт (для веб-клиентов)
python mcp_server.py --transport sse --port 8000
```

## Конфигурация Claude Code

Добавить в `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "realtime-parser": {
      "command": "python",
      "args": ["C:/Users/User/Documents/ZipMobile/SHOPS/RealTime/mcp_server.py"]
    }
  }
}
```

## MCP Tools (Инструменты)

### 1. parse_product_realtime

Парсит товар по URL. Автоматически определяет магазин по домену.

**Вход:**
```json
{
  "url": "https://green-spark.ru/catalog/akb/product.html"
}
```

**Выход:**
```json
{
  "success": true,
  "price": 5500.0,
  "price_wholesale": 5000.0,
  "in_stock": true,
  "stock_quantity": 10,
  "article": "GS-00012345",
  "name": "Аккумулятор для Samsung Galaxy A12",
  "shop_code": "greenspark",
  "error": null,
  "response_time_ms": 250
}
```

### 2. parse_product_by_shop

Парсит товар с явным указанием магазина (когда URL нестандартный).

**Вход:**
```json
{
  "shop_code": "greenspark",
  "url": "https://m.green-spark.ru/..."
}
```

### 3. get_parser_configs

Возвращает список всех настроенных парсеров.

**Выход:**
```json
[
  {
    "shop_code": "greenspark",
    "domains": ["green-spark.ru", "greenspark.ru"],
    "parser_type": "api_json",
    "is_active": true,
    "test_url": null
  },
  {
    "shop_code": "05gsm",
    "domains": ["05gsm.ru"],
    "parser_type": "html",
    "is_active": true,
    "test_url": null
  }
]
```

### 4. test_parser_config

Тестирует конфигурацию парсера на test_url.

**Вход:**
```json
{
  "shop_code": "greenspark"
}
```

### 5. check_url_parser

Проверяет, есть ли парсер для данного URL.

**Вход:**
```json
{
  "url": "https://example.com/product"
}
```

**Выход:**
```json
{
  "has_parser": false,
  "shop_code": null,
  "parser_type": null
}
```

## CLI использование

```bash
# Парсинг по URL
python parser.py "https://green-spark.ru/catalog/.../product.html"

# С явным указанием магазина
python parser.py --shop greenspark "https://..."
```

## База данных

### Подключение

```
Host: 85.198.98.104
Port: 5433
Database: db_greenspark
User: postgres
```

### Таблица shop_parser_configs

| Поле | Тип | Описание |
|------|-----|----------|
| shop_code | VARCHAR(50) | Уникальный код магазина |
| domain_patterns | TEXT[] | Домены магазина |
| parser_type | VARCHAR(20) | 'api_json' или 'html' |
| api_config | JSONB | Настройки API эндпоинтов |
| json_paths | JSONB | JSONPath для извлечения из API |
| html_selectors | JSONB | CSS селекторы для HTML |
| regex_patterns | JSONB | Regex паттерны (альтернатива) |
| request_config | JSONB | delay, timeout, cookies |
| transformers | JSONB | Преобразование данных |
| is_active | BOOLEAN | Активен ли парсер |
| test_url | TEXT | URL для тестирования |

## Добавление нового магазина

### Пример: API JSON парсер

```sql
INSERT INTO shop_parser_configs (shop_code, domain_patterns, parser_type, api_config, json_paths, request_config)
VALUES (
    'newshop',
    ARRAY['newshop.ru', 'www.newshop.ru'],
    'api_json',
    '{
        "base_url": "https://newshop.ru",
        "detail_endpoint": "/api/product/",
        "url_to_path_regex": "/product/(\\d+)",
        "path_param_format": "id={part}"
    }'::jsonb,
    '{
        "price": "data.price",
        "stock": "data.availability",
        "article": "data.sku",
        "name": "data.title",
        "in_stock_check": "not_in",
        "out_of_stock_values": [0, "none", null]
    }'::jsonb,
    '{
        "delay": 1.0,
        "timeout": 30,
        "cookies_required": false
    }'::jsonb
);
```

### Пример: HTML парсер

```sql
INSERT INTO shop_parser_configs (shop_code, domain_patterns, parser_type, html_selectors, request_config)
VALUES (
    'htmlshop',
    ARRAY['htmlshop.ru'],
    'html',
    '{
        "price": ".product-price .value",
        "article": ".product-sku",
        "name": "h1.product-title",
        "stock": ".availability",
        "in_stock_text": ["в наличии", "есть"],
        "out_of_stock_text": ["нет в наличии", "под заказ"]
    }'::jsonb,
    '{
        "delay": 1.5,
        "timeout": 30,
        "cookies_required": false
    }'::jsonb
);
```

## Конфигурация json_paths

| Поле | Описание | Пример |
|------|----------|--------|
| price | Путь к цене | `"product.prices[0].price"` |
| price_path_filter | Фильтр для массива цен | `{"field": "name", "value": "Розница"}` |
| price_wholesale | Путь к оптовой цене | `"product.prices[1].price"` |
| stock | Путь к наличию | `"product.quantity"` |
| article | Путь к артикулу | `"product.article"` |
| name | Путь к названию | `"product.name"` |
| in_stock_check | Тип проверки | `"not_in"` или `"in"` |
| out_of_stock_values | Значения = нет в наличии | `["none", "", null, 0]` |
| in_stock_values | Значения = в наличии | `["many", "few", "one"]` |

## Конфигурация api_config

| Поле | Описание | Пример |
|------|----------|--------|
| base_url | Базовый URL API | `"https://shop.ru"` |
| detail_endpoint | Эндпоинт детальной информации | `"/api/product/"` |
| url_to_path_regex | Regex для извлечения пути из URL | `"/catalog/(.+?)(?:\\.html)?/?$"` |
| path_param_format | Формат параметра | `"path[]={part}"` или `"id={part}"` |
| path_separator | Разделитель параметров | `"&"` |

## Cookies

Для магазинов с защитой (GreenSpark) требуются cookies:

1. Cookies хранятся в `{shop_code}/cookies.json`
2. Обновляются через `setup_cookies.py` (Playwright)
3. В конфиге: `"cookies_source": "file:cookies.json"`

## Fallback механизм

Если API возвращает HTML вместо JSON (защита), парсер автоматически пытается извлечь данные из HTML через regex:
- Цена: JSON в HTML, data-атрибуты, microdata
- Артикул: JSON, текст "Артикул: XXX"
- Название: JSON, `<h1>`, microdata
- Наличие: поиск текста "нет в наличии"

## Логирование

Все запросы логируются в таблицу `parser_request_log`:

```sql
SELECT shop_code, url, success, price, in_stock, response_time_ms, error_message
FROM parser_request_log
ORDER BY created_at DESC
LIMIT 10;
```

## Ограничения

1. **Rate limiting**: Задержка между запросами настраивается в `request_config.delay`
2. **JavaScript-сайты**: Требуют активных cookies (обновлять через Playwright)
3. **Капча**: Не обходится, требует ручного вмешательства
