#!/usr/bin/env python3
"""
Moba.ru Multi-Store Parser — parallel Playwright + proxy rotation.

Parses 42 physical stores across 30+ cities using ?cid=XXXXX parameter.
Each store has its own product availability.
Each browser uses its own SOCKS5 proxy from proxy-service (port 8110).
Auto-rotates proxy on failure. Telegram notifications.

Requirements:
    pip install playwright beautifulsoup4 httpx
    playwright install chromium

Usage:
    python moba_multicity_parser.py                     # all stores, save to DB
    python moba_multicity_parser.py --no-db             # JSON only
    python moba_multicity_parser.py --stores 3          # first 3 stores only
    python moba_multicity_parser.py --city Москва       # only Moscow stores
    python moba_multicity_parser.py --parallel 10       # 10 browsers (default)
    python moba_multicity_parser.py --list              # list stores and exit
    python moba_multicity_parser.py --no-proxy          # without proxy (direct)
    python moba_multicity_parser.py --no-tg             # without Telegram
"""
import asyncio
import json
import re
import os
import sys
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("moba_multi")

# Подавить спам от httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

# ─── config ───────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent / "moba_data"
BASE_DOMAIN = "moba.ru"

PROXY_SERVICE_URL = os.environ.get("PROXY_SERVICE_URL", "http://localhost:8110")
MAX_PROXY_RETRIES = 5          # макс попыток смены прокси на одну точку
REQUEST_DELAY_PROXY = 0.5      # задержка между страницами (прокси)
REQUEST_DELAY_DIRECT = 1.5     # задержка между страницами (прямое)
STORE_DELAY = 3                # задержка между запуском магазинов
MAX_PAGES = 200

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8212954323:AAHW3wdM1z76pLC7RhUZbjd4b2OAfXJU7Kc")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6416413182")

# DB
TABLE_NOMENCLATURE = "moba_nomenclature"
TABLE_PRODUCT_URLS = "moba_product_urls"
TABLE_OUTLETS = "zip_outlets"

