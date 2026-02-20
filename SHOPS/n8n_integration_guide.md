# n8n Workflows - Proxy Manager & MCP Integration Guide

Все воркфлоу интегрированы с:
- **Proxy Manager** (`services/proxy-manager`) - управление прокси
- **MCP Playwright Server** (`mcp/playwright-server`) - браузерная автоматизация

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        n8n Workflow                              │
└─────────────────────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌─────────────────────┐            ┌─────────────────────┐
│   Proxy Manager     │            │  MCP Playwright     │
│   :8000             │            │  :3001              │
│                     │            │                     │
│ GET /get            │            │ POST /tools/        │
│ POST /report        │            │   get_cookies       │
│ POST /full-cycle    │            │   get_page          │
└─────────────────────┘            │   solve_captcha     │
          │                        └─────────────────────┘
          ▼                                    │
┌─────────────────────┐                        ▼
│   PostgreSQL        │            ┌─────────────────────┐
│   zip_proxies       │            │   Target Sites      │
└─────────────────────┘            │   - gsmarena.com    │
                                   │   - green-spark.ru  │
                                   │   - moba.ru         │
                                   └─────────────────────┘
```

## Сервисы

### Proxy Manager (http://proxy-manager:8000)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/get` | GET | Получить рабочий прокси |
| `/report` | POST | Сообщить результат использования |
| `/full-cycle` | POST | Полный цикл: scrape + check + cleanup |
| `/stats` | GET | Статистика прокси |

**Параметры `/get`:**
- `type` - http, https, socks4, socks5
- `exclude` - сайты для исключения (через запятую)

**Параметры `/report`:**
- `proxy` - адрес прокси (ip:port)
- `success` - true/false
- `response_time` - время ответа (мс)
- `banned_site` - сайт где забанен (опционально)

### MCP Playwright Server (http://mcp-playwright:3001)

| Tool | Описание |
|------|----------|
| `get_cookies` | Получить cookies после обхода защиты |
| `get_page` | Получить HTML с JS рендерингом |
| `solve_captcha` | Решить капчу (2captcha) |
| `screenshot` | Скриншот страницы |

**Поддерживаемые сайты:**
- `greenspark` - green-spark.ru (headless detection)
- `moba` - moba.ru (Yandex SmartCaptcha)
- `gsmarena` - gsmarena.com (Cloudflare)

## Воркфлоу по магазинам

### GSMArena

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_brand_v2.json` | Парсинг бренда | POST /gsmarena/parse/brand |
| `api_get_brands.json` | Список брендов | GET /gsmarena/brands |
| `api_get_models.json` | Список моделей | GET /gsmarena/models |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/gsmarena/parse/brand \
  -H "Content-Type: application/json" \
  -d '{
    "brand": "samsung",
    "max_models": 10,
    "use_proxy": true,
    "use_mcp": true,
    "save_to_db": true
  }'
```

### GreenSpark

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_city_v2.json` | Парсинг города | POST /greenspark/parse/city |
| `api_get_cities.json` | Список городов | GET /greenspark/cities |
| `api_get_categories.json` | Список категорий | GET /greenspark/categories |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/greenspark/parse/city \
  -H "Content-Type: application/json" \
  -d '{
    "city_id": 290112,
    "city_name": "Москва",
    "category": "komplektuyushchie_dlya_remonta",
    "use_proxy": true,
    "use_mcp": true,
    "save_to_db": true
  }'
```

### Moba

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_catalog.json` | Парсинг каталога | POST /moba/parse/catalog |
| `api_get_categories.json` | Список категорий | GET /moba/categories |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/moba/parse/catalog \
  -H "Content-Type: application/json" \
  -d '{
    "category_url": "/catalog/zapchasti-dlya-telefonov/",
    "max_pages": 10,
    "save_to_db": true
  }'
```

### 05GSM

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_all.json` | Парсинг каталога | POST /05gsm/parse/all |
| `api_check_price.json` | Проверка цены | POST /05gsm/price |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/05gsm/parse/all \
  -H "Content-Type: application/json" \
  -d '{
    "category": "zapchasti_dlya_telefonov",
    "max_pages": 50,
    "use_proxy": true,
    "save_to_db": true
  }'
```

### LCD-Stock

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_all.json` | Парсинг (5 outlet'ов) | POST /lcdstock/parse/all |
| `api_check_price.json` | Проверка цены | POST /lcdstock/price |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/lcdstock/parse/all \
  -H "Content-Type: application/json" \
  -d '{
    "category": "displei",
    "outlet": "savelovskiy",
    "max_pages": 50,
    "save_to_db": true
  }'
```

### Liberti

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_all.json` | Скачивание Excel прайсов | POST /liberti/parse/all |
| `api_check_price.json` | Проверка цены | POST /liberti/price |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/liberti/parse/all \
  -H "Content-Type: application/json" \
  -d '{
    "cities": ["ekaterinburg", "moscow"],
    "save_to_db": true
  }'
```

