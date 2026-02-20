#!/usr/bin/env python3
"""
Write parsed Moba products to DB using a SINGLE persistent connection.
Uses Supabase Transaction mode pooler (port 6543) to avoid MaxClients issues.

Usage:
    python3 write_to_db.py                          # latest JSON from moba_data/
    python3 write_to_db.py --file path/to/file.json # specific file
    python3 write_to_db.py --dry-run                # count only, no DB write
"""
import json
import sys
import os
import argparse
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import get_db_config

TABLE_STAGING = "moba_staging"
TABLE_NOMENCLATURE = "moba_nomenclature"
TABLE_PRODUCT_URLS = "moba_product_urls"
TABLE_OUTLETS = "zip_outlets"

SHOP_CODE = "moba-online"
SHOP_NAME = "Moba.ru"
SHOP_CITY = "Москва"

BATCH_SIZE = 200


def p(msg):
    print(msg, flush=True)


def find_latest_json() -> str:
    data_dir = Path(__file__).resolve().parent / "moba_data"
    files = sorted(data_dir.glob("moba_products_*.json"), reverse=True)
    if not files:
        p("ERROR: No moba_products_*.json files found")
        sys.exit(1)
    return str(files[0])


def load_products(filepath: str) -> list:
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    products = data.get("products", []) if isinstance(data, dict) else data
    return products


def connect():
    cfg = get_db_config()
    # Для облачного Supabase: transaction mode pooler (port 6543)
    if cfg.get("sslmode"):
        cfg["port"] = 6543
        cfg.pop("tcp_user_timeout", None)
        cfg.pop("options", None)
    conn = psycopg2.connect(**cfg)
    conn.autocommit = True
    return conn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", "-f")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    filepath = args.file or find_latest_json()
    products = load_products(filepath)
    p(f"Loaded {len(products)} products from {filepath}")

    # Prepare rows
    rows = []
    for prod in products:
        article = (prod.get("article") or "").strip()
        if not article:
            continue
        name = (prod.get("name") or "")[:200]
        price = float(prod.get("price", 0) or 0)
        category = (prod.get("category") or "")[:100]
        url = prod.get("url", "")
        if url and not url.startswith("http"):
            url = f"https://moba.ru{url}"
        rows.append((article, name, price, category, url))

    p(f"Prepared {len(rows)} valid rows")

    if args.dry_run:
        unique = len(set(r[0] for r in rows))
        p(f"Dry run: {len(rows)} rows, {unique} unique articles")
        return

    # Connect
    p("Connecting to DB (port 6543, transaction mode) ...")
    conn = connect()
    cur = conn.cursor()

    # Test
    cur.execute("SELECT 1")
    p(f"Connected OK: {cur.fetchone()}")

    # Ensure outlet
    p(f"Ensuring outlet {SHOP_CODE} ...")
    cur.execute(f"""
        INSERT INTO {TABLE_OUTLETS} (code, city, name, is_active)
        VALUES (%s, %s, %s, true)
        ON CONFLICT (code) DO UPDATE SET city = EXCLUDED.city, name = EXCLUDED.name
        RETURNING id
    """, (SHOP_CODE, SHOP_CITY, SHOP_NAME))
    outlet_id = cur.fetchone()[0]
    p(f"Outlet ready: {outlet_id}")

    # Clear staging (DELETE instead of TRUNCATE — safer with transaction pooler)
    p("Clearing staging table ...")
    cur.execute(f"DELETE FROM {TABLE_STAGING}")
    p(f"Staging cleared ({cur.rowcount} rows deleted)")

    # Bulk insert to staging
    p(f"Inserting {len(rows)} rows to staging in batches of {BATCH_SIZE} ...")
    sql = f"""
        INSERT INTO {TABLE_STAGING} (article, name, price, category, url)
        VALUES %s
    """
    total = len(rows)
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        execute_values(cur, sql, batch, page_size=BATCH_SIZE)
        done = min(i + BATCH_SIZE, total)
        p(f"  [{done}/{total}] staged")

    p(f"All {total} rows staged")

    # Verify staging count
    cur.execute(f"SELECT count(*) FROM {TABLE_STAGING}")
    staging_count = cur.fetchone()[0]
    p(f"Staging count verified: {staging_count}")

    # UPSERT nomenclature (price в nomenclature)
    p("UPSERT staging → nomenclature (with price) ...")
    cur.execute(f"""
        INSERT INTO {TABLE_NOMENCLATURE} (article, name, category, price, first_seen_at, updated_at)
        SELECT DISTINCT ON (s.article)
            s.article, s.name, s.category, s.price, NOW(), NOW()
        FROM {TABLE_STAGING} s
        ON CONFLICT (article) DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            price = EXCLUDED.price,
            updated_at = NOW()
    """)
    p(f"Nomenclature: {cur.rowcount} rows upserted")

    # INSERT product_urls (multi-URL: сохраняем outlet_id)
    p("INSERT staging → product_urls ...")
    cur.execute(f"""
        INSERT INTO {TABLE_PRODUCT_URLS} (nomenclature_id, outlet_id, url, updated_at)
        SELECT DISTINCT ON (s.url)
            n.id, %s::uuid, s.url, NOW()
        FROM {TABLE_STAGING} s
        JOIN {TABLE_NOMENCLATURE} n ON n.article = s.article
        WHERE s.url IS NOT NULL AND s.url != ''
        ORDER BY s.url
        ON CONFLICT (url) DO NOTHING
    """, (str(outlet_id),))
    p(f"Product URLs: {cur.rowcount} rows inserted")

    # Final counts
    cur.execute(f"SELECT count(*) FROM {TABLE_NOMENCLATURE}")
    p(f"Total nomenclature: {cur.fetchone()[0]}")
    cur.execute(f"SELECT count(*) FROM {TABLE_PRODUCT_URLS}")
    p(f"Total product_urls: {cur.fetchone()[0]}")

    cur.close()
    conn.close()
    p("=== DONE ===")


if __name__ == "__main__":
    main()
