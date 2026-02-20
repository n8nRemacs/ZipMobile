"""
Парсер GreenSpark.ru v4 — proxy-service + Homelab DB + staging
Обновлено: 2026-02-19

Изменения от v3:
- IPRotator + SSH-туннели → ProxyClient (HTTP к proxy-service)
- db_greenspark на 85.198.98.104 → Homelab PostgreSQL localhost:5433
- save_products_incremental → save_staging + process_staging (TZ-005/006)
- Мгновенная смена прокси при бане (пул ~5000 IP)
- CookieManager — Playwright + Xvfb локально на Homelab
"""

import httpx
import json
import time
import os
import re
import sys
import argparse
import psycopg2
import subprocess
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlencode, unquote

# Отключаем буферизацию stdout для немедленного вывода в nohup логи
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from config import (
    BASE_URL, API_URL, PRODUCTS_ENDPOINT,
    ROOT_CATEGORY, REQUEST_DELAY, REQUEST_TIMEOUT, PER_PAGE,
    DEFAULT_SHOP_ID, DATA_DIR,
    PRODUCTS_JSON, PRODUCTS_XLSX, ERRORS_LOG, CATEGORIES_JSON
)

# Telegram уведомления
try:
    from telegram_notifier import TelegramNotifier, get_notifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[WARN] telegram_notifier не найден")

# === Конфигурация БД (Homelab PostgreSQL) ===
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5433))
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mi31415926pSss!")

# === Proxy-service ===
PROXY_SERVICE_URL = os.environ.get("PROXY_SERVICE_URL", "http://localhost:8110")

# Файл с cookies
COOKIES_FILE = "cookies.json"

# Файл со списком торговых точек (заменяет greenspark_cities.json)
_SHOPS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "greenspark_shops.json")

# Инкрементальное сохранение
SAVE_EVERY_N_PRODUCTS = 200

# Ротация прокси
MAX_PROXY_RETRIES = 3
PROXY_WAIT_SECONDS = 300  # 5 мин ожидания если нет прокси


