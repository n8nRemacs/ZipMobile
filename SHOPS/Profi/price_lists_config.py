#!/usr/bin/env python3
"""
Конфигурация всех прайс-листов Profi (siriust.ru)
Каждая запись содержит: URL, город, магазин, код outlet
"""

PRICE_LISTS = [
    # Москва
    {
        "url": "https://siriust.ru/club/price/Optovyy.xls",
        "city": "Москва",
        "shop": "Отдел оптовых продаж",
        "outlet_code": "profi-msk-opt"
    },
    {
        "url": "https://www.siriust.ru/club/price/Savelovo-1.xls",
        "city": "Москва",
        "shop": "Савеловский радиорынок",
        "outlet_code": "profi-msk-savelovo"
    },
    {
        "url": "https://www.siriust.ru/club/price/Mitino-%201.xls",
        "city": "Москва",
        "shop": "Митинский радиорынок",
        "outlet_code": "profi-msk-mitino"
    },
    {
        "url": "https://www.siriust.ru/club/price/Yuzhnyy.xls",
        "city": "Москва",
        "shop": "Радиокомплекс Южный",
        "outlet_code": "profi-msk-yuzhny"
    },
    # Санкт-Петербург
    {
        "url": "https://www.siriust.ru/club/price/Sankt-Peterburg-%201.xls",
        "city": "Санкт-Петербург",
        "shop": "СПб точка 1",
        "outlet_code": "profi-spb-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Sankt-Peterburg-%202.xls",
        "city": "Санкт-Петербург",
        "shop": "СПб точка 2",
        "outlet_code": "profi-spb-2"
    },
    # Адлер / Сочи
    {
        "url": "https://www.siriust.ru/club/price/Adler.xls",
        "city": "Адлер",
        "shop": "Профи Адлер",
        "outlet_code": "profi-adler"
    },
    # Архангельск
    {
        "url": "https://www.siriust.ru/club/price/Arkhangelsk.xls",
        "city": "Архангельск",
        "shop": "Профи Архангельск",
        "outlet_code": "profi-arkhangelsk"
    },
    # Астрахань
    {
        "url": "https://www.siriust.ru/club/price/Astraxan.xls",
        "city": "Астрахань",
        "shop": "Профи Астрахань",
        "outlet_code": "profi-astrakhan"
    },
    # Волгоград
    {
        "url": "https://www.siriust.ru/club/price/Volgograd.xls",
        "city": "Волгоград",
        "shop": "Профи Волгоград",
        "outlet_code": "profi-volgograd"
    },
    # Воронеж
    {
        "url": "https://www.siriust.ru/club/price/Voronezh.xls",
        "city": "Воронеж",
        "shop": "Профи Воронеж",
        "outlet_code": "profi-voronezh"
    },
    # Екатеринбург
    {
        "url": "https://www.siriust.ru/club/price/Ekaterinburg-%201.xls",
        "city": "Екатеринбург",
        "shop": "Екатеринбург точка 1",
        "outlet_code": "profi-ekb-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Ekaterinburg-%202.xls",
        "city": "Екатеринбург",
        "shop": "Екатеринбург точка 2",
        "outlet_code": "profi-ekb-2"
    },
    # Ижевск
    {
        "url": "https://www.siriust.ru/club/price/Izhevsk-%201.xls",
        "city": "Ижевск",
        "shop": "Ижевск точка 1",
        "outlet_code": "profi-izhevsk-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Izhevsk-%202.xls",
        "city": "Ижевск",
        "shop": "Ижевск точка 2",
        "outlet_code": "profi-izhevsk-2"
    },
    # Казань
    {
        "url": "https://www.siriust.ru/club/price/Kazan-%201.xls",
        "city": "Казань",
        "shop": "Казань точка 1",
        "outlet_code": "profi-kazan-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Kazan-%202.xls",
        "city": "Казань",
        "shop": "Казань точка 2",
        "outlet_code": "profi-kazan-2"
    },
    # Калининград
    {
        "url": "https://www.siriust.ru/club/price/Kaliningrad.xls",
        "city": "Калининград",
        "shop": "Профи Калининград",
        "outlet_code": "profi-kaliningrad"
    },
    # Краснодар
    {
        "url": "https://www.siriust.ru/club/price/Krasnodar-%201.xls",
        "city": "Краснодар",
        "shop": "Краснодар точка 1",
        "outlet_code": "profi-krasnodar-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Krasnodar-%202.xls",
        "city": "Краснодар",
        "shop": "Краснодар точка 2",
        "outlet_code": "profi-krasnodar-2"
    },
    # Красноярск
    {
        "url": "https://www.siriust.ru/club/price/Krasnoyarsk-%201.xls",
        "city": "Красноярск",
        "shop": "Красноярск точка 1",
        "outlet_code": "profi-krasnoyarsk-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Krasnoyarsk-%202.xls",
        "city": "Красноярск",
        "shop": "Красноярск точка 2",
        "outlet_code": "profi-krasnoyarsk-2"
    },
    # Нижний Новгород
    {
        "url": "https://www.siriust.ru/club/price/Nizhniy-Novgorod-%201.xls",
        "city": "Нижний Новгород",
        "shop": "Нижний Новгород точка 1",
        "outlet_code": "profi-nn-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Nizhniy-Novgorod-%202.xls",
        "city": "Нижний Новгород",
        "shop": "Нижний Новгород точка 2",
        "outlet_code": "profi-nn-2"
    },
    # Новосибирск
    {
        "url": "https://www.siriust.ru/club/price/Novosibirsk-%201.xls",
        "city": "Новосибирск",
        "shop": "Новосибирск точка 1",
        "outlet_code": "profi-nsk-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Novosibirsk-%202.xls",
        "city": "Новосибирск",
        "shop": "Новосибирск точка 2",
        "outlet_code": "profi-nsk-2"
    },
    # Омск
    {
        "url": "https://www.siriust.ru/club/price/Omsk.xls",
        "city": "Омск",
        "shop": "Профи Омск",
        "outlet_code": "profi-omsk"
    },
    # Пермь
    {
        "url": "https://www.siriust.ru/club/price/Perm-%201.xls",
        "city": "Пермь",
        "shop": "Пермь точка 1",
        "outlet_code": "profi-perm-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Perm-%202.xls",
        "city": "Пермь",
        "shop": "Пермь точка 2",
        "outlet_code": "profi-perm-2"
    },
    # Ростов-на-Дону
    {
        "url": "https://www.siriust.ru/club/price/Rostov-na-Donu-%201.xls",
        "city": "Ростов-на-Дону",
        "shop": "Ростов точка 1",
        "outlet_code": "profi-rostov-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Rostov-na-Donu-%202.xls",
        "city": "Ростов-на-Дону",
        "shop": "Ростов точка 2",
        "outlet_code": "profi-rostov-2"
    },
    # Самара
    {
        "url": "https://www.siriust.ru/club/price/Samara-%201.xls",
        "city": "Самара",
        "shop": "Самара точка 1",
        "outlet_code": "profi-samara-1"
    },
    {
        "url": "https://www.siriust.ru/club/price/Samara-%202.xls",
        "city": "Самара",
        "shop": "Самара точка 2",
        "outlet_code": "profi-samara-2"
    },
    # Саратов
    {
        "url": "https://www.siriust.ru/club/price/Saratov.xls",
        "city": "Саратов",
        "shop": "Профи Саратов",
        "outlet_code": "profi-saratov"
    },
    # Тюмень
    {
        "url": "https://www.siriust.ru/club/price/Tyumen.xls",
        "city": "Тюмень",
        "shop": "Профи Тюмень",
        "outlet_code": "profi-tyumen"
    },
    # Уфа
    {
        "url": "https://www.siriust.ru/club/price/Ufa.xls",
        "city": "Уфа",
        "shop": "Профи Уфа",
        "outlet_code": "profi-ufa"
    },
    # Челябинск
    {
        "url": "https://www.siriust.ru/club/price/Chelyabinsk.xls",
        "city": "Челябинск",
        "shop": "Профи Челябинск",
        "outlet_code": "profi-chelyabinsk"
    },
]

# Для быстрого доступа по URL
PRICE_LISTS_BY_URL = {p["url"]: p for p in PRICE_LISTS}

# Для быстрого доступа по outlet_code
PRICE_LISTS_BY_OUTLET = {p["outlet_code"]: p for p in PRICE_LISTS}


def get_all_urls():
    """Получить список всех URL"""
    return [p["url"] for p in PRICE_LISTS]


def get_info_by_url(url: str) -> dict:
    """Получить информацию о прайс-листе по URL"""
    return PRICE_LISTS_BY_URL.get(url, {"city": "Неизвестно", "shop": "Неизвестно", "outlet_code": None})


def get_info_by_outlet(outlet_code: str) -> dict:
    """Получить информацию о прайс-листе по outlet_code"""
    return PRICE_LISTS_BY_OUTLET.get(outlet_code, None)


def get_outlets_count():
    """Получить количество торговых точек"""
    return len(PRICE_LISTS)


def get_cities():
    """Получить уникальные города"""
    return list(set(p["city"] for p in PRICE_LISTS))
