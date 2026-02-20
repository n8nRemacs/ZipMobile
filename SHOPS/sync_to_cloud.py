#!/usr/bin/env python3
"""
sync_to_cloud.py — Синхронизация финальных данных из Homelab в Supabase Cloud.

Синхронизирует ТОЛЬКО финальные таблицы для production API:
  - zip_nomenclature (каталог)
  - zip_current_prices (цены)
  - zip_nomenclature_models, zip_nomenclature_features (связи)
  - zip_dict_* (справочники — AI может создавать новые записи)

НЕ синхронизирует:
  - {shop}_* таблицы (per-shop данные остаются на Homelab)
  - zip_nomenclature_staging (рабочая таблица AI)
  - staging, parse_log, история

Usage:
    python3 sync_to_cloud.py                   # все таблицы
    python3 sync_to_cloud.py --dry-run         # только подсчёт
    python3 sync_to_cloud.py --only-catalog    # только zip_nomenclature + связи
    python3 sync_to_cloud.py --only-prices     # только zip_current_prices/stock
    python3 sync_to_cloud.py --only-dicts      # только справочники
    python3 sync_to_cloud.py --table zip_dict_brands  # одна таблица
"""
import argparse
import time

import psycopg2
from psycopg2.extras import execute_values

from db_config import get_cloud_config, get_local_config

# Таблицы для синхронизации: table_name → conflict_column(s)
# None = TRUNCATE + INSERT (полная замена)
# str = ON CONFLICT (col) DO UPDATE (UPSERT)

CATALOG_TABLES = {
    "zip_nomenclature": "id",
    "zip_nomenclature_models": None,       # полная замена
    "zip_nomenclature_features": None,     # полная замена
}

PRICE_TABLES = {
    "zip_current_prices": None,            # полная замена (snapshot)
}