# Все торговые точки Moba.ru
# Format: (subdomain, cid, store_name, city)
STORES = [
    # Online (без cid — полный каталог)
    ("moba.ru", "", "Online", "Москва"),
    # Москва — 5 магазинов
    ("moba.ru", "9705", "Митино", "Москва"),
    ("moba.ru", "12352", "Новые Черёмушки", "Москва"),
    ("moba.ru", "9703", "Пражская", "Москва"),
    ("moba.ru", "9704", "Савёлово", "Москва"),
    ("moba.ru", "9706", "Сити", "Москва"),
    # Московская область — 5 точек
    ("lyubercy.moba.ru", "41999", "ТЦ Феникс", "Люберцы"),
    ("mytishhi.moba.ru", "14244", "Артимолл", "Мытищи"),
    ("orekhovo-zuevo.moba.ru", "16048", "Орехово-Зуево", "Орехово-Зуево"),
    ("reutov.moba.ru", "182882", "Экватор", "Реутов"),
    ("noginsk.moba.ru", "15534", "Соборная, 12", "Ногинск"),
    # Санкт-Петербург — 3 магазина
    ("sankt-peterburg.moba.ru", "37987", "Просвещения, 23А", "Санкт-Петербург"),
    ("sankt-peterburg.moba.ru", "9701", "Садовая", "Санкт-Петербург"),
    ("sankt-peterburg.moba.ru", "9700", "Юнона", "Санкт-Петербург"),
    # Новосибирск — 3 магазина
    ("novosibirsk.moba.ru", "11815", "Блюхера, 20", "Новосибирск"),
    ("novosibirsk.moba.ru", "9702", "Мичурина, 12А", "Новосибирск"),
    ("novosibirsk.moba.ru", "9707", "Мичурина, 10/1", "Новосибирск"),
    # Красноярск — 2 магазина
    ("krasnoyarsk.moba.ru", "17740", "Взлетная, 2", "Красноярск"),
    ("krasnoyarsk.moba.ru", "256", "Радиорынок", "Красноярск"),
    # Казань
    ("kazan.moba.ru", "27508", "ТОК Караван", "Казань"),
    # Краснодар
    ("krasnodar.moba.ru", "16423", "Коммунаров, 96", "Краснодар"),
    # Владивосток
    ("vladivostok.moba.ru", "57147", "Луговая, 21", "Владивосток"),
    # Хабаровск
    ("khabarovsk.moba.ru", "142480", "Льва Толстого, 15", "Хабаровск"),
    # Омск
    ("omsk.moba.ru", "14411", "Карла Маркса, 29", "Омск"),
    # Барнаул
    ("barnaul.moba.ru", "37791", "Строителей, 16", "Барнаул"),
    # Воронеж
    ("voronezh.moba.ru", "42515", "Никитинская, 36", "Воронеж"),
    # Нижний Новгород
    ("nizhniy-novgorod.moba.ru", "14541", "Мурашкинская, 7", "Нижний Новгород"),
    # Самара
    ("samara.moba.ru", "156114", "Победы, 105", "Самара"),
    # Уфа
    ("ufa.moba.ru", "62790", "Революционная, 99", "Уфа"),
    # Тула
    ("tula.moba.ru", "15367", "ТЦ УтюгЪ", "Тула"),
    # Тюмень
    ("tyumen.moba.ru", "61746", "Герцена, 86А", "Тюмень"),
    # Сургут
    ("surgut.moba.ru", "13888", "Дзержинского, 6", "Сургут"),
    # Иркутск
    ("irkutsk.moba.ru", "17858", "Фурье, 16", "Иркутск"),
    # Калуга
    ("kaluga.moba.ru", "38423", "Суворова, 154, корп. 1", "Калуга"),
    # Кемерово
    ("kemerovo.moba.ru", "161607", "Ленина, 28", "Кемерово"),
    # Нижневартовск
    ("nizhnevartovsk.moba.ru", "8504", "Омская, 24", "Нижневартовск"),
    # Петрозаводск
    ("petrozavodsk.moba.ru", "14615", "Гоголя, 29", "Петрозаводск"),
    # Анапа
    ("anapa.moba.ru", "12191", "Астраханская, 76/9", "Анапа"),
    # Архангельск
    ("arhangelsk.moba.ru", "39249", "Алмаз", "Архангельск"),
    # Брянск
    ("bryansk.moba.ru", "15368", "3 Интернационала, 17А", "Брянск"),
    # Владимир
    ("vladimir.moba.ru", "15351", "850-летия, 5", "Владимир"),
    # Вологда
    ("vologda.moba.ru", "16689", "Ярославская, 25", "Вологда"),
    # Ярославль
    ("yaroslavl.moba.ru", "166426", "ТЦ Лабиринт", "Ярославль"),
]

# Фиксированный список категорий для парсинга
ROOT_CATEGORIES = [
    {"url": "/catalog/displei/", "name": "Дисплеи"},
    {"url": "/catalog/akkumulyatory-1/", "name": "Аккумуляторы"},
    {"url": "/catalog/korpusa-zadnie-kryshki/", "name": "Корпуса, задние крышки"},
    {"url": "/catalog/zapchasti/", "name": "Запчасти"},
    {"url": "/catalog/zapchasti-dlya-igrovykh-pristavok/", "name": "Запчасти для игровых приставок"},
    {"url": "/catalog/dlya-noutbukov/", "name": "Для ноутбуков"},
    {"url": "/catalog/korpusnye-chasti-ramki-skotch-stilusy-tolkateli-i-t-p/", "name": "Корпусные части, рамки, скотч, стилусы"},
    {"url": "/catalog/mikroskhemy-kontrollery-usiliteli-i-t-p/", "name": "Микросхемы, контроллеры, усилители"},
    {"url": "/catalog/stekla-plenki-oca-polyarizatory-i-t-p-dlya-displeynykh-moduley/", "name": "Стёкла, плёнки, OCA, поляризаторы"},
    {"url": "/catalog/shleyfy-platy/", "name": "Шлейфы, платы"},
]


# ─── ProxyClient ─────────────────────────────────────────────────────

