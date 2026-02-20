"""
Extractors - модули извлечения данных из разных источников
"""

from .api_json import ApiJsonExtractor
from .html import HtmlExtractor

__all__ = ['ApiJsonExtractor', 'HtmlExtractor']
