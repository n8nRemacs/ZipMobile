#!/usr/bin/env python3
"""
sync_from_cloud.py — Синхронизация инфраструктурных таблиц из Cloud в Homelab.

Запускать ПЕРЕД парсерами (по cron), чтобы локальная копия была актуальной.
Синхронизирует таблицы, которые управляются из админки (Cloud → Homelab):
  - zip_shops (магазины)
  - zip_outlets (торговые точки)
  - zip_cities (города)
  - zip_timezones (часовые пояса)
  - zip_countries (страны)

Usage:
    python3 sync_from_cloud.py             # синхронизация
    python3 sync_from_cloud.py --dry-run   # только подсчёт
    python3 sync_from_cloud.py --table zip_outlets  # одна таблица
"""
import argparse
import time

import psycopg2
from psycopg2.extras import execute_values

from db_config import get_cloud_config, get_local_config

# Таблицы для синхронизации из Cloud → Homelab
# table_name → primary key column
SYNC_TABLES = {
    "zip_shops": "id",
    "zip_outlets": "id",
    "zip_cities": "id",
    "zip_timezones": "id",
    "zip_countries": "id",
}

BATCH_SIZE = 500


def p(msg):
    print(msg, flush=True)


def table_exists(cur, table_name):
    """Проверяет существование таблицы."""
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
    """, (table_name,))
    return cur.fetchone()[0]


def sync_table(cloud_cur, local_cur, table_name, pk_col, dry_run=False):
    """UPSERT из Cloud в Homelab."""
    if not table_exists(cloud_cur, table_name):
        p(f"  {table_name}: не существует в облаке, пропускаем")
        return 0

    cloud_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cloud_cur.fetchone()[0]

    if count == 0:
        p(f"  {table_name}: пусто в облаке")
        return 0

    if dry_run:
        p(f"  {table_name}: {count} строк (dry-run)")
        return count

    # Получаем колонки из Cloud
    cloud_cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
    cloud_cols = [desc[0] for desc in cloud_cur.description]

    # Проверяем пересечение с локальными колонками
    if table_exists(local_cur, table_name):
        local_cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
        local_cols = {desc[0] for desc in local_cur.description}
        cols = [c for c in cloud_cols if c in local_cols]
    else:
        cols = cloud_cols

    cols_str = ", ".join(cols)

    # Читаем данные из Cloud
    p(f"  {table_name}: читаю {count} строк из облака...")
    cloud_cur.execute(f"SELECT {cols_str} FROM {table_name}")
    rows = cloud_cur.fetchall()

    # UPSERT в локальную БД
    update_cols = [c for c in cols if c != pk_col]
    update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
    placeholders = ", ".join(["%s"] * len(cols))
    template = f"({placeholders})"

    sql = f"""
        INSERT INTO {table_name} ({cols_str}) VALUES %s
        ON CONFLICT ({pk_col}) DO UPDATE SET {update_set}
    """

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        execute_values(local_cur, sql, batch, template=template, page_size=BATCH_SIZE)

    p(f"  {table_name}: {len(rows)} строк синхронизировано")
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description="Sync infrastructure tables from Cloud to Homelab")
    ap.add_argument("--dry-run", action="store_true", help="Только подсчёт")
    ap.add_argument("--table", help="Одна конкретная таблица")
    args = ap.parse_args()

    p("Подключение к Cloud...")
    cloud_cfg = get_cloud_config()
    cloud_cfg["port"] = 6543
    cloud_cfg.pop("options", None)
    cloud_cfg["connect_timeout"] = 30
    cloud_cfg["keepalives"] = 1
    cloud_cfg["keepalives_idle"] = 30
    cloud_cfg["keepalives_interval"] = 10
    cloud_cfg["keepalives_count"] = 3
    cloud_conn = psycopg2.connect(**cloud_cfg)
    cloud_conn.autocommit = True
    cloud_cur = cloud_conn.cursor()

    p("Подключение к Local...")
    local_conn = psycopg2.connect(**get_local_config())
    local_conn.autocommit = True
    local_cur = local_conn.cursor()

    start = time.time()
    total = 0

    if args.table:
        if args.table not in SYNC_TABLES:
            p(f"WARN: {args.table} не в списке. Доступные: {', '.join(SYNC_TABLES.keys())}")
            return
        tables = {args.table: SYNC_TABLES[args.table]}
    else:
        tables = SYNC_TABLES

    p(f"\nСинхронизация {len(tables)} таблиц из Cloud...")
    p("=" * 50)

    for table_name, pk_col in tables.items():
        try:
            total += sync_table(cloud_cur, local_cur, table_name, pk_col, dry_run=args.dry_run)
        except Exception as e:
            p(f"  ERROR {table_name}: {e}")
            # Переподключение при ошибке
            try:
                cloud_cur.close()
                cloud_conn.close()
            except Exception:
                pass
            cloud_conn = psycopg2.connect(**cloud_cfg)
            cloud_conn.autocommit = True
            cloud_cur = cloud_conn.cursor()

    elapsed = time.time() - start
    p(f"\n{'=' * 50}")
    p(f"ИТОГО: {total} строк за {elapsed:.1f}с")
    p(f"{'=' * 50}")

    cloud_cur.close()
    cloud_conn.close()
    local_cur.close()
    local_conn.close()

    p("=== ГОТОВО ===")


if __name__ == "__main__":
    main()
