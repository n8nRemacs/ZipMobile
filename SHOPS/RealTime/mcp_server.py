"""
MCP Server для Real-time парсинга товаров

Предоставляет инструменты для парсинга актуальных цен
и наличия товаров по URL из любого настроенного магазина.

Запуск:
    python mcp_server.py

Или через uvicorn:
    uvicorn mcp_server:app --host 0.0.0.0 --port 8000
"""

import os
import sys

# Добавляем текущую директорию в path для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Optional
from mcp.server.fastmcp import FastMCP

from parser import UniversalParser, ParseResult
from config_loader import get_all_configs, get_config_by_url, get_config_by_shop, ParserConfig

# Создаем MCP сервер
mcp = FastMCP("realtime-parser")

# Глобальный парсер
_parser: Optional[UniversalParser] = None


def get_parser() -> UniversalParser:
    """Получить или создать парсер"""
    global _parser
    if _parser is None:
        _parser = UniversalParser()
    return _parser


@mcp.tool()
def parse_product_realtime(url: str) -> dict:
    """
    Парсит актуальную цену и наличие товара по URL.

    Автоматически определяет магазин по домену URL
    и использует соответствующую конфигурацию парсера.

    Args:
        url: Полный URL страницы товара

    Returns:
        {
            "success": true/false,
            "price": 5500.0,
            "price_wholesale": 5000.0,
            "in_stock": true,
            "stock_quantity": 10,
            "article": "GS-00012345",
            "name": "Название товара",
            "shop_code": "greenspark",
            "error": null,
            "response_time_ms": 250
        }
    """
    parser = get_parser()
    result = parser.parse(url)
    return result.to_dict()


@mcp.tool()
def parse_product_by_shop(shop_code: str, url: str) -> dict:
    """
    Парсит товар с явным указанием магазина.

    Используйте когда URL не соответствует стандартному
    домену магазина (например, мобильная версия сайта).

    Args:
        shop_code: Код магазина (greenspark, 05gsm, taggsm и т.д.)
        url: URL страницы товара

    Returns:
        Аналогично parse_product_realtime
    """
    parser = get_parser()
    result = parser.parse_by_shop(shop_code, url)
    return result.to_dict()


@mcp.tool()
def get_parser_configs() -> list:
    """
    Получить список всех доступных парсеров.

    Returns:
        [
            {
                "shop_code": "greenspark",
                "domains": ["green-spark.ru", "greenspark.ru"],
                "parser_type": "api_json",
                "is_active": true,
                "test_url": "https://green-spark.ru/catalog/.../product.html"
            },
            ...
        ]
    """
    configs = get_all_configs()
    return [
        {
            "shop_code": c.shop_code,
            "domains": c.domain_patterns,
            "parser_type": c.parser_type,
            "is_active": c.is_active,
            "test_url": c.test_url
        }
        for c in configs
    ]


@mcp.tool()
def test_parser_config(shop_code: str) -> dict:
    """
    Тестирует конфигурацию парсера на test_url.

    Args:
        shop_code: Код магазина

    Returns:
        {
            "success": true/false,
            "config": {...},
            "test_result": {...}
        }
    """
    config = get_config_by_shop(shop_code)
    if not config:
        return {
            "success": False,
            "error": f"Config not found for shop: {shop_code}"
        }

    if not config.test_url:
        return {
            "success": False,
            "error": f"No test_url configured for shop: {shop_code}",
            "config": {
                "shop_code": config.shop_code,
                "parser_type": config.parser_type,
                "domains": config.domain_patterns
            }
        }

    parser = get_parser()
    result = parser.parse_by_shop(shop_code, config.test_url)

    return {
        "success": result.success,
        "config": {
            "shop_code": config.shop_code,
            "parser_type": config.parser_type,
            "domains": config.domain_patterns,
            "test_url": config.test_url
        },
        "test_result": result.to_dict()
    }


@mcp.tool()
def check_url_parser(url: str) -> dict:
    """
    Проверяет, есть ли парсер для данного URL.

    Args:
        url: URL для проверки

    Returns:
        {
            "has_parser": true/false,
            "shop_code": "greenspark",
            "parser_type": "api_json"
        }
    """
    config = get_config_by_url(url)
    if config:
        return {
            "has_parser": True,
            "shop_code": config.shop_code,
            "parser_type": config.parser_type,
            "domains": config.domain_patterns
        }
    return {
        "has_parser": False,
        "shop_code": None,
        "parser_type": None
    }


# Ресурс с информацией о сервере
@mcp.resource("parser://info")
def get_parser_info() -> str:
    """Информация о парсере"""
    configs = get_all_configs()
    info = f"""Real-time Parser MCP Server
===========================

Доступные магазины: {len(configs)}

"""
    for c in configs:
        info += f"- {c.shop_code} ({c.parser_type}): {', '.join(c.domain_patterns)}\n"

    info += """
Инструменты:
- parse_product_realtime(url) - парсить товар по URL
- parse_product_by_shop(shop_code, url) - парсить с указанием магазина
- get_parser_configs() - список всех парсеров
- test_parser_config(shop_code) - тест конфигурации
- check_url_parser(url) - проверить доступность парсера
"""
    return info


if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser(description='MCP Real-time Parser Server')
    arg_parser.add_argument('--transport', choices=['stdio', 'sse'], default='stdio',
                           help='Transport type (default: stdio)')
    arg_parser.add_argument('--port', type=int, default=8000,
                           help='Port for SSE transport (default: 8000)')
    args = arg_parser.parse_args()

    if args.transport == 'stdio':
        mcp.run(transport='stdio')
    else:
        mcp.run(transport='sse', sse_port=args.port)
