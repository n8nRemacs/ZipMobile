"""
Get cookies via CDP browser endpoint using raw HTTP
"""
import json
import requests

CDP_URL = "http://localhost:9222"


def get_all_cookies():
    """Get ALL cookies from browser via Storage.getCookies"""

    # First get targets
    resp = requests.get(f"{CDP_URL}/json/list")
    targets = resp.json()

    moba_target = None
    for t in targets:
        if "moba.ru" in t.get("url", ""):
            moba_target = t
            print(f"[*] Found moba.ru target: {t['id']}")
            break

    if not moba_target:
        print("[!] moba.ru not found in targets")
        return {}

    # Try to get cookies via /json/protocol endpoint
    # This is a workaround - some CDP implementations expose this

    # Actually, let's try activating the target first
    print(f"[*] Target URL: {moba_target['url']}")
    print(f"[*] WS URL: {moba_target['webSocketDebuggerUrl']}")

    # The only way is WebSocket, but we're blocked by CORS
    # Let's try selenium with debuggerAddress

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_experimental_option("debuggerAddress", "localhost:9222")

        print("[*] Connecting via Selenium...")
        driver = webdriver.Chrome(options=options)

        # Switch to moba.ru tab
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            if "moba.ru" in driver.current_url:
                print(f"[+] Found moba.ru tab: {driver.current_url}")
                break

        # Get cookies
        cookies = driver.get_cookies()
        print(f"[+] Got {len(cookies)} cookies")

        cookie_dict = {}
        for c in cookies:
            cookie_dict[c['name']] = c['value']
            print(f"  {c['name']}: {c['value'][:50]}...")

        return cookie_dict

    except ImportError:
        print("[!] Selenium not installed: pip install selenium")
        return {}
    except Exception as e:
        print(f"[!] Selenium error: {e}")
        return {}


if __name__ == "__main__":
    cookies = get_all_cookies()

    if cookies:
        with open("moba_cookies.json", "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Saved {len(cookies)} cookies to moba_cookies.json")

        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        print(f"\n[*] Cookie string:\n{cookie_str}")
