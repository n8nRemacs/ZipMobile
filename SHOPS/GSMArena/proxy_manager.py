#!/usr/bin/env python3
"""
Менеджер прокси для GSMArena парсера
- Фоновое тестирование прокси
- Пул рабочих прокси
- Хранение использованных/забаненных
- Автоматическое обновление
"""

import os
import json
import time
import random
import requests
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Set

# Файлы (общие для всех парсеров)
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'proxies')
os.makedirs(DATA_DIR, exist_ok=True)

PROXIES_RAW_FILE = os.path.join(DATA_DIR, "proxies_raw.txt")       # Все прокси (сырые)
PROXIES_WORKING_FILE = os.path.join(DATA_DIR, "proxies_working.txt")  # Рабочие прокси
PROXIES_USED_FILE = os.path.join(DATA_DIR, "proxies_used.json")    # Использованные прокси
PROXIES_BANNED_FILE = os.path.join(DATA_DIR, "proxies_banned.json")  # Забаненные прокси (по сайтам)

# Настройки
TEST_URL = "https://www.gsmarena.com/"
TEST_TIMEOUT = 10
MIN_WORKING_PROXIES = 50  # Минимум рабочих прокси в пуле
REFRESH_INTERVAL = 300     # Обновление списка каждые 5 минут
TEST_WORKERS = 20          # Параллельных тестеров

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


