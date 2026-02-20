#!/usr/bin/env python3
"""
seed_local_from_cloud.py — Начальная миграция данных из Supabase Cloud в локальную БД.
Однократный запуск после init_local_db.sql.

Переносит:
  - zip_outlets (центральная таблица)
  - {shop}_nomenclature (для каждого магазина)
  - {shop}_prices (для каждого магазина)
  - НЕ переносит staging (пересоздаётся при каждом парсинге)

Usage:
    python3 seed_local_from_cloud.py                # всё
    python3 seed_local_from_cloud.py --shop moba    # только один магазин
    python3 seed_local_from_cloud.py --dry-run      # только подсчёт
    python3 seed_local_from_cloud.py --outlets-only  # только zip_outlets
"""
import argparse
import sys
import time

import psycopg2
from psycopg2.extras import execute_values

from db_config import get_cloud_config, get_local_config

SHOPS = [
    "_05gsm", "memstech", "signal23", "taggsm", "liberti",
    "profi", "lcdstock", "orizhka", "moysklad_naffas", "moba",
]

TABLE_OVERRIDES = {}

BATCH_SIZE = 2000  # Локально можно лить большими батчами


def p(msg):
    print(msg, flush=True)


def get_table(shop, table_type):
    if shop in TABLE_OVERRIDES and table_type in TABLE_OVERRIDES[shop]:
        return TABLE_OVERRIDES[shop][table_type]
    return f"{shop}_{table_type}"


def copy_table(cloud_cur, local_cur, table_name, conflict_col=None, dry_run=False):
    """Копирует таблицу из облака в локальную БД.
    Использует колонки ЛОКАЛЬНОЙ таблицы (они могут отличаться от облака).
    """
    cloud_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cloud_cur.fetchone()[0]
    if count == 0:
        p(f"  {table_name}: пусто, пропускаем")
        return 0

    if dry_run:
        p(f"  {table_name}: {count} строк (dry-run)")
        return count

    # Колонки из ЛОКАЛЬНОЙ таблицы (без id)
    local_cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
    local_cols = [desc[0] for desc in local_cur.description]
    cols_no_id = [c for c in local_cols if c != "id"]

    # Проверяем какие колонки есть в облаке
    cloud_cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
    cloud_cols = {desc[0] for desc in cloud_cur.description}

    # Берём только пересечение
    common_cols = [c for c in cols_no_id if c in cloud_cols]
    cols_str = ", ".join(common_cols)

    # Читаем данные порциями для больших таблиц
    p(f"  {table_name}: читаю {count} строк из облака...")
    cloud_cur.execute(f"SELECT {cols_str} FROM {table_name}")
    rows = cloud_cur.fetchall()

    # Вставляем в локальную БД
    placeholders = ", ".join(["%s"] * len(common_cols))
    if conflict_col:
        update_set = ", ".join(
            [f"{c} = EXCLUDED.{c}" for c in common_cols if c != conflict_col]
        )
        sql = f"""
            INSERT INTO {table_name} ({cols_str}) VALUES %s
            ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set}
        """
    else:
        sql = f"INSERT INTO {table_name} ({cols_str}) VALUES %s ON CONFLICT DO NOTHING"

    template = f"({placeholders})"
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        execute_values(local_cur, sql, batch, template=template, page_size=BATCH_SIZE)
        done = min(i + BATCH_SIZE, len(rows))
        if done % 10000 == 0 or done == len(rows):
            p(f"    [{done}/{len(rows)}]")

    p(f"  {table_name}: {len(rows)} строк скопировано")
    return len(rows)


def seed_outlets(cloud_cur, local_cur, dry_run=False):
    """Копирует zip_outlets (только нужные колонки)."""
    p("--- zip_outlets ---")
    OUTLET_COLS = "id, shop_id, code, name, city, address, phone, is_active, created_at, updated_at"

    cloud_cur.execute("SELECT COUNT(*) FROM zip_outlets")
    count = cloud_cur.fetchone()[0]
    if dry_run:
        p(f"  zip_outlets: {count} строк (dry-run)")
        return count

    cloud_cur.execute(f"SELECT {OUTLET_COLS} FROM zip_outlets")
    rows = cloud_cur.fetchall()

    sql = f"""
        INSERT INTO zip_outlets ({OUTLET_COLS}) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            shop_id = EXCLUDED.shop_id, code = EXCLUDED.code,
            name = EXCLUDED.name, city = EXCLUDED.city,
            address = EXCLUDED.address, phone = EXCLUDED.phone,
            is_active = EXCLUDED.is_active, updated_at = EXCLUDED.updated_at
    """
    execute_values(local_cur, sql, rows, page_size=500)
    p(f"  zip_outlets: {len(rows)} строк скопировано")
    return len(rows)


def seed_shop(shop, cloud_cur, local_cur, dry_run=False):
    """Копирует nomenclature + prices для одного магазина."""
    p(f"--- {shop} ---")
    nom_table = get_table(shop, "nomenclature")
    prices_table = get_table(shop, "prices")

    total = 0
    total += copy_table(cloud_cur, local_cur, nom_table, conflict_col="article", dry_run=dry_run)
    total += copy_table(cloud_cur, local_cur, prices_table, dry_run=dry_run)
    return total


def main():
    ap = argparse.ArgumentParser(description="Seed local DB from Supabase Cloud")
    ap.add_argument("--shop", help="Только один магазин (prefix)")
    ap.add_argument("--dry-run", action="store_true", help="Только подсчёт")
    ap.add_argument("--outlets-only", action="store_true", help="Только zip_outlets")
    args = ap.parse_args()

    p("Подключение к Cloud...")
    cloud_cfg = get_cloud_config()
    cloud_cfg["port"] = 6543  # Transaction mode pooler — стабильнее
    cloud_cfg.pop("options", None)  # port 6543 не поддерживает options
    cloud_cfg["connect_timeout"] = 30
    cloud_cfg["keepalives"] = 1
    cloud_cfg["keepalives_idle"] = 30
    cloud_cfg["keepalives_interval"] = 10
    cloud_cfg["keepalives_count"] = 3
    cloud_conn = psycopg2.connect(**cloud_cfg)
    cloud_conn.autocommit = True  # transaction mode pooler требует
    cloud_cur = cloud_conn.cursor()

    p("Подключение к Local...")
    local_conn = psycopg2.connect(**get_local_config())
    local_conn.autocommit = True
    local_cur = local_conn.cursor()

    start = time.time()
    total = 0

    # zip_outlets — всегда
    total += seed_outlets(cloud_cur, local_cur, dry_run=args.dry_run)

    if not args.outlets_only:
        shops = [args.shop] if args.shop else SHOPS
        for shop in shops:
            if shop not in SHOPS and args.shop:
                p(f"WARN: {shop} не в списке, пропускаем")
                continue
            try:
                total += seed_shop(shop, cloud_cur, local_cur, dry_run=args.dry_run)
            except Exception as e:
                p(f"  ERROR {shop}: {e}")
                p(f"  Переподключение к Cloud...")
                try:
                    cloud_cur.close()
                    cloud_conn.close()
                except Exception:
                    pass
                cloud_conn = psycopg2.connect(**cloud_cfg)
                cloud_conn.autocommit = True
                cloud_cur = cloud_conn.cursor()

    elapsed = time.time() - start
    p(f"\n=== ГОТОВО: {total} строк за {elapsed:.1f}с ===")

    cloud_cur.close()
    cloud_conn.close()
    local_cur.close()
    local_conn.close()


if __name__ == "__main__":
    main()