def get_db():
    """Подключение к Homelab PostgreSQL"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


# ============================================================
# ProxyClient — HTTP-клиент к proxy-service
# ============================================================

class ProxyClient:
    """Клиент к proxy-service для получения/ротации прокси"""

    def __init__(self, base_url: str = PROXY_SERVICE_URL, protocol: str = "http"):
        self.base_url = base_url.rstrip("/")
        self.protocol = protocol
        self.current_proxy = None  # {"host": ..., "port": ..., "protocol": ..., "cookies": ...}

    def get_proxy(self, for_site: str = "greenspark") -> Optional[Dict]:
        """Получить рабочий прокси от proxy-service"""
        try:
            url = f"{self.base_url}/proxy/get?protocol={self.protocol}&for_site={for_site}"
            response = httpx.get(url, timeout=15)
            if response.status_code == 200:
                self.current_proxy = response.json()
                return self.current_proxy
            elif response.status_code == 404:
                print("[PROXY] Нет рабочих прокси в пуле")
                return None
            else:
                print(f"[PROXY] Ошибка: {response.status_code}")
                return None
        except Exception as e:
            print(f"[PROXY] Исключение при получении прокси: {e}")
            return None

    def report_success(self, response_time: float = None):
        """Сообщить proxy-service об успешном использовании"""
        if not self.current_proxy:
            return
        self._report(success=True, response_time=response_time)

    def report_failure(self, banned: bool = False):
        """Сообщить proxy-service о неудаче (опционально — бан на сайте)"""
        if not self.current_proxy:
            return
        self._report(success=False, banned_site="greenspark" if banned else None)

    def _report(self, success: bool, response_time: float = None, banned_site: str = None):
        """Отправить отчёт в proxy-service"""
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
        except Exception as e:
            print(f"[PROXY] Ошибка отчёта: {e}")

    @property
    def proxy_url(self) -> Optional[str]:
        """URL прокси для httpx.Client"""
        if not self.current_proxy:
            return None
        p = self.current_proxy
        proto = p.get("protocol", self.protocol)
        return f"{proto}://{p['host']}:{p['port']}"

    @property
    def cookies(self) -> Optional[dict]:
        """Cookies из последнего ответа proxy-service (или None если не вернул)"""
        if not self.current_proxy:
            return None
        return self.current_proxy.get("cookies")

    def get_stats(self) -> Optional[Dict]:
        """Получить статистику proxy-service"""
        try:
            response = httpx.get(f"{self.base_url}/proxy/stats", timeout=5)
            return response.json() if response.status_code == 200 else None
        except:
            return None


# ============================================================
# CookieManager — Playwright + Xvfb локально
# ============================================================

class CookieManager:
    """Получение cookies через Playwright + Xvfb на Homelab.
    Поддерживает получение cookies через прокси (SOCKS5) чтобы
    IP cookies совпадал с IP запросов.
    """

    def __init__(self, shop_id: str = str(DEFAULT_SHOP_ID)):
        self.shop_id = shop_id

    def get_cookies(self, proxy_url: str = None) -> Optional[dict]:
        """Получить cookies через xvfb-run + Playwright.
        proxy_url — socks5://host:port для Playwright browser launch.
        """
        proxy_info = f" через {proxy_url}" if proxy_url else " (direct)"
        print(f"[COOKIES] Получение cookies (shop_id={self.shop_id}){proxy_info}...")

        # Формируем proxy-аргумент для Playwright
        if proxy_url:
            proxy_arg = f"proxy={{'server': '{proxy_url}'}}"
        else:
            proxy_arg = ""

        cookie_script = f'''
import asyncio
from playwright.async_api import async_playwright
import json

SHOP_ID = "{self.shop_id}"

async def get_cookies():
    async with async_playwright() as p:
        launch_args = {{
            'headless': False,
            'args': ['--disable-blink-features=AutomationControlled', '--no-sandbox',
                     '--ignore-certificate-errors'],
        }}
        {"launch_args['proxy'] = {'server': '" + proxy_url + "'}" if proxy_url else ""}
        browser = await p.chromium.launch(**launch_args)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
            viewport={{'width': 1920, 'height': 1080}},
            locale='ru-RU',
            ignore_https_errors=True,
        )
        await context.add_cookies([
            {{'name': 'magazine', 'value': SHOP_ID, 'domain': 'green-spark.ru', 'path': '/'}},
            {{'name': 'global_magazine', 'value': SHOP_ID, 'domain': 'green-spark.ru', 'path': '/'}},
        ])
        page = await context.new_page()
        await page.add_init_script('Object.defineProperty(navigator, "webdriver", {{get: () => undefined}})')
        try:
            await page.goto('https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/', wait_until='domcontentloaded', timeout=30000)
        except Exception as e:
            print(f'GOTO_ERROR:{{e}}')
        await page.wait_for_timeout(7000)
        try:
            await page.goto('https://green-spark.ru/local/api/catalog/products/?path[]=komplektuyushchie_dlya_remonta&perPage=10', wait_until='domcontentloaded', timeout=30000)
        except Exception as e:
            print(f'API_ERROR:{{e}}')
        await page.wait_for_timeout(3000)
        cookies = await context.cookies()
        cookies_dict = {{c['name']: c['value'] for c in cookies}}
        cookies_dict['magazine'] = SHOP_ID
        cookies_dict['global_magazine'] = SHOP_ID
        cookies_dict['catalog-per-page'] = '100'
        with open('cookies.json', 'w') as f:
            json.dump(cookies_dict, f, indent=2)
        print(f'OK:{{len(cookies_dict)}}')
        await browser.close()

asyncio.run(get_cookies())
'''
        local_script = "/tmp/get_cookies_gs_v4.py"
        with open(local_script, 'w') as f:
            f.write(cookie_script)

        try:
            cmd = f"xvfb-run --auto-servernum python3 {local_script}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120,
                                    cwd=os.path.dirname(os.path.abspath(__file__)))

            if 'OK:' in result.stdout:
                print(f"[COOKIES] Cookies получены успешно{proxy_info}")
                return self._load_cookies()
            else:
                stderr_short = result.stderr[:300] if result.stderr else ""
                stdout_short = result.stdout[:300] if result.stdout else ""
                print(f"[COOKIES] Ошибка: {stderr_short or stdout_short}")
                return None

        except subprocess.TimeoutExpired:
            print(f"[COOKIES] Таймаут xvfb-run (120 сек)")
            return None
        except Exception as e:
            print(f"[COOKIES] Исключение: {e}")
            return None

    def _load_cookies(self) -> Optional[dict]:
        """Загрузить cookies из файла"""
        cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), COOKIES_FILE)
        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            cookies.pop("__meta__", None)
            return cookies
        except Exception as e:
            print(f"[COOKIES] Ошибка загрузки: {e}")
            return None


# ============================================================
# GreenSparkParser — ядро парсинга (из v3, адаптировано)
# ============================================================

class GreenSparkParser:
    """Парсер каталога GreenSpark с proxy-service ротацией"""

    def __init__(self, proxy_client: ProxyClient = None, cookie_manager: CookieManager = None,
                 use_db: bool = True):
        self.proxy_client = proxy_client
        self.cookie_manager = cookie_manager
        self.client = None
        self.delay = REQUEST_DELAY
        self.last_request = 0
        self.products: List[Dict] = []
        self.categories: Dict[str, str] = {}
        self.errors: List[Dict] = []
        self.seen_ids: set = set()
        self.current_city: str = None
        self.current_city_id: int = None
        self.blocked = False
        self.use_db = use_db

        # Staging-буфер
        self.staging_buffer: List[Dict] = []
        self.total_staged = 0

        # Статистика
        self.stats = {
            "products_total": 0,
            "products_session": 0,
            "cities_done": 0,
            "cities_total": 0,
            "bans": 0,
            "proxy_switches": 0,
            "start_time": datetime.now(),
        }
        self._last_tg_notify = 0  # timestamp последнего TG уведомления о смене прокси

        # Telegram
        self.notifier = get_notifier() if TELEGRAM_AVAILABLE else None

        os.makedirs(DATA_DIR, exist_ok=True)

    def init_client(self, cookies: dict = None, proxy_url: str = None):
        """Инициализировать HTTP клиент с cookies и прокси"""
        if cookies is None:
            cookies = self._load_cookies()

        default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
        user_agent = unquote(cookies.get("__jua_", "")) or default_ua

        if self.client:
            self.client.close()

        # Получаем proxy_url из ProxyClient если не передан
        if proxy_url is None and self.proxy_client:
            proxy_url = self.proxy_client.proxy_url

        client_kwargs = {
            "timeout": REQUEST_TIMEOUT,
            "headers": {
                "User-Agent": user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            },
            "cookies": cookies,
            "follow_redirects": True,
        }

        if proxy_url:
            client_kwargs["proxy"] = proxy_url
            # SOCKS5 прокси могут вызывать SSL ошибки (self-signed cert)
            if "socks" in proxy_url:
                client_kwargs["verify"] = False
            print(f"[CLIENT] Используем прокси: {proxy_url}")
        else:
            print(f"[CLIENT] Без прокси (direct)")

        self.client = httpx.Client(**client_kwargs)
        self.blocked = False

    def _load_cookies(self) -> dict:
        """Загрузить cookies из файла"""
        cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), COOKIES_FILE)
        if os.path.exists(cookies_path):
            try:
                with open(cookies_path, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                cookies.pop("__meta__", None)
                print(f"Cookies загружены из {cookies_path}")
                return cookies
            except Exception as e:
                print(f"Ошибка загрузки cookies: {e}")

        return {
            "magazine": str(DEFAULT_SHOP_ID),
            "global_magazine": str(DEFAULT_SHOP_ID),
            "catalog-per-page": str(PER_PAGE),
        }

    def _rate_limit(self):
        """Ограничение частоты запросов"""
        elapsed = time.time() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request = time.time()

    def _switch_proxy(self, reason: str = "ban") -> bool:
        """Переключить прокси через proxy-service.
        При смене прокси получает новые cookies через Playwright + тот же прокси,
        чтобы IP сессии совпадал с IP запросов.
        """
        if not self.proxy_client:
            return False

        self.stats["bans"] += 1
        self.stats["proxy_switches"] += 1

        old_proxy = self.proxy_client.proxy_url or "direct"
        print(f"\n[BAN] Прокси {old_proxy} забанен: {reason}")

        # Сообщаем о бане
        self.proxy_client.report_failure(banned=True)

        # Получаем новый прокси
        for attempt in range(MAX_PROXY_RETRIES):
            new_proxy = self.proxy_client.get_proxy()
            if new_proxy:
                print(f"[PROXY] Новый прокси: {self.proxy_client.proxy_url}")

                # Telegram (не чаще раза в 60 секунд)
                if self.notifier and (time.time() - self._last_tg_notify) >= 60:
                    self.notifier.notify_ip_switch(
                        server_name="proxy-service",
                        old_ip=old_proxy,
                        new_ip=self.proxy_client.proxy_url,
                        reason=reason,
                        products_parsed=self.stats["products_session"],
                        total_products=self.stats["products_total"],
                    )
                    self._last_tg_notify = time.time()

                proxy_url = self.proxy_client.proxy_url

                # ВСЕГДА получаем свежие cookies через Playwright (proxy-service кэш ненадёжен)
                if self.cookie_manager and proxy_url and "socks" in proxy_url:
                    print(f"[COOKIES] Получаем свежие cookies через Playwright → {proxy_url}...")
                    new_cookies = self.cookie_manager.get_cookies(proxy_url=proxy_url)
                    if new_cookies:
                        self.init_client(new_cookies, proxy_url)
                        if self.current_city_id:
                            self.set_city(self.current_city_id, self.current_city)
                        self.stats["products_session"] = 0
                        return True
                    else:
                        print(f"[COOKIES] Не удалось получить cookies через прокси, пробуем следующий")
                        self.proxy_client.report_failure(banned=False)
                        continue
                else:
                    # HTTP прокси или нет cookie_manager — переиспользуем текущие cookies
                    cookies_dict = {}
                    if self.client:
                        for cookie in self.client.cookies.jar:
                            cookies_dict[cookie.name] = cookie.value
                    if not cookies_dict:
                        cookies_dict = self._load_cookies()

                    self.init_client(cookies_dict, proxy_url)
                    if self.current_city_id:
                        self.set_city(self.current_city_id, self.current_city)
                    self.stats["products_session"] = 0
                    return True

            print(f"[PROXY] Нет прокси (попытка {attempt + 1}/{MAX_PROXY_RETRIES}), ждём {PROXY_WAIT_SECONDS}с...")
            time.sleep(PROXY_WAIT_SECONDS)

        # Все попытки исчерпаны
        if self.notifier:
            self.notifier.notify_error(
                error="Нет доступных прокси после 3 попыток",
                server_name="proxy-service",
                total_products=self.stats["products_total"]
            )
        return False

    # === Загрузка городов ===

    def load_cities(self) -> List[Dict]:
        """Загрузить список городов"""
        cities_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "greenspark_cities.json")
        with open(cities_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_parsed_city_ids(self) -> set:
        """Получить ID городов которые уже спарсены (имеют товары в greenspark_product_urls)"""
        if not self.use_db:
            return set()
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT
                    (o.api_config->>'set_city')::int as city_id
                FROM zip_outlets o
                INNER JOIN greenspark_product_urls gp ON o.id = gp.outlet_id
                WHERE (o.code LIKE 'gs-%' OR o.code LIKE 'greenspark-%')
                  AND o.api_config->>'set_city' IS NOT NULL
            """)
            result = set(row[0] for row in cur.fetchall() if row[0])
            cur.close()
            conn.close()
            return result
        except Exception as e:
            print(f"[DB] Ошибка получения спарсенных городов: {e}")
            return set()

    def set_city(self, city_id: int, city_name: str):
        """Установить город для парсинга"""
        self.client.cookies.set("magazine", str(city_id))
        self.client.cookies.set("global_magazine", str(city_id))
        self.current_city = city_name
        self.current_city_id = city_id

    # === Парсинг каталога (из v3, без изменений) ===

    def _build_path_params(self, path_parts: List[str]) -> str:
        """Построить параметры path[] для URL"""
        return "&".join([f"path[]={part}" for part in path_parts])

    def get_category_data(self, path_parts: List[str], page: int = 1) -> Optional[dict]:
        """Получить данные категории через API с ротацией прокси при бане.
        До 10 попыток с ротацией прокси.
        """
        max_attempts = 10
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            self._rate_limit()

            path_params = self._build_path_params(path_parts)
            url = f"{API_URL}{PRODUCTS_ENDPOINT}?{path_params}&orderBy=quantity&orderDirection=desc&perPage={PER_PAGE}&page={page}"

            try:
                t0 = time.time()
                response = self.client.get(url)
                elapsed_ms = (time.time() - t0) * 1000

                # Проверяем блокировку
                content_type = response.headers.get('content-type', '')
                if 'application/json' not in content_type:
                    print(f"[BLOCK] Не JSON ответ: {content_type} (попытка {attempt}/{max_attempts})")
                    if self.proxy_client and self._switch_proxy(f"Не JSON: {content_type[:50]}"):
                        continue
                    self.blocked = True
                    return None

                if response.status_code == 403:
                    print(f"[BLOCK] HTTP 403 (попытка {attempt}/{max_attempts})")
                    if self.proxy_client and self._switch_proxy("HTTP 403"):
                        continue
                    self.blocked = True
                    return None

                response.raise_for_status()

                # Успех — сообщаем proxy-service
                if self.proxy_client:
                    self.proxy_client.report_success(response_time=elapsed_ms)

                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    if self.proxy_client and self._switch_proxy("HTTP 403"):
                        continue
                    self.blocked = True
                self.errors.append({
                    "path": "/".join(path_parts),
                    "error": f"HTTP {e.response.status_code}",
                    "time": datetime.now().isoformat()
                })
                return None
            except (httpx.ProxyError, httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                print(f"[PROXY ERROR] {e} (попытка {attempt}/{max_attempts})")
                if self.proxy_client and self._switch_proxy(f"Proxy error: {str(e)[:80]}"):
                    continue
                self.blocked = True
                return None
            except Exception as e:
                self.errors.append({
                    "path": "/".join(path_parts),
                    "error": str(e),
                    "time": datetime.now().isoformat()
                })
                return None

        print(f"[GIVE UP] Все {max_attempts} попыток исчерпаны для {'/'.join(path_parts)}")
        return None

    def extract_article(self, picture_url: str) -> str:
        """Извлечь артикул из URL картинки"""
        match = re.search(r'gs-(\d+)', picture_url, re.IGNORECASE)
        if match:
            return f"GS-{match.group(1)}"

        match = re.search(r'ip-(\d+)', picture_url, re.IGNORECASE)
        if match:
            return f"ИП-{match.group(1)}"

        return ""

    def fetch_article_from_api(self, product_url: str) -> str:
        """Получить артикул через детальный API"""
        self._rate_limit()
        try:
            match = re.search(r'/catalog/(.+?)(?:\.html)?/?$', product_url)
            if not match:
                return ""

            path_str = match.group(1).rstrip('/')
            path_parts = path_str.split('/')
            path_params = self._build_path_params(path_parts)
            api_url = f"{API_URL}catalog/detail/?{path_params}"

            response = self.client.get(api_url)
            if response.status_code != 200:
                return ""

            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                return ""

            data = response.json()
            product = data.get("product", {})
            article = product.get("article", "")

            return article.strip() if article else ""
        except:
            return ""

    def fetch_article_from_page(self, product_url: str) -> str:
        """Получить артикул (API + HTML fallback)"""
        article = self.fetch_article_from_api(product_url)
        if article:
            return article

        self._rate_limit()
        try:
            response = self.client.get(product_url)
            if response.status_code != 200:
                return ""

            html = response.text
            # Формат 1: GS-00001234 (буквы-тире-цифры)
            match = re.search(r'Артикул[:\s]*([А-ЯA-Zа-яa-z]{2,3}-\d+)', html, re.IGNORECASE)
            if match:
                return match.group(1).upper()
            # Формат 2: 00000000656 (чистые цифры, 8+ символов)
            match = re.search(r'Артикул[:\s]*(\d{8,})', html, re.IGNORECASE)
            if match:
                return match.group(1)
            return ""
        except:
            return ""

    def extract_breadcrumbs_path(self, breadcrumbs: List[dict]) -> tuple:
        """Извлечь путь из хлебных крошек"""
        slug_parts = []
        name_parts = []

        for crumb in breadcrumbs:
            url = crumb.get("url", "")
            name = crumb.get("name", "")

            match = re.search(r'/catalog/(.+?)/?$', url)
            if match:
                full_path = match.group(1).rstrip('/')
                last_part = full_path.split('/')[-1]
                slug_parts.append(last_part)
            name_parts.append(name)

        return "/".join(slug_parts), " / ".join(name_parts)

    def extract_product_info(self, product: dict, category_slug: str, category_name: str) -> Optional[Dict]:
        """Извлечь информацию о товаре"""
        try:
            product_id = product.get("id")

            if product_id in self.seen_ids:
                return None
            self.seen_ids.add(product_id)

            url_path = product.get("url", "")
            full_url = BASE_URL + url_path if url_path else ""

            article = product.get("article", "").strip()
            if not article:
                picture = product.get("picture", {})
                picture_url = picture.get("original", "") or picture.get("webp", "")
                article = self.extract_article(picture_url)

            prices = product.get("prices", [])
            price_retail = 0.0
            price_green5 = 0.0

            for p in prices:
                name = p.get("name", "").lower()
                price_value = p.get("price", 0) or 0

                if "розница" in name:
                    price_retail = float(price_value)
                elif "грин 5" in name:
                    price_green5 = float(price_value)

            return {
                "url": full_url,
                "category": category_name,
                "article": article,
                "name": product.get("name", ""),
                "price": price_retail,
                "price_wholesale": price_green5,
            }

        except Exception as e:
            self.errors.append({
                "product_id": str(product.get("id")),
                "error": str(e),
                "time": datetime.now().isoformat()
            })
            return None

    def crawl_category(self, path_parts: List[str], depth: int = 0):
        """Рекурсивный обход категории"""
        if self.blocked:
            return

        path_str = "/".join(path_parts)
        indent = "  " * depth

        print(f"{indent}[{depth}] Обход: {path_str}")

        data = self.get_category_data(path_parts, page=1)
        if not data:
            print(f"{indent}    [SKIP] Не удалось получить данные")
            return

        section_meta = data.get("sectionMeta", {})
        breadcrumbs = section_meta.get("breadcrumbs", [])
        category_slug, category_name = self.extract_breadcrumbs_path(breadcrumbs)

        if category_slug:
            self.categories[category_slug] = category_name

        subsections = data.get("subsections", [])

        if subsections:
            print(f"{indent}    Подкатегорий: {len(subsections)}")
            for sub in subsections:
                if self.blocked:
                    break
                sub_url = sub.get("url", "")
                match = re.search(r'/catalog/(.+?)/?$', sub_url)
                if match:
                    sub_path = match.group(1).rstrip('/').split('/')
                    self.crawl_category(sub_path, depth + 1)
        else:
            self._collect_products_from_category(data, path_parts, category_slug, category_name, depth)

    def _collect_products_from_category(self, first_page_data: dict, path_parts: List[str],
                                        category_slug: str, category_name: str, depth: int):
        """Собрать все товары из категории"""
        if self.blocked:
            return

        indent = "  " * depth

        products_data = first_page_data.get("products", {})
        products_list = products_data.get("data", [])
        meta = products_data.get("meta", {})
        total_pages = meta.get("pageCount", 1)
        total_products = meta.get("total", 0)

        print(f"{indent}    Товаров: {total_products}, страниц: {total_pages}")

        page_count = 0
        for product in products_list:
            info = self.extract_product_info(product, category_slug, category_name)
            if info:
                info["city_id"] = self.current_city_id
                info["city_name"] = self.current_city
                self.products.append(info)
                self.staging_buffer.append(info)
                page_count += 1

        print(f"{indent}    Страница 1/{total_pages}: +{page_count} товаров")
        self._maybe_save_staging()

        for page in range(2, total_pages + 1):
            if self.blocked:
                break

            data = self.get_category_data(path_parts, page=page)
            if not data:
                continue

            products_data = data.get("products", {})
            products_list = products_data.get("data", [])

            page_count = 0
            for product in products_list:
                info = self.extract_product_info(product, category_slug, category_name)
                if info:
                    info["city_id"] = self.current_city_id
                    info["city_name"] = self.current_city
                    self.products.append(info)
                    self.staging_buffer.append(info)
                    page_count += 1

            print(f"{indent}    Страница {page}/{total_pages}: +{page_count} товаров")
            self._maybe_save_staging()

    # === Staging (TZ-005/006) ===

    def _maybe_save_staging(self):
        """Сохранить в staging если накопилось достаточно товаров"""
        if not self.use_db:
            return
        if len(self.staging_buffer) >= SAVE_EVERY_N_PRODUCTS:
            saved = save_staging(self.staging_buffer)
            self.total_staged += saved
            self.stats["products_total"] += saved
            self.stats["products_session"] += saved
            self.staging_buffer = []

    def _flush_staging(self):
        """Сохранить оставшиеся товары в staging"""
        if not self.use_db:
            return
        if self.staging_buffer:
            saved = save_staging(self.staging_buffer)
            self.total_staged += saved
            self.stats["products_total"] += saved
            self.stats["products_session"] += saved
            self.staging_buffer = []

    # === Допарсинг артикулов ===

    def reparse_missing_articles(self):
        """Допарсинг артикулов через БД + HTTP"""
        missing = [(i, p) for i, p in enumerate(self.products) if not p.get("article")]

        if not missing:
            print("Все товары имеют артикулы")
            return

        print(f"\n{'='*60}")
        print(f"Допарсинг артикулов: {len(missing)} товаров без артикула")
        print(f"{'='*60}")

        # ШАГ 1: Batch поиск по БД
        if self.use_db:
            print(f"\n[Шаг 1] Поиск артикулов в БД (batch)...")

            urls_to_lookup = []
            url_to_indices = {}
            for i, product in missing:
                url = product.get("url", "")
                if url:
                    urls_to_lookup.append(url)
                    if url not in url_to_indices:
                        url_to_indices[url] = []
                    url_to_indices[url].append(i)

            db_articles = self._batch_lookup_articles(urls_to_lookup)
            print(f"  Найдено в БД: {len(db_articles)} артикулов")

            from_db = 0
            for url, article in db_articles.items():
                if article and url in url_to_indices:
                    for idx in url_to_indices[url]:
                        self.products[idx]["article"] = article
                        from_db += 1
            print(f"  Применено из БД: {from_db}")
        else:
            from_db = 0

        # ШАГ 2: HTTP допарсинг оставшихся
        still_missing = [(i, p) for i, p in enumerate(self.products) if not p.get("article")]

        if not still_missing:
            print(f"\n[Шаг 2] HTTP допарсинг не требуется")
            print(f"\nИтого: найдено {from_db} артикулов из БД")
            return

        print(f"\n[Шаг 2] HTTP допарсинг {len(still_missing)} товаров...")

        from_http = 0
        for idx, (i, product) in enumerate(still_missing):
            if self.blocked:
                print("[BLOCK] Допарсинг прерван из-за блокировки")
                break

            url = product.get("url", "")
            if not url:
                continue

            article = self.fetch_article_from_page(url)

            if article:
                self.products[i]["article"] = article
                from_http += 1

            if (idx + 1) % 50 == 0:
                print(f"  HTTP: {idx + 1}/{len(still_missing)}, найдено: {from_http}")

        print(f"\n{'='*60}")
        print(f"Допарсинг завершён: из БД={from_db}, HTTP={from_http}, всего={from_db + from_http}")
        print(f"{'='*60}")

    def _batch_lookup_articles(self, urls: List[str]) -> Dict[str, str]:
        """Batch поиск артикулов по списку URL"""
        if not urls:
            return {}
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT url, article FROM greenspark_nomenclature WHERE url = ANY(%s) AND article IS NOT NULL AND article != ''",
                (urls,)
            )
            result = {row[0]: row[1] for row in cur.fetchall()}
            cur.close()
            conn.close()
            return result
        except Exception as e:
            print(f"[BATCH LOOKUP ERROR] {e}")
            return {}

    # === Основные методы ===

    def parse_catalog(self, start_category: str = None, reparse_articles: bool = True):
        """Парсит каталог"""
        start = start_category or ROOT_CATEGORY

        print(f"\n{'='*60}")
        print(f"Парсинг каталога GreenSpark.ru v4")
        print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Корневая категория: {start}")
        if self.proxy_client and self.proxy_client.current_proxy:
            print(f"Прокси: {self.proxy_client.proxy_url}")
        print(f"{'='*60}\n")

        print("[Этап 1] Обход каталога и сбор товаров\n")
        path_parts = start.split('/')
        self.crawl_category(path_parts)

        print(f"\n{'='*60}")
        print(f"Этап 1 завершён: {len(self.products)} товаров")
        print(f"Категорий: {len(self.categories)}")
        print(f"Ошибок: {len(self.errors)}")
        print(f"{'='*60}")

        if reparse_articles and not self.blocked:
            print("\n[Этап 2] Допарсинг артикулов")
            self.reparse_missing_articles()

        # Сохраняем оставшиеся товары в staging
        self._flush_staging()

        missing_articles = len([p for p in self.products if not p.get("article")])
        print(f"\n{'='*60}")
        print(f"ИТОГО: {len(self.products)} товаров")
        print(f"С артикулами: {len(self.products) - missing_articles}")
        print(f"Без артикулов: {missing_articles}")
        if self.use_db:
            print(f"Сохранено в staging: {self.total_staged}")
        print(f"{'='*60}")

    def parse_city(self, city_id: int, city_name: str, start_category: str = None,
                   reparse_articles: bool = True) -> int:
        """Парсить один город, возвращает количество товаров"""
        self.products = []
        self.seen_ids = set()
        self.blocked = False
        self.staging_buffer = []
        self.total_staged = 0

        self.set_city(city_id, city_name)
        self.parse_catalog(start_category, reparse_articles)

        return len(self.products)

    def close(self):
        if self.client:
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================
# Staging — save + process (TZ-005/006)
# ============================================================