class ProxyManager:
    """Менеджер прокси с фоновым тестированием"""

    def __init__(self, site_name: str = "gsmarena"):
        """
        Args:
            site_name: Имя сайта для отслеживания банов (gsmarena, greenspark, etc.)
        """
        self.site_name = site_name
        self.working_proxies: List[str] = []
        self.used_proxies: Set[str] = set()
        self.banned_proxies: dict = {}  # {proxy: [site1, site2, ...]}
        self.raw_proxies: List[str] = []
        self.lock = threading.Lock()
        self.running = False
        self._load_state()

    def _load_state(self):
        """Загрузить состояние из файлов"""
        # Рабочие прокси
        if os.path.exists(PROXIES_WORKING_FILE):
            with open(PROXIES_WORKING_FILE, 'r') as f:
                self.working_proxies = [line.strip() for line in f if line.strip()]
            print(f"[PROXY] Loaded {len(self.working_proxies)} working proxies")

        # Использованные
        if os.path.exists(PROXIES_USED_FILE):
            with open(PROXIES_USED_FILE, 'r') as f:
                data = json.load(f)
                self.used_proxies = set(data.get('proxies', []))
            print(f"[PROXY] Loaded {len(self.used_proxies)} used proxies")

        # Забаненные (формат: {proxy: [site1, site2, ...]})
        if os.path.exists(PROXIES_BANNED_FILE):
            with open(PROXIES_BANNED_FILE, 'r') as f:
                data = json.load(f)
                self.banned_proxies = data.get('proxies', {})
            # Считаем сколько забанено для нашего сайта
            banned_for_site = sum(1 for p, sites in self.banned_proxies.items() if self.site_name in sites)
            print(f"[PROXY] Loaded {len(self.banned_proxies)} banned proxies ({banned_for_site} for {self.site_name})")

        # Сырые прокси
        if os.path.exists(PROXIES_RAW_FILE):
            with open(PROXIES_RAW_FILE, 'r') as f:
                self.raw_proxies = [line.strip() for line in f if line.strip()]
            print(f"[PROXY] Loaded {len(self.raw_proxies)} raw proxies")

    def _save_state(self):
        """Сохранить состояние в файлы"""
        with self.lock:
            # Рабочие
            with open(PROXIES_WORKING_FILE, 'w') as f:
                for proxy in self.working_proxies:
                    f.write(f"{proxy}\n")

            # Использованные
            with open(PROXIES_USED_FILE, 'w') as f:
                json.dump({
                    'proxies': list(self.used_proxies),
                    'updated': datetime.now().isoformat()
                }, f)

            # Забаненные (формат: {proxy: [site1, site2, ...]})
            with open(PROXIES_BANNED_FILE, 'w') as f:
                json.dump({
                    'proxies': self.banned_proxies,
                    'updated': datetime.now().isoformat()
                }, f, indent=2)

    def fetch_raw_proxies(self) -> List[str]:
        """Получить свежий список прокси из всех источников"""
        all_proxies = []

        for url in GITHUB_PROXY_SOURCES:
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
                for line in response.text.split('\n'):
                    line = line.strip()
                    if ':' in line and line[0].isdigit():
                        proxy = line.split()[0]
                        all_proxies.append(proxy)
            except Exception as e:
                print(f"[PROXY] Error fetching {url}: {e}")

        # Убираем дубликаты и уже использованные
        # Забаненные для НАШЕГО сайта тоже исключаем
        banned_for_site = {p for p, sites in self.banned_proxies.items() if self.site_name in sites}
        unique = set(all_proxies) - self.used_proxies - banned_for_site
        self.raw_proxies = list(unique)

        # Сохраняем
        with open(PROXIES_RAW_FILE, 'w') as f:
            for proxy in self.raw_proxies:
                f.write(f"{proxy}\n")

        print(f"[PROXY] Fetched {len(self.raw_proxies)} new proxies (excluded {len(self.used_proxies)} used, {len(self.banned_proxies)} banned)")
        return self.raw_proxies

    def test_proxy(self, proxy: str) -> bool:
        """Тестировать прокси на GSMArena"""
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

    def test_proxies_batch(self, proxies: List[str], max_working: int = 100) -> List[str]:
        """Тестировать пакет прокси параллельно"""
        working = []
        tested = 0

        print(f"[PROXY] Testing {len(proxies)} proxies (need {max_working} working)...")

        with ThreadPoolExecutor(max_workers=TEST_WORKERS) as executor:
            futures = {executor.submit(self.test_proxy, p): p for p in proxies}

            for future in as_completed(futures):
                proxy = futures[future]
                tested += 1

                try:
                    if future.result():
                        working.append(proxy)
                        print(f"[PROXY] [{len(working)}/{max_working}] {proxy} - OK")

                        if len(working) >= max_working:
                            # Отменяем оставшиеся
                            for f in futures:
                                f.cancel()
                            break
                except:
                    pass

                if tested % 100 == 0:
                    print(f"[PROXY] Tested {tested}...")

        return working

    def get_proxy(self) -> Optional[str]:
        """Получить рабочий прокси для использования"""
        with self.lock:
            if not self.working_proxies:
                return None

            # Берём первый из пула
            proxy = self.working_proxies.pop(0)
            self.used_proxies.add(proxy)

            print(f"[PROXY] Выдан прокси: {proxy} (осталось {len(self.working_proxies)})")
            return proxy

    def mark_banned(self, proxy: str, site: str = None):
        """Пометить прокси как забаненный определённым сайтом (429/блокировка)

        Args:
            proxy: IP:PORT прокси
            site: Имя сайта который забанил (по умолчанию self.site_name)
        """
        site = site or self.site_name
        with self.lock:
            if proxy not in self.banned_proxies:
                self.banned_proxies[proxy] = []
            if site not in self.banned_proxies[proxy]:
                self.banned_proxies[proxy].append(site)
            if proxy in self.working_proxies:
                self.working_proxies.remove(proxy)
        print(f"[PROXY] Прокси забанен {site}: {proxy} (всего забанен: {self.banned_proxies[proxy]})")
        self._save_state()

    def is_banned_for_site(self, proxy: str, site: str = None) -> bool:
        """Проверить забанен ли прокси для определённого сайта"""
        site = site or self.site_name
        return proxy in self.banned_proxies and site in self.banned_proxies[proxy]

    def get_proxies_not_banned_for(self, site: str) -> List[str]:
        """Получить прокси которые НЕ забанены для указанного сайта"""
        return [p for p in self.working_proxies if not self.is_banned_for_site(p, site)]

    def refill_pool(self, target: int = MIN_WORKING_PROXIES):
        """Пополнить пул рабочих прокси"""
        current = len(self.working_proxies)
        if current >= target:
            print(f"[PROXY] Пул достаточен: {current} прокси")
            return

        need = target - current
        print(f"[PROXY] Нужно пополнить пул: {current} -> {target} (нужно {need})")

        # Если мало сырых - скачиваем новые
        if len(self.raw_proxies) < need * 10:
            self.fetch_raw_proxies()

        # Берём случайную порцию для тестирования
        to_test = random.sample(self.raw_proxies, min(need * 20, len(self.raw_proxies)))

        # Тестируем
        new_working = self.test_proxies_batch(to_test, max_working=need)

        # Добавляем в пул
        with self.lock:
            self.working_proxies.extend(new_working)
            # Удаляем протестированные из сырых
            for p in to_test:
                if p in self.raw_proxies:
                    self.raw_proxies.remove(p)

        print(f"[PROXY] Пул пополнен: {len(self.working_proxies)} рабочих прокси")
        self._save_state()

    def background_refill(self):
        """Фоновое пополнение пула"""
        while self.running:
            try:
                self.refill_pool()
            except Exception as e:
                print(f"[PROXY] Error in background refill: {e}")

            time.sleep(REFRESH_INTERVAL)

    def continuous_test_loop(self):
        """Непрерывное тестирование ВСЕХ прокси по кругу"""
        print(f"[PROXY] Starting continuous test loop for {self.site_name}...")

        while self.running:
            try:
                # Если мало сырых - скачиваем новые
                if len(self.raw_proxies) < 1000:
                    self.fetch_raw_proxies()

                if not self.raw_proxies:
                    print("[PROXY] No raw proxies to test, waiting...")
                    time.sleep(60)
                    continue

                # Берём следующую партию для тестирования
                batch_size = min(500, len(self.raw_proxies))
                batch = self.raw_proxies[:batch_size]

                print(f"[PROXY] Testing batch of {batch_size} proxies...")

                # Тестируем параллельно
                with ThreadPoolExecutor(max_workers=TEST_WORKERS) as executor:
                    futures = {executor.submit(self.test_proxy, p): p for p in batch}

                    for future in as_completed(futures):
                        if not self.running:
                            break

                        proxy = futures[future]
                        try:
                            if future.result():
                                with self.lock:
                                    if proxy not in self.working_proxies:
                                        self.working_proxies.append(proxy)
                                        print(f"[PROXY] +1 working: {proxy} (total: {len(self.working_proxies)})")
                        except:
                            pass

                # Удаляем протестированные из сырых
                with self.lock:
                    for p in batch:
                        if p in self.raw_proxies:
                            self.raw_proxies.remove(p)

                # Сохраняем состояние
                self._save_state()

                # Небольшая пауза между батчами
                time.sleep(10)

            except Exception as e:
                print(f"[PROXY] Error in continuous test: {e}")
                time.sleep(30)

    def start_background(self, mode='continuous'):
        """Запустить фоновое обновление

        Args:
            mode: 'continuous' - непрерывное тестирование всех прокси
                  'refill' - пополнение только когда мало
        """
        self.running = True
        if mode == 'continuous':
            thread = threading.Thread(target=self.continuous_test_loop, daemon=True)
            thread.start()
            print("[PROXY] Continuous test loop started (collect → test → store working)")
        else:
            thread = threading.Thread(target=self.background_refill, daemon=True)
            thread.start()
            print("[PROXY] Background refill started")

    def stop_background(self):
        """Остановить фоновое обновление"""
        self.running = False
        self._save_state()
        print("[PROXY] Background refill stopped")

    def status(self) -> dict:
        """Статус менеджера"""
        # Подсчёт банов по сайтам
        bans_by_site = {}
        for proxy, sites in self.banned_proxies.items():
            for site in sites:
                bans_by_site[site] = bans_by_site.get(site, 0) + 1

        return {
            'site': self.site_name,
            'working': len(self.working_proxies),
            'used': len(self.used_proxies),
            'banned_total': len(self.banned_proxies),
            'banned_for_site': sum(1 for p, s in self.banned_proxies.items() if self.site_name in s),
            'bans_by_site': bans_by_site,
            'raw': len(self.raw_proxies)
        }


