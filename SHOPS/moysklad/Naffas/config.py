"""
Конфигурация парсера NAFFAS (b2b.moysklad.ru)
"""

# API
CATALOG_ID = "S1AlNWEsMzM7"
API_URL = f"https://b2b.moysklad.ru/desktop-api/public/{CATALOG_ID}/products.json"

# Пути к файлам
DATA_DIR = "data"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"
