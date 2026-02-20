#!/usr/bin/env python3
"""
Automated moba.ru cookie capture via headless Chrome.

Uses Playwright with stealth to navigate moba.ru, handle Yandex SmartCaptcha,
and save cookies for use by moba_full_parser.py (curl_cffi).

Strategies (tried in order):
  1. Stealth browser — auto-pass invisible SmartCaptcha via JS checks
  2. Checkbox click — find and click SmartCaptcha checkbox if present
  3. 2captcha API — external service solves the challenge (requires API key)

Requirements:
    pip install playwright playwright-stealth
    playwright install chromium
    playwright install-deps          # system libs on Linux

Usage:
    python auto_cookies.py                       # capture cookies
    python auto_cookies.py --validate            # just check existing cookies
    python auto_cookies.py --force               # recapture even if valid
    python auto_cookies.py --twocaptcha KEY      # use 2captcha for challenge
    python auto_cookies.py --headed              # visible browser (debug)
"""
import asyncio
import json
import os
import re
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("auto_cookies")

SCRIPT_DIR = Path(__file__).resolve().parent
COOKIES_FILE = SCRIPT_DIR / "moba_cookies.json"
SCREENSHOTS_DIR = SCRIPT_DIR / "screenshots"
TARGET_URL = "https://moba.ru/"

# Detect SmartCaptcha on page
CAPTCHA_INDICATORS = [
    "smartcaptcha",
    "smart-captcha",
    "captcha-container",
    "CheckboxCaptcha",
    "AdvancedCaptcha",
    "captcha__image",
    "captcha__checkbox",
    "showcaptcha",
]

# Detect successful moba.ru page
SUCCESS_INDICATORS = [
    "каталог",
    "корзин",
    "запчаст",
    "аккумулятор",
    "main_item_wrapper",
    "catalog",
]


# ─── cookie validation ────────────────────────────────────────────────

def validate_cookies(cookies_path: str = None) -> bool:
    """Check if saved cookies still grant access to moba.ru (via curl_cffi)."""
    path = Path(cookies_path) if cookies_path else COOKIES_FILE
    if not path.exists():
        log.warning("No cookies file: %s", path)
        return False

    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        log.warning("curl_cffi not installed — skipping validation")
        return True

    with open(path) as f:
        cookies = json.load(f)
    if not cookies:
        log.warning("Cookies file is empty")
        return False

    session = curl_requests.Session(impersonate="chrome120")
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".moba.ru")
    try:
        resp = session.get(TARGET_URL, timeout=15, allow_redirects=True)
        lower = resp.text.lower()
        if resp.status_code != 200:
            log.warning("Validation: HTTP %s", resp.status_code)
            return False
        if "captcha" in resp.url.lower() or any(c in lower[:3000] for c in CAPTCHA_INDICATORS):
            log.warning("Validation: still getting captcha")
            return False
        if any(s in lower for s in SUCCESS_INDICATORS):
            log.info("Cookies valid (catalog page returned)")
            return True
        log.warning("Validation: page loaded but doesn't look like moba.ru")
        return False
    except Exception as e:
        log.error("Validation error: %s", e)
        return False
    finally:
        session.close()


# ─── cookie extraction ────────────────────────────────────────────────

async def _extract_cookies(context) -> dict:
    """Pull all moba.ru cookies from the Playwright browser context."""
    raw = await context.cookies(["https://moba.ru", "https://www.moba.ru"])
    d = {c["name"]: c["value"] for c in raw}
    log.info("Extracted %d browser cookies", len(d))
    return d


def _save(cookies: dict, path: Path = None):
    path = path or COOKIES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    log.info("Saved %d cookies → %s", len(cookies), path)


def _screenshot(page, name: str):
    """Async helper — returns a coroutine."""
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    return page.screenshot(path=str(SCREENSHOTS_DIR / name))


def _is_captcha(content: str, url: str) -> bool:
    lower = content.lower()
    return (
        "captcha" in url.lower()
        or any(ind in lower for ind in CAPTCHA_INDICATORS)
    )


def _is_success(content: str) -> bool:
    lower = content.lower()
    return any(ind in lower for ind in SUCCESS_INDICATORS)


# ─── SmartCaptcha solving ─────────────────────────────────────────────