# Синглтоны для каждого сайта
_managers = {}

def get_manager(site_name: str = "gsmarena") -> ProxyManager:
    """Получить менеджер прокси для сайта"""
    global _managers
    if site_name not in _managers:
        _managers[site_name] = ProxyManager(site_name)
    return _managers[site_name]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Proxy Manager")
    parser.add_argument('--site', '-s', default='gsmarena', help='Site name (gsmarena, greenspark, etc.)')
    parser.add_argument('--fetch', action='store_true', help='Fetch new proxies')
    parser.add_argument('--test', type=int, default=0, help='Test N proxies')
    parser.add_argument('--refill', action='store_true', help='Refill working pool')
    parser.add_argument('--status', action='store_true', help='Show status')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (background refill)')
    args = parser.parse_args()

    manager = ProxyManager(site_name=args.site)

    if args.fetch:
        manager.fetch_raw_proxies()

    if args.test > 0:
        proxies = manager.raw_proxies[:args.test]
        working = manager.test_proxies_batch(proxies, max_working=args.test)
        print(f"\nWorking: {len(working)}/{args.test}")

    if args.refill:
        manager.refill_pool()

    if args.status:
        status = manager.status()
        print(f"\n=== Proxy Manager Status ({status['site']}) ===")
        print(f"Working proxies: {status['working']}")
        print(f"Used proxies: {status['used']}")
        print(f"Raw proxies: {status['raw']}")
        print(f"\nBanned proxies total: {status['banned_total']}")
        print(f"Banned for {status['site']}: {status['banned_for_site']}")
        if status['bans_by_site']:
            print("\nBans by site:")
            for site, count in status['bans_by_site'].items():
                print(f"  {site}: {count}")

    if args.daemon:
        print(f"Starting daemon mode for {args.site} (Ctrl+C to stop)...")
        manager.start_background()
        try:
            while True:
                time.sleep(60)
                status = manager.status()
                print(f"[DAEMON] Working: {status['working']}, Used: {status['used']}, Banned for {args.site}: {status['banned_for_site']}")
        except KeyboardInterrupt:
            manager.stop_background()
            print("\nDaemon stopped")