# Кэш: city_id (из greenspark) → outlet_code (из zip_outlets)
_outlet_code_cache: Dict[int, str] = {}


def load_outlet_codes():
    """Загрузить маппинг city_id → outlet_code из zip_outlets"""
    global _outlet_code_cache
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT code, api_config->>'set_city' as city_id
            FROM zip_outlets
            WHERE code LIKE 'gs-%' OR code LIKE 'greenspark-%'
        """)
        for row in cur.fetchall():
            code, city_id_str = row
            if city_id_str:
                _outlet_code_cache[int(city_id_str)] = code
        cur.close()
        conn.close()
        print(f"[OUTLETS] Загружено {len(_outlet_code_cache)} маппингов city_id → outlet_code")
    except Exception as e:
        print(f"[OUTLETS] Ошибка загрузки: {e}")


def get_outlet_code_for_city(city_id: int) -> Optional[str]:
    """Получить outlet_code по city_id (GreenSpark set_city)"""
    if not _outlet_code_cache:
        load_outlet_codes()
    return _outlet_code_cache.get(city_id)


def save_staging(products: List[Dict], verbose: bool = True) -> int:
    """Сохранить товары в greenspark_staging (батч)
    Схема: article, name, price, price_wholesale, url, category, outlet_code, processed
    """
    if not products:
        return 0

    conn = get_db()
    cur = conn.cursor()
    saved = 0

    try:
        for p in products:
            name = p.get("name", "").strip()
            url = p.get("url", "").strip()
            if not name or not url:
                continue

            article = p.get("article", "").strip() or None
            city_id = p.get("city_id")
            outlet_code = get_outlet_code_for_city(city_id) if city_id else None

            cur.execute("""
                INSERT INTO greenspark_staging
                    (name, url, article, category, price, price_wholesale,
                     outlet_code, processed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, false)
            """, (
                name, url, article, p.get("category", ""),
                p.get("price", 0), p.get("price_wholesale", 0),
                outlet_code
            ))
            saved += 1

        conn.commit()
        if verbose:
            print(f"    [STAGING] Сохранено {saved} товаров")
        return saved

    except Exception as e:
        conn.rollback()
        print(f"    [STAGING ERROR] {e}")
        return 0
    finally:
        cur.close()
        conn.close()


def ensure_db_schema():
    """Создать недостающие индексы для корректной работы UPSERT"""
    conn = get_db()
    cur = conn.cursor()
    try:
        # UNIQUE index на url в greenspark_nomenclature (нужен для ON CONFLICT)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_greenspark_nomenclature_url
            ON greenspark_nomenclature(url)
        """)
        conn.commit()
        print("[DB] Индекс idx_greenspark_nomenclature_url создан/существует")
    except Exception as e:
        conn.rollback()
        print(f"[DB] Ошибка создания индекса: {e}")
    finally:
        cur.close()
        conn.close()


