"""
Конфигурация парсера 05GSM.ru
"""

# URLs
BASE_URL = "https://05gsm.ru"
SITEMAP_INDEX = f"{BASE_URL}/sitemap.xml"
SITEMAP_PRODUCTS = f"{BASE_URL}/sitemap-iblock-44.xml"  # Основной каталог товаров

# Настройки запросов
REQUEST_DELAY = 0.5  # Задержка между запросами (секунды)
REQUEST_TIMEOUT = 30  # Таймаут запроса (секунды)
MAX_RETRIES = 3  # Количество повторных попыток
CONCURRENT_REQUESTS = 5  # Параллельные запросы

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Пути к файлам
DATA_DIR = "data"
SITEMAP_CACHE = f"{DATA_DIR}/sitemap_urls.json"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"
ERRORS_LOG = f"{DATA_DIR}/errors.json"

# Фильтры URL (regex)
PRODUCT_URL_PATTERN = r"/catalog/(\d+)/$"  # Числовой ID товара
CATEGORY_URL_PATTERN = r"/catalog/[a-z_]+/"  # Категории (символьные)
