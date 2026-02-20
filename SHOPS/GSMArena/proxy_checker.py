#!/usr/bin/env python3
"""
Proxy Checker для GSMArena
- Берёт ТОЛЬКО raw (непроверенные) прокси из PostgreSQL
- Использует FOR UPDATE SKIP LOCKED чтобы несколько чеккеров не пересекались
- Помечает: working (годные) / dead (негодные)
- Парсер берёт только working прокси
"""

import time
import requests
import psycopg2
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import signal
import sys

# ============================================================================
# Configuration
# ============================================================================

DB_CONFIG = {
    'host': '85.198.98.104',
    'port': 5433,
    'user': 'postgres',
    'password': 'Mi31415926pSss!',
    'database': 'postgres'
}

# Тестовый URL - должен возвращать 200 и содержать маркер
TEST_URL = "https://www.gsmarena.com/makers.php3"
TEST_MARKER = "Samsung"

# Настройки
BATCH_SIZE = 100
TEST_WORKERS = 50
TEST_TIMEOUT = 12
PAUSE_BETWEEN_BATCHES = 1

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.5',
}

running = True


def signal_handler(sig, frame):
    global running
    print("\n[CHECKER] Stopping...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ============================================================================
# Database
# ============================================================================

def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn


def grab_raw_proxies(limit: int = BATCH_SIZE) -> list:
    """
    Взять raw прокси для проверки с блокировкой.
    Использует SELECT FOR UPDATE SKIP LOCKED - несколько чеккеров не возьмут одни и те же.
    Сразу помечает их как 'checking' чтобы другие не взяли.
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Берём и сразу блокируем
        cur.execute("""
            UPDATE zip_proxies
            SET status = 'checking'
            WHERE proxy IN (
                SELECT proxy FROM zip_proxies
                WHERE status = 'raw'
                ORDER BY created_at
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            RETURNING proxy
        """, (limit,))

        proxies = [row[0] for row in cur.fetchall()]
        conn.commit()
        return proxies

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] grab_raw_proxies: {e}")
        return []
    finally:
        conn.close()


def mark_working(proxy: str):
    """Пометить прокси как рабочий"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE zip_proxies
            SET status = 'working',
                last_tested_at = NOW(),
                success_count = success_count + 1
            WHERE proxy = %s
        """, (proxy,))
        conn.commit()
    finally:
        conn.close()


def mark_dead(proxy: str):
    """Пометить прокси как нерабочий"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE zip_proxies
            SET status = 'dead',
                last_tested_at = NOW(),
                fail_count = fail_count + 1
            WHERE proxy = %s
        """, (proxy,))
        conn.commit()
    finally:
        conn.close()


def get_stats() -> dict:
    """Получить статистику"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM zip_proxies GROUP BY status")
    stats = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return stats


def reset_checking():
    """Сбросить зависшие checking прокси обратно в raw"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE zip_proxies
        SET status = 'raw'
        WHERE status = 'checking'
    """)
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


# ============================================================================
# Testing
# ============================================================================

def test_proxy(proxy: str) -> tuple:
    """Тестировать один прокси. Returns: (proxy, is_working)"""
    try:
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}

        response = requests.get(
            TEST_URL,
            proxies=proxies,
            headers=HEADERS,
            timeout=TEST_TIMEOUT,
            allow_redirects=True
        )

        # Успех = статус 200 + маркер на странице
        if response.status_code == 200 and TEST_MARKER in response.text:
            return (proxy, True)
        return (proxy, False)

    except:
        return (proxy, False)


def test_batch(proxies: list) -> tuple:
    """Тестировать пачку параллельно. Returns: (working_count, dead_count)"""
    working = 0
    dead = 0

    with ThreadPoolExecutor(max_workers=TEST_WORKERS) as executor:
        futures = {executor.submit(test_proxy, p): p for p in proxies}

        for future in as_completed(futures):
            proxy, is_working = future.result()

            if is_working:
                mark_working(proxy)
                working += 1
                print(f"  ✓ {proxy}")
            else:
                mark_dead(proxy)
                dead += 1

    return (working, dead)


