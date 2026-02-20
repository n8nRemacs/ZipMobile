"""
Получение cookies через Playwright со stealth-режимом
Используется playwright-stealth для обхода детекции

Установка:
    pip install playwright playwright-stealth
    playwright install chromium
"""
import json
import asyncio
import random
import os
from datetime import datetime
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext

# Попытка импорта stealth
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("[WARN] playwright-stealth не установлен. pip install playwright-stealth")

COOKIES_FILE = "cookies.json"
TARGET_URL = "https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/"
API_TEST_URL = "https://green-spark.ru/local/api/catalog/products/?path[]=komplektuyushchie_dlya_remonta&perPage=10"


# Реалистичные User-Agent (актуальные на 2024-2025)
USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Yandex Browser
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 YaBrowser/24.12.0.0 Safari/537.36",
]

# Размеры экранов (реалистичные)
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 2560, "height": 1440},
]

# Локали
LOCALES = ["ru-RU", "ru", "en-US"]


class StealthCookieGetter:
    """Получение cookies через stealth Playwright"""

    def __init__(self, shop_id: str = "16344", local_ip: str = None):
        """
        Args:
            shop_id: ID магазина GreenSpark
            local_ip: Локальный IP для привязки (для серверов с несколькими IP)
        """
        self.shop_id = shop_id
        self.local_ip = local_ip
        self.user_agent = random.choice(USER_AGENTS)
        self.viewport = random.choice(VIEWPORTS)
        self.locale = random.choice(LOCALES)

    async def get_cookies(self, headless: bool = False, timeout: int = 30) -> Optional[Dict]:
        """
        Получить cookies через браузер

        ВАЖНО: Сайт green-spark.ru детектит headless браузеры!
        По умолчанию headless=False (использовать Xvfb на сервере)

        Args:
            headless: Запускать без GUI (НЕ РЕКОМЕНДУЕТСЯ - сайт детектит!)
            timeout: Таймаут в секундах

        Returns:
            Dict с cookies или None при ошибке
        """
        # ВАЖНО: headless=False требует Xvfb на сервере
        # Запуск: xvfb-run python stealth_cookies.py
        print(f"[COOKIES] Запуск браузера (headless={headless})...")
        print(f"[COOKIES] User-Agent: {self.user_agent[:60]}...")
        print(f"[COOKIES] Viewport: {self.viewport}")
        if self.local_ip:
            print(f"[COOKIES] Local IP: {self.local_ip}")

        async with async_playwright() as p:
            # Аргументы запуска браузера
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--hide-scrollbars",
                "--mute-audio",
                f"--window-size={self.viewport['width']},{self.viewport['height']}",
            ]

            browser = await p.chromium.launch(
                headless=headless,
                args=launch_args,
            )

            # Создаём контекст с реалистичными параметрами
            context = await browser.new_context(
                user_agent=self.user_agent,
                viewport=self.viewport,
                locale=self.locale,
                timezone_id="Europe/Moscow",
                geolocation={"latitude": 55.7558, "longitude": 37.6173},  # Москва
                permissions=["geolocation"],
                color_scheme="light",
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                java_script_enabled=True,
            )

            # Устанавливаем начальные cookies
            await context.add_cookies([
                {"name": "magazine", "value": self.shop_id, "domain": "green-spark.ru", "path": "/"},
                {"name": "global_magazine", "value": self.shop_id, "domain": "green-spark.ru", "path": "/"},
                {"name": "catalog-per-page", "value": "100", "domain": "green-spark.ru", "path": "/"},
            ])

            page = await context.new_page()

            # Применяем stealth если доступен
            if STEALTH_AVAILABLE:
                await stealth_async(page)
                print("[COOKIES] Stealth режим активирован")
            else:
                # Ручные stealth патчи
                await self._apply_manual_stealth(page)

            try:
                # Шаг 1: Открываем главную страницу каталога
                print(f"[COOKIES] Открываю {TARGET_URL}...")
                await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=timeout * 1000)

                # Ждём загрузки с рандомной задержкой (имитация человека)
                await page.wait_for_timeout(random.randint(3000, 5000))

                # Шаг 2: Скроллим страницу (имитация человека)
                await self._human_scroll(page)

                # Шаг 3: Делаем запрос к API
                print("[COOKIES] Активация API сессии...")
                await page.goto(API_TEST_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
                await page.wait_for_timeout(random.randint(1500, 2500))

                # Проверяем что получили JSON
                content = await page.content()
                if "application/json" in content or '"products"' in content:
                    print("[COOKIES] API ответил корректно (JSON)")
                else:
                    print("[COOKIES] Предупреждение: API вернул не JSON")

                # Шаг 4: Возвращаемся на каталог
                await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
                await page.wait_for_timeout(random.randint(2000, 3000))

                # Получаем cookies
                cookies = await context.cookies()
                cookies_dict = self._cookies_to_dict(cookies)

                # Добавляем обязательные cookies
                cookies_dict["magazine"] = self.shop_id
                cookies_dict["global_magazine"] = self.shop_id
                cookies_dict["catalog-per-page"] = "100"

                # Сохраняем User-Agent для парсера
                cookies_dict["__jua_"] = self.user_agent.replace(" ", "%20")

                print(f"[COOKIES] Получено {len(cookies_dict)} cookies")
                print(f"[COOKIES] Ключевые: {[k for k in cookies_dict if k.startswith('__') or k == 'PHPSESSID']}")

                await browser.close()
                return cookies_dict

            except Exception as e:
                print(f"[COOKIES] Ошибка: {e}")
                await browser.close()
                return None

    async def _apply_manual_stealth(self, page):
        """Ручные патчи для обхода детекции (если нет playwright-stealth)"""
        await page.add_init_script("""
            // Убираем webdriver
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

            // Подменяем plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Подменяем languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en']
            });

            // Chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // WebGL vendor
            const getParameterProxyHandler = {
                apply: function(target, thisArg, args) {
                    const param = args[0];
                    const UNMASKED_VENDOR_WEBGL = 0x9245;
                    const UNMASKED_RENDERER_WEBGL = 0x9246;
                    if (param === UNMASKED_VENDOR_WEBGL) return 'Google Inc. (NVIDIA)';
                    if (param === UNMASKED_RENDERER_WEBGL) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0)';
                    return target.apply(thisArg, args);
                }
            };

            try {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                if (gl) {
                    const originalGetParameter = gl.getParameter.bind(gl);
                    gl.getParameter = new Proxy(originalGetParameter, getParameterProxyHandler);
                }
            } catch(e) {}
        """)

    async def _human_scroll(self, page):
        """Имитация человеческого скролла"""
        try:
            for _ in range(random.randint(2, 4)):
                await page.mouse.wheel(0, random.randint(100, 300))
                await page.wait_for_timeout(random.randint(200, 500))
        except:
            pass

    def _cookies_to_dict(self, cookies: list) -> dict:
        """Преобразовать список cookies в dict"""
        return {cookie["name"]: cookie["value"] for cookie in cookies}

    def save_cookies(self, cookies: dict, filename: str = None):
        """Сохранить cookies в файл"""
        filename = filename or COOKIES_FILE

        # Добавляем метаданные
        cookies["__meta__"] = {
            "timestamp": datetime.now().isoformat(),
            "user_agent": self.user_agent,
            "local_ip": self.local_ip,
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"[COOKIES] Сохранено в {filename}")

    @staticmethod
    def load_cookies(filename: str = None) -> Optional[dict]:
        """Загрузить cookies из файла"""
        filename = filename or COOKIES_FILE

        if not os.path.exists(filename):
            return None

        try:
            with open(filename, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            # Убираем метаданные
            cookies.pop("__meta__", None)
            return cookies
        except Exception as e:
            print(f"[COOKIES] Ошибка загрузки: {e}")
            return None


async def get_fresh_cookies(shop_id: str = "16344", local_ip: str = None,
                            headless: bool = True, save: bool = True) -> Optional[dict]:
    """
    Удобная функция для получения свежих cookies

    Args:
        shop_id: ID магазина
        local_ip: Локальный IP для привязки
        headless: Без GUI
        save: Сохранить в файл

    Returns:
        Dict с cookies
    """
    getter = StealthCookieGetter(shop_id=shop_id, local_ip=local_ip)
    cookies = await getter.get_cookies(headless=headless)

    if cookies and save:
        getter.save_cookies(cookies)

    return cookies


def get_cookies_sync(shop_id: str = "16344", local_ip: str = None,
                     headless: bool = True, save: bool = True) -> Optional[dict]:
    """Синхронная обёртка для get_fresh_cookies"""
    return asyncio.run(get_fresh_cookies(shop_id, local_ip, headless, save))


# === CLI ===
if __name__ == "__main__":
    import sys

    headless = "--headless" in sys.argv or "-h" in sys.argv
    shop_id = "16344"
    local_ip = None

    # Парсим аргументы
    for i, arg in enumerate(sys.argv):
        if arg == "--shop" and i + 1 < len(sys.argv):
            shop_id = sys.argv[i + 1]
        if arg == "--ip" and i + 1 < len(sys.argv):
            local_ip = sys.argv[i + 1]

    print(f"Shop ID: {shop_id}")
    print(f"Local IP: {local_ip or 'auto'}")
    print(f"Headless: {headless}")
    print()

    cookies = get_cookies_sync(shop_id=shop_id, local_ip=local_ip, headless=headless)

    if cookies:
        print("\n" + "=" * 50)
        print("Cookies готовы! Запускайте парсер:")
        print("  python parser.py")
    else:
        print("\nОшибка получения cookies!")
        sys.exit(1)
