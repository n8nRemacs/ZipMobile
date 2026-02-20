"""
CookieFetcher — получение cookies для сайтов через Playwright+Xvfb.
Запускается как подпроцесс через xvfb-run, результат читается из stdout.
Параллелизм ограничен через Semaphore(cookie_fetch_concurrency) из config.
"""
import asyncio
import json
import logging
import os
import sys
import tempfile
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.cookie_fetch_concurrency)
    return _semaphore


# Playwright-скрипт для green-spark.ru
# Пишет JSON в stdout (не в файл) для thread-safety
_GREENSPARK_SCRIPT = '''
import asyncio
import json
import sys

SHOP_ID = "{shop_id}"
PROXY_URL = "{proxy_url}"

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        launch_args = {{
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--ignore-certificate-errors",
            ],
        }}
        if PROXY_URL:
            launch_args["proxy"] = {{"server": PROXY_URL}}
        browser = await p.chromium.launch(**launch_args)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            viewport={{"width": 1920, "height": 1080}},
            locale="ru-RU",
            ignore_https_errors=True,
        )
        await context.add_cookies([
            {{"name": "magazine", "value": SHOP_ID, "domain": "green-spark.ru", "path": "/"}},
            {{"name": "global_magazine", "value": SHOP_ID, "domain": "green-spark.ru", "path": "/"}},
        ])
        page = await context.new_page()
        await page.add_init_script('Object.defineProperty(navigator, "webdriver", {{get: () => undefined}})')
        try:
            await page.goto(
                "https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception as e:
            pass
        await page.wait_for_timeout(7000)
        try:
            await page.goto(
                "https://green-spark.ru/local/api/catalog/products/?path[]=komplektuyushchie_dlya_remonta&perPage=10",
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception as e:
            pass
        await page.wait_for_timeout(3000)
        cookies = await context.cookies()
        cookies_dict = {{c["name"]: c["value"] for c in cookies}}
        cookies_dict["magazine"] = SHOP_ID
        cookies_dict["global_magazine"] = SHOP_ID
        cookies_dict["catalog-per-page"] = "100"
        print("COOKIES:" + json.dumps(cookies_dict, ensure_ascii=False))
        sys.stdout.flush()
        await browser.close()

asyncio.run(main())
'''

# shop_id по умолчанию: Москва (1008)
_DEFAULT_SHOP_ID = "1008"

# Конфиги сайтов: site_key → (script_template, shop_id)
_SITE_CONFIGS = {
    "greenspark": (_GREENSPARK_SCRIPT, _DEFAULT_SHOP_ID),
}


class CookieFetcher:
    """Получение cookies для сайтов через Playwright+Xvfb.

    Использует xvfb-run + subprocess для запуска Playwright с headless=False.
    Результат читается из stdout subprocess'а для thread-safety.
    """

    async def fetch_cookies(
        self,
        host: str,
        port: int,
        site_key: str = "greenspark",
        shop_id: str = _DEFAULT_SHOP_ID,
    ) -> Optional[dict]:
        """Получить cookies для site_key через прокси host:port.

        Returns dict с cookies или None при ошибке.
        """
        if site_key not in _SITE_CONFIGS:
            logger.warning(f"Unknown site_key: {site_key}")
            return None

        script_template, default_shop_id = _SITE_CONFIGS[site_key]
        effective_shop_id = shop_id or default_shop_id
        proxy_url = f"socks5://{host}:{port}"

        script_code = script_template.format(
            shop_id=effective_shop_id,
            proxy_url=proxy_url,
        )

        sem = _get_semaphore()
        async with sem:
            return await self._run_playwright(script_code, host, port, site_key)

    async def _run_playwright(
        self,
        script_code: str,
        host: str,
        port: int,
        site_key: str,
    ) -> Optional[dict]:
        """Запустить Playwright-скрипт как subprocess, вернуть cookies из stdout."""
        # Пишем скрипт во временный файл
        fd, script_path = tempfile.mkstemp(suffix=".py", prefix=f"cookie_{site_key}_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(script_code)

            cmd = ["xvfb-run", "--auto-servernum", sys.executable, script_path]
            logger.info(f"[CookieFetcher] Запуск Playwright для {site_key} через {host}:{port}")

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=settings.cookie_fetch_timeout,
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.communicate()
                    logger.warning(
                        f"[CookieFetcher] Таймаут {settings.cookie_fetch_timeout}с для {host}:{port}"
                    )
                    return None

                stdout_text = stdout.decode("utf-8", errors="replace")
                stderr_text = stderr.decode("utf-8", errors="replace")

                # Ищем маркер COOKIES: в stdout
                for line in stdout_text.splitlines():
                    if line.startswith("COOKIES:"):
                        json_str = line[len("COOKIES:"):]
                        try:
                            cookies = json.loads(json_str)
                            logger.info(
                                f"[CookieFetcher] OK: {site_key} через {host}:{port}, "
                                f"{len(cookies)} cookies"
                            )
                            return cookies
                        except json.JSONDecodeError as e:
                            logger.error(f"[CookieFetcher] JSON decode error: {e}, data={json_str[:200]}")
                            return None

                # Не нашли маркер — ошибка
                stderr_short = stderr_text[:400] if stderr_text else ""
                stdout_short = stdout_text[:200] if stdout_text else ""
                logger.warning(
                    f"[CookieFetcher] Нет COOKIES: маркера для {host}:{port}. "
                    f"stderr={stderr_short!r} stdout={stdout_short!r}"
                )
                return None

            except FileNotFoundError:
                logger.error("[CookieFetcher] xvfb-run не найден. Установите xvfb: apt install xvfb")
                return None
            except Exception as e:
                logger.error(f"[CookieFetcher] Исключение для {host}:{port}: {e}")
                return None
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass
