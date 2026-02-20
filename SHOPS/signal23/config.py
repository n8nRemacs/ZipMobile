"""
Конфигурация парсера Signal23.ru
"""

# URL источника
BASE_URL = "https://signal23.ru"

# Стартовые категории для парсинга
START_CATEGORIES = [
    "/zapchasti-dlya-telefonov/",
    "/zapchasti-dlya-planshetov/",
    "/zapchasti-dlya-noutbukov/",
    "/zapchasti-dlya-pk/",
]

# Параметры запросов
REQUEST_DELAY = 0.3          # Задержка между запросами (сек)
REQUEST_TIMEOUT = 30         # Таймаут запроса (сек)
MAX_RETRIES = 3              # Количество повторов
ITEMS_PER_PAGE = 100         # Товаров на странице (макс)

# User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

# Выходные файлы
DATA_DIR = "data"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
CATEGORIES_JSON = f"{DATA_DIR}/categories.json"
ERRORS_LOG = f"{DATA_DIR}/errors.json"