def process_staging(verbose: bool = True) -> Dict[str, int]:
    """Перенести данные из staging → nomenclature + product_urls.

    price хранится в nomenclature (справочная цена).
    product_urls: связь номенклатура → URL (outlet_id = NULL для single-URL).
    """
    conn = get_db()
    cur = conn.cursor()
    result = {"nomenclature": 0, "product_urls": 0, "errors": 0}

    try:
        # Получить необработанные записи из staging
        cur.execute("""
            SELECT id, name, url, article, category, price, price_wholesale
            FROM greenspark_staging
            WHERE processed = false
            ORDER BY created_at
        """)
        rows = cur.fetchall()

        if not rows:
            if verbose:
                print("[PROCESS] Staging пуст (или всё обработано)")
            return result

        if verbose:
            print(f"[PROCESS] Обработка {len(rows)} записей из staging...")

        for idx, row in enumerate(rows):
            staging_id, name, url, article, category, price, price_wholesale = row

            try:
                cur.execute("SAVEPOINT sp")

                # UPSERT в greenspark_nomenclature (по url) + price
                cur.execute("""
                    INSERT INTO greenspark_nomenclature (name, url, article, category, price, price_wholesale, first_seen_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (url) DO UPDATE SET
                        name = EXCLUDED.name,
                        article = COALESCE(EXCLUDED.article, greenspark_nomenclature.article),
                        category = EXCLUDED.category,
                        price = EXCLUDED.price,
                        price_wholesale = EXCLUDED.price_wholesale,
                        updated_at = NOW()
                    RETURNING id
                """, (name, url, article, category, price, price_wholesale))

                nom_row = cur.fetchone()
                if not nom_row:
                    cur.execute("ROLLBACK TO SAVEPOINT sp")
                    continue
                nom_id = nom_row[0]
                result["nomenclature"] += 1

                # INSERT в greenspark_product_urls (single-URL: outlet_id = NULL)
                cur.execute("""
                    INSERT INTO greenspark_product_urls
                        (nomenclature_id, outlet_id, url, updated_at)
                    VALUES (%s, NULL, %s, NOW())
                    ON CONFLICT (url) DO NOTHING
                """, (nom_id, url))
                result["product_urls"] += 1

                cur.execute("UPDATE greenspark_staging SET processed = true WHERE id = %s", (staging_id,))
                cur.execute("RELEASE SAVEPOINT sp")

            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT sp")
                result["errors"] += 1
                if verbose:
                    print(f"    [PROCESS ERROR] staging_id={staging_id}: {e}")

            if verbose and (idx + 1) % 1000 == 0:
                print(f"    [PROCESS] {idx + 1}/{len(rows)}...")

        conn.commit()

        if verbose:
            print(f"[PROCESS] Готово: nomenclature={result['nomenclature']}, product_urls={result['product_urls']}, errors={result['errors']}")

        return result

    except Exception as e:
        conn.rollback()
        print(f"[PROCESS ERROR] {e}")
        return result
    finally:
        cur.close()
        conn.close()


