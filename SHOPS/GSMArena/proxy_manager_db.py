#!/usr/bin/env python3
"""
Менеджер прокси с хранением в PostgreSQL
- Все серверы используют общий пул прокси
- Автоматическая синхронизация
- Отслеживание банов по сайтам
"""

import os
import time
import random
import requests
import threading
import psycopg2
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List

# Настройки БД
DB_CONFIG = {
    'host': '85.198.98.104',
    'port': 5433,
    'user': 'postgres',
    'password': 'Mi31415926pSss!',
    'database': 'postgres'
}

# Настройки тестирования
TEST_URL = "https://www.gsmarena.com/"
TEST_TIMEOUT = 10
TEST_WORKERS = 30
BATCH_SIZE = 500

# GitHub sources
GITHUB_PROXY_SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


class ProxyManagerDB:
    """Менеджер прокси с хранением в PostgreSQL"""

    def __init__(self, site_name: str = "gsmarena"):
        self.site_name = site_name
        self.running = False
        self._conn = None

    def _get_conn(self):
        """Получить соединение с БД"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**DB_CONFIG)
            self._conn.autocommit = True
        return self._conn

    def fetch_and_save_proxies(self) -> int:
        """Скачать прокси из источников и сохранить в БД"""
        all_proxies = []

        for url in GITHUB_PROXY_SOURCES:
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
                for line in response.text.split('\n'):
                    line = line.strip()
                    if ':' in line and line[0].isdigit():
                        proxy = line.split()[0]
                        all_proxies.append(proxy)
                print(f"[PROXY] Fetched from {url.split('/')[-1]}: +{len(response.text.split())}")
            except Exception as e:
                print(f"[PROXY] Error fetching {url}: {e}")

        # Убираем дубликаты
        unique = list(set(all_proxies))
        print(f"[PROXY] Total unique proxies: {len(unique)}")

        # Сохраняем в БД (INSERT IGNORE)
        conn = self._get_conn()
        cur = conn.cursor()

        inserted = 0
        for proxy in unique:
            try:
                cur.execute("""
                    INSERT INTO zip_proxies (proxy, status)
                    VALUES (%s, 'raw')
                    ON CONFLICT (proxy) DO NOTHING
                """, (proxy,))
                if cur.rowcount > 0:
                    inserted += 1
            except:
                pass

        print(f"[PROXY] Inserted {inserted} new proxies to DB")
        return inserted

    def get_proxies_to_test(self, limit: int = BATCH_SIZE) -> List[str]:
        """Получить прокси для тестирования (raw или давно не тестированные)"""
        conn = self._get_conn()
        cur = conn.cursor()

        # Берём raw прокси или те, что не тестировались > 1 часа
        cur.execute("""
            SELECT proxy FROM zip_proxies
            WHERE status = 'raw'
               OR (status != 'banned' AND (last_tested_at IS NULL OR last_tested_at < NOW() - INTERVAL '1 hour'))
            ORDER BY last_tested_at NULLS FIRST
            LIMIT %s
        """, (limit,))

        return [row[0] for row in cur.fetchall()]

    def get_working_proxy(self, exclude_banned_for: str = None) -> Optional[str]:
        """Получить рабочий прокси для использования"""
        conn = self._get_conn()
        cur = conn.cursor()

        site = exclude_banned_for or self.site_name

        # Берём рабочий прокси, не забаненный для этого сайта
        cur.execute("""
            SELECT proxy FROM zip_proxies
            WHERE status = 'working'
              AND NOT (%s = ANY(banned_sites))
            ORDER BY last_used_at NULLS FIRST, success_count DESC
            LIMIT 1
        """, (site,))

        row = cur.fetchone()
        if row:
            proxy = row[0]
            # Отмечаем использование
            cur.execute("""
                UPDATE zip_proxies
                SET last_used_at = NOW(), status = 'used'
                WHERE proxy = %s
            """, (proxy,))
            return proxy
        return None

    def mark_working(self, proxy: str):
        """Отметить прокси как рабочий"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE zip_proxies
            SET status = 'working',
                last_tested_at = NOW(),
                success_count = success_count + 1
            WHERE proxy = %s
        """, (proxy,))

    def mark_failed(self, proxy: str):
        """Отметить неудачную попытку"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE zip_proxies
            SET last_tested_at = NOW(),
                fail_count = fail_count + 1,
                status = CASE WHEN fail_count >= 3 THEN 'dead' ELSE status END
            WHERE proxy = %s
        """, (proxy,))

    def mark_banned(self, proxy: str, site: str = None):
        """Отметить прокси как забаненный сайтом"""
        site = site or self.site_name
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE zip_proxies
            SET banned_sites = array_append(banned_sites, %s),
                status = CASE
                    WHEN array_length(banned_sites, 1) >= 3 THEN 'banned'
                    ELSE status
                END
            WHERE proxy = %s AND NOT (%s = ANY(banned_sites))
        """, (site, proxy, site))
        print(f"[PROXY] Banned by {site}: {proxy}")

    def return_to_pool(self, proxy: str):
        """Вернуть прокси в пул рабочих"""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE zip_proxies
            SET status = 'working'
            WHERE proxy = %s AND status = 'used'
        """, (proxy,))

    def test_proxy(self, proxy: str) -> bool:
        """Тестировать прокси"""
        try:
            response = requests.get(
                TEST_URL,
                proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                timeout=TEST_TIMEOUT,
                headers=HEADERS
            )
            return response.status_code == 200
        except:
            return False

    def test_batch(self, proxies: List[str]) -> int:
        """Тестировать пакет прокси параллельно"""
        working_count = 0

        with ThreadPoolExecutor(max_workers=TEST_WORKERS) as executor:
            futures = {executor.submit(self.test_proxy, p): p for p in proxies}

            for future in as_completed(futures):
                proxy = futures[future]
                try:
                    if future.result():
                        self.mark_working(proxy)
                        working_count += 1
                        print(f"[PROXY] Working: {proxy}")
                    else:
                        self.mark_failed(proxy)
                except:
                    self.mark_failed(proxy)

        return working_count

    def continuous_test_loop(self):
        """Непрерывное тестирование прокси"""
        print(f"[PROXY] Starting continuous test loop...")

        while self.running:
            try:
                # Проверяем сколько сырых прокси
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM zip_proxies WHERE status = 'raw'")
                raw_count = cur.fetchone()[0]

                # Если мало - скачиваем новые
                if raw_count < 1000:
                    print(f"[PROXY] Only {raw_count} raw proxies, fetching more...")
                    self.fetch_and_save_proxies()

                # Берём батч для тестирования
                proxies = self.get_proxies_to_test(BATCH_SIZE)

                if not proxies:
                    print("[PROXY] No proxies to test, waiting...")
                    time.sleep(60)
                    continue

                print(f"[PROXY] Testing batch of {len(proxies)} proxies...")
                working = self.test_batch(proxies)
                print(f"[PROXY] Batch done: {working}/{len(proxies)} working")

                # Пауза между батчами
                time.sleep(5)

            except Exception as e:
                print(f"[PROXY] Error: {e}")
                time.sleep(30)

    def start_daemon(self):
        """Запустить daemon тестирования"""
        self.running = True
        thread = threading.Thread(target=self.continuous_test_loop, daemon=True)
        thread.start()
        print("[PROXY] Daemon started")

    def stop_daemon(self):
        """Остановить daemon"""
        self.running = False
        print("[PROXY] Daemon stopped")

    def status(self) -> dict:
        """Получить статистику"""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT status, COUNT(*)
            FROM zip_proxies
            GROUP BY status
        """)

        stats = {row[0]: row[1] for row in cur.fetchall()}

        # Баны по сайтам
        cur.execute("""
            SELECT unnest(banned_sites) as site, COUNT(*)
            FROM zip_proxies
            WHERE array_length(banned_sites, 1) > 0
            GROUP BY site
        """)
        bans = {row[0]: row[1] for row in cur.fetchall()}

        return {
            'raw': stats.get('raw', 0),
            'working': stats.get('working', 0),
            'used': stats.get('used', 0),
            'dead': stats.get('dead', 0),
            'banned': stats.get('banned', 0),
            'total': sum(stats.values()),
            'bans_by_site': bans
        }