class ProxyClient:
    """Клиент к proxy-service для получения/ротации SOCKS5 прокси."""

    def __init__(self, base_url: str = PROXY_SERVICE_URL):
        self.base_url = base_url.rstrip("/")
        self.current_proxy = None

    def get_proxy(self, for_site: str = "moba", protocol: str = "socks5", country: str = None) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/proxy/get?protocol={protocol}&for_site={for_site}"
            if country:
                url += f"&country={country}"
            response = httpx.get(url, timeout=15)
            if response.status_code == 200:
                self.current_proxy = response.json()
                return self.current_proxy
            elif response.status_code == 404:
                log.warning("[PROXY] Нет рабочих SOCKS5 прокси в пуле")
                return None
            else:
                log.warning("[PROXY] Ошибка: %d", response.status_code)
                return None
        except Exception as e:
            log.error("[PROXY] Исключение: %s", e)
            return None

    def report_success(self, response_time: float = None):
        if not self.current_proxy:
            return
        self._report(success=True, response_time=response_time)

    def report_failure(self, banned: bool = False):
        if not self.current_proxy:
            return
        self._report(success=False, banned_site="moba" if banned else None)

    def _report(self, success: bool, response_time: float = None, banned_site: str = None):
        try:
            payload = {
                "host": self.current_proxy["host"],
                "port": self.current_proxy["port"],
                "success": success,
            }
            if response_time is not None:
                payload["response_time"] = response_time
            if banned_site:
                payload["banned_site"] = banned_site
            httpx.post(f"{self.base_url}/proxy/report", json=payload, timeout=5)
        except Exception:
            pass

    @property
    def proxy_url(self) -> Optional[str]:
        if not self.current_proxy:
            return None
        p = self.current_proxy
        return f"socks5://{p['host']}:{p['port']}"

    def get_stats(self) -> Optional[Dict]:
        try:
            response = httpx.get(f"{self.base_url}/proxy/stats", timeout=5)
            return response.json() if response.status_code == 200 else None
        except Exception:
            return None


# ─── Telegram ─────────────────────────────────────────────────────────

