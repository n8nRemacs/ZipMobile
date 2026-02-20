# ТЗ: Запуск и тестирование GreenSpark parser_v4.py
Обновлено: 2026-02-19 16:30 (UTC+4)

## Что сделано

1. **proxy-service** задеплоен на Homelab (systemd, порт 8110) — работает
2. **parser_v4.py** написан и задеплоен на сервер
3. **БД** подготовлена — таблицы greenspark_staging/nomenclature/prices существуют
4. **UNIQUE constraint на article** в greenspark_nomenclature — **УДАЛЁН** (разные товары могут иметь одинаковый артикул)
5. **SAVEPOINT'ы** добавлены в process_staging (одна ошибка не ломает транзакцию)
6. **Парсинг Москвы** работает через SOCKS5 прокси (проверено многократно)
7. **Staging пишется** корректно (6166 записей сейчас в staging)
8. **process_staging** тоже работал (8074 → nomenclature+prices, 0 ошибок), но данные пропали из-за конфликта двух процессов

## Что НЕ сделано

1. **Полный цикл в одном запуске**: парсинг → staging → process_staging → проверка nomenclature+prices
2. **Запуск на все 62 города** (`--all-cities --all`)
3. **Cron-задача** для ежедневного парсинга
4. **Обновление CLAUDE.md** с финальным статусом

---

## Текущее состояние сервера (213.108.170.194)

### Сервисы
- proxy-service: **active** (systemd), порт 8110
- PostgreSQL: localhost:5433 (Docker Supabase, контейнер supabase-db)

### Proxy-service статистика
- working: ~51 прокси
- raw: ~103k
- banned_by_site.greenspark: ~16
- dead: ~949

### БД (все таблицы в `public` схеме, PostgreSQL)
```
greenspark_staging:       6166 записей (processed=false, от предыдущих запусков)
greenspark_nomenclature:  0 записей
greenspark_prices:        0 записей
```

### Файлы на сервере
```
/mnt/projects/repos/ZipMobile/SHOPS/GreenSpark/parser_v4.py   (63KB, актуальная версия)
/mnt/projects/repos/ZipMobile/SHOPS/GreenSpark/config.py       (константы)
/mnt/projects/repos/ZipMobile/SHOPS/GreenSpark/telegram_notifier.py
/mnt/projects/repos/ZipMobile/SHOPS/GreenSpark/cookies.json    (последние cookies)
/mnt/projects/repos/ZipMobile/SHOPS/GreenSpark/data/greenspark_cities.json  (62 города)
```

---

## КРИТИЧЕСКИЕ ПРАВИЛА (выучить наизусть)

### 1. ОДИН процесс парсера
**НИКОГДА не запускать два процесса parser_v4.py одновременно.**
Перед запуском ВСЕГДА проверять:
```bash
ssh root@213.108.170.194 "ps aux | grep parser_v4 | grep -v grep"
```
Если есть процесс — НЕ запускать новый. Спросить пользователя.

### 2. Cookies через прокси
Cookies GreenSpark привязаны к IP. При смене прокси ОБЯЗАТЕЛЬНО получать новые cookies через тот же прокси.
Это уже реализовано в parser_v4.py (_switch_proxy → CookieManager.get_cookies(proxy_url)).

### 3. Только SOCKS5
HTTP прокси не работают для HTTPS сайтов (green-spark.ru).
Протокол: `socks5`. Это настроено в main() → `ProxyClient(protocol="socks5")`.

### 4. verify=False для SOCKS5
Некоторые SOCKS5 прокси имеют self-signed SSL сертификаты.
`httpx.Client(verify=False)` — уже настроено в init_client().

### 5. НЕ использовать direct
Прямой IP сервера (213.108.170.194) НЕ должен светиться на green-spark.ru.
Всегда использовать прокси. Флаг `--no-proxy` только для дебага.

### 6. SSH вывод через файлы
SSH команды через tool не показывают stdout. Всегда:
```bash
ssh root@213.108.170.194 "COMMAND > /tmp/result.txt 2>&1"
scp root@213.108.170.194:/tmp/result.txt C:/tmp/result.txt
# потом Read tool
```

---

## Схема БД (актуальная)

