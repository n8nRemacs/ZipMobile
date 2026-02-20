"""
Конфигурация парсера MemsTech.ru
"""

BASE_URL = "https://memstech.ru"
CATALOG_URL = f"{BASE_URL}/catalog"

# Корневые категории для парсинга
ROOT_CATEGORIES = [
    "voltpack",      # VoltPack
    "iphone",        # iPhone
    "android",       # Android
    "ipad",          # iPad
    "macbook",       # MacBook
    "watch",         # Watch
    "noutbuki",      # Ноутбуки
]

# Настройки парсера
ITEMS_PER_PAGE = 30
MAX_PAGES = 100  # Максимум страниц на категорию
REQUEST_DELAY = 0.3  # Задержка между запросами (секунды)
REQUEST_TIMEOUT = 30  # Таймаут запроса (секунды)

# User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Файлы данных
DATA_DIR = "data"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"