class TelegramNotifier:
    """Отправка уведомлений в Telegram для парсера Moba."""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.enabled = bool(self.bot_token and self.chat_id)

    def send(self, message: str) -> bool:
        if not self.enabled:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            response = httpx.post(url, json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }, timeout=10)
            return response.status_code == 200
        except Exception as e:
            log.error("[TG] %s", e)
            return False

    def notify_start(self, stores_count: int, parallel: int, use_proxy: bool):
        self.send(
            f"\U0001F680 <b>Парсер Moba.ru запущен</b>\n\n"
            f"\U0001F3EA Точек: {stores_count}\n"
            f"\U0001F5A5\uFE0F Параллельно: {parallel} браузеров\n"
            f"\U0001F310 Прокси: {'SOCKS5 (proxy-service)' if use_proxy else 'direct'}\n"
            f"\u23F0 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def notify_store_done(self, label: str, products: int, stores_done: int, stores_total: int):
        self.send(
            f"\u2705 <b>{label}</b>: {products} товаров\n"
            f"\U0001F4CA Прогресс: {stores_done}/{stores_total}"
        )

    def notify_proxy_switch(self, label: str, old_proxy: str, new_proxy: str, reason: str):
        self.send(
            f"\U0001F504 <b>Смена прокси</b> [{label}]\n\n"
            f"\U0001F6AB Старый: <code>{old_proxy}</code>\n"
            f"\u2705 Новый: <code>{new_proxy}</code>\n"
            f"\U0001F4DD Причина: {reason}\n"
            f"\u23F0 {datetime.now().strftime('%H:%M:%S')}"
        )

    def notify_error(self, label: str, error: str):
        self.send(
            f"\u274C <b>Ошибка</b> [{label}]\n\n"
            f"\U0001F4DD {str(error)[:300]}\n"
            f"\u23F0 {datetime.now().strftime('%H:%M:%S')}"
        )

    def notify_complete(self, total_products: int, stores_done: int,
                        stores_failed: int, duration_minutes: int):
        hours = duration_minutes // 60
        mins = duration_minutes % 60
        self.send(
            f"\u2705 <b>ПАРСИНГ MOBA ЗАВЕРШЁН</b>\n\n"
            f"\U0001F4CA <b>Итого:</b>\n"
            f"\u2022 Товаров: <b>{total_products}</b>\n"
            f"\u2022 Точек: <b>{stores_done}</b> OK, {stores_failed} ошибок\n"
            f"\u23F1 Время: {hours}ч {mins}м\n\n"
            f"\u23F0 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )


# ─── parsing ──────────────────────────────────────────────────────────

def parse_products_from_html(html: str) -> List[Dict]:
    """Extract product articles and basic info from a catalog page."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("tr.item.main_item_wrapper")
    if not items:
        for sel in ["div.catalog-item", "div.item-card", "div.product-item"]:
            items = soup.select(sel)
            if items:
                break

    products = []
    for item in items:
        try:
            for a in item.find_all("a", href=True):
                href = a.get("href", "")
                if href.startswith("/catalog/") and href.count("/") >= 3:
                    text = a.get_text(strip=True)
                    if text and len(text) > 5:
                        parts = href.rstrip("/").split("/")
                        pid = parts[-1] if parts[-1].isdigit() else None
                        if pid:
                            price_el = item.select_one(".cost") or item.find(class_="price")
                            price = 0.0
                            if price_el:
                                m = re.search(r"([\d\s]+)", price_el.get_text(strip=True).replace("\xa0", " "))
                                if m:
                                    try:
                                        price = float(m.group(1).replace(" ", "").strip())
                                    except ValueError:
                                        pass
                            products.append({
                                "article": f"MOBA-{pid}",
                                "name": text[:200],
                                "price": price,
                                "url": href,
                            })
                        break
        except Exception:
            continue

    return products


def has_next_page(html: str, current_page: int) -> bool:
    """Check if there's a next page in pagination."""
    soup = BeautifulSoup(html, "html.parser")
    next_link = (
        soup.find("a", class_="flex-next")
        or soup.find("a", class_="next")
        or soup.find("a", {"rel": "next"})
    )
    if next_link:
        return True
    pagen = soup.find_all("a", href=lambda h: h and f"PAGEN_1={current_page+1}" in h)
    return bool(pagen)


# ─── Playwright helpers ──────────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
SUCCESS_INDICATORS = ["каталог", "catalog", "main_item_wrapper", "корзин"]

BROWSER_ARGS = [
    "--no-sandbox", "--disable-dev-shm-usage", "--lang=ru-RU,ru",
    "--disable-blink-features=AutomationControlled",
    "--ignore-certificate-errors",
    "--disable-gpu",
]


async def _launch_browser(pw_instance, proxy_url: Optional[str] = None):
    """Launch browser with optional SOCKS5 proxy."""
    kwargs = {"headless": True, "args": BROWSER_ARGS}
    if proxy_url:
        kwargs["proxy"] = {"server": proxy_url}
    return await pw_instance.chromium.launch(**kwargs)


async def _make_context(browser, subdomain: str, cookies: Optional[Dict[str, str]] = None):
    """Create a browser context with anti-detection and resource blocking."""
    ctx = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        user_agent=USER_AGENT,
        ignore_https_errors=True,
    )
    if cookies:
        pw_cookies = [{"name": k, "value": v, "domain": subdomain, "path": "/"}
                      for k, v in cookies.items()]
        await ctx.add_cookies(pw_cookies)
    return ctx


async def _make_page(ctx):
    """Create page with anti-detection + resource blocking."""
    page = await ctx.new_page()
    await page.add_init_script(
        'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    )
    await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,webp,woff,woff2,ttf,eot}",
                      lambda route: route.abort())
    await page.route("**/{analytics,metrika,mc.yandex,google-analytics}**",
                      lambda route: route.abort())
    return page