### greenspark_staging
```
id              uuid PK (gen_random_uuid)
name            text NOT NULL
url             text
article         varchar(200)
category        text
price           numeric(12,2)
price_wholesale numeric(12,2)
in_stock        boolean (default true)
outlet_code     varchar(100)      -- gs-moskva, gs-sankt-peterburg, etc.
processed       boolean (default false)
created_at      timestamptz (default now)
-- ещё есть: old_price, quantity, raw_data, brand, brand_raw, model_raw, part_type_raw, category_raw, barcode, stock_level, product_id, loaded_at
```

### greenspark_nomenclature
```
id              uuid PK (gen_random_uuid)
name            text NOT NULL
url             text                     -- UNIQUE INDEX (idx_greenspark_nomenclature_url)
article         varchar(200)             -- НЕТ unique constraint (был удалён!)
category        text
first_seen_at   timestamptz (default now)
updated_at      timestamptz (default now)
-- ещё: brand_raw, zip_nomenclature_id, is_active, brand, model, part_type, product_id, barcode
```
**FK:** greenspark_prices.nomenclature_id → greenspark_nomenclature.id

### greenspark_prices
```
id              uuid PK (gen_random_uuid)
nomenclature_id uuid NOT NULL FK → greenspark_nomenclature(id)
outlet_id       uuid NOT NULL FK → zip_outlets(id)
price           numeric(12,2)
in_stock        boolean (default true)
product_url     text
updated_at      timestamptz (default now)
UNIQUE(nomenclature_id, outlet_id)
-- ещё: price_old, old_price, quantity, stock_level
```

### zip_outlets (60 штук для GreenSpark)
```
code: gs-moskva, gs-sankt-peterburg, gs-novosibirsk, ...
api_config: {"set_city": 290112}   -- GreenSpark city_id для cookie magazine
stock_mode: 'api'
shop_id: 1 (greenspark)
```

---

## Пайплайн парсера

```
1. ProxyClient.get_proxy(protocol=socks5) → получить SOCKS5 прокси
2. CookieManager.get_cookies(proxy_url) → Playwright+Xvfb через тот же прокси
3. GreenSparkParser.init_client(cookies, proxy) → httpx.Client с verify=False
4. parser.parse_city(city_id, city_name) → обход каталога + сбор товаров
   └── save_staging() каждые 200 товаров
5. process_staging() → staging → nomenclature (UPSERT ON CONFLICT url) + prices (UPSERT ON CONFLICT nom_id,outlet_id)
```

При бане (не-JSON ответ / 403):
```
_switch_proxy() → report_failure(banned=True) → get_proxy() → get_cookies(new_proxy) → init_client(new_cookies, new_proxy)
```

---

## Шаг 1: Очистить staging и запустить тест на Москву

### 1.1 Проверить что парсер НЕ запущен
```bash
ssh root@213.108.170.194 "ps aux | grep parser_v4 | grep -v grep"
```
Если есть процессы — НЕ ПРОДОЛЖАТЬ.

### 1.2 Проверить proxy-service
```bash
ssh root@213.108.170.194 "curl -s http://localhost:8110/proxy/stats > /tmp/ps.txt"
scp root@213.108.170.194:/tmp/ps.txt C:/tmp/ps.txt
```
Должно быть working > 0.

### 1.3 Очистить staging
```bash
ssh root@213.108.170.194 "psql 'postgresql://postgres:Mi31415926pSss!@localhost:5433/postgres' -c 'DELETE FROM greenspark_staging' > /tmp/clean.txt 2>&1"
```

### 1.4 Задеплоить актуальный parser_v4.py (если менялся локально)
```bash
scp "C:/Projects/Sync/ZipMobile/SHOPS/GreenSpark/parser_v4.py" root@213.108.170.194:/mnt/projects/repos/ZipMobile/SHOPS/GreenSpark/parser_v4.py
```

### 1.5 Запустить ОДИН процесс

**ВАЖНО:** `nohup` через SSH ненадёжен — процесс умирает при закрытии SSH-сессии. Использовать один из вариантов:

