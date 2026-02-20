"""
Конфигурация парсера Profi (Excel прайс-лист)
"""

# Исходный файл
SOURCE_FILE = "Profi Astrahan.xls"

# Пути к файлам
DATA_DIR = "data"
PRODUCTS_CSV = f"{DATA_DIR}/products.csv"
PRODUCTS_JSON = f"{DATA_DIR}/products.json"

# Структура Excel файла
HEADER_ROW = 14  # Строка с заголовками
DATA_START_ROW = 15  # Начало данных

# Индексы колонок (0-based)
COL_CODE = 2  # Код/Артикул
COL_BARCODE = 3  # Штрих-код
COL_NAME = 4  # Наименование
COL_AVAILABILITY = 5  # Наличие (* = в наличии)
COL_PRICE = 6  # Цена (Розница)
