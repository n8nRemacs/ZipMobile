# n8n Workflows для Normalizer

4 воркфлоу, каждый — отдельный webhook, вызываемый из Normalizer API.

## Список воркфлоу

| # | Файл | Webhook URL | Описание |
|---|---|---|---|
| 1 | `01_classify.json` | `/webhook/normalizer/classify` | Классификация: запчасть или нет |
| 2 | `02_extract_brand_models.json` | `/webhook/normalizer/extract-brand-models` | Извлечение бренда и моделей из названия |
| 3 | `03_validate_brand.json` | `/webhook/normalizer/validate-brand` | Валидация бренда: найти совпадение в справочнике |
| 4 | `04_validate_models.json` | `/webhook/normalizer/validate-models` | Валидация моделей: найти совпадения в справочнике |

## Как импортировать

1. Открыть n8n → Workflows → Import from File
2. Выбрать JSON файл
3. **Настроить credentials:** в каждом воркфлоу есть нода `OpenAI Request` — указать свой OpenAI API key
4. Активировать воркфлоу (toggle Active)

## Структура каждого воркфлоу

Каждый воркфлоу разбит на мелкие блоки для простоты отладки:

```
Webhook (trigger)
    │
    ▼
Prepare Prompt (Code) — формирование system + user prompt
    │
    ▼
OpenAI Request (HTTP Request) — вызов OpenAI API
    │
    ▼
Parse Response (Code) — парсинг JSON из ответа AI
    │
    ▼
Respond (Respond to Webhook) — возврат результата
```

## Настройки

### OpenAI API Key

В каждом воркфлоу нода `OpenAI Request` использует Header Auth:
- **Header Name:** `Authorization`
- **Header Value:** `Bearer sk-YOUR-KEY-HERE`

Замените на свой ключ в каждом воркфлоу, или создайте один credential и переиспользуйте.

### Модель

По умолчанию используется `gpt-4o-mini`. Можно поменять на `gpt-4o` для большей точности (дороже) в ноде `Prepare Prompt` → переменная `model`.

## Входы/Выходы

### 01 Classify

**Вход:**
```json
{"name": "Дисплей iPhone 14 Pro OLED GX черный", "article": "DSP-IP14P-BK"}
```

**Выход:**
```json
{"is_spare_part": true, "nomenclature_type": "display", "confidence": 0.97}
```

### 02 Extract Brand Models

**Вход:**
```json
{"name": "Дисплей iPhone 14 Pro OLED GX черный"}
```

**Выход:**
```json
{"brand": "Apple", "models": ["iPhone 14 Pro"], "confidence": 0.95}
```

### 03 Validate Brand

**Вход:**
```json
{
  "brand_raw": "Aple",
  "all_brands": [{"id": 1, "name": "Apple"}, {"id": 2, "name": "Samsung"}]
}
```

**Выход:**
```json
{"is_new": false, "match_id": 1, "match": "Apple", "confidence": 0.95, "reasoning": "Опечатка: Aple → Apple"}
```

### 04 Validate Models

**Вход:**
```json
{
  "models_raw": ["iPhone 14Pro"],
  "brand_id": 1,
  "all_models": [{"id": 10, "name": "iPhone 14 Pro"}, {"id": 11, "name": "iPhone 14"}]
}
```

**Выход:**
```json
{
  "matches": [
    {"model": "iPhone 14Pro", "is_new": false, "match_id": 10, "match": "iPhone 14 Pro", "confidence": 0.96, "reasoning": "Пробел: 14Pro → 14 Pro"}
  ]
}
```

## Отладка

1. Открыть воркфлоу в n8n
2. Нажать "Execute Workflow" (ручной запуск)
3. Использовать Test Webhook URL из ноды Webhook
4. Отправить curl на тестовый URL
5. Смотреть вывод каждой ноды отдельно — промпт, raw ответ OpenAI, распарсенный результат