**Вариант A (рекомендуемый): screen**
```bash
ssh root@213.108.170.194 "screen -dmS greenspark bash -c 'cd /mnt/projects/repos/ZipMobile/SHOPS/GreenSpark && python3 parser_v4.py --city Москва --all > /var/log/greenspark_v4_test.log 2>&1'"
```
Управление: `screen -r greenspark` (подключиться), `Ctrl+A D` (отключиться), `screen -ls` (список).

**Вариант B: systemd-run**
```bash
ssh root@213.108.170.194 "systemd-run --unit=greenspark-parser --working-directory=/mnt/projects/repos/ZipMobile/SHOPS/GreenSpark -- python3 parser_v4.py --city Москва --all"
```
Логи: `journalctl -u greenspark-parser -f`

**Вариант C: setsid (менее надёжен чем A/B)**
```bash
ssh root@213.108.170.194 "cd /mnt/projects/repos/ZipMobile/SHOPS/GreenSpark && setsid python3 parser_v4.py --city Москва --all > /var/log/greenspark_v4_test.log 2>&1 &"
```

### 1.6 Проверить что запущен ОДИН процесс
```bash
ssh root@213.108.170.194 "ps aux | grep parser_v4 | grep -v grep | wc -l > /tmp/pc.txt"
# Должно быть 1 (python3) или 2 (bash wrapper + python3)
```

### 1.7 Мониторинг (каждые 5-10 минут)
```bash
ssh root@213.108.170.194 "tail -30 /var/log/greenspark_v4_test.log > /tmp/tail.txt && psql 'postgresql://postgres:Mi31415926pSss!@localhost:5433/postgres' -t -c \"SELECT 'staging', COUNT(*), 'processed=' || COUNT(*) FILTER (WHERE processed) FROM greenspark_staging UNION ALL SELECT 'nomenclature', COUNT(*), '' FROM greenspark_nomenclature UNION ALL SELECT 'prices', COUNT(*), '' FROM greenspark_prices\" > /tmp/counts.txt"
scp root@213.108.170.194:/tmp/tail.txt C:/tmp/tail.txt
scp root@213.108.170.194:/tmp/counts.txt C:/tmp/counts.txt
```

### 1.8 Ожидаемый результат для Москвы
- staging: ~8000-10000 записей
- nomenclature: ~8000-10000 записей (после process_staging)
- prices: ~8000-10000 записей (после process_staging)
- Время: ~30-60 минут (парсинг) + ~10 минут (допарсинг артикулов) + ~1 минута (process_staging)
- Лог должен завершиться строками:
  ```
  [PROCESS] Готово: nomenclature=XXXX, prices=XXXX, errors=0
  Парсинг завершён!
  ```

### 1.9 Если процесс завершился но process_staging не запустился
Запустить вручную:
```bash
ssh root@213.108.170.194 "cd /mnt/projects/repos/ZipMobile/SHOPS/GreenSpark && python3 parser_v4.py --process > /var/log/greenspark_process.log 2>&1"
```

---

## Шаг 2: Запуск на все 62 города (после успешного теста Москвы)

### 2.1 Очистить staging
```bash
ssh root@213.108.170.194 "psql 'postgresql://postgres:Mi31415926pSss!@localhost:5433/postgres' -c 'DELETE FROM greenspark_staging; DELETE FROM greenspark_prices; DELETE FROM greenspark_nomenclature'"
```

### 2.2 Запустить (через screen)
```bash
ssh root@213.108.170.194 "screen -dmS greenspark bash -c 'cd /mnt/projects/repos/ZipMobile/SHOPS/GreenSpark && python3 parser_v4.py --all-cities --all --skip-parsed > /var/log/greenspark_v4_full.log 2>&1'"
```

### 2.3 Мониторинг
```bash
# Прогресс
ssh root@213.108.170.194 "grep '=== ГОРОД' /var/log/greenspark_v4_full.log | tail -5 > /tmp/cities_progress.txt"
# Баны
ssh root@213.108.170.194 "grep -c 'BAN' /var/log/greenspark_v4_full.log > /tmp/ban_count.txt"
# Proxy stats
ssh root@213.108.170.194 "curl -s http://localhost:8110/proxy/stats > /tmp/ps.txt"
```

