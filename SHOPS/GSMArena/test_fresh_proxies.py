#!/usr/bin/env python3
"""Test fresh proxies against GSMArena and add working ones to DB"""

import requests
import psycopg2
import concurrent.futures
import sys
from datetime import datetime

DB_CONFIG = {
    'host': '85.198.98.104',
    'port': 5433,
    'user': 'postgres',
    'password': 'Mi31415926pSss!',
    'database': 'postgres'
}

TEST_URL = "https://www.gsmarena.com/samsung-phones-9.php"
TIMEOUT = 10


def test_proxy(proxy):
    """Test if proxy works for GSMArena"""
    proxy = proxy.strip()
    if not proxy:
        return None

    try:
        proxies = {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(TEST_URL, proxies=proxies, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 200 and 'Samsung' in resp.text:
            return proxy
    except:
        pass
    return None


def main():
    # Read proxies
    with open('/tmp/fresh_proxies.txt', 'r') as f:
        all_proxies = [p.strip() for p in f.readlines() if p.strip()]

    print(f"Testing {len(all_proxies)} proxies against GSMArena...")

    # Test first 500 proxies in parallel
    test_batch = all_proxies[:500]
    working = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(test_proxy, p): p for p in test_batch}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            if result:
                working.append(result)
                print(f"[{i+1}/{len(test_batch)}] Working: {result} (total: {len(working)})")
            else:
                if (i+1) % 50 == 0:
                    print(f"[{i+1}/{len(test_batch)}] tested, {len(working)} working")

    print(f"\nFound {len(working)} working proxies for GSMArena")

    if not working:
        print("No working proxies found!")
        return

    # Add to database
    print("\nAdding to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    added = 0
    for proxy in working:
        try:
            cur.execute("""
                INSERT INTO zip_proxies (proxy, status, success_count)
                VALUES (%s, 'working', 10)
                ON CONFLICT (proxy) DO UPDATE
                SET status = 'working',
                    success_count = 10,
                    banned_sites = array_remove(COALESCE(zip_proxies.banned_sites, '{}'), 'gsmarena')
            """, (proxy,))
            added += 1
        except Exception as e:
            print(f"Error adding {proxy}: {e}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"Added/updated {added} proxies in database")


if __name__ == "__main__":
    main()
