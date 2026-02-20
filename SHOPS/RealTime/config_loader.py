"""
Загрузчик конфигураций парсеров из БД

Загружает настройки парсинга из таблицы shop_parser_configs
по домену URL или коду магазина.
"""

import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from functools import lru_cache

# Конфигурация БД
DB_HOST = os.environ.get("DB_HOST", "85.198.98.104")
DB_PORT = int(os.environ.get("DB_PORT", 5433))
DB_NAME = os.environ.get("DB_NAME", "db_greenspark")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mi31415926pSss!")


def get_db():
    """Подключение к БД"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"
    )


class ParserConfig:
    """Конфигурация парсера для магазина"""

    def __init__(self, row: Dict[str, Any]):
        self.id = row['id']
        self.shop_code = row['shop_code']
        self.domain_patterns = row['domain_patterns']
        self.parser_type = row['parser_type']
        self.api_config = row.get('api_config') or {}
        self.json_paths = row.get('json_paths') or {}
        self.html_selectors = row.get('html_selectors') or {}
        self.regex_patterns = row.get('regex_patterns') or {}
        self.request_config = row.get('request_config') or {}
        self.transformers = row.get('transformers') or {}
        self.is_active = row.get('is_active', True)
        self.test_url = row.get('test_url')
        self.notes = row.get('notes')

    def __repr__(self):
        return f"<ParserConfig {self.shop_code} ({self.parser_type})>"

    @property
    def delay(self) -> float:
        return self.request_config.get('delay', 1.0)

    @property
    def timeout(self) -> int:
        return self.request_config.get('timeout', 30)

    @property
    def cookies_required(self) -> bool:
        return self.request_config.get('cookies_required', False)

    @property
    def cookies_source(self) -> Optional[str]:
        return self.request_config.get('cookies_source')

    @property
    def headers(self) -> Dict[str, str]:
        return self.request_config.get('headers', {})


class ConfigLoader:
    """Загрузчик конфигураций из БД"""

    def __init__(self):
        self._cache: Dict[str, ParserConfig] = {}

    def get_config_by_shop_code(self, shop_code: str) -> Optional[ParserConfig]:
        """Получить конфиг по коду магазина"""
        if shop_code in self._cache:
            return self._cache[shop_code]

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT * FROM shop_parser_configs
                WHERE shop_code = %s AND is_active = true
            """, (shop_code,))
            row = cur.fetchone()
            if row:
                config = ParserConfig(dict(row))
                self._cache[shop_code] = config
                return config
            return None
        finally:
            cur.close()
            conn.close()

    def get_config_by_url(self, url: str) -> Optional[ParserConfig]:
        """Найти конфиг по URL (сопоставление с domain_patterns)"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Убираем www.
        if domain.startswith('www.'):
            domain = domain[4:]

        # Проверяем кэш
        for config in self._cache.values():
            if self._domain_matches(domain, config.domain_patterns):
                return config

        # Ищем в БД
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT * FROM shop_parser_configs
                WHERE is_active = true
            """)
            rows = cur.fetchall()

            for row in rows:
                config = ParserConfig(dict(row))
                self._cache[config.shop_code] = config

                if self._domain_matches(domain, config.domain_patterns):
                    return config

            return None
        finally:
            cur.close()
            conn.close()

    def _domain_matches(self, domain: str, patterns: list) -> bool:
        """Проверить соответствие домена паттернам"""
        for pattern in patterns:
            pattern = pattern.lower()
            if pattern.startswith('www.'):
                pattern = pattern[4:]

            # Точное совпадение
            if domain == pattern:
                return True

            # Поддомен
            if domain.endswith('.' + pattern):
                return True

        return False

    def get_all_configs(self) -> list:
        """Получить все активные конфиги"""
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT * FROM shop_parser_configs
                WHERE is_active = true
                ORDER BY shop_code
            """)
            rows = cur.fetchall()
            configs = []
            for row in rows:
                config = ParserConfig(dict(row))
                self._cache[config.shop_code] = config
                configs.append(config)
            return configs
        finally:
            cur.close()
            conn.close()

    def clear_cache(self):
        """Очистить кэш"""
        self._cache.clear()


# Глобальный загрузчик
_loader: Optional[ConfigLoader] = None


def get_loader() -> ConfigLoader:
    """Получить глобальный загрузчик"""
    global _loader
    if _loader is None:
        _loader = ConfigLoader()
    return _loader


def get_config_by_url(url: str) -> Optional[ParserConfig]:
    """Shortcut: найти конфиг по URL"""
    return get_loader().get_config_by_url(url)


def get_config_by_shop(shop_code: str) -> Optional[ParserConfig]:
    """Shortcut: получить конфиг по коду магазина"""
    return get_loader().get_config_by_shop_code(shop_code)


def get_all_configs() -> list:
    """Shortcut: получить все конфиги"""
    return get_loader().get_all_configs()
