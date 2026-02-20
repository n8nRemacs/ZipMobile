#!/usr/bin/env python3
"""
Интегрированный парсинг GSMArena:
1. Запуск менеджера прокси в фоне
2. Параллельный парсинг брендов
3. Автоматическое пополнение пула прокси
"""

import os
import sys
import time
import argparse
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed

from proxy_manager import ProxyManager, get_manager

# Бренды для парсинга
DEFAULT_BRANDS = ['nokia', 'motorola', 'sony', 'lg', 'asus', 'lenovo', 'meizu', 'zte']


def parse_brand_with_manager(brand: str, manager_working_file: str):
    """Парсить бренд используя прокси из менеджера"""
    print(f"[{brand}] Starting...")

    # Читаем рабочий прокси из файла (менеджер обновляет его)
    if not os.path.exists(manager_working_file):
        print(f"[{brand}] No working proxies file!")
        return brand, False, "No proxies"

    with open(manager_working_file, 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]

    if not proxies:
        print(f"[{brand}] No proxies available!")
        return brand, False, "Empty proxy list"

    # Берём прокси для этого бренда (по индексу)
    brand_idx = DEFAULT_BRANDS.index(brand) if brand in DEFAULT_BRANDS else 0
    proxy = proxies[brand_idx % len(proxies)]

    print(f"[{brand}] Using proxy: {proxy}")

    # Создаём временный файл с одним прокси
    proxy_file = f"proxy_{brand}.txt"
    with open(proxy_file, 'w') as f:
        f.write(f"{proxy}\n")

    # Запускаем парсер
    cmd = [
        sys.executable, 'parser.py',
        '--brand', brand,
        '--proxy',
        '--resume'
    ]

    try:
        # Патчим PROXIES_FILE в parser.py через env
        env = os.environ.copy()
        env['PROXIES_FILE'] = proxy_file

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hours max
            env=env
        )

        output = result.stdout + result.stderr

        # Ищем ключевые строки
        for line in output.split('\n'):
            if any(x in line for x in ['models parsed', 'saved to DB', 'Error', '429']):
                print(f"[{brand}] {line}")

        success = 'models parsed' in output or 'saved to DB' in output
        return brand, success, output

    except subprocess.TimeoutExpired:
        print(f"[{brand}] Timeout!")
        return brand, False, "Timeout"
    except Exception as e:
        print(f"[{brand}] Error: {e}")
        return brand, False, str(e)
    finally:
        # Удаляем временный файл
        try:
            os.remove(proxy_file)
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description='Integrated GSMArena Parser')
    parser.add_argument('--brands', '-b', nargs='+', default=DEFAULT_BRANDS, help='Brands to parse')
    parser.add_argument('--workers', '-w', type=int, default=5, help='Number of parallel workers')
    parser.add_argument('--min-proxies', '-p', type=int, default=50, help='Minimum working proxies in pool')
    args = parser.parse_args()

    print("=" * 60)
    print("GSMArena Integrated Parser")
    print("=" * 60)
    print(f"Brands: {', '.join(args.brands)}")
    print(f"Workers: {args.workers}")
    print()

    # Инициализируем менеджер прокси
    manager = ProxyManager()

    # Пополняем пул если нужно
    print("[SETUP] Checking proxy pool...")
    manager.refill_pool(target=args.min_proxies)

    status = manager.status()
    print(f"[SETUP] Proxy pool ready: {status['working']} working proxies")

    if status['working'] < args.workers:
        print(f"[ERROR] Not enough working proxies ({status['working']} < {args.workers})")
        return

    # Запускаем фоновое обновление прокси
    manager.start_background()

    print()
    print(f"[START] Launching {len(args.brands)} parsers...")
    print()

    start_time = time.time()
    results = []

    # Запускаем параллельно
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(parse_brand_with_manager, brand, 'proxies_working.txt'): brand
            for brand in args.brands
        }

        for future in as_completed(futures):
            brand = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"[DONE] {brand} finished")
            except Exception as e:
                print(f"[ERROR] {brand}: {e}")
                results.append((brand, False, str(e)))

    # Останавливаем фоновое обновление
    manager.stop_background()

    # Итоги
    elapsed = time.time() - start_time
    print()
    print("=" * 60)
    print(f"COMPLETED in {elapsed/60:.1f} minutes")
    print("=" * 60)

    success = sum(1 for _, ok, _ in results if ok)
    print(f"Success: {success}/{len(args.brands)}")

    for brand, ok, _ in results:
        status = "OK" if ok else "FAIL"
        print(f"  {brand}: {status}")


if __name__ == '__main__':
    main()