# ============================================================================
# Main
# ============================================================================

def run_checker(daemon: bool = False):
    """Запустить чеккер"""
    global running

    print(f"[CHECKER] Proxy Checker started")
    print(f"[CHECKER] URL: {TEST_URL}")
    print(f"[CHECKER] Workers: {TEST_WORKERS}, Batch: {BATCH_SIZE}")

    # Сбросить зависшие checking
    reset_count = reset_checking()
    if reset_count:
        print(f"[CHECKER] Reset {reset_count} stuck 'checking' proxies to 'raw'")

    stats = get_stats()
    print(f"[CHECKER] Stats: raw={stats.get('raw', 0)}, working={stats.get('working', 0)}, dead={stats.get('dead', 0)}")
    print()

    iteration = 0
    total_working = 0
    total_dead = 0

    while running:
        iteration += 1

        # Берём пачку raw прокси (с блокировкой)
        proxies = grab_raw_proxies(BATCH_SIZE)

        if not proxies:
            stats = get_stats()
            print(f"[CHECKER] No raw proxies left. working={stats.get('working', 0)}, dead={stats.get('dead', 0)}")
            if daemon:
                print("[CHECKER] Waiting for new proxies...")
                time.sleep(60)
                continue
            else:
                break

        print(f"[CHECKER] #{iteration} Testing {len(proxies)} proxies...")

        # Тестируем
        working, dead = test_batch(proxies)
        total_working += working
        total_dead += dead

        # Статистика
        stats = get_stats()
        print(f"[CHECKER] Batch: +{working} working, +{dead} dead")
        print(f"[CHECKER] Total: raw={stats.get('raw', 0)}, working={stats.get('working', 0)}, dead={stats.get('dead', 0)}\n")

        if not daemon:
            break

        time.sleep(PAUSE_BETWEEN_BATCHES)

    print(f"\n[CHECKER] Done. Found {total_working} working proxies, {total_dead} dead")


def show_status():
    """Показать статус"""
    stats = get_stats()
    total = sum(stats.values())

    print("\n=== Proxy Status ===")
    print(f"Total:    {total}")
    print(f"  raw:      {stats.get('raw', 0):>6} (не проверены)")
    print(f"  checking: {stats.get('checking', 0):>6} (проверяются)")
    print(f"  working:  {stats.get('working', 0):>6} (годные)")
    print(f"  dead:     {stats.get('dead', 0):>6} (негодные)")
    print(f"  used:     {stats.get('used', 0):>6} (используются)")
    print(f"  banned:   {stats.get('banned', 0):>6} (забанены)")

    # Последние рабочие
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT proxy, success_count, last_tested_at
        FROM zip_proxies
        WHERE status = 'working'
        ORDER BY last_tested_at DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    conn.close()

    if rows:
        print(f"\nRecent working proxies:")
        for proxy, success, tested in rows:
            print(f"  {proxy} (success: {success})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Proxy Checker for GSMArena")
    parser.add_argument('--daemon', '-d', action='store_true', help='Run continuously')
    parser.add_argument('--status', '-s', action='store_true', help='Show status')
    parser.add_argument('--reset', action='store_true', help='Reset checking to raw')
    parser.add_argument('--batch', '-b', type=int, default=BATCH_SIZE, help=f'Batch size (default: {BATCH_SIZE})')
    parser.add_argument('--workers', '-w', type=int, default=TEST_WORKERS, help=f'Workers (default: {TEST_WORKERS})')
    args = parser.parse_args()

    BATCH_SIZE = args.batch
    TEST_WORKERS = args.workers

    if args.status:
        show_status()
    elif args.reset:
        count = reset_checking()
        print(f"Reset {count} proxies from 'checking' to 'raw'")
    else:
        run_checker(daemon=args.daemon)
