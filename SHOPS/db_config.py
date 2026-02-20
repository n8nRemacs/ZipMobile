"""
Единая конфигурация подключения к PostgreSQL.
Используется всеми парсерами.

Два режима:
  - "local"  — Supabase self-hosted на Homelab (localhost, без SSL)
  - "cloud"  — Supabase Cloud (production, через pooler, SSL)

Переключение: env DB_TARGET=local|cloud (по умолчанию local)
"""
import os

# === LOCAL (Homelab Supabase self-hosted, 213.108.170.194) ===
LOCAL_HOST = os.environ.get("LOCAL_DB_HOST", "localhost")
LOCAL_PORT = int(os.environ.get("LOCAL_DB_PORT", 5433))
LOCAL_USER = os.environ.get("LOCAL_DB_USER", "postgres")
LOCAL_PASSWORD = os.environ.get("LOCAL_DB_PASSWORD", "Mi31415926pSss!")
LOCAL_DATABASE = os.environ.get("LOCAL_DB_NAME", "postgres")

# === CLOUD (Supabase Cloud — production) ===
CLOUD_HOST = "aws-1-eu-west-3.pooler.supabase.com"
CLOUD_PORT = 5432
CLOUD_USER = "postgres.griexhozxrqtepcilfnu"
CLOUD_PASSWORD = "Mi31415926pSss!"
CLOUD_DATABASE = "postgres"

# По умолчанию парсеры пишут в локальную БД
DB_TARGET = os.environ.get("DB_TARGET", "local")  # "local" | "cloud"


def get_db_config(target: str = None):
    """Возвращает dict для psycopg2.connect()"""
    t = target or DB_TARGET
    if t == "local":
        return {
            "host": LOCAL_HOST,
            "port": LOCAL_PORT,
            "user": LOCAL_USER,
            "password": LOCAL_PASSWORD,
            "dbname": LOCAL_DATABASE,
        }
    else:
        return {
            "host": CLOUD_HOST,
            "port": CLOUD_PORT,
            "user": CLOUD_USER,
            "password": CLOUD_PASSWORD,
            "dbname": CLOUD_DATABASE,
            "sslmode": "require",
        }


def get_local_config():
    """Для парсеров — всегда локальная БД"""
    return get_db_config("local")


def get_cloud_config():
    """Для sync_to_cloud.py — всегда облако"""
    return get_db_config("cloud")


def get_connection_string(target: str = None):
    """Connection string для psycopg2 / psql"""
    cfg = get_db_config(target)
    ssl = "?sslmode=require" if cfg.get("sslmode") else ""
    return (
        f"postgresql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}{ssl}"
    )


# === Обратная совместимость ===
# Старый код использует эти переменные напрямую
DB_HOST = LOCAL_HOST if DB_TARGET == "local" else CLOUD_HOST
DB_PORT = LOCAL_PORT if DB_TARGET == "local" else CLOUD_PORT
DB_USER = LOCAL_USER if DB_TARGET == "local" else CLOUD_USER
DB_PASSWORD = LOCAL_PASSWORD if DB_TARGET == "local" else CLOUD_PASSWORD
DB_NAME = LOCAL_DATABASE if DB_TARGET == "local" else CLOUD_DATABASE

# Префиксы таблиц по магазинам
TABLE_PREFIXES = {
    "05gsm": "_05gsm",
    "greenspark": "greenspark",
    "lcdstock": "lcdstock",
    "liberti": "liberti",
    "memstech": "memstech",
    "moba": "moba",
    "moysklad": "moysklad",
    "orizhka": "orizhka",
    "profi": "profi",
    "signal23": "signal23",
    "taggsm": "taggsm",
    "gsmarena": "zip_gsmarena",
    "master": "master",
    "zip": "zip",
}

def get_table_name(shop: str, table: str) -> str:
    """
    Возвращает имя таблицы с префиксом магазина

    Примеры:
        get_table_name("liberti", "nomenclature") -> "liberti_nomenclature"
        get_table_name("liberti", "prices") -> "liberti_prices"
        get_table_name("liberti", "staging") -> "liberti_staging"
        get_table_name("liberti", "current_prices") -> "liberti_current_prices"
    """
    prefix = TABLE_PREFIXES.get(shop.lower(), shop.lower())
    return f"{prefix}_{table}"