### 2.4 Ожидаемый результат
- 62 города × ~5000-10000 товаров = ~300k-600k записей
- Время: 8-24 часа
- Баны: нормально, парсер автоматически переключает прокси

---

## Шаг 3: Cron (после успешного полного прогона)

```bash
ssh root@213.108.170.194 "echo '0 1 * * * root cd /mnt/projects/repos/ZipMobile/SHOPS/GreenSpark && python3 parser_v4.py --all-cities --all --skip-parsed >> /var/log/greenspark.log 2>&1' > /etc/cron.d/greenspark-parser"
```

---

## Известные проблемы и решения

### Проблема: Два процесса конфликтуют
**Симптомы:** Данные в staging появляются и исчезают.
**Причина:** Два процесса пишут в один лог файл, первый процесс вызывает clear_staging() при старте.
**Решение:** НИКОГДА не запускать два процесса. Перед запуском ВСЕГДА проверять `ps aux | grep parser_v4`.

### Проблема: "current transaction is aborted"
**Симптомы:** process_staging обрабатывает 30 записей, потом 8000 ошибок.
**Причина:** Была UNIQUE constraint на article + отсутствие SAVEPOINT'ов.
**Решение:** ✅ Уже исправлено — constraint удалён, SAVEPOINT'ы добавлены.

### Проблема: HTTP прокси возвращают HTML вместо JSON
**Причина:** HTTP прокси не могут туннелировать HTTPS через CONNECT.
**Решение:** ✅ Используем только SOCKS5.

### Проблема: Cookies не работают через прокси
**Причина:** GreenSpark привязывает cookies к IP.
**Решение:** ✅ Cookies получаются через тот же SOCKS5 прокси (Playwright).

### Проблема: SSL CERTIFICATE_VERIFY_FAILED через SOCKS5
**Причина:** Некоторые SOCKS5 прокси перехватывают SSL.
**Решение:** ✅ verify=False в httpx + ignore_https_errors=True в Playwright.

### Проблема: Процесс умирает без ошибки в логе
**Возможные причины:**
- Два процесса: один перезаписывает лог другого
- Playwright/Xvfb крашится при получении cookies
- SSH-сессия обрывается → nohup через SSH ненадёжен (процесс привязан к PTY сессии)
**Решение:**
1. Запускать через `screen -dmS` или `systemd-run` (см. шаг 1.5)
2. Запускать ОДИН процесс
3. Логи в /var/log/ (не /tmp/)

---

## CLI парсера (справка)

```bash
python3 parser_v4.py --help

# Один город
python3 parser_v4.py --city "Москва" --all       # парсинг + process_staging
python3 parser_v4.py --city "Москва" --no-db      # без БД (тест парсинга)

# Все города
python3 parser_v4.py --all-cities --all            # все города + process_staging
python3 parser_v4.py --all-cities --all --skip-parsed  # пропускать уже спарсенные

# Только process_staging (без парсинга)
python3 parser_v4.py --process

# Очистка staging
python3 parser_v4.py --clear-staging

# Другие опции
--no-reparse    # без допарсинга артикулов (быстрее)
--no-proxy      # без прокси (ОПАСНО, только для теста!)
--category slug # парсить конкретную категорию
--proxy-service http://localhost:8110  # URL proxy-service
```

---

## Связанные файлы (локально на Windows)

```
C:\Projects\Sync\ZipMobile\SHOPS\GreenSpark\parser_v4.py     — основной парсер
C:\Projects\Sync\ZipMobile\SHOPS\GreenSpark\config.py         — константы
C:\Projects\Sync\ZipMobile\SHOPS\GreenSpark\telegram_notifier.py
C:\Projects\Sync\ZipMobile\proxy-service\                     — proxy-service (уже задеплоен)
C:\Projects\Sync\ZipMobile\SHOPS\GreenSpark\data\greenspark_cities.json
```

## Связанные ТЗ
- TZ-005-PARSER-STANDARDIZATION.md — стандарт staging → nomenclature → prices
- TZ-006-LOCAL-SUPABASE-PARSERS.md — перенос парсеров на Homelab
- TZ-007-GREENSPARK-PROXY-SERVICE.md — proxy-service
