"""
Get cookies via CDP HTTP interface or pychrome
"""
import json
import requests

CDP_URL = "http://localhost:9222"
PAGE_ID = "18"  # moba.ru page ID
OUTPUT_FILE = "moba_cookies.json"


def get_page_info():
    """Get list of pages"""
    resp = requests.get(f"{CDP_URL}/json")
    pages = resp.json()
    for p in pages:
        if "moba.ru" in p.get("url", ""):
            return p
    return None


def evaluate_js(page_ws_url, expression):
    """Execute JS via CDP - needs websocket, trying alternative"""
    # CDP doesn't have HTTP-only eval endpoint
    # We need to use a library
    pass


def get_cookies_via_pychrome():
    """Use pychrome library"""
    try:
        import pychrome
    except ImportError:
        print("[!] Install: pip install pychrome")
        return {}

    browser = pychrome.Browser(url=CDP_URL)
    tabs = browser.list_tab()

    for tab in tabs:
        if "moba.ru" in str(tab):
            tab.start()
            # Get cookies
            cookies = tab.Network.getCookies(urls=["https://moba.ru/"])
            tab.stop()
            return cookies.get("cookies", [])

    return []


def get_cookies_via_selenium():
    """Use Selenium to get cookies"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        print("[!] Install: pip install selenium")
        return {}

    options = Options()
    options.add_experimental_option("debuggerAddress", "localhost:9222")

    driver = webdriver.Chrome(options=options)

    # Get cookies
    cookies = driver.get_cookies()
    cookie_dict = {c['name']: c['value'] for c in cookies}

    return cookie_dict


if __name__ == "__main__":
    print("[*] Method 1: pychrome")
    cookies = get_cookies_via_pychrome()

    if not cookies:
        print("[*] Method 2: selenium")
        cookies = get_cookies_via_selenium()

    if cookies:
        if isinstance(cookies, list):
            cookie_dict = {c['name']: c['value'] for c in cookies}
        else:
            cookie_dict = cookies

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(cookie_dict, f, indent=2, ensure_ascii=False)

        print(f"\n[+] Got {len(cookie_dict)} cookies:")
        for name, value in cookie_dict.items():
            print(f"  {name}: {value[:50]}...")

        print(f"\n[+] Saved to {OUTPUT_FILE}")
    else:
        print("[!] Failed to get cookies")
