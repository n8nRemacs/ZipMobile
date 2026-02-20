# GSMArena Parser - n8n Workflows

Набор workflows для парсинга телефонов с GSMArena.com через n8n 2.0.1.

## Структура

```
n8n/
├── api_get_brands.json       # API: GET /gsmarena/brands
├── api_get_models.json       # API: GET /gsmarena/models/:brand
├── api_parse_brand.json      # API: POST /gsmarena/parse/brand
├── api_parse_models.json     # API: POST /gsmarena/parse/models
├── proxy_scraper.json        # Парсер бесплатных прокси
├── proxy_checker.json        # Проверка прокси
└── README.md                 # Эта документация
```

## Установка

### 1. Создать PostgreSQL Credentials

В n8n: **Settings → Credentials → Add Credential → PostgreSQL**

```
Name: PostgreSQL GSMArena
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

### GET /gsmarena/brands
Получить список всех брендов с GSMArena.

```bash
curl http://localhost:5678/webhook/gsmarena/brands
```

**Response:**
```json
{
  "success": true,
  "count": 126,
  "brands": [
    {"name": "Samsung", "code": "samsung", "url": "...", "device_count": 1446},
    {"name": "Apple", "code": "apple", "url": "...", "device_count": 143},
    ...
  ]
}
```

### GET /gsmarena/models/:brand
Получить список моделей бренда.

```bash
curl http://localhost:5678/webhook/gsmarena/models/apple
curl http://localhost:5678/webhook/gsmarena/models/samsung?max_pages=5
```

**Response:**
```json
{
  "success": true,
  "brand": {"name": "Apple", "code": "apple", "url": "..."},
  "count": 143,
  "models": [
    {"name": "iPhone 16 Pro Max", "url": "...", "gsmarena_id": "12345"},
    ...
  ]
}
```

### POST /gsmarena/parse/brand
Парсить все модели бренда с сохранением в БД.

```bash
curl -X POST http://localhost:5678/webhook/gsmarena/parse/brand \
  -H "Content-Type: application/json" \
  -d '{
    "brand": "apple",
    "max_models": 10,
    "delay_seconds": 2,
    "save_to_db": true
  }'
```

**Parameters:**
- `brand` (required): код бренда (apple, samsung, xiaomi...)
- `max_models`: лимит моделей (0 = все)
- `delay_seconds`: задержка между запросами (default: 2)
- `save_to_db`: сохранять в PostgreSQL (default: true)

### POST /gsmarena/parse/models
Парсить конкретные модели по URL.

```bash
curl -X POST http://localhost:5678/webhook/gsmarena/parse/models \
  -H "Content-Type: application/json" \
  -d '{
    "models": [
      {"url": "https://www.gsmarena.com/apple_iphone_16_pro_max-12999.php", "brand": "Apple"},
      {"url": "https://www.gsmarena.com/samsung_galaxy_s24_ultra-12771.php", "brand": "Samsung"}
    ],
    "delay_seconds": 2,
    "save_to_db": true
  }'
```

## Прокси Workflows

### Proxy Scraper
Парсит бесплатные прокси из GitHub репозиториев.

- **Источники:** TheSpeedX, monosans, clarketm, proxifly и др.
- **Расписание:** каждые 6 часов
- **Действие:** сохраняет в `zip_proxies` со статусом `raw`

### Proxy Checker
Проверяет прокси на работоспособность.

- **Расписание:** каждые 30 минут
- **Действие:** берёт `raw` прокси, тестирует, обновляет статус на `working` или `dead`

## Таблица zip_proxies

```sql
CREATE TABLE zip_proxies (
    proxy VARCHAR(50) PRIMARY KEY,        -- ip:port
    status VARCHAR(20) DEFAULT 'raw',     -- raw, checking, working, dead, used, banned
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,
    banned_sites TEXT[] DEFAULT '{}',     -- ['gsmarena', 'google', ...]
    last_tested_at TIMESTAMP,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_proxies_status ON zip_proxies(status);
CREATE INDEX idx_proxies_last_tested ON zip_proxies(last_tested_at);
```

## Статусы прокси

| Статус | Описание |
|--------|----------|
| `raw` | Новый, не проверен |
| `checking` | Сейчас проверяется |
| `working` | Рабочий, готов к использованию |
| `used` | Используется парсером |
| `dead` | Не работает |
| `banned` | Забанен на многих сайтах |

## Настройка расписания

В каждом workflow можно изменить расписание:

1. Открыть workflow
2. Кликнуть на ноду **Schedule Trigger**
3. Изменить интервал
4. Сохранить и активировать

## Troubleshooting

### Ошибка "Brand not found"
Проверьте правильность кода бренда. Используйте GET /brands для получения списка.

### 429 Too Many Requests
GSMArena блокирует частые запросы:
- Увеличьте `delay_seconds` до 3-5
- Используйте прокси (запустите proxy_scraper и proxy_checker)

### Прокси не работают
1. Запустите `proxy_scraper` для загрузки свежих прокси
2. Запустите `proxy_checker` для проверки
3. Проверьте статистику: `SELECT status, count(*) FROM zip_proxies GROUP BY status`

### PostgreSQL Credential Error
Убедитесь что:
- ID credentials в JSON совпадает с созданным
- Или замените `POSTGRES_CREDENTIAL_ID` на реальный ID

## Примеры использования

### Парсинг топ-5 брендов
```bash
for brand in samsung apple xiaomi huawei oppo; do
  curl -X POST http://localhost:5678/webhook/gsmarena/parse/brand \
    -H "Content-Type: application/json" \
    -d "{\"brand\": \"$brand\", \"max_models\": 50}"
  sleep 10
done
```

### Допарсить недостающие модели
```bash
curl -X POST http://localhost:5678/webhook/gsmarena/parse/models \
  -H "Content-Type: application/json" \
  -d '{
    "models": [
      {"url": "https://www.gsmarena.com/samsung_galaxy_a55-12824.php", "brand": "Samsung"},
      {"url": "https://www.gsmarena.com/xiaomi_14_ultra-12546.php", "brand": "Xiaomi"}
    ]
  }'
```

## Ограничения n8n

1. **Нет нативной поддержки прокси** - HTTP Request node не поддерживает прокси напрямую
2. **Cheerio не встроен** - для парсинга HTML нужен `require('cheerio')` в Code node
3. **Лимит execution time** - длинные парсинги могут таймаутиться

## Рекомендации

- Парсите по 50-100 моделей за раз
- Используйте delay_seconds >= 2
- Мониторьте логи в n8n для отслеживания ошибок
- Периодически запускайте proxy_scraper для обновления пула
