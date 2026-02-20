"""
Получение cookies через Playwright для обхода JS-защиты GreenSpark
"""
import json
import asyncio
from playwright.async_api import async_playwright

COOKIES_FILE = "cookies.json"
TARGET_URL = "https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/"
SHOP_ID = "16344"  # ID магазина (Астрахань)


async def get_cookies(headless: bool = False):
    """Получить cookies через браузер"""
    print("Запуск браузера..." + (" (headless)" if headless else " (видимый)"))

    async with async_playwright() as p:
        # Запускаем браузер
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 YaBrowser/24.12.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
        )

        # Устанавливаем cookies магазина заранее
        await context.add_cookies([
            {"name": "magazine", "value": SHOP_ID, "domain": "green-spark.ru", "path": "/"},
            {"name": "global_magazine", "value": SHOP_ID, "domain": "green-spark.ru", "path": "/"},
            {"name": "catalog-per-page", "value": "100", "domain": "green-spark.ru", "path": "/"},
        ])

        page = await context.new_page()

        # Убираем признаки автоматизации
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """)

        print(f"Открываю {TARGET_URL}...")
        await page.goto(TARGET_URL, wait_until="domcontentloaded")

        # Ждём пока JS-защита пройдёт
        print("Ожидание загрузки (5 сек)...")
        await page.wait_for_timeout(5000)

        # Делаем запрос к API чтобы активировать сессию
        print("Активация сессии через API...")
        await page.goto(
            f"https://green-spark.ru/local/api/catalog/products/?path[]=komplektuyushchie_dlya_remonta&perPage=10",
            wait_until="domcontentloaded"
        )
        await page.wait_for_timeout(2000)

        # Возвращаемся на страницу каталога
        await page.goto(TARGET_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Получаем cookies
        cookies = await context.cookies()

        # Преобразуем в простой dict
        cookies_dict = {}
        for cookie in cookies:
            cookies_dict[cookie["name"]] = cookie["value"]

        # Добавляем магазин если нет
        cookies_dict["magazine"] = SHOP_ID
        cookies_dict["global_magazine"] = SHOP_ID
        cookies_dict["catalog-per-page"] = "100"

        # Сохраняем
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies_dict, f, ensure_ascii=False, indent=2)

        print(f"\nСохранено {len(cookies_dict)} cookies в {COOKIES_FILE}")
        print(f"Ключевые: {[k for k in cookies_dict.keys() if k.startswith('__') or k == 'PHPSESSID']}")

        await browser.close()

    return cookies_dict


def main():
    import sys
    headless = "--headless" in sys.argv or "-h" in sys.argv

    cookies = asyncio.run(get_cookies(headless=headless))
    print("\nCookies готовы! Запускайте парсер:")
    print("  python parser.py")


if __name__ == "__main__":
    main()