### MemsTech

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_all.json` | Парсинг (10 городов) | POST /memstech/parse/all |
| `api_check_price.json` | Проверка цены | POST /memstech/price |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/memstech/parse/all \
  -H "Content-Type: application/json" \
  -d '{
    "city": "msk",
    "category": "iphone",
    "max_pages": 50,
    "save_to_db": true
  }'
```

### MoySklad (Naffas)

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_all.json` | Парсинг через API | POST /moysklad/parse/all |
| `api_check_price.json` | Проверка цены | POST /moysklad/price |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/moysklad/parse/all \
  -H "Content-Type: application/json" \
  -d '{"save_to_db": true}'
```

### Orizhka

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_all.json` | Парсинг Tilda API | POST /orizhka/parse/all |
| `api_check_price.json` | Проверка цены | POST /orizhka/price |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/orizhka/parse/all \
  -H "Content-Type: application/json" \
  -d '{
    "categories": ["346541913282"],
    "save_to_db": true
  }'
```

### Signal23

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_all.json` | Парсинг OpenCart | POST /signal23/parse/all |
| `api_check_price.json` | Проверка цены | POST /signal23/price |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/signal23/parse/all \
  -H "Content-Type: application/json" \
  -d '{
    "category": "zapchasti-dlya-telefonov",
    "max_pages": 50,
    "save_to_db": true
  }'
```

### Taggsm

| Файл | Описание | Endpoint |
|------|----------|----------|
| `api_parse_all.json` | Парсинг (85 городов) | POST /taggsm/parse/all |
| `api_check_price.json` | Проверка цены | POST /taggsm/price |

**Пример вызова:**
```bash
curl -X POST http://n8n:5678/webhook/taggsm/parse/all \
  -H "Content-Type: application/json" \
  -d '{
    "category_path": "900000",
    "city": "Москва",
    "max_pages": 100,
    "save_to_db": true
  }'
```

### Proxy Manager Cron

| Файл | Описание |
|------|----------|
| `cron_proxy_full_cycle.json` | Автоматический сбор прокси (3 раза в день) |

## Логика интеграции

### 1. Получение прокси
```javascript
// В начале воркфлоу
GET http://proxy-manager:8000/get?type=http&exclude=gsmarena

// Response
{
  "proxy": "185.32.4.123:8080",
  "proxy_type": "http",
  "success_count": 15
}
```

### 2. Получение cookies через MCP
```javascript
// POST http://mcp-playwright:3001/tools/get_cookies
{
  "site": "moba"  // или "greenspark", "gsmarena"
}

// Response
{
  "success": true,
  "cookies": [...],
  "cookie_string": "session=abc; ...",
  "user_agent": "Mozilla/5.0 ..."
}
```

### 3. Использование в HTTP запросах
```javascript
// HTTP Request Node
{
  "url": "https://moba.ru/catalog/",
  "headers": {
    "Cookie": "{{ $json.cookie_header }}",
    "User-Agent": "{{ $json.user_agent }}"
  },
  "proxy": "{{ $json.proxy_url }}"
}
```

### 4. Отчёт о результате
```javascript
// В конце воркфлоу
POST http://proxy-manager:8000/report?proxy=185.32.4.123:8080&success=true&response_time=1500

// Если заблокирован на сайте
POST http://proxy-manager:8000/report?proxy=185.32.4.123:8080&success=false&banned_site=moba
```

## Docker Compose

```yaml
version: '3.8'

services:
  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=admin
    volumes:
      - n8n_data:/home/node/.n8n

  proxy-manager:
    build: ./services/proxy-manager
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=85.198.98.104
      - DB_PORT=5433
      - DB_PASSWORD=Mi31415926pSss!

  mcp-playwright:
    build: ./mcp/playwright-server
    ports:
      - "3001:3001"
    environment:
      - MODE=http
      - CAPTCHA_SERVICE=2captcha
      - CAPTCHA_API_KEY=your_key

volumes:
  n8n_data:
```

## Импорт воркфлоу в n8n

1. Открыть n8n UI (http://localhost:5678)
2. Создать новый воркфлоу
3. Меню → Import from File
4. Выбрать JSON файл из папки n8n

## Настройка Credentials

После импорта нужно настроить:

1. **PostgreSQL Credential**
   - Host: 85.198.98.104
   - Port: 5433
   - Database: postgres / db_moba / db_gsmarena
   - User: postgres
   - Password: Mi31415926pSss!

2. **Обновить ID в воркфлоу**
   - Найти `POSTGRES_CREDENTIAL_ID`
   - Заменить на реальный ID credential

## Troubleshooting

### Прокси не работает
1. Проверить статус: `GET http://proxy-manager:8000/stats`
2. Запустить сбор: `POST http://proxy-manager:8000/full-cycle`

### MCP не возвращает cookies
1. Проверить логи: `docker logs mcp-playwright`
2. Проверить API ключ captcha в `.env`
3. Для moba.ru - обязательно нужен captcha solver

### Блокировка на сайте
1. Воркфлоу автоматически репортит ban в Proxy Manager
2. При следующем запросе этот прокси не будет выдан для данного сайта
3. Проверить banned_sites: `GET http://proxy-manager:8000/list?limit=10`