def clear_staging():
    """Очистить staging таблицу (только processed записи, или все если force)"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM greenspark_staging WHERE processed = true")
        count = cur.rowcount
        conn.commit()
        print(f"[STAGING] Очищено {count} обработанных записей")
    finally:
        cur.close()
        conn.close()


def clear_staging_all():
    """Очистить ВСЮ staging таблицу"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM greenspark_staging")
        count = cur.rowcount
        conn.commit()
        print(f"[STAGING] Очищено {count} записей (все)")
    finally:
        cur.close()
        conn.close()


# ============================================================
# Helpers — транслитерация и список торговых точек
# ============================================================

_TRANSLIT_TABLE = [
    ("а","a"),("б","b"),("в","v"),("г","g"),("д","d"),("е","e"),
    ("ё","e"),("ж","zh"),("з","z"),("и","i"),("й","y"),("к","k"),
    ("л","l"),("м","m"),("н","n"),("о","o"),("п","p"),("р","r"),
    ("с","s"),("т","t"),("у","u"),("ф","f"),("х","h"),("ц","ts"),
    ("ч","ch"),("ш","sh"),("щ","sch"),("ъ",""),("ы","y"),("ь",""),
    ("э","e"),("ю","yu"),("я","ya"),(" ","-"),("–","-"),("—","-"),
    ("(",""),(")",""),(",",""),(".",""),("/","-"),
]


