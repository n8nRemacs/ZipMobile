"""
HTML Extractor

Извлечение данных из HTML страниц.
Поддерживает CSS селекторы и regex паттерны.
"""

import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup


class HtmlExtractor:
    """Извлекатель данных из HTML"""

    def __init__(self, config):
        """
        Args:
            config: ParserConfig с html_selectors и regex_patterns
        """
        self.config = config
        self.selectors = config.html_selectors
        self.patterns = config.regex_patterns

    def extract_by_selector(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """Извлечь текст по CSS селектору"""
        if not selector:
            return None

        element = soup.select_one(selector)
        if element:
            return element.get_text(strip=True)
        return None

    def extract_by_regex(self, html: str, pattern: str) -> Optional[str]:
        """Извлечь значение по regex паттерну"""
        if not pattern:
            return None

        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1) if match.groups() else match.group(0)
        return None

    def extract_product_data(self, html: str) -> Dict[str, Any]:
        """
        Извлечь данные товара из HTML.

        Возвращает:
        {
            "price": float,
            "price_wholesale": float,
            "in_stock": bool,
            "article": str,
            "name": str
        }
        """
        soup = BeautifulSoup(html, 'html.parser')
        result = {}

        # Цена
        price_text = self._extract_field(soup, html, 'price')
        result['price'] = self._parse_price(price_text)

        # Оптовая цена
        wholesale_text = self._extract_field(soup, html, 'price_wholesale')
        result['price_wholesale'] = self._parse_price(wholesale_text)

        # Артикул
        article_text = self._extract_field(soup, html, 'article')
        result['article'] = article_text.strip() if article_text else None

        # Название
        name_text = self._extract_field(soup, html, 'name')
        result['name'] = name_text.strip() if name_text else None

        # Наличие
        result['in_stock'] = self._check_in_stock(soup, html)

        return result

    def _extract_field(self, soup: BeautifulSoup, html: str, field: str) -> Optional[str]:
        """Извлечь поле (сначала селектор, потом regex)"""
        # Пробуем CSS селектор
        selector = self.selectors.get(field)
        if selector:
            value = self.extract_by_selector(soup, selector)
            if value:
                return value

        # Пробуем regex
        pattern = self.patterns.get(field)
        if pattern:
            value = self.extract_by_regex(html, pattern)
            if value:
                return value

        return None

    def _parse_price(self, text: Optional[str]) -> Optional[float]:
        """Парсинг цены из текста"""
        if not text:
            return None

        # Убираем все кроме цифр, точки и запятой
        cleaned = re.sub(r'[^\d.,]', '', text)

        if not cleaned:
            return None

        # Заменяем запятую на точку
        cleaned = cleaned.replace(',', '.')

        # Если несколько точек, оставляем только последнюю
        parts = cleaned.split('.')
        if len(parts) > 2:
            cleaned = ''.join(parts[:-1]) + '.' + parts[-1]

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _check_in_stock(self, soup: BeautifulSoup, html: str) -> bool:
        """Проверить наличие товара"""
        # Проверяем CSS класс
        in_stock_class = self.selectors.get('in_stock_class')
        if in_stock_class:
            element = soup.select_one(f'.{in_stock_class}')
            if element:
                return True

        # Проверяем селектор наличия
        stock_selector = self.selectors.get('stock')
        if stock_selector:
            element = soup.select_one(stock_selector)
            if element:
                text = element.get_text(strip=True).lower()

                # Проверяем out_of_stock_text
                out_texts = self.selectors.get('out_of_stock_text', [])
                for out_text in out_texts:
                    if out_text.lower() in text:
                        return False

                # Проверяем in_stock_text
                in_texts = self.selectors.get('in_stock_text', [])
                for in_text in in_texts:
                    if in_text.lower() in text:
                        return True

        # По умолчанию - в наличии, если есть цена
        return True

    def extract_all_products(self, html: str) -> list:
        """
        Извлечь все товары со страницы списка.

        Использует селекторы:
        - product_list: селектор контейнера списка
        - product_item: селектор отдельного товара
        - product_link: селектор ссылки на товар
        """
        soup = BeautifulSoup(html, 'html.parser')
        products = []

        item_selector = self.selectors.get('product_item')
        if not item_selector:
            return products

        items = soup.select(item_selector)

        for item in items:
            product = {}

            # Ссылка
            link_selector = self.selectors.get('product_link', 'a')
            link_el = item.select_one(link_selector)
            if link_el and link_el.get('href'):
                product['url'] = link_el.get('href')

            # Название
            name_selector = self.selectors.get('product_name')
            if name_selector:
                name_el = item.select_one(name_selector)
                if name_el:
                    product['name'] = name_el.get_text(strip=True)

            # Цена
            price_selector = self.selectors.get('product_price')
            if price_selector:
                price_el = item.select_one(price_selector)
                if price_el:
                    product['price'] = self._parse_price(price_el.get_text())

            if product.get('url') or product.get('name'):
                products.append(product)

        return products
