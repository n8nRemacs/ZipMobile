#!/usr/bin/env python3
"""
Moba.ru diagnostic script — максимальное логирование.
Сравнение direct vs proxy.

Usage:
    python3 moba_diag.py direct    # без прокси
    python3 moba_diag.py proxy     # через SOCKS5 прокси
"""
import asyncio
import sys
import time
import json
import httpx
from datetime import datetime

PROXY_SERVICE_URL = "http://localhost:8110"
SUBDOMAIN = "moba.ru"
CID = "9705"  # Москва/Митино
TARGET_PRODUCTS = 100

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

BROWSER_ARGS = [
    "--no-sandbox", "--disable-dev-shm-usage", "--lang=ru-RU,ru",
    "--disable-blink-features=AutomationControlled",
    "--ignore-certificate-errors",
    "--disable-gpu",
]

# Первая категория с большим кол-вом товаров
TEST_CATEGORY = "/catalog/displei/"


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}", flush=True)


def get_proxy():
    """Get SOCKS5 proxy from proxy-service."""
    try:
        r = httpx.get(f"{PROXY_SERVICE_URL}/proxy/get?protocol=socks5&for_site=moba", timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data, f"socks5://{data['host']}:{data['port']}"
        else:
            log(f"PROXY ERROR: status {r.status_code}")
            return None, None
    except Exception as e:
        log(f"PROXY ERROR: {e}")
        return None, None


async def run_diag(mode: str):
    log(f"=== ДИАГНОСТИКА MOBA.RU — режим: {mode.upper()} ===")
    log(f"Цель: {TARGET_PRODUCTS} товаров из категории 'Дисплеи', cid={CID}")

    proxy_url = None
    proxy_data = None
    if mode == "proxy":
        proxy_data, proxy_url = get_proxy()
        if not proxy_url:
            log("ABORT: не удалось получить прокси")
            return
        log(f"Прокси: {proxy_url}")
    else:
        log("Прямое подключение (без прокси)")

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        # ── 1. Запуск браузера ──
        log("--- ЭТАП 1: Запуск браузера ---")
        t0 = time.time()

        launch_kwargs = {"headless": True, "args": BROWSER_ARGS}
        if proxy_url:
            launch_kwargs["proxy"] = {"server": proxy_url}

        log(f"Launch args: headless=True, proxy={'yes: ' + proxy_url if proxy_url else 'no'}")
        browser = await pw.chromium.launch(**launch_kwargs)
        log(f"Браузер запущен за {time.time()-t0:.1f}s")

        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            user_agent=USER_AGENT,
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        await page.add_init_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        )

        # Логируем ВСЕ сетевые запросы и ответы
        request_log = []

        def on_request(req):
            request_log.append({
                "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "method": req.method,
                "url": req.url[:120],
                "type": req.resource_type,
            })

        def on_response(resp):
            log(f"  RESPONSE: {resp.status} {resp.url[:100]}")

        def on_request_failed(req):
            log(f"  FAILED: {req.url[:100]} — {req.failure}")

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_request_failed)

        # ── 2. Навигация на главную (SmartCaptcha) ──
        log("")
        log("--- ЭТАП 2: Навигация на moba.ru (SmartCaptcha) ---")
        base = f"https://{SUBDOMAIN}"
        t1 = time.time()
        try:
            resp = await page.goto(base, wait_until="domcontentloaded", timeout=30_000)
            log(f"goto() завершён за {time.time()-t1:.1f}s")
            if resp:
                log(f"  HTTP status: {resp.status}")
                headers = await resp.all_headers()
                log(f"  Response headers: {json.dumps(dict(list(headers.items())[:15]), ensure_ascii=False)}")
            else:
                log("  resp = None")
        except Exception as e:
            log(f"goto() ОШИБКА за {time.time()-t1:.1f}s: {e}")
            await browser.close()
            return

        # Ждём SmartCaptcha
        log("Ожидание SmartCaptcha (7s)...")
        await page.wait_for_timeout(7000)

        # Проверяем результат
        html = await page.content()
        html_len = len(html)
        log(f"HTML длина: {html_len}")
        log(f"HTML первые 500 символов:")
        # Убираем переносы для компактности
        snippet = html[:500].replace("\n", " ").replace("\r", "")
        log(f"  {snippet}")

        # Проверяем индикаторы
        indicators = ["каталог", "catalog", "main_item_wrapper", "корзин", "smartcaptcha", "captcha"]
        for ind in indicators:
            found = ind in html.lower()
            log(f"  '{ind}' в HTML: {found}")

        # Куки
        cookies = await ctx.cookies()
        log(f"Cookies ({len(cookies)}):")
        for c in cookies:
            log(f"  {c['name']}={c['value'][:50]}... domain={c['domain']} path={c['path']}")

        # SmartCaptcha ещё не прошла?
        success_indicators = ["каталог", "catalog", "main_item_wrapper", "корзин"]
        captcha_passed = any(s in html.lower() for s in success_indicators)

        if not captcha_passed:
            log("SmartCaptcha НЕ пройдена, ждём ещё 25с...")
            for wait in range(5):
                await page.wait_for_timeout(5000)
                html = await page.content()
                captcha_passed = any(s in html.lower() for s in success_indicators)
                log(f"  Попытка {wait+2}: captcha_passed={captcha_passed}, html_len={len(html)}")
                if captcha_passed:
                    break

        if not captcha_passed:
            log("ABORT: SmartCaptcha не пройдена после 32с")
            log(f"HTML title: {await page.title()}")
            log(f"HTML body[:300]: {html[:300]}")
            await browser.close()
            return

        log(f"SmartCaptcha OK! Обновляем куки...")
        cookies = await ctx.cookies()
        log(f"Cookies после SmartCaptcha ({len(cookies)}):")
        for c in cookies:
            log(f"  {c['name']}={c['value'][:50]}... domain={c['domain']}")

        # ── 3. Парсинг категории ──
        log("")
        log("--- ЭТАП 3: Парсинг категории 'Дисплеи' ---")

        total_products = 0
        page_num = 0

        while total_products < TARGET_PRODUCTS:
            page_num += 1
            url = f"{base}{TEST_CATEGORY}?cid={CID}"
            if page_num > 1:
                url += f"&PAGEN_1={page_num}"

            log(f"")
            log(f"Страница {page_num}: {url}")
            t2 = time.time()

            try:
                resp2 = await page.goto(url, wait_until="commit", timeout=60_000)
                elapsed = time.time() - t2
                log(f"  goto() за {elapsed:.1f}s")
                if resp2:
                    log(f"  HTTP status: {resp2.status}")
                    h2 = await resp2.all_headers()
                    ct = h2.get("content-type", "?")
                    cl = h2.get("content-length", "?")
                    log(f"  content-type: {ct}, content-length: {cl}")
                else:
                    log(f"  resp = None")
            except Exception as e:
                log(f"  goto() ОШИБКА за {time.time()-t2:.1f}s: {e}")
                break

            await page.wait_for_timeout(2000)
            html = await page.content()
            log(f"  HTML длина: {len(html)}")

            # Ищем товары
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            items = soup.select("tr.item.main_item_wrapper")
            log(f"  Найдено tr.item.main_item_wrapper: {len(items)}")

            if not items:
                for sel in ["div.catalog-item", "div.item-card", "div.product-item"]:
                    items = soup.select(sel)
                    if items:
                        log(f"  Найдено {sel}: {len(items)}")
                        break

            if not items:
                log(f"  НЕТ ТОВАРОВ на странице!")
                # Покажем HTML-фрагмент для диагностики
                body = soup.find("body")
                if body:
                    body_text = body.get_text(" ", strip=True)[:300]
                    log(f"  Body text[:300]: {body_text}")
                # Проверяем на бан/капчу
                for kw in ["captcha", "smartcaptcha", "blocked", "banned", "403", "429"]:
                    if kw in html.lower():
                        log(f"  WARNING: '{kw}' найден в HTML!")
                break

            # Считаем товары
            page_products = 0
            for item in items:
                for a in item.find_all("a", href=True):
                    href = a.get("href", "")
                    if href.startswith("/catalog/") and href.count("/") >= 3:
                        text = a.get_text(strip=True)
                        if text and len(text) > 5:
                            parts = href.rstrip("/").split("/")
                            pid = parts[-1] if parts[-1].isdigit() else None
                            if pid:
                                page_products += 1
                                if total_products + page_products <= 3:
                                    log(f"  Товар: MOBA-{pid} '{text[:60]}'")
                                break

            total_products += page_products
            log(f"  +{page_products} товаров (total: {total_products})")

            # Проверяем пагинацию
            has_next = bool(soup.find("a", class_="flex-next") or
                          soup.find("a", class_="next") or
                          soup.find_all("a", href=lambda h: h and f"PAGEN_1={page_num+1}" in h))
            log(f"  Следующая страница: {has_next}")

            if not has_next:
                log("  Последняя страница")
                break

            await asyncio.sleep(1.5)

        log("")
        log(f"=== ИТОГО: {total_products} товаров за {page_num} страниц ===")
        log(f"Всего сетевых запросов: {len(request_log)}")

        await browser.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    if mode not in ("direct", "proxy"):
        print("Usage: python3 moba_diag.py [direct|proxy]")
        sys.exit(1)
    asyncio.run(run_diag(mode))
