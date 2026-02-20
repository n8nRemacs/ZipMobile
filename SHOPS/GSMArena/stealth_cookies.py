"""
Получение cookies для GSMArena через Playwright со stealth-режимом

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
from playwright.async_api import async_playwright

try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("[WARN] playwright-stealth не установлен. pip install playwright-stealth")

COOKIES_FILE = "cookies.json"
TARGET_URL = "https://www.gsmarena.com/"
TEST_URL = "https://www.gsmarena.com/makers.php3"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]


class GSMArenaStealthCookies:
    """Получение cookies для GSMArena через stealth Playwright"""

    def __init__(self):
        self.user_agent = random.choice(USER_AGENTS)
        self.viewport = random.choice(VIEWPORTS)

    async def get_cookies(self, headless: bool = True, timeout: int = 30) -> Optional[Dict]:
        """Получить cookies через браузер"""
        print(f"[COOKIES] Запуск браузера (headless={headless})...")
        print(f"[COOKIES] User-Agent: {self.user_agent[:60]}...")

        async with async_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                f"--window-size={self.viewport['width']},{self.viewport['height']}",
            ]

            browser = await p.chromium.launch(
                headless=headless,
                args=launch_args,
            )

            context = await browser.new_context(
                user_agent=self.user_agent,
                viewport=self.viewport,
                locale="en-US",
                timezone_id="America/New_York",
                color_scheme="light",
            )

            page = await context.new_page()

            if STEALTH_AVAILABLE:
                await stealth_async(page)
                print("[COOKIES] Stealth режим активирован")
            else:
                await self._apply_manual_stealth(page)

            try:
                # Открываем главную
                print(f"[COOKIES] Открываю {TARGET_URL}...")
                await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
                await page.wait_for_timeout(random.randint(2000, 4000))

                # Скроллим
                await self._human_scroll(page)

                # Переходим на makers
                print(f"[COOKIES] Открываю {TEST_URL}...")
                await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
                await page.wait_for_timeout(random.randint(2000, 3000))

                # Проверяем что страница загрузилась
                content = await page.content()
                if "All brands" in content or "makers" in content.lower():
                    print("[COOKIES] Страница загружена успешно!")
                else:
                    print("[COOKIES] Предупреждение: возможно страница не загрузилась")

                # Ещё немного побродим
                await self._human_scroll(page)
                await page.wait_for_timeout(random.randint(1000, 2000))

                # Получаем cookies
                cookies = await context.cookies()
                cookies_dict = {c["name"]: c["value"] for c in cookies}

                # Сохраняем User-Agent
                cookies_dict["__user_agent__"] = self.user_agent

                print(f"[COOKIES] Получено {len(cookies_dict)} cookies")

                await browser.close()
                return cookies_dict

            except Exception as e:
                print(f"[COOKIES] Ошибка: {e}")
                await browser.close()
                return None

    async def _apply_manual_stealth(self, page):
        """Ручные патчи для обхода детекции"""
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}, app: {}};
        """)

    async def _human_scroll(self, page):
        """Имитация человеческого скролла"""
        try:
            for _ in range(random.randint(2, 4)):
                await page.mouse.wheel(0, random.randint(100, 300))
                await page.wait_for_timeout(random.randint(300, 600))
        except:
            pass

    def save_cookies(self, cookies: dict, filename: str = None):
        """Сохранить cookies в файл"""
        filename = filename or COOKIES_FILE
        cookies["__meta__"] = {
            "timestamp": datetime.now().isoformat(),
            "user_agent": self.user_agent,
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
            user_agent = cookies.pop("__user_agent__", None)
            cookies.pop("__meta__", None)
            return cookies, user_agent
        except:
            return None, None


async def get_fresh_cookies(headless: bool = True, save: bool = True) -> Optional[dict]:
    """Получить свежие cookies"""
    getter = GSMArenaStealthCookies()
    cookies = await getter.get_cookies(headless=headless)
    if cookies and save:
        getter.save_cookies(cookies)
    return cookies


def get_cookies_sync(headless: bool = True, save: bool = True) -> Optional[dict]:
    """Синхронная обёртка"""
    return asyncio.run(get_fresh_cookies(headless, save))


async def get_cookies_with_proxy(proxy: str = None, headless: bool = True, save: bool = True, timeout: int = 30) -> Optional[dict]:
    """Получить cookies через указанный прокси"""
    getter = GSMArenaStealthCookies()
    print(f"[COOKIES] Запуск браузера через прокси {proxy} (headless={headless})...")
    print(f"[COOKIES] User-Agent: {getter.user_agent[:60]}...")

    async with async_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            f"--window-size={getter.viewport['width']},{getter.viewport['height']}",
        ]

        # Настройка прокси
        proxy_settings = None
        if proxy:
            proxy_settings = {"server": f"http://{proxy}"}

        try:
            browser = await p.chromium.launch(
                headless=headless,
                args=launch_args,
                proxy=proxy_settings,
            )

            context = await browser.new_context(
                user_agent=getter.user_agent,
                viewport=getter.viewport,
                locale="en-US",
                timezone_id="America/New_York",
                color_scheme="light",
            )

            page = await context.new_page()

            if STEALTH_AVAILABLE:
                await stealth_async(page)
                print("[COOKIES] Stealth режим активирован")
            else:
                await getter._apply_manual_stealth(page)

            # Открываем главную
            print(f"[COOKIES] Открываю {TARGET_URL} через прокси...")
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
            await page.wait_for_timeout(random.randint(2000, 4000))

            # Скроллим
            await getter._human_scroll(page)

            # Переходим на makers
            print(f"[COOKIES] Открываю {TEST_URL}...")
            await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=timeout * 1000)
            await page.wait_for_timeout(random.randint(2000, 3000))

            # Проверяем что страница загрузилась
            content = await page.content()
            if "All brands" in content or "makers" in content.lower():
                print("[COOKIES] Страница загружена успешно через прокси!")
            else:
                print("[COOKIES] Предупреждение: возможно страница не загрузилась")

            # Ещё немного побродим
            await getter._human_scroll(page)
            await page.wait_for_timeout(random.randint(1000, 2000))

            # Получаем cookies
            cookies = await context.cookies()
            cookies_dict = {c["name"]: c["value"] for c in cookies}

            # Сохраняем User-Agent
            cookies_dict["__user_agent__"] = getter.user_agent

            print(f"[COOKIES] Получено {len(cookies_dict)} cookies через прокси")

            await browser.close()

            if save:
                getter.save_cookies(cookies_dict)

            return cookies_dict

        except Exception as e:
            print(f"[COOKIES] Ошибка получения cookies через прокси: {e}")
            return None


def get_cookies_with_proxy_sync(proxy: str = None, headless: bool = True, save: bool = True) -> Optional[dict]:
    """Синхронная обёртка для получения cookies через прокси"""
    return asyncio.run(get_cookies_with_proxy(proxy, headless, save))


if __name__ == "__main__":
    import sys
    headless = "--headless" in sys.argv or "-h" in sys.argv
    print(f"Headless: {headless}")
    cookies = get_cookies_sync(headless=headless)
    if cookies:
        print("\nCookies готовы!")
    else:
        print("\nОшибка!")
        sys.exit(1)
