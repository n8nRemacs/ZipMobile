"""
Универсальный Real-time парсер

Парсит данные о товаре (цена, наличие, артикул) по URL.
Конфигурация загружается из БД по домену.
"""

import os
import re
import json
import time
import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse

from config_loader import get_config_by_url, get_config_by_shop, ParserConfig
from extractors.api_json import ApiJsonExtractor
from extractors.html import HtmlExtractor


@dataclass
class ParseResult:
    """Результат парсинга товара"""
    success: bool
    price: Optional[float] = None
    price_wholesale: Optional[float] = None
    in_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    article: Optional[str] = None
    name: Optional[str] = None
    shop_code: Optional[str] = None
    error: Optional[str] = None
    response_time_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'price': self.price,
            'price_wholesale': self.price_wholesale,
            'in_stock': self.in_stock,
            'stock_quantity': self.stock_quantity,
            'article': self.article,
            'name': self.name,
            'shop_code': self.shop_code,
            'error': self.error,
            'response_time_ms': self.response_time_ms
        }


class UniversalParser:
    """Универсальный парсер товаров"""

    def __init__(self, cookies_dir: str = None):
        """
        Args:
            cookies_dir: директория с файлами cookies (по коду магазина)
        """
        self.cookies_dir = cookies_dir or os.path.dirname(os.path.abspath(__file__))
        self._clients: Dict[str, httpx.Client] = {}
        self._last_request: Dict[str, float] = {}

    def _get_client(self, config: ParserConfig) -> httpx.Client:
        """Получить или создать HTTP клиент для магазина"""
        if config.shop_code in self._clients:
            return self._clients[config.shop_code]

        # Загружаем cookies
        cookies = {}
        if config.cookies_required:
            cookies = self._load_cookies(config)

        # Формируем headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "ru,en;q=0.9",
        }
        headers.update(config.headers)

        client = httpx.Client(
            timeout=config.timeout,
            headers=headers,
            cookies=cookies,
            follow_redirects=True
        )

        self._clients[config.shop_code] = client
        return client

    def _load_cookies(self, config: ParserConfig) -> dict:
        """Загрузить cookies для магазина"""
        source = config.cookies_source
        if not source:
            return {}

        if source.startswith('file:'):
            # Загрузка из файла
            filename = source[5:]
            cookie_path = os.path.join(self.cookies_dir, config.shop_code, filename)

            # Пробуем альтернативный путь
            if not os.path.exists(cookie_path):
                cookie_path = os.path.join(self.cookies_dir, filename)

            if os.path.exists(cookie_path):
                try:
                    with open(cookie_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"Error loading cookies from {cookie_path}: {e}")

        elif source.startswith('db:'):
            # Загрузка из БД (TODO: реализовать)
            pass

        return {}

    def _rate_limit(self, config: ParserConfig):
        """Ограничение частоты запросов"""
        last = self._last_request.get(config.shop_code, 0)
        elapsed = time.time() - last
        if elapsed < config.delay:
            time.sleep(config.delay - elapsed)
        self._last_request[config.shop_code] = time.time()

    def parse(self, url: str) -> ParseResult:
        """
        Парсить товар по URL.

        Args:
            url: URL страницы товара

        Returns:
            ParseResult с данными о товаре
        """
        start_time = time.time()

        # Находим конфигурацию по URL
        config = get_config_by_url(url)
        if not config:
            return ParseResult(
                success=False,
                error=f"No parser config found for URL: {url}"
            )

        try:
            self._rate_limit(config)

            if config.parser_type == 'api_json':
                result = self._parse_api_json(url, config)
            elif config.parser_type == 'html':
                result = self._parse_html(url, config)
            else:
                return ParseResult(
                    success=False,
                    shop_code=config.shop_code,
                    error=f"Unknown parser type: {config.parser_type}"
                )

            result.shop_code = config.shop_code
            result.response_time_ms = int((time.time() - start_time) * 1000)
            return result

        except Exception as e:
            return ParseResult(
                success=False,
                shop_code=config.shop_code,
                error=str(e),
                response_time_ms=int((time.time() - start_time) * 1000)
            )

    def _parse_api_json(self, url: str, config: ParserConfig, fallback_to_html: bool = True) -> ParseResult:
        """Парсинг через JSON API с fallback на HTML"""
        extractor = ApiJsonExtractor(config)
        client = self._get_client(config)

        # Строим URL API
        api_url = extractor.build_api_url(url)
        if not api_url:
            if fallback_to_html:
                return self._parse_html_fallback(url, config)
            return ParseResult(
                success=False,
                error="Failed to build API URL from product URL"
            )

        # Запрос к API
        response = client.get(api_url)

        if response.status_code != 200:
            return ParseResult(
                success=False,
                error=f"API returned status {response.status_code}"
            )

        content_type = response.headers.get('content-type', '')
        if 'application/json' not in content_type:
            # API вернул HTML вместо JSON - пробуем fallback
            if fallback_to_html:
                return self._parse_html_fallback(url, config)
            return ParseResult(
                success=False,
                error=f"Expected JSON, got {content_type}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            return ParseResult(
                success=False,
                error=f"Failed to parse JSON: {e}"
            )

        # Извлекаем данные
        extracted = extractor.extract_product_data(data)

        return ParseResult(
            success=True,
            price=extracted.get('price'),
            price_wholesale=extracted.get('price_wholesale'),
            in_stock=extracted.get('in_stock'),
            stock_quantity=extracted.get('stock_quantity'),
            article=extracted.get('article'),
            name=extracted.get('name')
        )

    def _parse_html(self, url: str, config: ParserConfig) -> ParseResult:
        """Парсинг через HTML"""
        extractor = HtmlExtractor(config)
        client = self._get_client(config)

        # Запрос страницы
        response = client.get(url)

        if response.status_code != 200:
            return ParseResult(
                success=False,
                error=f"HTTP status {response.status_code}"
            )

        html = response.text

        # Извлекаем данные
        extracted = extractor.extract_product_data(html)

        return ParseResult(
            success=True,
            price=extracted.get('price'),
            price_wholesale=extracted.get('price_wholesale'),
            in_stock=extracted.get('in_stock'),
            article=extracted.get('article'),
            name=extracted.get('name')
        )

    def _parse_html_fallback(self, url: str, config: ParserConfig) -> ParseResult:
        """
        Fallback парсинг через HTML с regex.
        Используется когда API недоступен.
        """
        client = self._get_client(config)

        # Запрос страницы товара напрямую
        response = client.get(url)

        if response.status_code != 200:
            return ParseResult(
                success=False,
                error=f"HTML fallback: HTTP status {response.status_code}"
            )

        html = response.text

        # Универсальные regex паттерны
        result = {}

        # Цена - ищем разные форматы
        price_patterns = [
            r'"price":\s*(\d+(?:\.\d+)?)',  # JSON в HTML
            r'data-price="(\d+(?:\.\d+)?)"',  # data-атрибут
            r'itemprop="price"\s+content="(\d+(?:\.\d+)?)"',  # microdata
            r'class="[^"]*price[^"]*"[^>]*>[\s\S]*?(\d[\d\s]*)\s*(?:₽|руб|р\.)',  # текст с ценой
        ]
        for pattern in price_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(' ', '')
                try:
                    result['price'] = float(price_str)
                    break
                except ValueError:
                    continue

        # Артикул
        article_patterns = [
            r'"article":\s*"([^"]+)"',  # JSON
            r'Артикул[:\s]*</?\w+[^>]*>?\s*([A-ZА-Яa-zа-я]{2,3}[-\s]?\d+)',  # Текст
            r'data-article="([^"]+)"',  # data-атрибут
            r'itemprop="sku"[^>]*>([^<]+)',  # microdata
        ]
        for pattern in article_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                result['article'] = match.group(1).strip()
                break

        # Название товара
        name_patterns = [
            r'"name":\s*"([^"]+)"',  # JSON
            r'<h1[^>]*>([^<]+)</h1>',  # H1
            r'itemprop="name"[^>]*>([^<]+)',  # microdata
        ]
        for pattern in name_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                result['name'] = match.group(1).strip()
                break

        # Наличие
        in_stock = True  # По умолчанию в наличии
        out_of_stock_patterns = [
            r'нет в наличии',
            r'под заказ',
            r'отсутствует',
            r'"availability":\s*"OutOfStock"',
            r'class="[^"]*out-of-stock',
        ]
        for pattern in out_of_stock_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                in_stock = False
                break

        result['in_stock'] = in_stock

        # Проверяем что нашли хоть что-то
        if result.get('price') or result.get('article') or result.get('name'):
            return ParseResult(
                success=True,
                price=result.get('price'),
                in_stock=result.get('in_stock'),
                article=result.get('article'),
                name=result.get('name')
            )

        return ParseResult(
            success=False,
            error="HTML fallback: Could not extract product data"
        )

    def parse_by_shop(self, shop_code: str, url: str) -> ParseResult:
        """
        Парсить товар с явным указанием магазина.

        Полезно когда URL может не совпадать с domain_patterns.
        """
        config = get_config_by_shop(shop_code)
        if not config:
            return ParseResult(
                success=False,
                error=f"No parser config found for shop: {shop_code}"
            )

        start_time = time.time()

        try:
            self._rate_limit(config)

            if config.parser_type == 'api_json':
                result = self._parse_api_json(url, config)
            elif config.parser_type == 'html':
                result = self._parse_html(url, config)
            else:
                return ParseResult(
                    success=False,
                    shop_code=config.shop_code,
                    error=f"Unknown parser type: {config.parser_type}"
                )

            result.shop_code = config.shop_code
            result.response_time_ms = int((time.time() - start_time) * 1000)
            return result

        except Exception as e:
            return ParseResult(
                success=False,
                shop_code=config.shop_code,
                error=str(e),
                response_time_ms=int((time.time() - start_time) * 1000)
            )

    def close(self):
        """Закрыть все HTTP клиенты"""
        for client in self._clients.values():
            client.close()
        self._clients.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Глобальный экземпляр парсера
_parser: Optional[UniversalParser] = None


def get_parser() -> UniversalParser:
    """Получить глобальный парсер"""
    global _parser
    if _parser is None:
        _parser = UniversalParser()
    return _parser


def parse_product(url: str) -> ParseResult:
    """Shortcut: парсить товар по URL"""
    return get_parser().parse(url)


def parse_product_by_shop(shop_code: str, url: str) -> ParseResult:
    """Shortcut: парсить товар с указанием магазина"""
    return get_parser().parse_by_shop(shop_code, url)


if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser(description='Universal product parser')
    arg_parser.add_argument('url', help='Product URL to parse')
    arg_parser.add_argument('--shop', help='Shop code (optional)')
    args = arg_parser.parse_args()

    with UniversalParser() as parser:
        if args.shop:
            result = parser.parse_by_shop(args.shop, args.url)
        else:
            result = parser.parse(args.url)

        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
