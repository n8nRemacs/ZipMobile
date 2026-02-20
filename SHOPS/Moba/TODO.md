# Moba.ru Parser — TODO
Обновлено: 2026-02-16 00:30 (GMT+4)

## Статус: Москва DONE, мульти-город NOT STARTED

## Что уже работает
- `moba_playwright_parser.py` — парсер Москвы через Playwright (SmartCaptcha обходится автоматически)
- `write_to_db.py` — запись в БД через staging (port 6543, batch 200)
- В БД: 12,764 товара в `moba_nomenclature` + `moba_prices` (outlet `moba-online`)
- JSON: `moba_data/moba_products_20260215_230702.json` (26,936 позиций, 11MB)

## TODO

### 1. Задеплоить и протестировать мульти-город
- Файл: `moba_multicity_parser.py` (уже написан, 33 города)
- Деплой: `scp moba_multicity_parser.py avito-homelab:/mnt/projects/repos/ZipMobile/SHOPS/Moba/`
- Тест на 2 города: `python3 moba_multicity_parser.py --cities 2 --no-db`
- Полный запуск: `nohup python3 -u moba_multicity_parser.py --skip-moscow -j 4 --no-db > /tmp/moba_multi.log 2>&1 &`
- Цены одинаковые во всех городах — парсим только наличие

### 2. Написать мульти-город DB writer
- `write_to_db.py` сейчас пишет только Москву (outlet `moba-online`)
- Нужно: для каждого города создать outlet `moba-{subdomain}` и записать prices
- Файлы: `moba_data/moba_{subdomain}_YYYYMMDD.json` (создаются парсером)
- Таблица `zip_outlets`: code=`moba-kazan`, city=`Казань`, name=`Moba.ru Казань`
- **Важно**: port 6543, BATCH_SIZE=200, autocommit=True

### 3. Обновить Orchestrator adapter
- Файл: `orchestrator/src/parsers/moba.py`
- Сейчас: вызывает `moba_full_parser.py` + cookie refresh (не работает)
- Нужно: вызывать `moba_playwright_parser.py --no-db` → читать JSON → write_to_db.py
- Или: интегрировать Playwright прямо в adapter

### 4. Добавить retry при page navigation errors
- В `moba_playwright_parser.py`, метод `PlaywrightFetcher.get()`
- 2 из 240 категорий пропущены из-за "Page.content: Unable to retrieve content"
- Нужно: retry 2-3 раза при ошибке навигации

## Ключевые ограничения
- Supabase PgBouncer: port 5432 = Session mode (max ~15 clients, НЕ ИСПОЛЬЗОВАТЬ)
- Supabase PgBouncer: port 6543 = Transaction mode (OK для batch)
- execute_values: max ~300 rows/batch (500 зависает), используем 200
- Homelab: `ssh avito-homelab`, путь `/mnt/projects/repos/ZipMobile/SHOPS/Moba/`
- SSH может дропнуться — всегда запускать через `nohup`
- Playwright + stealth установлены на homelab

## Файлы
```
SHOPS/Moba/
├── moba_playwright_parser.py   # Москва парсер (Playwright) ✅
├── moba_multicity_parser.py    # Мульти-город парсер ⏳
├── write_to_db.py              # DB writer (staging approach) ✅
├── moba_parser.py              # Старый парсер (curl_cffi + cookies)
├── moba_full_parser.py         # Старый полный парсер
├── auto_cookies.py             # Cookie capture (не нужен с Playwright)
├── db_wrapper.py → ../db_wrapper.py
├── db_config.py → ../db_config.py
└── moba_data/                  # JSON/CSV результаты парсинга
```

## DB таблицы (Supabase project griexhozxrqtepcilfnu)
- `moba_nomenclature` — товары (article, name, category)
- `moba_prices` — цены по outlet-ам (nomenclature_id, outlet_id, price, in_stock)
- `moba_staging` — промежуточная для bulk write
- `zip_outlets` — точки продаж (code, city, name)