def _transliterate(text: str) -> str:
    """Транслитерация русского текста в URL-slug."""
    result = text.lower()
    for src, dst in _TRANSLIT_TABLE:
        result = result.replace(src, dst)
    result = re.sub(r'[^a-z0-9-]', '', result)
    result = re.sub(r'-+', '-', result).strip('-')
    return result


def _load_shops_from_file() -> List[Dict]:
    """Загрузить список точек из greenspark_shops.json (fallback)."""
    if os.path.exists(_SHOPS_FILE):
        with open(_SHOPS_FILE, "r", encoding="utf-8") as f:
            shops = json.load(f)
        print(f"[SYNC_OUTLETS] Загружено из файла: {len(shops)} точек")
        return shops
    print("[SYNC_OUTLETS] Файл greenspark_shops.json не найден")
    return []


def sync_outlets(proxy_service_url: str = PROXY_SERVICE_URL) -> List[Dict]:
    """Синхронизировать список торговых точек с green-spark.ru/local/api/shop/list/.

    Использует proxy-service для получения прокси + cookies.
    Сохраняет результат в data/greenspark_shops.json.
    Возвращает список точек [{shop_id, city_name, shop_name, address}].
    """
    print("[SYNC_OUTLETS] Получаем прокси + cookies из proxy-service...")
    proxy_url = None
    cookies = {}
    try:
        resp = httpx.get(
            f"{proxy_service_url.rstrip('/')}/proxy/get?protocol=socks5&for_site=greenspark",
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            proto = data.get("protocol", "socks5")
            proxy_url = f"{proto}://{data['host']}:{data['port']}"
            cookies = data.get("cookies") or {}
            print(f"[SYNC_OUTLETS] Прокси: {proxy_url}, cookies: {len(cookies)} шт.")
        else:
            print(f"[SYNC_OUTLETS] proxy-service вернул {resp.status_code}, работаем без прокси")
    except Exception as e:
        print(f"[SYNC_OUTLETS] Ошибка proxy-service: {e}, работаем без прокси")

    if not cookies:
        cookies = {"magazine": str(DEFAULT_SHOP_ID), "global_magazine": str(DEFAULT_SHOP_ID)}

    print("[SYNC_OUTLETS] GET https://green-spark.ru/local/api/shop/list/ ...")
    client_kwargs = {
        "timeout": 60,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json, */*",
            "Accept-Language": "ru,en;q=0.9",
        },
        "cookies": cookies,
        "follow_redirects": True,
    }
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
        if "socks" in proxy_url:
            client_kwargs["verify"] = False

    try:
        with httpx.Client(**client_kwargs) as client:
            resp = client.get("https://green-spark.ru/local/api/shop/list/")
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "application/json" not in content_type:
                print(f"[SYNC_OUTLETS] Ответ не JSON (captcha?): {content_type[:80]}")
                return _load_shops_from_file()
            raw = resp.json()
    except Exception as e:
        print(f"[SYNC_OUTLETS] Ошибка запроса: {e}")
        return _load_shops_from_file()

    # Парсинг JSON: {"А": {"Абакан": {"name": "...", "shops": [{"id": "...", ...}]}}}
    shops = []
    for _letter, cities_dict in raw.items():
        if not isinstance(cities_dict, dict):
            continue
        for city_name, city_data in cities_dict.items():
            if not isinstance(city_data, dict):
                continue
            for shop in city_data.get("shops", []):
                shops.append({
                    "shop_id": str(shop.get("id", "")),
                    "city_name": city_data.get("name") or city_name,
                    "shop_name": shop.get("name", ""),
                    "address": shop.get("address", ""),
                })

    city_count = len({s["city_name"] for s in shops})
    print(f"[SYNC_OUTLETS] Получено {len(shops)} точек из {city_count} городов")

    os.makedirs(os.path.dirname(_SHOPS_FILE), exist_ok=True)
    with open(_SHOPS_FILE, "w", encoding="utf-8") as f:
        json.dump(shops, f, ensure_ascii=False, indent=2)
    print(f"[SYNC_OUTLETS] Сохранено → {_SHOPS_FILE}")

    return shops


# ============================================================
# Ensure outlets
# ============================================================

def ensure_outlets(shops: List[Dict] = None):
    """Создать/обновить zip_outlets для всех торговых точек GreenSpark.

    shops — список из sync_outlets() или загружается из greenspark_shops.json.
    Код outlet: gs-{city_slug} (gs-{city_slug}-{N} если несколько точек в городе).
    api_config: {"shop_id": "281974"}.
    Также создаёт специальный outlet gs-all для хранения единых цен номенклатуры.
    """
    if shops is None:
        shops = _load_shops_from_file()
    if not shops:
        print("[OUTLETS] Нет данных о точках, пропускаем")
        return

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM zip_shops WHERE code = 'greenspark'")
        shop_row = cur.fetchone()
        if not shop_row:
            print("[OUTLETS ERROR] Магазин 'greenspark' не найден! Запустите setup_greenspark_in_zip.sql")
            return
        gs_shop_id = shop_row[0]

        # Существующие коды
        cur.execute("SELECT code FROM zip_outlets WHERE code LIKE 'gs-%'")
        existing_codes = {row[0] for row in cur.fetchall()}

        # Кэш zip_cities id по имени
        city_id_cache: Dict[str, object] = {}

        def get_or_create_city(name: str, slug: str):
            if name in city_id_cache:
                return city_id_cache[name]
            cur.execute("SELECT id FROM zip_cities WHERE name = %s", (name,))
            row = cur.fetchone()
            if not row:
                cur.execute("""
                    INSERT INTO zip_cities (code, name, is_active) VALUES (%s, %s, true)
                    ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                """, (slug, name))
                row = cur.fetchone()
            city_id_cache[name] = row[0]
            return row[0]

        # Считаем количество точек на город для суффикса кода
        city_counts: Dict[str, int] = {}
        created = updated = 0

        for shop in shops:
            city_name = shop["city_name"]
            shop_id_gs = shop["shop_id"]
            city_slug = _transliterate(city_name)

            city_counts[city_name] = city_counts.get(city_name, 0) + 1
            n = city_counts[city_name]
            outlet_code = f"gs-{city_slug}" if n == 1 else f"gs-{city_slug}-{n}"

            zip_city_id = get_or_create_city(city_name, city_slug)
            outlet_name = shop.get("shop_name") or f"GreenSpark {city_name}"
            api_cfg = json.dumps({"shop_id": shop_id_gs})

            if outlet_code in existing_codes:
                cur.execute(
                    "UPDATE zip_outlets SET name = %s, api_config = %s, is_active = true WHERE code = %s",
                    (outlet_name, api_cfg, outlet_code),
                )
                updated += 1
            else:
                cur.execute("""
                    INSERT INTO zip_outlets (shop_id, city_id, code, name, is_active, api_config)
                    VALUES (%s, %s, %s, %s, true, %s)
                    ON CONFLICT (code) DO UPDATE SET
                        name = EXCLUDED.name,
                        api_config = EXCLUDED.api_config,
                        is_active = true
                """, (gs_shop_id, zip_city_id, outlet_code, outlet_name, api_cfg))
                created += 1

        # Создаём общий outlet gs-all для единых цен номенклатуры
        if "gs-all" not in existing_codes:
            cur.execute("SELECT id FROM zip_cities WHERE name = 'Москва' LIMIT 1")
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT id FROM zip_cities LIMIT 1")
                row = cur.fetchone()
            if row:
                cur.execute("""
                    INSERT INTO zip_outlets (shop_id, city_id, code, name, is_active, api_config)
                    VALUES (%s, %s, 'gs-all', 'GreenSpark — все точки', true, '{}'::jsonb)
                    ON CONFLICT (code) DO NOTHING
                """, (gs_shop_id, row[0]))
                print("[OUTLETS] Создан outlet gs-all")

        conn.commit()
        print(f"[OUTLETS] Создано: {created}, обновлено: {updated} outlet-ов (всего точек: {len(shops)})")
    except Exception as e:
        conn.rollback()
        print(f"[OUTLETS ERROR] {e}")
        import traceback; traceback.print_exc()
    finally:
        cur.close()
        conn.close()


# ============================================================
# Main — CLI
# ============================================================

def main():
    arg_parser = argparse.ArgumentParser(description='Парсер GreenSpark.ru v4 — однопроходный')
    arg_parser.add_argument('--sync-outlets', action='store_true',
                            help='Только синхронизация торговых точек с сайта (без парсинга)')
    arg_parser.add_argument('--no-sync', action='store_true',
                            help='Не синхронизировать точки перед парсингом')
    arg_parser.add_argument('--category', type=str, help='Стартовая категория')
    arg_parser.add_argument('--no-reparse', action='store_true', help='Без допарсинга артикулов')
    arg_parser.add_argument('--no-db', action='store_true', help='Без сохранения в БД')
    arg_parser.add_argument('--no-proxy', action='store_true', help='Без прокси (прямой доступ)')
    arg_parser.add_argument('--all', action='store_true', help='Парсинг + process_staging')
    arg_parser.add_argument('--process', action='store_true', help='Только process_staging')
    arg_parser.add_argument('--clear-staging', action='store_true', help='Очистить staging')
    arg_parser.add_argument('--proxy-service', type=str, default=PROXY_SERVICE_URL,
                            help=f'URL proxy-service (по умолчанию: {PROXY_SERVICE_URL})')
    # Устаревшие флаги — оставлены для совместимости, игнорируются
    arg_parser.add_argument('--all-cities', action='store_true', help=argparse.SUPPRESS)
    arg_parser.add_argument('--city', type=str, help=argparse.SUPPRESS)
    arg_parser.add_argument('--skip-parsed', action='store_true', help=argparse.SUPPRESS)
    args = arg_parser.parse_args()

    # Только очистка staging
    if args.clear_staging:
        clear_staging_all()
        return

    # Только process_staging
    if args.process:
        print("[*] Processing staging → nomenclature + prices...")
        ensure_db_schema()
        result = process_staging()
        print(f"Результат: {result}")
        return

    use_db = not args.no_db

    # Инициализация ProxyClient (SOCKS5)
    proxy_client = None
    if not args.no_proxy:
        proxy_client = ProxyClient(base_url=args.proxy_service, protocol="socks5")
        stats = proxy_client.get_stats()
        if stats:
            print(f"[PROXY] proxy-service OK: working={stats.get('working', 0)}, raw={stats.get('raw', 0)}")
        else:
            print("[PROXY] proxy-service недоступен! Используйте --no-proxy для прямого доступа")
            return

        proxy = proxy_client.get_proxy()
        if not proxy:
            print("[PROXY] Нет рабочих SOCKS5 прокси. Запустите POST /proxy/refresh и подождите 3-5 мин")
            return
        print(f"[PROXY] Первый SOCKS5 прокси: {proxy_client.proxy_url}")

    # Только синхронизация точек
    if args.sync_outlets:
        shops = sync_outlets(args.proxy_service)
        if use_db and shops:
            ensure_db_schema()
            ensure_outlets(shops)
        return

    # CookieManager — fallback
    cookie_manager = CookieManager()

    # ВСЕГДА получаем свежие cookies через Playwright (proxy-service кэш ненадёжен)
    print("[INIT] Получение свежих cookies через Playwright...")
    proxy_for_cookies = proxy_client.proxy_url if proxy_client else None
    cookies = cookie_manager.get_cookies(proxy_url=proxy_for_cookies)
    if not cookies:
        cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), COOKIES_FILE)
        if os.path.exists(cookies_path):
            print("[INIT] Playwright не смог, используем cookies из файла (IP может не совпасть!)")
            with open(cookies_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            cookies.pop("__meta__", None)
        else:
            print("[ERROR] Не удалось получить cookies!")
            return

    # Подготовка БД и синхронизация точек
    if use_db:
        ensure_db_schema()
        clear_staging()
        if not args.no_sync:
            shops = sync_outlets(args.proxy_service)
            ensure_outlets(shops)
        else:
            ensure_outlets()

    # Создаём парсер — ОДНОПРОХОДНЫЙ режим
    parser = GreenSparkParser(proxy_client=proxy_client, cookie_manager=cookie_manager, use_db=use_db)
    parser.init_client(cookies)

    notifier = get_notifier() if TELEGRAM_AVAILABLE else None

    print(f"\n{'='*60}")
    print(f"ОДНОПРОХОДНЫЙ ПАРСИНГ GreenSpark.ru v4")
    print(f"Прокси: {'proxy-service (socks5)' if proxy_client else 'direct'}")
    print(f"БД: {'Homelab PostgreSQL' if use_db else 'отключена'}")
    print(f"{'='*60}\n")

    if notifier:
        notifier.notify_start(
            server_name="homelab/proxy-service",
            ip=proxy_client.proxy_url if proxy_client else "direct",
            cities_count=1,
        )

    parser.parse_catalog(
        start_category=args.category,
        reparse_articles=not args.no_reparse,
    )

    if use_db and args.all:
        print(f"\n{'='*60}")
        print(f"[PROCESS] Перенос staging → nomenclature + prices")
        print(f"{'='*60}")
        result = process_staging()

    if notifier:
        duration_min = int((datetime.now() - parser.stats["start_time"]).total_seconds() / 60)
        notifier.notify_complete(
            total_products=parser.stats["products_total"],
            cities_done=1,
            duration_minutes=duration_min,
            errors=len(parser.errors),
        )

    parser.close()

    if proxy_client:
        stats = proxy_client.get_stats()
        if stats:
            print(f"\n[PROXY STATS] working={stats.get('working', 0)}, "
                  f"banned_greenspark={stats.get('banned_by_site', {}).get('greenspark', 0)}")

    print("\nПарсинг завершён!")


if __name__ == "__main__":
    main()
