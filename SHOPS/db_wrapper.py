"""
Database wrapper для миграции на Supabase
Автоматически маппит старые имена таблиц на новые с префиксами
"""
import psycopg2
import re
from db_config import get_db_config

# Маппинг старых имён таблиц на новые
# Формат: (old_name, new_name)
TABLE_MAPPING = {
    # LCD-Stock (старая схема)
    "products": "lcdstock_products",
    "stock": "lcdstock_stock",
    "lcd_nomenclature": "lcdstock_nomenclature",
    "lcd_prices": "lcdstock_prices",  # DEPRECATED v10 → use lcd_product_urls
    "lcd_product_urls": "lcdstock_product_urls",

    # GreenSpark
    "parser_progress": "greenspark_parser_progress",
    "parser_queue": "greenspark_parser_queue",
    "parser_request_log": "greenspark_parser_request_log",
    "parser_servers": "greenspark_parser_servers",
    "product_lookup": "greenspark_product_lookup",
    "shop_cookies": "greenspark_shop_cookies",
    "shop_parser_configs": "greenspark_shop_parser_configs",

    # GSMArena
    "gsmarena_phones": "zip_gsmarena_phones",

    # Master
    "unified_nomenclature": "master_unified_nomenclature",

    # Общие таблицы (остаются с zip_ префиксом)
    "outlets": "zip_outlets",
    "cities": "zip_cities",
    "regions": "zip_cities",  # регионы объединены с городами

    # === Стандартизация v1.0 (2026-01-26) ===
    # Moba
    "moba_prices": "moba_prices",  # DEPRECATED v10 → use moba_product_urls
    "moba_product_urls": "moba_product_urls",

    # МойСклад / NAFFAS
    "moysklad_prices": "moysklad_naffas_prices",  # DEPRECATED v10
    "naffas_prices": "moysklad_naffas_prices",  # DEPRECATED v10
    "moysklad_product_urls": "moysklad_naffas_product_urls",
    "naffas_product_urls": "moysklad_naffas_product_urls",
    "naffas_nomenclature": "moysklad_naffas_nomenclature",

    # Orizhka
    "orizhka_prices": "orizhka_prices",  # DEPRECATED v10
    "orizhka_product_urls": "orizhka_product_urls",

    # Staging таблицы
    "lcdstock_staging": "lcdstock_staging",
    "orizhka_staging": "orizhka_staging",

    # 05GSM (парсер использует gsm05_ префикс)
    "gsm05_nomenclature": "_05gsm_nomenclature",
    "gsm05_prices": "_05gsm_prices",  # DEPRECATED v10
    "gsm05_product_urls": "_05gsm_product_urls",
    "gsm05_staging": "_05gsm_staging",
}


def rewrite_sql(sql: str) -> str:
    """
    Переписывает SQL запрос, заменяя старые имена таблиц на новые

    Обрабатывает:
    - FROM table_name
    - INTO table_name
    - UPDATE table_name
    - JOIN table_name
    - TABLE table_name
    - INSERT INTO table_name
    - CREATE TABLE table_name
    - ALTER TABLE table_name
    - DROP TABLE table_name
    - TRUNCATE TABLE table_name
    """
    result = sql

    for old_name, new_name in TABLE_MAPPING.items():
        # Паттерны для замены (с учётом границ слов)
        patterns = [
            (rf'\bFROM\s+{old_name}\b', f'FROM {new_name}'),
            (rf'\bINTO\s+{old_name}\b', f'INTO {new_name}'),
            (rf'\bUPDATE\s+{old_name}\b', f'UPDATE {new_name}'),
            (rf'\bJOIN\s+{old_name}\b', f'JOIN {new_name}'),
            (rf'\bTABLE\s+{old_name}\b', f'TABLE {new_name}'),
            (rf'\b{old_name}\s+AS\b', f'{new_name} AS'),
            (rf'\b{old_name}\s+[a-z]\b', lambda m: m.group().replace(old_name, new_name)),
        ]

        for pattern, replacement in patterns:
            if callable(replacement):
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            else:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


class SupabaseConnection:
    """
    Обёртка над psycopg2 connection с автоматической заменой имён таблиц
    """

    def __init__(self, target: str = None):
        self._conn = psycopg2.connect(**get_db_config(target))

    def cursor(self):
        return SupabaseCursor(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    @property
    def autocommit(self):
        return self._conn.autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._conn.autocommit = value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class SupabaseCursor:
    """
    Обёртка над psycopg2 cursor с автоматической заменой имён таблиц
    """

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        rewritten_sql = rewrite_sql(sql)
        if params:
            return self._cursor.execute(rewritten_sql, params)
        return self._cursor.execute(rewritten_sql)

    def executemany(self, sql, params_list):
        rewritten_sql = rewrite_sql(sql)
        return self._cursor.executemany(rewritten_sql, params_list)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size)

    def close(self):
        return self._cursor.close()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def __iter__(self):
        return iter(self._cursor)

    def batch_insert(self, sql, values, page_size=1000):
        """Batch INSERT через execute_values (psycopg2.extras)."""
        from psycopg2.extras import execute_values
        rewritten_sql = rewrite_sql(sql)
        execute_values(self._cursor, rewritten_sql, values, page_size=page_size)

    def set_timeout(self, seconds):
        """Устанавливает statement_timeout для тяжёлых запросов."""
        self._cursor.execute(f"SET statement_timeout = '{seconds}s'")


def get_db(target: str = None):
    """
    Возвращает connection к PostgreSQL с автоматической заменой имён таблиц.
    target: "local" | "cloud" | None (по умолчанию из DB_TARGET)
    """
    return SupabaseConnection(target)


# Для обратной совместимости
def connect(**kwargs):
    """Игнорирует переданные параметры и подключается к БД"""
    return SupabaseConnection()
