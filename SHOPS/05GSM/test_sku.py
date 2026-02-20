"""Тест парсинга артикула"""
from parser import Parser05GSM
import json

p = Parser05GSM()
product = p.parse_product_page('https://05gsm.ru/catalog/37539/')
print(json.dumps(product, ensure_ascii=False, indent=2))
