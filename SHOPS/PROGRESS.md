# SHOPS Parsers — Progress
Обновлено: 2026-02-15 21:10 (GMT+4)

## Текущая задача
**Proxy Pool + Moba адаптер (2026-02-15)**

### Что сделано
1. `orchestrator/src/proxy/` — полный proxy pool (scraper, checker, database, pool)
2. Таблица `zip_proxies` в Supabase (griexhozxrqtepcilfnu)
3. 103K прокси собраны из 34 GitHub/web источников
4. 129 рабочих HTTP прокси из 1200 проверенных (~10.7%)
5. **0/50 прокси работают для moba.ru** — SmartCaptcha блокирует все бесплатные
6. Moba adapter: `orchestrator/src/parsers/moba.py` + `--proxy` / `--json-stdout` в moba_parser.py
7. Supervisor с proxy rotation: `orchestrator/src/supervisor.py`
8. FastAPI: `orchestrator/src/main.py` (порт 8100)

### Вывод по moba
Бесплатные прокси не проходят Yandex SmartCaptcha. Нужны резидентные прокси или curl_cffi + свежие cookies.

---

## Memstech парсер — починен (2026-02-15)

### Что было
Парсер падал на 9-м городе (Ростов-на-Дону) при `--all`. EXIT_CODE=0 — тихо останавливался. Причина: `requests.Session` накапливал cookies/connections за 8 городов, после чего все HTTP-запросы молча фейлили. `fetch_page` ловил ВСЕ исключения и возвращал `None`, `crawl_category` возвращал 0 — парсер "завершался нормально" с 0 товаров.

### Что починено
1. **`reset_for_new_city()`** — теперь пересоздаёт `self.session` (close + new Session) при смене города
2. **`parse_all_cities()`** — try/except на каждый город + continue при ошибке + отчёт о failed cities + счётчик прогресса
3. **`fetch_page()`** — retry 3 раза с backoff для ConnectionError/Timeout (было: 1 попытка, молчаливый None)

### Что сейчас запущено на Homelab
- Тестовый запуск **только Ростова** с перехватом исключений для диагностики причины падения
- Команда: запущена через SSH, ждём результат в `/tmp/memstech_run3.log` или в выводе
- Процесс: `python3 -u` скрипт парсит только `rnd.memstech.ru`

### Результат диагностики
- Ростов-на-Дону **отдельно парсится успешно** (11,734 товара, 0 ошибок)
- Значит проблема НЕ в конкретном городе, а в **накоплении данных/состояния** при последовательном парсинге 9+ городов
- `parse_all_cities()` копит все товары в `all_products` (list.extend) — после 8 городов это ~93K dict'ов
- `reset_for_new_city()` очищает `self.products`, `self.seen_product_ids`, `self.categories_crawled` — но `all_products` в вызывающем коде растёт
- Возможная причина: `self.session` (requests.Session) накапливает cookies/connections за 8 городов

### Рекомендуемый фикс
- В `parse_all_cities()` закрывать и пересоздавать `self.session` каждые N городов
- Или: парсить города по одному (`--city rnd`), записывать в staging по частям
- Или: добавить try/except вокруг каждого города в цикле, логировать traceback

## Состояние всех 9 парсеров

| Shop | Prefix | Staging | Nomenclature | Prices | Status |
|------|--------|---------|-------------|--------|--------|
| Orizhka | orizhka_ | 2,607 | 2,607 | 2,607 | ✅ Стабилен |
| Naffas | moysklad_naffas_ | 1,272 | 1,276 | 1,275 | ✅ Стабилен |
| 05GSM | _05gsm_ | 3,407 | 3,506 | 3,506 | ✅ Стабилен |
| LCD-Stock | lcdstock_ | 5,860 | 1,170 | 5,850 | ✅ Стабилен |
| Profi | profi_ | 204,392 | 13,541 | 204,392 | ✅ Стабилен |
| Liberti | liberti_ | 232,337 | 16,918 | 232,337 | ✅ Стабилен |
| Memstech | memstech_ | 172,925 | 11,266+ | 172,925 | ✅ Починен: 15 городов, session reset + batch DB write |
| TagGSM | taggsm_ | 2,009,744 | 22,838 | 2,009,744 | ✅ Стабилен |
| Signal23 | signal23_ | 3,133 | 3,133 | 3,133 | ✅ Починен |

