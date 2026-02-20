# GreenSpark Parser - n8n Workflows

Набор workflows для парсинга каталога green-spark.ru через n8n 2.0.1.

## Структура

```
n8n/
├── api_get_cities.json       # API: GET /greenspark/cities
├── api_get_categories.json   # API: GET /greenspark/categories
├── api_parse_city.json       # API: POST /greenspark/parse/city
├── mcp_get_cookies.json      # MCP: получение cookies через Playwright
├── parse_with_proxy.json     # Парсинг с ротацией прокси
└── README.md                 # Эта документация
```

## Установка

### 1. Создать PostgreSQL Credentials

В n8n: **Settings → Credentials → Add Credential → PostgreSQL**

```
Name: PostgreSQL GreenSpark
Host: 85.198.98.104
Port: 5433
Database: postgres
User: postgres
Password: Mi31415926pSss!
```

### 2. Импортировать Workflows

1. Открыть n8n
2. **Workflows → Import from File**
3. Выбрать JSON файлы по очереди
4. В каждом workflow найти ноды PostgreSQL и выбрать созданный Credential

### 3. Активировать Webhooks

После импорта API workflows:
1. Открыть workflow
2. Нажать **Activate**
3. Webhook URL появится в настройках Webhook ноды

## API Endpoints

### GET /greenspark/cities
Получить список городов из БД.

```bash
curl http://localhost:5678/webhook/greenspark/cities
```

**Response:**
```json
{
  "success": true,
  "count": 60,
  "cities": [
    {"city_id": 16344, "name": "Интернет-магазин", "products_count": 15420},
    {"city_id": 1234, "name": "Москва", "products_count": 12500},
    ...
  ]
}
```

### GET /greenspark/categories
Получить список категорий товаров.

```bash
curl http://localhost:5678/webhook/greenspark/categories
curl "http://localhost:5678/webhook/greenspark/categories?city_id=1234"
```

**Response:**
```json
{
  "success": true,
  "count": 25,
  "categories": [
    {"name": "Дисплеи", "slug": "displei", "full_path": "komplektuyushchie_dlya_remonta/displei"},
    {"name": "Аккумуляторы", "slug": "akkumulyatory", "full_path": "komplektuyushchie_dlya_remonta/akkumulyatory"},
    ...
  ]
}
```

### POST /greenspark/parse/city
Парсить все товары города.

```bash
curl -X POST http://localhost:5678/webhook/greenspark/parse/city \
  -H "Content-Type: application/json" \
  -d '{
    "city_id": "16344",
    "max_pages": 50,
    "delay_ms": 1000,
    "use_proxy": true,
    "save_to_db": true
  }'
```

**Parameters:**
- `city_id` (optional): ID города (default: 16344 - интернет-магазин)
- `max_pages`: лимит страниц на категорию (default: 100)
- `delay_ms`: задержка между запросами в мс (default: 1000)
- `use_proxy`: использовать прокси из БД (default: true)
- `save_to_db`: сохранять в PostgreSQL (default: true)

### POST /greenspark/parse/products
Парсить категорию с ротацией прокси.

```bash
curl -X POST http://localhost:5678/webhook/greenspark/parse/products \
  -H "Content-Type: application/json" \
  -d '{
    "city_id": "16344",
    "category": "displei",
    "max_pages": 10,
    "delay_ms": 1500,
    "use_proxy": true
  }'
```

### POST /greenspark/mcp/cookies
Получить cookies через MCP/Playwright (требует настроенный MCP сервер).

```bash
curl -X POST http://localhost:5678/webhook/greenspark/mcp/cookies \
  -H "Content-Type: application/json" \
  -d '{"city_id": "16344"}'
```

**Response:**
```json
{
  "success": true,
  "city_id": "16344",
  "cookie_string": "magazine=16344; global_magazine=16344; ...",
  "cookies_count": 5
}
```

## MCP Server Setup

Для обхода headless-детекции нужен MCP сервер с Playwright:

### 1. Установить MCP Server

```bash
npm install -g @anthropic/mcp-server-playwright
```

### 2. Конфигурация

Создать `mcp-config.json`:

