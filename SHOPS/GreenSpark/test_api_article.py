"""Проверка артикула через API для товара без артикула"""
import sys
sys.path.insert(0, '.')
from parser_v3 import GreenSparkParser

# Товар без артикула из списка
test_url = "https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/zapchasti_dlya_apple/zvonki_dinamiki_vibro/vibro_dlya_iphone_5.html"

print(f"Тестируем: {test_url}")
print("=" * 60)

# Создаём парсер и инициализируем клиент
parser = GreenSparkParser(shop_id=16344)
parser.init_client()
print("Клиент инициализирован")

# Пробуем получить артикул
article = parser.fetch_article_from_api(test_url)

print(f"\nРезультат: {article if article else 'Артикул не найден'}")

# Теперь проверим товар который точно имеет артикул
print("\n" + "=" * 60)
print("Контрольная проверка товара с артикулом:")
test_url2 = "https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/zapchasti_dlya_mobilnykh_ustroystv/displei_2/dlya_nokia/displey_dlya_nokia_520_525_510.html"
print(f"URL: {test_url2}")

article2 = parser.fetch_article_from_api(test_url2)
print(f"Результат: {article2 if article2 else 'Артикул не найден'}")