async def _pass_smartcaptcha(page, subdomain: str, label: str) -> bool:
    """Navigate to moba.ru and wait for SmartCaptcha. Returns True on success."""
    base = f"https://{subdomain}"
    try:
        await page.goto(base, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(7000)
    except Exception as e:
        log.error("[%s] SmartCaptcha goto failed: %s", label, str(e)[:100])
        return False

    for wait_round in range(6):
        html = await page.content()
        if any(s in html.lower() for s in SUCCESS_INDICATORS):
            return True
        if wait_round < 5:
            await page.wait_for_timeout(5000)

    log.warning("[%s] SmartCaptcha не пройдена", label)
    return False


# ─── store parser ────────────────────────────────────────────────────

async def parse_store(
    subdomain: str,
    cid: str,
    store_name: str,
    city: str,
    sem: asyncio.Semaphore,
    pw_instance,
    use_proxy: bool = True,
    notifier: TelegramNotifier = None,
    stats: dict = None,
    stagger_delay: float = 0,
    fixed_proxy: str = None,
) -> Tuple[str, str, str, str, List[Dict]]:
    """
    Parse one physical store.
    Uses ONE browser: SmartCaptcha → parse categories in same context.
    With proxy: auto-rotates on failure (or uses fixed_proxy if provided).
    Returns (subdomain, cid, store_name, city, products).
    """
    label = f"{city}/{store_name}"
    page_delay = REQUEST_DELAY_PROXY if use_proxy else REQUEST_DELAY_DIRECT

    # Stagger start to avoid all stores hitting at once
    if stagger_delay > 0:
        await asyncio.sleep(stagger_delay)

    async with sem:
        base = f"https://{subdomain}"
        all_products = []
        seen_articles = set()
        categories_done = 0

        proxy_client = ProxyClient() if (use_proxy and not fixed_proxy) else None
        max_attempts = MAX_PROXY_RETRIES if use_proxy else 2  # 2 attempts for direct

        for attempt in range(max_attempts):
            # ── получить прокси ──
            proxy_url = None
            if fixed_proxy:
                proxy_url = fixed_proxy
                if attempt == 0:
                    log.info("[%s] Прокси: %s (fixed, попытка %d)", label, proxy_url, attempt + 1)
                else:
                    log.info("[%s] Прокси: %s (fixed, retry %d)", label, proxy_url, attempt + 1)
                    await asyncio.sleep(10)
            elif proxy_client:
                old_proxy = proxy_client.proxy_url
                proxy = proxy_client.get_proxy(for_site="moba", country="RU")
                if not proxy:
                    log.error("[%s] Нет прокси (попытка %d/%d)",
                              label, attempt + 1, max_attempts)
                    await asyncio.sleep(30)
                    continue
                proxy_url = proxy_client.proxy_url
                log.info("[%s] Прокси: %s (попытка %d)", label, proxy_url, attempt + 1)

                if notifier and attempt > 0 and old_proxy:
                    notifier.notify_proxy_switch(label, old_proxy, proxy_url,
                                                 "connection failed / ban")
            else:
                if attempt > 0:
                    log.info("[%s] Повторная попытка %d", label, attempt + 1)
                    await asyncio.sleep(10)

            # ── Один браузер: SmartCaptcha → парсинг ──
            browser = None
            try:
                browser = await _launch_browser(pw_instance, proxy_url)
                ctx = await _make_context(browser, subdomain)
                page = await _make_page(ctx)

                # SmartCaptcha
                if not await _pass_smartcaptcha(page, subdomain, label):
                    if proxy_client:
                        proxy_client.report_failure(banned=True)
                    continue

                cookies = await ctx.cookies()
                log.info("[%s] SmartCaptcha OK, %d cookies, парсинг %d categories, cid=%s",
                         label, len(cookies), len(ROOT_CATEGORIES) - categories_done, cid)

                # ── Парсинг категорий в том же браузере ──
                proxy_failed = False
                consecutive_empty = 0

                for ci in range(categories_done, len(ROOT_CATEGORIES)):
                    cat = ROOT_CATEGORIES[ci]
                    cat_count = 0

                    for page_num in range(1, MAX_PAGES + 1):
                        url = f"{base}{cat['url']}"
                        if cid:
                            url += f"?cid={cid}"
                        if page_num > 1:
                            url += ("&" if cid else "?") + f"PAGEN_1={page_num}"

                        try:
                            await page.goto(url, wait_until="commit", timeout=60_000)
                            await page.wait_for_timeout(2000)
                            html = await page.content()
                        except Exception as e:
                            err_str = str(e)[:100]
                            log.warning("[%s] Page failed: %s", label, err_str)
                            proxy_failed = True
                            break

                        prods = parse_products_from_html(html)
                        if not prods:
                            break

                        for p in prods:
                            if p["article"] not in seen_articles:
                                seen_articles.add(p["article"])
                                p["category"] = cat["name"]
                                all_products.append(p)
                                cat_count += 1

                        if not has_next_page(html, page_num):
                            break

                        await asyncio.sleep(page_delay)

                    categories_done = ci + 1

                    if cat_count > 0:
                        consecutive_empty = 0
                    else:
                        consecutive_empty += 1

                    log.info("[%s] cat %d/%d '%s': +%d (total: %d)",
                             label, ci + 1, len(ROOT_CATEGORIES), cat["name"],
                             cat_count, len(all_products))

                    if proxy_failed:
                        break

                    # Ban detection: 3 empty categories only meaningful with proxy
                    if consecutive_empty >= 3 and use_proxy:
                        log.warning("[%s] 3 empty categories — proxy banned", label)
                        proxy_failed = True
                        if proxy_client:
                            proxy_client.report_failure(banned=True)
                        break

                if not proxy_failed:
                    if proxy_client:
                        proxy_client.report_success()
                    break  # all done
                else:
                    if proxy_client:
                        proxy_client.report_failure(banned=False)
                    log.info("[%s] Switching proxy, parsed %d so far ...",
                             label, len(all_products))

            except Exception as e:
                log.error("[%s] Browser crash: %s", label, str(e)[:200])
                if proxy_client:
                    proxy_client.report_failure(banned=False)
            finally:
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass

        log.info("[%s] DONE: %d products", label, len(all_products))

        # Обновить общую статистику
        if stats is not None:
            stats["stores_done"] += 1
            stats["total_products"] += len(all_products)
            if not all_products:
                stats["stores_failed"] += 1

        if notifier and stats:
            notifier.notify_store_done(label, len(all_products),
                                       stats["stores_done"], stats["stores_total"])

        return (subdomain, cid, store_name, city, all_products)


# ─── DB functions ─────────────────────────────────────────────────────

def save_store_to_db(subdomain: str, cid: str, store_name: str, city: str, products: List[Dict]):
    """Save store products to DB v10 — nomenclature (with price) + product_urls (per-store outlet)."""
    try:
        from db_wrapper import get_db
    except ImportError:
        log.error("Cannot import db_wrapper")
        return

    outlet_code = f"moba-{cid}" if cid else "moba-online"
    outlet_name = f"Moba.ru {city}, {store_name}" if cid else "Moba.ru Online"
    label = f"{city}/{store_name}"

    conn = get_db()
    if not conn:
        return
    cur = conn.cursor()

    try:
        # Ensure outlet
        cur.execute(f"""
            INSERT INTO {TABLE_OUTLETS} (code, city, name, is_active)
            VALUES (%s, %s, %s, true)
            ON CONFLICT (code) DO UPDATE SET city = EXCLUDED.city, name = EXCLUDED.name
        """, (outlet_code, city, outlet_name))
        conn.commit()

        cur.execute(f"SELECT id FROM {TABLE_OUTLETS} WHERE code = %s", (outlet_code,))
        outlet_id = cur.fetchone()[0]

        count = 0
        BATCH = 500
        for i, p in enumerate(products):
            article = p.get("article", "").strip()
            if not article:
                continue

            price = p.get("price", 0)

            cur.execute(f"""
                INSERT INTO {TABLE_NOMENCLATURE} (name, article, category, price, first_seen_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (article) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    updated_at = NOW()
                RETURNING id
            """, (p.get("name", ""), article, p.get("category"), price))
            row = cur.fetchone()

            nom_id = row[0]
            url = p.get("url", "")
            if url and not url.startswith("http"):
                url = f"https://{subdomain}{url}"

            if url:
                cur.execute(f"""
                    INSERT INTO {TABLE_PRODUCT_URLS} (nomenclature_id, outlet_id, url, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (url) DO NOTHING
                """, (nom_id, outlet_id, url))
            count += 1

            if (i + 1) % BATCH == 0:
                conn.commit()
                log.info("[%s] DB: %d/%d written", label, i + 1, len(products))

        conn.commit()
        log.info("[%s] DB: %d records saved (outlet=%s)", label, count, outlet_code)

    except Exception as e:
        log.error("[%s] DB error: %s", label, e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# ─── main ─────────────────────────────────────────────────────────────

async def amain():
    ap = argparse.ArgumentParser(description="Moba.ru multi-store parser with proxy rotation")
    ap.add_argument("--no-db", action="store_true", help="JSON only, no DB")
    ap.add_argument("--stores", type=int, default=None, help="Limit stores count")
    ap.add_argument("--parallel", "-j", type=int, default=None, help="Parallel browsers (default: 2 direct, 5 proxy)")
    ap.add_argument("--list", action="store_true", help="List stores and exit")
    ap.add_argument("--skip-moscow", action="store_true", help="Skip moba.ru subdomain stores")
    ap.add_argument("--city", type=str, default=None, help="Filter by city name")
    ap.add_argument("--no-proxy", action="store_true", help="Direct connection (no proxy)")
    ap.add_argument("--proxies", type=str, default=None, help="Fixed proxies (comma-separated socks5://ip:port), distributed round-robin")
    ap.add_argument("--no-tg", action="store_true", help="Disable Telegram notifications")
    args = ap.parse_args()

    stores = STORES[:]
    if args.skip_moscow:
        stores = [s for s in stores if s[0] != "moba.ru"]
    if args.city:
        stores = [s for s in stores if args.city.lower() in s[3].lower()]
    if args.stores:
        stores = stores[:args.stores]

    if args.list:
        for i, (sub, cid, name, city) in enumerate(stores, 1):
            print(f"{i:3d}. {city:20s} {name:25s} cid={cid:8s} https://{sub}/")
        print(f"\nTotal: {len(stores)} stores")
        return

    # ── Режим прокси ──
    fixed_proxies = None
    if args.proxies:
        fixed_proxies = [p.strip() for p in args.proxies.split(",") if p.strip()]
        use_proxy = True
        parallel = args.parallel or (5 * len(fixed_proxies))
        log.info("[PROXY] Fixed proxies (%d): %s", len(fixed_proxies), fixed_proxies)
    else:
        use_proxy = not args.no_proxy
        parallel = args.parallel or (5 if use_proxy else 2)

    # ── Проверить proxy-service ──
    if use_proxy and not fixed_proxies:
        pc = ProxyClient()
        stats = pc.get_stats()
        if stats:
            log.info("[PROXY] proxy-service OK: %s", stats)
        else:
            log.error("[PROXY] proxy-service недоступен на %s!", PROXY_SERVICE_URL)
            log.error("[PROXY] Запустите с --no-proxy для прямого подключения")
            return

    # ── Telegram ──
    notifier = TelegramNotifier() if not args.no_tg else None
    if notifier:
        notifier.notify_start(len(stores), parallel, use_proxy)

    # ── Статистика ──
    shared_stats = {
        "stores_done": 0,
        "stores_failed": 0,
        "stores_total": len(stores),
        "total_products": 0,
        "start_time": datetime.now(),
    }

    log.info("Parsing %d stores with %d parallel browsers (proxy=%s)",
             len(stores), parallel, "ON" if use_proxy else "OFF")

    sem = asyncio.Semaphore(parallel)

    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        tasks = [
            parse_store(sub, cid, name, city, sem, pw,
                        use_proxy=use_proxy, notifier=notifier, stats=shared_stats,
                        stagger_delay=i * STORE_DELAY,
                        fixed_proxy=fixed_proxies[i % len(fixed_proxies)] if fixed_proxies else None)
            for i, (sub, cid, name, city) in enumerate(stores)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # ── Обработка результатов ──
    DATA_DIR.mkdir(exist_ok=True)
    all_results = {}
    total_products = 0
    stores_failed = 0

    for r in results:
        if isinstance(r, Exception):
            log.error("Task exception: %s", r)
            stores_failed += 1
            continue
        subdomain, cid, store_name, city, products = r
        label = f"{city}/{store_name}"
        all_results[label] = {
            "cid": cid,
            "subdomain": subdomain,
            "products": len(products),
        }
        total_products += len(products)
        if not products:
            stores_failed += 1

        if products:
            fname = DATA_DIR / f"moba_cid{cid}_{datetime.now().strftime('%Y%m%d')}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump({
                    "city": city,
                    "store_name": store_name,
                    "cid": cid,
                    "subdomain": subdomain,
                    "date": datetime.now().isoformat(),
                    "total": len(products),
                    "products": products,
                }, f, ensure_ascii=False, indent=2)

            if not args.no_db:
                save_store_to_db(subdomain, cid, store_name, city, products)

    # ── Summary ──
    duration = int((datetime.now() - shared_stats["start_time"]).total_seconds() / 60)
    log.info("\n=== SUMMARY ===")
    for label, info in sorted(all_results.items()):
        log.info("  %s (cid=%s): %d products", label, info["cid"], info["products"])
    log.info("Total: %d products across %d stores (%d failed), %d min",
             total_products, len(all_results), stores_failed, duration)

    # ── Telegram: завершение ──
    if notifier:
        notifier.notify_complete(total_products, len(all_results) - stores_failed,
                                 stores_failed, duration)


if __name__ == "__main__":
    asyncio.run(amain())