```json
{
  "servers": {
    "playwright": {
      "command": "mcp-server-playwright",
      "args": ["--headless=false"],
      "env": {
        "DISPLAY": ":99"
      }
    }
  }
}
```

### 3. Запуск с Xvfb (Linux)

```bash
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
mcp-server-playwright --port 3001
```

**Примечание:** Если MCP сервер недоступен, workflow использует fallback cookies.

## Таблицы БД

### outlets
```sql
CREATE TABLE outlets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE,    -- 'greenspark-16344'
    city VARCHAR(200),
    name VARCHAR(300),
    is_active BOOLEAN DEFAULT true
);
```

### greenspark_nomenclature
```sql
CREATE TABLE greenspark_nomenclature (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500),
    product_url VARCHAR(500) UNIQUE,
    article VARCHAR(100),
    category VARCHAR(200),
    first_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### greenspark_prices
```sql
CREATE TABLE greenspark_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INT REFERENCES greenspark_nomenclature(id),
    outlet_id INT REFERENCES outlets(id),
    price DECIMAL(10,2),
    price_wholesale DECIMAL(10,2),
    in_stock BOOLEAN,
    updated_at TIMESTAMP,
    UNIQUE(nomenclature_id, outlet_id)
);
```

### zip_proxies (общая)
```sql
-- Используется совместно с GSMArena парсером
CREATE TABLE zip_proxies (
    proxy VARCHAR(50) PRIMARY KEY,
    status VARCHAR(20) DEFAULT 'raw',
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,
    banned_sites TEXT[] DEFAULT '{}',
    last_tested_at TIMESTAMP,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Ротация прокси

Workflow `parse_with_proxy.json`:
1. Берёт рабочий прокси из `zip_proxies` (status='working', не забанен на greenspark)
2. При успехе - увеличивает `success_count`
3. При ошибке - увеличивает `fail_count`, добавляет 'greenspark' в `banned_sites`
4. Если прокси не работает - переключается на прямое соединение

## Особенности GreenSpark API

### Cookies
Сайт использует cookies для определения города:
- `magazine` - ID магазина/города
- `global_magazine` - глобальный ID
- `catalog-per-page` - товаров на странице (макс. 100)

### Формат цен
- `price` - розничная цена
- `opt_price` - оптовая цена (для B2B)

### Лимиты
- Максимум 100 товаров на страницу
- Рекомендуемая задержка: 1-2 секунды
- При частых запросах возможна блокировка по IP

## Troubleshooting

### Ошибка "City not found"
Проверьте что город существует в таблице `outlets` с кодом `greenspark-{city_id}`.

### 403 Forbidden
- Проверьте cookies (попробуйте MCP для обновления)
- Используйте прокси
- Увеличьте delay_ms

### Пустые данные
- API может вернуть пустой список если город не поддерживается
- Используйте city_id=16344 (интернет-магазин) как fallback

### PostgreSQL Credential Error
1. Проверьте что credentials созданы в n8n
2. Замените `POSTGRES_CREDENTIAL_ID` на реальный ID в JSON файлах

## Примеры использования

### Парсинг интернет-магазина
```bash
curl -X POST http://localhost:5678/webhook/greenspark/parse/city \
  -H "Content-Type: application/json" \
  -d '{"city_id": "16344", "max_pages": 100}'
```

### Парсинг нескольких городов
```bash
for city in 16344 1234 5678; do
  curl -X POST http://localhost:5678/webhook/greenspark/parse/city \
    -H "Content-Type: application/json" \
    -d "{\"city_id\": \"$city\", \"max_pages\": 50}"
  sleep 30
done
```

### Только категория дисплеев
```bash
curl -X POST http://localhost:5678/webhook/greenspark/parse/products \
  -H "Content-Type: application/json" \
  -d '{
    "city_id": "16344",
    "category": "displei",
    "max_pages": 20
  }'
```

## Рекомендации

1. Начните с `city_id=16344` (интернет-магазин) - там полный каталог
2. Используйте delay_ms >= 1000 для избежания блокировок
3. Запускайте proxy_scraper/checker из GSMArena для поддержания пула прокси
4. Мониторьте логи n8n для отслеживания ошибок
5. При массовом парсинге используйте MCP для свежих cookies