def get_manager(site_name: str = "gsmarena") -> ProxyManagerDB:
    """Получить менеджер"""
    return ProxyManagerDB(site_name)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Proxy Manager (PostgreSQL)")
    parser.add_argument('--site', '-s', default='gsmarena', help='Site name')
    parser.add_argument('--fetch', action='store_true', help='Fetch new proxies')
    parser.add_argument('--test', type=int, default=0, help='Test N proxies')
    parser.add_argument('--status', action='store_true', help='Show status')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    args = parser.parse_args()

    manager = ProxyManagerDB(site_name=args.site)

    if args.fetch:
        manager.fetch_and_save_proxies()

    if args.test > 0:
        proxies = manager.get_proxies_to_test(args.test)
        working = manager.test_batch(proxies)
        print(f"\nWorking: {working}/{len(proxies)}")

    if args.status:
        status = manager.status()
        print(f"\n=== Proxy Manager Status ===")
        print(f"Total: {status['total']}")
        print(f"Raw: {status['raw']}")
        print(f"Working: {status['working']}")
        print(f"Used: {status['used']}")
        print(f"Dead: {status['dead']}")
        print(f"Banned: {status['banned']}")
        if status['bans_by_site']:
            print(f"\nBans by site:")
            for site, count in status['bans_by_site'].items():
                print(f"  {site}: {count}")

    if args.daemon:
        print(f"Starting daemon mode (Ctrl+C to stop)...")
        manager.start_daemon()
        try:
            while True:
                time.sleep(60)
                s = manager.status()
                print(f"[STATUS] Raw: {s['raw']}, Working: {s['working']}, Used: {s['used']}, Dead: {s['dead']}")
        except KeyboardInterrupt:
            manager.stop_daemon()
            print("\nDaemon stopped")
