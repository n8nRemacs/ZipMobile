"""
Конфигурация парсера GreenSpark.ru
"""

# URLs (можно использовать IP: 85.198.98.104)
HOST = "green-spark.ru"  # или "85.198.98.104"
BASE_URL = f"https://{HOST}"
API_URL = f"https://{HOST}/local/api"
PRODUCTS_ENDPOINT = "/catalog/products/"

# Корневая категория для парсинга
ROOT_CATEGORY = "komplektuyushchie_dlya_remonta"

# Настройки запросов
REQUEST_DELAY = 1.5  # Задержка между запросами (секунды)
REQUEST_TIMEOUT = 30  # Таймаут запроса (секунды)
PER_PAGE = 100  # Товаров на страницу

# Магазин по умолчанию
DEFAULT_SHOP_ID = 16344

# Пути к файлам
DATA_DIR = "data"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"
PRODUCTS_XLSX = f"{DATA_DIR}/products.xlsx"
ERRORS_LOG = f"{DATA_DIR}/errors.json"
CATEGORIES_JSON = f"{DATA_DIR}/categories.json"
