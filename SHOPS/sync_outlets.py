#!/usr/bin/env python3
"""
sync_outlets.py — Синхронизация zip_outlets из Supabase Cloud в локальную БД.
Запускать перед парсерами (по cron), чтобы локальная копия была актуальной.

Usage:
    python3 sync_outlets.py             # синхронизация
    python3 sync_outlets.py --dry-run   # только подсчёт
"""
import argparse
import time

import psycopg2
from psycopg2.extras import execute_values

from db_config import get_cloud_config, get_local_config


def p(msg):
    print(msg, flush=True)


def main():
    ap = argparse.ArgumentParser(description="Sync zip_outlets from Cloud to Local")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    p("Подключение к Cloud...")
    cloud_conn = psycopg2.connect(**get_cloud_config())
    cloud_cur = cloud_conn.cursor()

    cloud_cur.execute("SELECT COUNT(*) FROM zip_outlets")
    count = cloud_cur.fetchone()[0]
    p(f"zip_outlets в облаке: {count} строк")

    if args.dry_run:
        p("Dry-run, выходим")
        cloud_cur.close()
        cloud_conn.close()
        return

    # Читаем все колонки кроме id (который UUID, нужен как есть)
    cloud_cur.execute("SELECT * FROM zip_outlets LIMIT 0")
    cols = [desc[0] for desc in cloud_cur.description]
    cols_str = ", ".join(cols)

    cloud_cur.execute(f"SELECT {cols_str} FROM zip_outlets")
    rows = cloud_cur.fetchall()

    p("Подключение к Local...")
    local_conn = psycopg2.connect(**get_local_config())
    local_conn.autocommit = True
    local_cur = local_conn.cursor()

    # UPSERT по id (UUID PK)
    update_cols = [c for c in cols if c != "id"]
    update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
    placeholders = ", ".join(["%s"] * len(cols))

    sql = f"""
        INSERT INTO zip_outlets ({cols_str}) VALUES %s
        ON CONFLICT (id) DO UPDATE SET {update_set}
    """
    template = f"({placeholders})"

    start = time.time()
    execute_values(local_cur, sql, rows, template=template, page_size=500)
    elapsed = time.time() - start

    # Проверка
    local_cur.execute("SELECT COUNT(*) FROM zip_outlets")
    local_count = local_cur.fetchone()[0]

    p(f"Синхронизировано: {len(rows)} строк за {elapsed:.1f}с")
    p(f"zip_outlets в локальной БД: {local_count}")

    cloud_cur.close()
    cloud_conn.close()
    local_cur.close()
    local_conn.close()

    p("=== ГОТОВО ===")


if __name__ == "__main__":
    main()
