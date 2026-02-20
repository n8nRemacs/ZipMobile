"""Debug API response for article - correct path format"""
import sys
sys.path.insert(0, '.')
import re
from parser_v3 import GreenSparkParser

# Товар с известным артикулом
test_url = "https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/zapchasti_dlya_mobilnykh_ustroystv/displei_2/dlya_nokia/displey_dlya_nokia_520_525_510.html"

print(f"URL: {test_url}")
print("=" * 70)

# Создаём парсер
parser = GreenSparkParser(shop_id=16344)
parser.init_client()
print("Клиент инициализирован\n")

# Используем метод парсера для получения артикула
article = parser.fetch_article_from_api(test_url)
print(f"fetch_article_from_api: '{article}'")

# Тест через HTML fallback
article2 = parser.fetch_article_from_page(test_url)
print(f"fetch_article_from_page: '{article2}'")

# Теперь проверим товар без артикула в БД
print("\n" + "=" * 70)
print("Проверка товара без артикула в БД:")
test_url2 = "https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/zapchasti_dlya_apple/zvonki_dinamiki_vibro/vibro_dlya_iphone_5.html"
print(f"URL: {test_url2}")

article3 = parser.fetch_article_from_api(test_url2)
print(f"fetch_article_from_api: '{article3}'")

article4 = parser.fetch_article_from_page(test_url2)
print(f"fetch_article_from_page: '{article4}'")
