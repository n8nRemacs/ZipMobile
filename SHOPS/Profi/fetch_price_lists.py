#!/usr/bin/env python3
"""
Модуль для динамического получения списка прайс-листов с сайта siriust.ru
"""
import re
import httpx
from html.parser import HTMLParser
from urllib.parse import urljoin, unquote

PRICE_LISTS_PAGE = "https://siriust.ru/prays-listy/"


class PriceListParser(HTMLParser):
    """Парсер HTML для извлечения ссылок на .xls файлы"""
    def __init__(self):
        super().__init__()
        self.links = []
        self.in_link = False
        self.link_text = ""
        self.link_href = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            if ".xls" in href.lower():
                self.in_link = True
                self.link_href = href
                self.link_text = ""

    def handle_endtag(self, tag):
        if tag == "a" and self.in_link:
            self.in_link = False
            if self.link_href and self.link_text.strip():
                self.links.append({"url": self.link_href, "text": self.link_text.strip()})

    def handle_data(self, data):
        if self.in_link:
            self.link_text += data


# Карта URL → город, магазин
CITY_MAP = {
    "optovyy": ("Москва", "Отдел оптовых продаж"),
    "savelovo": ("Москва", "Савеловский радиорынок"),
    "mitino": ("Москва", "Митинский радиорынок"),
    "yuzhnyy": ("Москва", "Радиокомплекс Южный"),
    "sankt-peterburg": ("Санкт-Петербург", None),
    "adler": ("Адлер", "Профи Адлер"),
    "arxangelsk": ("Архангельск", "Профи Архангельск"),
    "astraxan": ("Астрахань", "Профи Астрахань"),
    "volgograd": ("Волгоград", "Профи Волгоград"),
    "voronezh": ("Воронеж", "Профи Воронеж"),
    "ekaterinburg": ("Екатеринбург", None),
    "izhevsk": ("Ижевск", "Профи Ижевск"),
    "kazan": ("Казань", None),
    "kaliningrad": ("Калининград", "Профи Калининград"),
    "kemerovo": ("Кемерово", "Профи Кемерово"),
    "kostroma": ("Кострома", "Профи Кострома"),
    "krasnodar": ("Краснодар", None),
    "naberezhnye chelny": ("Набережные Челны", "Профи Набережные Челны"),
    "nizhniy novgorod": ("Нижний Новгород", "Профи Нижний Новгород"),
    "omsk": ("Омск", "Профи Омск"),
    "orenburg": ("Оренбург", "Профи Оренбург"),
    "penza": ("Пенза", "Профи Пенза"),
    "perm": ("Пермь", "Профи Пермь"),
    "rostov-na-donu": ("Ростов-на-Дону", "Профи Ростов"),
    "ryazan": ("Рязань", "Профи Рязань"),
    "samara": ("Самара", None),
    "saratov": ("Саратов", "Профи Саратов"),
    "smolensk": ("Смоленск", "Профи Смоленск"),
    "stavropol": ("Ставрополь", "Профи Ставрополь"),
    "tolyatti": ("Тольятти", "Профи Тольятти"),
    "tyumen": ("Тюмень", "Профи Тюмень"),
    "ufa": ("Уфа", "Профи Уфа"),
    "cheboksary": ("Чебоксары", "Профи Чебоксары"),
    "chelyabinsk": ("Челябинск", None),
    "cherepovets": ("Череповец", "Профи Череповец"),
    "yaroslavl": ("Ярославль", "Профи Ярославль"),
}


def extract_city_from_url(url: str) -> tuple:
    """Извлечь город и магазин из URL файла"""
    filename = url.split("/")[-1].replace(".xls", "").split("?")[0]  # Убираем query string
    filename = unquote(filename)
    filename = re.sub(r'[-\s%20]*\d+$', '', filename)  # Убираем номер точки

    # Нормализуем для сравнения: lowercase, пробелы вместо дефисов
    filename_lower = filename.lower().replace("-", " ").replace("_", " ").strip()

    for key, (city, shop) in CITY_MAP.items():
        # Нормализуем ключ так же
        key_normalized = key.replace("-", " ")
        if key_normalized in filename_lower:
            return city, shop

    # Fallback: Title Case из имени файла
    return filename.replace("-", " ").replace("_", " ").title(), None


def fetch_price_lists() -> list:
    """Получить актуальный список прайс-листов с сайта"""
    print(f"[INFO] Fetching price lists from {PRICE_LISTS_PAGE}...")

    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(PRICE_LISTS_PAGE)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        print(f"[ERROR] Failed to fetch price lists page: {e}")
        return []

    parser = PriceListParser()
    parser.feed(html)

    price_lists = []
    seen_urls = set()

    for link in parser.links:
        url = link["url"]
        if not url.startswith("http"):
            url = urljoin(PRICE_LISTS_PAGE, url)

        if url in seen_urls:
            continue
        seen_urls.add(url)

        city, shop = extract_city_from_url(url)
        if not shop:
            match = re.search(r'[-\s%20]*(\d+)\.xls', url)
            num = match.group(1) if match else ""
            shop = f"{city} точка {num}" if num else f"Профи {city}"

        price_lists.append({"url": url, "city": city, "shop": shop})

    print(f"[INFO] Found {len(price_lists)} price lists on site")
    return price_lists


def get_info_by_url(url: str) -> dict:
    """Получить информацию о прайс-листе по URL"""
    city, shop = extract_city_from_url(url)
    if not shop:
        shop = f"Профи {city}"
    return {"city": city, "shop": shop}


if __name__ == "__main__":
    # Тест
    price_lists = fetch_price_lists()
    for pl in price_lists:
        print(f"  {pl['city']} - {pl['shop']}: {pl['url']}")