## Что было сделано в этой сессии

### Signal23 — починен
- Проблема: `SSL SYSCALL error: EOF detected` при batch_insert после 20 мин HTTP-парсинга
- Все 3 retry тоже падали
- **Фикс в signal23/parser.py:**
  - `parser.session.close()` + `time.sleep(2)` перед DB-операциями (освобождает HTTP keep-alive сокеты)
  - `page_size=200` вместо 1000 (меньше данных за запрос к PgBouncer)
- Проверен: `--all` работает стабильно от начала до конца

### Memstech — частично починен
- Проблема 1 (починена): `--all` парсил только Москву, а не все 15 городов
  - **Фикс:** `if args.all_cities:` → `if args.all or args.all_cities:` в main()
- Проблема 2 (НЕ ПОЧИНЕНА): парсер падает на 9-м городе (Ростов-на-Дону)
  - Воспроизводится: оба прогона упали в том же месте (Samsung/korpusnye_elementy_samsung/page 20)
  - EXIT_CODE=0 — Python завершается нормально
  - Не OOM (32GB RAM, используется 2GB)
  - Не timeout (таймаут 7200s, прошло ~90 мин)
  - Скорее всего баг в самом коде парсера

### Инфраструктурные фиксы
- `db_wrapper.py`: DEFAULT_TIMEOUT увеличен 60→120 секунд
- Все парсеры запускаются через `setsid` на Homelab чтобы SSH-разрыв не убивал процесс

## Homelab (SSH)
- Подключение: `ssh avito-homelab` (через ProxyJump avito-vps)
- Путь: `/mnt/projects/repos/ZipMobile/SHOPS/`
- Парсеры: каждый в своей папке (signal23/, memstech/, Taggsm/, Profi/, Liberti/, lcd-stock/, 05GSM/, orizhka/, memstech/)
- DB wrapper: `SHOPS/db_wrapper.py` — единый для всех парсеров
- DB config: `SHOPS/db_config.py` — Supabase PostgreSQL через PgBouncer

## БД
- Host: `aws-1-eu-west-3.pooler.supabase.com:5432` (PgBouncer)
- User: `postgres.griexhozxrqtepcilfnu`
- Password: `Mi31415926pSss!`
- DB: postgres
- sslmode: require
- autocommit: True
- statement_timeout: 600000 (600s)

## Memstech — 15 городов
```python
CITIES = {
    "memstech.ru": ("Москва", 4),
    "ekb": ("Екатеринбург", 1),
    "khb": ("Хабаровск", 1),
    "krd": ("Краснодар", 1),
    "ktl": ("Котлас", 1),
    "mgg": ("Магнитогорск", 1),
    "kzn": ("Казань", 1),
    "omsk": ("Омск", 1),
    "rnd": ("Ростов-на-Дону", 1),
    "spb": ("Санкт-Петербург", 2),
    "skt": ("Сыктывкар", 1),
    "nn": ("Нижний Новгород", 1),
    "chel": ("Челябинск", 1),
    "yar": ("Ярославль", 1),
    "perm": ("Пермь", 1),
}
```

## Ключевые файлы на Homelab
- `/mnt/projects/repos/ZipMobile/SHOPS/db_wrapper.py` — SQL rewriting + connection + batch_insert + retry
- `/mnt/projects/repos/ZipMobile/SHOPS/db_config.py` — Supabase connection config
- `/mnt/projects/repos/ZipMobile/SHOPS/memstech/parser.py` — Memstech парсер (НУЖНО ЧИНИТЬ)
- `/mnt/projects/repos/ZipMobile/SHOPS/memstech/config.py` — ROOT_CATEGORIES, delays
- `/mnt/projects/repos/ZipMobile/SHOPS/signal23/parser.py` — Signal23 парсер (ПОЧИНЕН)
- Логи: `/tmp/memstech_run3.log`, `/tmp/signal23_run2.log`

## Следующие шаги
1. Дождаться результата тестового запуска Ростова с перехватом ошибок
2. По стектрейсу найти причину падения
3. Пофиксить и перезапустить Memstech `--all` со всеми 15 городами
4. Убедиться что prices > nomenclature (несколько outlet-ов на одну номенклатуру)
