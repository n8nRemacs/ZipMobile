#!/usr/bin/env python3
"""
Параллельный парсинг GSMArena
Каждый бренд на своём прокси
"""
import subprocess
import sys
import time
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

# Бренды для допарсинга
BRANDS = ['vivo', 'realme', 'oneplus', 'google', 'nokia', 'motorola', 'tecno', 'poco']


def parse_brand_with_proxy(args):
    """Запустить парсинг бренда на конкретном прокси"""
    brand, proxy = args
    print(f"[{brand}] Starting on proxy {proxy}...")

    # Создаём файл с ОДНИМ прокси
    brand_proxy_file = f"proxy_{brand}.txt"
    with open(brand_proxy_file, 'w') as f:
        f.write(f"{proxy}\n")

    cmd = [
        sys.executable, '-c',
        f'''
import sys
sys.path.insert(0, ".")
import parser
parser.PROXIES_FILE = "{brand_proxy_file}"
parser.DELAY_MIN = 2.0
parser.DELAY_MAX = 4.0
p = parser.GSMArenaParser(use_db=True, use_proxy=True)
p.resume_mode = True
try:
    p.parse_brand("{brand}")
finally:
    p.close()
'''
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hours max
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        output = result.stdout + result.stderr

        # Логируем ключевые строки
        for line in output.split('\n'):
            if any(x in line for x in ['models parsed', 'Resume mode', 'Error', '429']):
                print(f"[{brand}] {line}")

        # Удаляем временный файл
        try:
            os.remove(brand_proxy_file)
        except:
            pass

        success = 'models parsed' in output and 'Error' not in output
        return brand, proxy, success, output

    except subprocess.TimeoutExpired:
        print(f"[{brand}] Timeout on {proxy}")
        return brand, proxy, False, "Timeout"
    except Exception as e:
        print(f"[{brand}] Error: {e}")
        return brand, proxy, False, str(e)


def test_proxy(proxy, timeout=10):
    """Быстрая проверка прокси"""
    import requests
    try:
        response = requests.get(
            "https://www.gsmarena.com/",
            proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        return response.status_code == 200
    except:
        return False


def find_working_proxies(proxies, count=10, timeout=10):
    """Найти работающие прокси"""
    print(f"Testing {len(proxies)} proxies to find {count} working ones...")
    working = []

    for i, proxy in enumerate(proxies):
        if len(working) >= count:
            break
        if test_proxy(proxy, timeout):
            working.append(proxy)
            print(f"  [{len(working)}/{count}] {proxy} - OK")
        else:
            if (i + 1) % 20 == 0:
                print(f"  Tested {i+1}...")

    return working


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Parallel GSMArena Parser')
    ap.add_argument('--brands', '-b', nargs='+', default=BRANDS, help='Brands to parse')
    ap.add_argument('--test-proxies', '-t', action='store_true', help='Test proxies first')
    ap.add_argument('--proxy-timeout', type=int, default=10, help='Proxy test timeout')
    args = ap.parse_args()

    brands = args.brands
    num_brands = len(brands)

    print(f"=" * 60)
    print(f"Parallel GSMArena Parser")
    print(f"=" * 60)
    print(f"Brands: {', '.join(brands)}")
    print()

    # Загружаем прокси
    if not os.path.exists('proxies.txt'):
        print("Error: proxies.txt not found! Run proxy_generator.py first.")
        sys.exit(1)

    with open('proxies.txt', 'r') as f:
        all_proxies = [line.strip() for line in f if line.strip()]

    print(f"Total proxies available: {len(all_proxies)}")

    # Опционально тестируем прокси
    if args.test_proxies:
        working_proxies = find_working_proxies(all_proxies, count=num_brands, timeout=args.proxy_timeout)
        if len(working_proxies) < num_brands:
            print(f"\nWarning: Only found {len(working_proxies)} working proxies, need {num_brands}")
            brands = brands[:len(working_proxies)]
    else:
        # Берём первые N прокси без теста
        working_proxies = all_proxies[:num_brands * 5]  # Берём с запасом

    # Распределяем прокси по брендам
    tasks = []
    for i, brand in enumerate(brands):
        proxy_idx = i % len(working_proxies)
        tasks.append((brand, working_proxies[proxy_idx]))

    print(f"\nStarting {len(tasks)} parallel parsers:")
    for brand, proxy in tasks:
        print(f"  {brand} -> {proxy}")
    print()

    start_time = time.time()
    results = []

    # Запускаем параллельно
    with ProcessPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(parse_brand_with_proxy, task): task[0]
            for task in tasks
        }

        for future in as_completed(futures):
            brand = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"[{brand}] Finished")
            except Exception as e:
                print(f"[{brand}] Exception: {e}")

    # Итоги
    elapsed = time.time() - start_time
    print()
    print(f"=" * 60)
    print(f"COMPLETED in {elapsed/60:.1f} minutes")
    print(f"=" * 60)

    success = sum(1 for _, _, ok, _ in results if ok)
    print(f"Success: {success}/{len(brands)}")


if __name__ == '__main__':
    main()
