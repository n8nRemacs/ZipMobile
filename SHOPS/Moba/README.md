# Moba.ru Parser
Обновлено: 2026-02-22 20:00 (GMT+4)

## Статус: ACTIVE

Основной парсер: `moba_multicity_parser.py` — парсит moba.ru через Playwright с автообходом SmartCaptcha. Записывает в Homelab PostgreSQL (порт 5433).

## Результат последнего парсинга

- **10 506 уникальных товаров** (только запчасти)
- Outlet: `moba-online` (moba.ru без cid — полный каталог)
- 10 категорий, MAX_PAGES=200

## Запуск

```bash
# Online каталог (полная номенклатура) — ~40 мин
python3 moba_multicity_parser.py --no-proxy --parallel 1 --stores 1

# Конкретный город
python3 moba_multicity_parser.py --no-proxy --parallel 1 --city Казань

# Все 43 магазина (online + 42 города) — ~4 часа
python3 moba_multicity_parser.py --no-proxy --parallel 3

# Через фиксированные прокси (round-robin)
python3 moba_multicity_parser.py --proxies socks5://ip1:port,socks5://ip2:port --parallel 6
```

### CLI-аргументы

| Аргумент | Описание |
|----------|----------|
| `--no-proxy` | Прямое подключение (рекомендуется с homelab) |
| `--proxies` | Фиксированные SOCKS5 прокси через запятую |
| `--parallel N` | Количество параллельных браузеров |
| `--stores N` | Ограничить кол-во магазинов |
| `--city NAME` | Фильтр по городу |
| `--no-db` | Только JSON, без записи в БД |
| `--no-tg` | Отключить Telegram-уведомления |
| `--list` | Показать список магазинов и выйти |

## Категории парсинга (10 шт.)

1. `/catalog/displei/` — Дисплеи
2. `/catalog/akkumulyatory-1/` — Аккумуляторы
3. `/catalog/korpusa-zadnie-kryshki/` — Корпуса, задние крышки
4. `/catalog/zapchasti/` — Запчасти
5. `/catalog/zapchasti-dlya-igrovykh-pristavok/` — Запчасти для игровых приставок
6. `/catalog/dlya-noutbukov/` — Для ноутбуков
7. `/catalog/korpusnye-chasti-ramki-skotch-stilusy-tolkateli-i-t-p/` — Корпусные части, рамки, скотч, стилусы
8. `/catalog/mikroskhemy-kontrollery-usiliteli-i-t-p/` — Микросхемы, контроллеры, усилители
9. `/catalog/stekla-plenki-oca-polyarizatory-i-t-p-dlya-displeynykh-moduley/` — Стёкла, плёнки, OCA, поляризаторы
10. `/catalog/shleyfy-platy/` — Шлейфы, платы

**НЕ парсим:** защитные стёкла, аксессуары, батарейки, клавиатуры, карты памяти, элементы питания, инструменты, кабели, чехлы.

## Архитектура

### SmartCaptcha
- Playwright headless Chromium
- Переход на главную → 30 сек ожидание → проверка маркеров (footer, каталог)
- Cookies сохраняются в контексте браузера, парсинг категорий в том же браузере

### Прокси
- **Direct с homelab** — полный каталог (~10K товаров), рекомендуется
- **Через SOCKS5 прокси** — moba.ru режет каталог для datacenter IP (даёт 14-30% от полного)
- **RU прокси** (194.135.17.31) — забанен после интенсивного использования
- Для полного каталога нужен residential/мобильный IP или direct

### БД (Homelab PostgreSQL :5433)

| Таблица | Назначение |
|---------|-----------|
| `moba_nomenclature` | Товары (article UNIQUE, name, category, price) |
| `moba_product_urls` | URL товаров по точкам (nomenclature_id, outlet_id, url UNIQUE) |
| `zip_outlets` | Торговые точки (code, city, name) |

- Артикул: `MOBA-{product_id}` (id из URL товара)
- ON CONFLICT (article) DO UPDATE — обновляет price, updated_at
- ON CONFLICT (url) DO NOTHING — не дублирует URL

### Магазины (43 шт.)

- **Online** — `moba.ru` без `?cid=`, outlet `moba-online`, полный каталог
- **Москва** — 5 точек (moba.ru + cid)
- **Московская область** — 5 точек (lyubercy, mytishhi, orekhovo-zuevo, reutov, noginsk)
- **Санкт-Петербург** — 3 точки
- **Регионы** — 30 точек (Новосибирск, Красноярск, Казань и др.)

Каждый городской магазин использует субдомен (`kazan.moba.ru`) + `?cid=` для привязки к точке.

## Файлы

```
SHOPS/Moba/
├── moba_multicity_parser.py   # ОСНОВНОЙ парсер (Playwright, multi-store)
├── moba_diag.py               # Диагностика direct vs proxy
├── moba_data/                 # JSON результаты парсинга
│
├── [LEGACY — не используются]
├── moba_parser.py             # Старый парсер (curl_cffi + cookies)
├── moba_playwright_parser.py  # Старый Playwright парсер (single-store)
├── moba_full_parser.py        # Старый полный парсер
├── write_to_db.py             # Старый batch DB writer
├── auto_cookies.py            # Старый cookie capture
├── run_with_cookies.py        # Старый wrapper
├── capture_moba.py            # Frida + Android
├── cdp_browser.py             # Chrome DevTools Protocol
├── get_cookies_*.py           # Различные методы захвата cookies
└── test_*.py                  # Тесты доступа
```

## Деплой

```bash
scp moba_multicity_parser.py root@213.108.170.194:/mnt/projects/repos/ZipMobile/SHOPS/Moba/
```

## Известные проблемы

1. **Datacenter IP = урезанный каталог** — moba.ru определяет datacenter по AS/IP range, отдаёт 14-30% товаров. Только домашний IP (homelab) даёт полный каталог.
2. **Сервер может ребутнуться** — /tmp очищается. Использовать systemd-run или screen для запуска.
3. **Один прокси на много потоков** — proxy-service quick-test убивает прокси при массовых запросах. Использовать `--proxies` для фиксированного назначения.
