"""
API JSON Extractor

Извлечение данных из JSON API ответов.
Поддерживает JSONPath-подобные выражения для навигации.
"""

import re
import json
import httpx
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urlencode


class ApiJsonExtractor:
    """Извлекатель данных из JSON API"""

    def __init__(self, config):
        """
        Args:
            config: ParserConfig с api_config и json_paths
        """
        self.config = config
        self.api_config = config.api_config
        self.json_paths = config.json_paths

    def build_api_url(self, product_url: str) -> Optional[str]:
        """
        Построить URL для API запроса из URL товара.

        Использует api_config:
        - base_url: базовый URL API
        - detail_endpoint: эндпоинт для детальной информации
        - url_to_path_regex: regex для извлечения пути из URL товара
        - path_param_format: формат параметра пути (например "path[]={part}")
        - path_separator: разделитель параметров (по умолчанию "&")
        """
        base_url = self.api_config.get('base_url', '')
        endpoint = self.api_config.get('detail_endpoint', '')
        url_regex = self.api_config.get('url_to_path_regex', '')
        param_format = self.api_config.get('path_param_format', 'path={path}')
        separator = self.api_config.get('path_separator', '&')

        if not url_regex:
            return None

        # Извлекаем путь из URL товара
        match = re.search(url_regex, product_url)
        if not match:
            return None

        path_str = match.group(1).rstrip('/')
        path_parts = path_str.split('/')

        # Формируем параметры
        if '{part}' in param_format:
            # Формат path[]={part} - каждая часть отдельно
            params = []
            for part in path_parts:
                params.append(param_format.replace('{part}', part))
            query_string = separator.join(params)
        else:
            # Формат path={path} - весь путь целиком
            query_string = param_format.replace('{path}', path_str)

        api_url = f"{base_url}{endpoint}?{query_string}"
        return api_url

    def extract_value(self, data: Dict, path: str) -> Any:
        """
        Извлечь значение по JSONPath-подобному пути.

        Поддерживаемые форматы:
        - "product.name" -> data["product"]["name"]
        - "product.prices[0].price" -> data["product"]["prices"][0]["price"]
        - "items[*].value" -> [item["value"] for item in data["items"]]
        """
        if not path or not data:
            return None

        parts = self._parse_path(path)
        current = data

        for part in parts:
            if current is None:
                return None

            if isinstance(part, str):
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
            elif isinstance(part, int):
                if isinstance(current, list) and len(current) > part:
                    current = current[part]
                else:
                    return None
            elif part == '*':
                # Wildcard - возвращаем список
                if isinstance(current, list):
                    return current
                return None

        return current

    def _parse_path(self, path: str) -> List:
        """Разобрать путь на части"""
        parts = []
        # Разбиваем по точкам и скобкам
        tokens = re.split(r'\.|\[|\]', path)

        for token in tokens:
            if not token:
                continue
            if token.isdigit():
                parts.append(int(token))
            elif token == '*':
                parts.append('*')
            else:
                parts.append(token)

        return parts

    def extract_with_filter(self, data: Dict, path: str, filter_config: Dict) -> Any:
        """
        Извлечь значение с фильтрацией массива.

        filter_config: {"field": "name", "value": "Розница"}
        """
        # Извлекаем массив
        array_path = path.rsplit('.', 1)[0] if '.' in path else path
        value_field = path.rsplit('.', 1)[1] if '.' in path else None

        items = self.extract_value(data, array_path)
        if not isinstance(items, list):
            return None

        # Фильтруем
        filter_field = filter_config.get('field')
        filter_value = filter_config.get('value')

        for item in items:
            if isinstance(item, dict):
                if item.get(filter_field) == filter_value:
                    if value_field:
                        return item.get(value_field)
                    return item

        return None

    def extract_product_data(self, json_data: Dict) -> Dict[str, Any]:
        """
        Извлечь данные товара из JSON ответа.

        Возвращает:
        {
            "price": float,
            "price_wholesale": float,
            "in_stock": bool,
            "stock_quantity": int,
            "article": str,
            "name": str
        }
        """
        result = {}

        # Цена
        price_path = self.json_paths.get('price')
        price_filter = self.json_paths.get('price_path_filter')

        if price_path:
            if price_filter:
                price = self.extract_with_filter(json_data, price_path, price_filter)
            else:
                price = self.extract_value(json_data, price_path)

            result['price'] = self._to_float(price)

        # Оптовая цена
        wholesale_path = self.json_paths.get('price_wholesale')
        wholesale_filter = self.json_paths.get('price_wholesale_filter')

        if wholesale_path:
            if wholesale_filter:
                wholesale = self.extract_with_filter(json_data, wholesale_path, wholesale_filter)
            else:
                wholesale = self.extract_value(json_data, wholesale_path)

            result['price_wholesale'] = self._to_float(wholesale)

        # Наличие
        stock_path = self.json_paths.get('stock')
        if stock_path:
            stock_value = self.extract_value(json_data, stock_path)
            result['in_stock'] = self._check_in_stock(stock_value)
            result['stock_quantity'] = self._to_stock_quantity(stock_value)

        # Артикул
        article_path = self.json_paths.get('article')
        if article_path:
            article = self.extract_value(json_data, article_path)
            result['article'] = str(article).strip() if article else None

        # Название
        name_path = self.json_paths.get('name')
        if name_path:
            name = self.extract_value(json_data, name_path)
            result['name'] = str(name).strip() if name else None

        return result

    def _to_float(self, value) -> Optional[float]:
        """Преобразовать в float"""
        if value is None:
            return None
        try:
            if isinstance(value, str):
                # Убираем пробелы и заменяем запятую
                value = value.replace(' ', '').replace(',', '.')
            return float(value)
        except (ValueError, TypeError):
            return None

    def _check_in_stock(self, value) -> bool:
        """Проверить наличие"""
        if value is None:
            return False

        out_of_stock_values = self.json_paths.get('out_of_stock_values', ['none', '', None, 0, '0'])
        in_stock_check = self.json_paths.get('in_stock_check', 'not_in')

        if in_stock_check == 'not_in':
            # В наличии, если значение НЕ в списке out_of_stock
            return value not in out_of_stock_values
        else:
            # В наличии, если значение В списке in_stock
            in_stock_values = self.json_paths.get('in_stock_values', [])
            return value in in_stock_values

    def _to_stock_quantity(self, value) -> Optional[int]:
        """Преобразовать в количество"""
        if value is None:
            return None

        # Маппинг текстовых значений
        stock_mapping = self.config.transformers.get('stock_mapping', {})
        if isinstance(value, str) and value in stock_mapping:
            return stock_mapping[value]

        try:
            return int(value)
        except (ValueError, TypeError):
            return None