async def _try_auto_solve(page, context) -> dict | None:
    """Strategy 1: wait for JS-based invisible captcha to auto-solve."""
    log.info("[strat-1] Waiting 8 s for invisible captcha auto-solve ...")
    await page.wait_for_timeout(8000)
    content = await page.content()
    if _is_success(content):
        log.info("[strat-1] Auto-solved!")
        return await _extract_cookies(context)
    return None


async def _try_checkbox(page, context) -> dict | None:
    """Strategy 2: click SmartCaptcha checkbox in iframe or page."""
    log.info("[strat-2] Looking for captcha checkbox ...")

    # Look inside iframes
    for frame in page.frames:
        url = frame.url or ""
        if "captcha" not in url.lower() and "smart" not in url.lower():
            continue
        log.info("  Found captcha frame: %s", url[:120])
        for sel in [
            ".CheckboxCaptcha-Button",
            ".CheckboxCaptcha-Anchor",
            "input[type='checkbox']",
            "button",
        ]:
            try:
                el = await frame.wait_for_selector(sel, timeout=2000)
                if el:
                    log.info("  Clicking %s in captcha frame ...", sel)
                    await el.click()
                    await page.wait_for_timeout(6000)
                    content = await page.content()
                    if _is_success(content):
                        log.info("[strat-2] Checkbox solved captcha!")
                        return await _extract_cookies(context)
            except Exception:
                pass

    # Try main page selectors
    for sel in [
        ".CheckboxCaptcha-Button",
        ".smartcaptcha button",
        "[data-captcha] button",
        ".captcha__checkbox",
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                log.info("  Clicking %s on page ...", sel)
                await el.click()
                await page.wait_for_timeout(6000)
                content = await page.content()
                if _is_success(content):
                    log.info("[strat-2] Button click solved captcha!")
                    return await _extract_cookies(context)
        except Exception:
            pass

    return None


async def _try_2captcha(page, context, api_key: str) -> dict | None:
    """Strategy 3: solve SmartCaptcha via 2captcha.com API."""
    import aiohttp

    log.info("[strat-3] Using 2captcha API ...")
    content = await page.content()

    # Find sitekey
    sitekey = None
    for pat in [
        r'data-sitekey="([^"]+)"',
        r"sitekey['\"]?\s*[:=]\s*['\"]([^'\"]+)",
        r'"sitekey"\s*:\s*"([^"]+)"',
    ]:
        m = re.search(pat, content, re.IGNORECASE)
        if m:
            sitekey = m.group(1)
            break

    if not sitekey:
        log.error("[strat-3] Cannot find SmartCaptcha sitekey")
        with open(SCREENSHOTS_DIR / "captcha_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        return None

    log.info("  sitekey: %s", sitekey)

    async with aiohttp.ClientSession() as sess:
        # Submit
        r = await sess.post(
            "https://2captcha.com/in.php",
            data={
                "key": api_key,
                "method": "yandex",
                "sitekey": sitekey,
                "pageurl": page.url,
                "json": "1",
            },
        )
        body = await r.json(content_type=None)
        if body.get("status") != 1:
            log.error("  2captcha submit error: %s", body)
            return None
        task_id = body["request"]
        log.info("  2captcha task: %s", task_id)

        # Poll (max ~150 s)
        result_url = (
            f"https://2captcha.com/res.php?key={api_key}&action=get&id={task_id}&json=1"
        )
        for attempt in range(30):
            await asyncio.sleep(5)
            r = await sess.get(result_url)
            body = await r.json(content_type=None)
            if body.get("status") == 1:
                token = body["request"]
                log.info("  Got token: %s...", token[:40])

                # Inject token and submit
                await page.evaluate(
                    """(token) => {
                    const inp = document.querySelector(
                        'input[name="smart-token"],'
                        + 'input[name="smartcaptcha-token"],'
                        + '[name*="captcha-token"]'
                    );
                    if (inp) inp.value = token;
                    if (typeof window.onSmartCaptchaSuccess === 'function')
                        window.onSmartCaptchaSuccess(token);
                    const form = document.querySelector('form');
                    if (form) form.submit();
                }""",
                    token,
                )
                await page.wait_for_timeout(6000)
                content = await page.content()
                if _is_success(content):
                    log.info("[strat-3] 2captcha solved!")
                    return await _extract_cookies(context)
                log.warning("  Token injected but page unchanged")
                await _screenshot(page, "05_after_2captcha.png")
                return None
            elif "CAPCHA_NOT_READY" in str(body.get("request", "")):
                continue
            else:
                log.error("  2captcha poll error: %s", body)
                return None

    log.error("  2captcha timeout")
    return None


# ─── main capture flow ────────────────────────────────────────────────

async def capture(
    twocaptcha_key: str = None,
    headless: bool = True,
) -> dict:
    """
    Open moba.ru in a stealth browser, handle SmartCaptcha, return cookies.
    """
    from playwright.async_api import async_playwright

    try:
        from playwright_stealth import stealth_async
        _has_stealth = True
    except ImportError:
        log.warning("playwright-stealth not installed — running without stealth")
        _has_stealth = False

    SCREENSHOTS_DIR.mkdir(exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--lang=ru-RU,ru",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
        )
        page = await context.new_page()

        if _has_stealth:
            await stealth_async(page)

        try:
            log.info("Navigating to %s ...", TARGET_URL)
            resp = await page.goto(
                TARGET_URL, wait_until="domcontentloaded", timeout=30_000
            )
            log.info("HTTP %s  url=%s", resp.status if resp else "?", page.url)
            await page.wait_for_timeout(3000)
            await _screenshot(page, "01_initial.png")

            content = await page.content()

            # ── already on the real page? ──
            if _is_success(content):
                log.info("No captcha — page loaded directly")
                return await _extract_cookies(context)

            # ── captcha flow ──
            if _is_captcha(content, page.url):
                log.info("SmartCaptcha detected on page")
            else:
                log.info("Page loaded but doesn't look like catalog or captcha, waiting ...")
                await page.wait_for_timeout(5000)
                content = await page.content()
                await _screenshot(page, "02_after_extra_wait.png")
                if _is_success(content):
                    return await _extract_cookies(context)

            # Strategy 1
            cookies = await _try_auto_solve(page, context)
            if cookies:
                return cookies
            await _screenshot(page, "03_after_auto.png")

            # Strategy 2
            cookies = await _try_checkbox(page, context)
            if cookies:
                return cookies
            await _screenshot(page, "04_after_checkbox.png")

            # Strategy 3
            if twocaptcha_key:
                cookies = await _try_2captcha(page, context, twocaptcha_key)
                if cookies:
                    return cookies
            else:
                log.warning(
                    "SmartCaptcha challenge — need 2captcha key.  "
                    "Run: python auto_cookies.py --twocaptcha YOUR_KEY"
                )

            await _screenshot(page, "99_failed.png")
            log.error("All strategies exhausted. Check screenshots/ for details.")
            return {}

        finally:
            await browser.close()


# ─── CLI ──────────────────────────────────────────────────────────────

async def amain():
    ap = argparse.ArgumentParser(description="Auto moba.ru cookie capture")
    ap.add_argument("--validate", action="store_true", help="Only validate existing cookies")
    ap.add_argument("--force", action="store_true", help="Force recapture")
    ap.add_argument("--twocaptcha", type=str, metavar="KEY", help="2captcha.com API key")
    ap.add_argument("--headed", action="store_true", help="Visible browser (debug)")
    ap.add_argument("--output", type=str, help="Output cookies file path")
    args = ap.parse_args()

    out = Path(args.output) if args.output else COOKIES_FILE

    if args.validate:
        ok = validate_cookies(str(out))
        sys.exit(0 if ok else 1)

    if not args.force and out.exists():
        log.info("Cookies file exists — validating ...")
        if validate_cookies(str(out)):
            log.info("Cookies are still valid, nothing to do")
            sys.exit(0)
        log.info("Cookies expired or invalid — recapturing ...")

    cookies = await capture(
        twocaptcha_key=args.twocaptcha,
        headless=not args.headed,
    )
    if not cookies:
        log.error("FAILED to capture cookies")
        sys.exit(1)

    _save(cookies, out)

    if validate_cookies(str(out)):
        log.info("SUCCESS — cookies captured and validated")
    else:
        log.warning("Cookies saved but curl_cffi validation failed (might still work in browser)")

    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(amain())