DICT_TABLES = {
    "zip_dict_brands": "id",
    "zip_dict_models": "id",
    "zip_dict_colors": "id",
    "zip_dict_qualities": "id",
    "zip_dict_part_types": "id",
    "zip_dict_features": "id",
    "zip_dict_device_types": "id",
    "zip_dict_categories": "id",
    "zip_dict_price_types": "id",
    "zip_product_types": "id",
    "zip_nomenclature_types": "id",
    "zip_accessory_types": "id",
    "zip_equipment_types": "id",
    "zip_shop_price_types": "id",
    "zip_brand_part_type_features": "id",
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


def sync_table_upsert(local_cur, cloud_cur, table_name, conflict_col, dry_run=False):
    """UPSERT: вставить новые, обновить существующие."""
    if not table_exists(local_cur, table_name):
        p(f"  {table_name}: не существует локально, пропускаем")
        return 0

    local_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = local_cur.fetchone()[0]

    if count == 0:
        p(f"  {table_name}: пусто, пропускаем")
        return 0

    if dry_run:
        p(f"  {table_name}: {count} строк (dry-run)")
        return count

    # Получаем колонки
    local_cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
    cols = [desc[0] for desc in local_cur.description]
    cols_str = ", ".join(cols)

    # Проверяем какие колонки есть в облаке
    if table_exists(cloud_cur, table_name):
        cloud_cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
        cloud_cols = {desc[0] for desc in cloud_cur.description}
        cols = [c for c in cols if c in cloud_cols]
        cols_str = ", ".join(cols)

    # Читаем данные
    p(f"  {table_name}: читаю {count} строк...")
    local_cur.execute(f"SELECT {cols_str} FROM {table_name}")
    rows = local_cur.fetchall()

    # Формируем UPSERT
    update_cols = [c for c in cols if c != conflict_col]
    update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
    placeholders = ", ".join(["%s"] * len(cols))
    template = f"({placeholders})"

    sql = f"""
        INSERT INTO {table_name} ({cols_str}) VALUES %s
        ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set}
    """

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        execute_values(cloud_cur, sql, batch, template=template, page_size=BATCH_SIZE)
        done = min(i + BATCH_SIZE, len(rows))
        if done % 5000 == 0 or done == len(rows):
            p(f"    [{done}/{len(rows)}]")

    p(f"  {table_name}: {len(rows)} строк синхронизировано")
    return len(rows)


def sync_table_replace(local_cur, cloud_cur, table_name, dry_run=False):
    """TRUNCATE + INSERT: полная замена данных в Cloud."""
    if not table_exists(local_cur, table_name):
        p(f"  {table_name}: не существует локально, пропускаем")
        return 0

    local_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = local_cur.fetchone()[0]

    if dry_run:
        p(f"  {table_name}: {count} строк (dry-run, полная замена)")
        return count

    # Получаем колонки
    local_cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
    cols = [desc[0] for desc in local_cur.description]
    cols_str = ", ".join(cols)

    # Проверяем какие колонки есть в облаке
    if table_exists(cloud_cur, table_name):
        cloud_cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
        cloud_cols = {desc[0] for desc in cloud_cur.description}
        cols = [c for c in cols if c in cloud_cols]
        cols_str = ", ".join(cols)

    if count == 0:
        # Просто очищаем облако
        cloud_cur.execute(f"TRUNCATE TABLE {table_name} CASCADE")
        p(f"  {table_name}: очищено (0 строк)")
        return 0

    # Читаем данные
    p(f"  {table_name}: читаю {count} строк...")
    local_cur.execute(f"SELECT {cols_str} FROM {table_name}")
    rows = local_cur.fetchall()

    # TRUNCATE + INSERT
    cloud_cur.execute(f"TRUNCATE TABLE {table_name} CASCADE")

    placeholders = ", ".join(["%s"] * len(cols))
    template = f"({placeholders})"
    sql = f"INSERT INTO {table_name} ({cols_str}) VALUES %s"

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        execute_values(cloud_cur, sql, batch, template=template, page_size=BATCH_SIZE)
        done = min(i + BATCH_SIZE, len(rows))
        if done % 5000 == 0 or done == len(rows):
            p(f"    [{done}/{len(rows)}]")

    p(f"  {table_name}: {len(rows)} строк (полная замена)")
    return len(rows)


def sync_table(local_cur, cloud_cur, table_name, conflict_col, dry_run=False):
    """Синхронизирует одну таблицу."""
    if conflict_col is None:
        return sync_table_replace(local_cur, cloud_cur, table_name, dry_run)
    else:
        return sync_table_upsert(local_cur, cloud_cur, table_name, conflict_col, dry_run)


def main():
    ap = argparse.ArgumentParser(description="Sync final data from Homelab to Supabase Cloud")
    ap.add_argument("--dry-run", action="store_true", help="Только подсчёт")
    ap.add_argument("--only-catalog", action="store_true", help="Только zip_nomenclature + связи")
    ap.add_argument("--only-prices", action="store_true", help="Только zip_current_prices/stock")
    ap.add_argument("--only-dicts", action="store_true", help="Только справочники")
    ap.add_argument("--table", help="Одна конкретная таблица")
    args = ap.parse_args()

    p("Подключение к Local...")
    local_conn = psycopg2.connect(**get_local_config())
    local_cur = local_conn.cursor()

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

    start = time.time()
    total = 0

    # Определяем какие таблицы синхронизировать
    if args.table:
        # Одна конкретная таблица
        all_tables = {**CATALOG_TABLES, **PRICE_TABLES, **DICT_TABLES}
        if args.table not in all_tables:
            p(f"WARN: {args.table} не в списке таблиц для синхронизации")
            p(f"Доступные: {', '.join(sorted(all_tables.keys()))}")
            return
        tables = {args.table: all_tables[args.table]}
    elif args.only_catalog:
        tables = CATALOG_TABLES
    elif args.only_prices:
        tables = PRICE_TABLES
    elif args.only_dicts:
        tables = DICT_TABLES
    else:
        # Все таблицы: сначала справочники, потом каталог, потом цены
        tables = {**DICT_TABLES, **CATALOG_TABLES, **PRICE_TABLES}

    p(f"\nСинхронизация {len(tables)} таблиц...")
    p("=" * 50)

    for table_name, conflict_col in tables.items():
        try:
            total += sync_table(local_cur, cloud_cur, table_name, conflict_col, dry_run=args.dry_run)
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

    local_cur.close()
    local_conn.close()
    cloud_cur.close()
    cloud_conn.close()


if __name__ == "__main__":
    main()
