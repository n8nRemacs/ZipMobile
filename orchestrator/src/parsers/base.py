"""
Base parser class — all shop adapters extend this.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Product:
    article: str
    name: str
    price: float
    in_stock: bool
    category: str = ""
    url: str = ""
    city: str = ""
    stock_level: int = 0


class ProxyBannedException(Exception):
    """Raised when a proxy is blocked/captcha'd by the target site."""
    pass


class BaseParser:
    shop_code: str = ""
    shop_name: str = ""
    needs_proxy: bool = False
    parser_dir: str = ""

    async def parse_all(self, proxy: str = None, checkpoint=None) -> List[Product]:
        raise NotImplementedError

    async def health_check(self, proxy: str = None) -> bool:
        """Quick check if the site is accessible."""
        return True
