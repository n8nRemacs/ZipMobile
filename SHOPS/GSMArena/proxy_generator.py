#!/usr/bin/env python3
"""
Генератор списка бесплатных прокси для GSMArena парсера
Источники: sslproxies.org, free-proxy-list.net
"""

import requests
from bs4 import BeautifulSoup
import os

PROXY_SOURCES = [
    "https://sslproxies.org/",
    "https://free-proxy-list.net/",
]

# GitHub raw sources with massive proxy lists
GITHUB_PROXY_SOURCES = [
    # TheSpeedX/PROXY-List (~44,000 proxies) - daily
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    # clarketm/proxy-list
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    # ShiftyTR/Proxy-List
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    # monosans/proxy-list - hourly
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    # proxifly - every 5 min
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    # vakhov/fresh-proxy-list - tested proxies
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/main/proxylist.txt",
    # jetkai/proxy-list - hourly with geolocation
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies.txt",
    # iplocate/free-proxy-list - every 30 min
    "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/proxy-list.txt",
    # sunny9577/proxy-scraper
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
    # mmpx12/proxy-list
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    # roosterkid/openproxylist
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
}

OUTPUT_FILE = "proxies.txt"


def fetch_proxies_from_source(url):
    """Fetch proxies from HTML table source"""
    proxies = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Parse table rows
        for row in soup.select('table tbody tr'):
            cols = row.select('td')
            if len(cols) >= 2:
                ip = cols[0].get_text().strip()
                port = cols[1].get_text().strip()
                if ip and port:
                    proxies.append(f"{ip}:{port}")
    except Exception as e:
        print(f"Error fetching from {url}: {e}")

    return proxies


def fetch_proxies_from_github(url):
    """Fetch proxies from GitHub raw text file (ip:port per line)"""
    proxies = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        for line in response.text.split('\n'):
            line = line.strip()
            if ':' in line and line[0].isdigit():
                proxies.append(line.split()[0])  # Take only ip:port part
    except Exception as e:
        print(f"Error fetching from {url}: {e}")
    return proxies


def test_proxy(proxy, timeout=5):
    """Test if proxy works"""
    try:
        response = requests.get(
            "https://httpbin.org/ip",
            proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
            timeout=timeout
        )
        return response.status_code == 200
    except:
        return False


def fetch_all_proxies(test=False, include_github=True):
    """Fetch proxies from all sources"""
    all_proxies = []

    # HTML table sources
    for source in PROXY_SOURCES:
        print(f"Fetching from {source}...")
        proxies = fetch_proxies_from_source(source)
        print(f"  Found {len(proxies)} proxies")
        all_proxies.extend(proxies)

    # GitHub raw text sources (massive lists)
    if include_github:
        for source in GITHUB_PROXY_SOURCES:
            name = source.split('/')[-3] if 'github' in source else source
            print(f"Fetching from {name}...")
            proxies = fetch_proxies_from_github(source)
            print(f"  Found {len(proxies)} proxies")
            all_proxies.extend(proxies)

    # Remove duplicates
    all_proxies = list(set(all_proxies))
    print(f"\nTotal unique proxies: {len(all_proxies)}")

    if test:
        print("\nTesting proxies (this may take a while)...")
        working = []
        for i, proxy in enumerate(all_proxies[:50]):  # Test first 50
            if test_proxy(proxy):
                working.append(proxy)
                print(f"  [{i+1}] {proxy} - OK")
            else:
                print(f"  [{i+1}] {proxy} - FAIL")
        all_proxies = working + all_proxies[50:]
        print(f"\nWorking proxies: {len(working)}")

    return all_proxies


def save_proxies(proxies, filename=None):
    """Save proxies to file"""
    filename = filename or OUTPUT_FILE
    with open(filename, "w") as f:
        for proxy in proxies:
            f.write(f"{proxy}\n")
    print(f"Saved {len(proxies)} proxies to {filename}")


def load_proxies(filename=None):
    """Load proxies from file"""
    filename = filename or OUTPUT_FILE
    if not os.path.exists(filename):
        return []

    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
    import sys

    test = "--test" in sys.argv
    proxies = fetch_all_proxies(test=test)
    save_proxies(proxies)

    print(f"\nГотово! Используйте в парсере:")
    print(f"  python parser.py --brand vivo --proxy")
