"""
Конфигурация парсера Liberti.ru (Liberty Project)
"""

BASE_URL = "https://liberti.ru"
CATALOG_URL = f"{BASE_URL}/catalog"

# Корневые категории для парсинга
ROOT_CATEGORIES = [
    "zapchasti",  # Парсим всё от корня и вглубь
]

# Настройки парсера
ITEMS_PER_PAGE = 48
MAX_PAGES = 100
REQUEST_DELAY = 0.3
REQUEST_TIMEOUT = 30

# User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Файлы данных
DATA_DIR = "data"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"
