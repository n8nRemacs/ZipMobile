"""
Get Chrome cookies directly from Android (requires root)
"""
import subprocess
import json
import sqlite3
import tempfile
import os

ADB = r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe"
COOKIES_FILE = "moba_cookies.json"


def run_adb(cmd):
    """Run adb command"""
    full_cmd = f'"{ADB}" {cmd}'
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def get_chrome_cookies():
    """Extract Chrome cookies from Android device"""

    print("[*] Getting Chrome cookies from device...")

    # Chrome stores cookies in SQLite database
    # Path: /data/data/com.android.chrome/app_chrome/Default/Cookies

    cookie_paths = [
        "/data/data/com.android.chrome/app_chrome/Default/Cookies",
        "/data/data/com.android.chrome/app_chrome/Profile 1/Cookies",
        "/data/user/0/com.android.chrome/app_chrome/Default/Cookies",
    ]

    # First, try to find the correct path
    for path in cookie_paths:
        result = run_adb(f'shell "su -c \'ls {path}\'"')
        if "No such file" not in result and path in result:
            print(f"[+] Found cookies at: {path}")

            # Copy to temp location
            run_adb(f'shell "su -c \'cp {path} /sdcard/chrome_cookies.db\'"')
            run_adb(f'shell "su -c \'chmod 644 /sdcard/chrome_cookies.db\'"')

            # Pull to PC
            local_db = os.path.join(tempfile.gettempdir(), "chrome_cookies.db")
            run_adb(f'pull /sdcard/chrome_cookies.db "{local_db}"')

            # Clean up
            run_adb('shell "rm /sdcard/chrome_cookies.db"')

            if os.path.exists(local_db):
                return parse_cookies_db(local_db, "moba.ru")

    print("[!] Could not find Chrome cookies database")
    return {}


def parse_cookies_db(db_path, domain_filter=None):
    """Parse Chrome cookies SQLite database"""
    cookies = {}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Chrome cookies table structure
        query = "SELECT host_key, name, value, encrypted_value FROM cookies"
        if domain_filter:
            query += f" WHERE host_key LIKE '%{domain_filter}%'"

        cursor.execute(query)

        for row in cursor.fetchall():
            host, name, value, encrypted = row
            # On Android, cookies are usually not encrypted
            cookie_value = value if value else ""
            if cookie_value:
                cookies[name] = cookie_value
                print(f"  {name}: {cookie_value[:50]}...")

        conn.close()

        # Clean up
        os.remove(db_path)

    except Exception as e:
        print(f"[!] Error parsing cookies: {e}")

    return cookies


def get_cookies_from_webview():
    """Alternative: Get cookies via WebView dump"""

    print("[*] Trying WebView cookie dump...")

    # Try to dump cookies from Chrome's SharedPreferences or other storage
    result = run_adb('shell "su -c \'cat /data/data/com.android.chrome/shared_prefs/WebViewChromiumPrefs.xml\'"')
    print(result[:500] if result else "[!] No WebView prefs")


def manual_cookie_input():
    """Manual cookie input from browser DevTools"""
    print("""
=== Ручной ввод cookies ===

1. Открой Chrome на телефоне
2. Зайди на moba.ru и пройди капчу
3. Открой в Chrome: chrome://inspect -> Pages
4. Или используй Eruda/VConsole для просмотра cookies
5. Скопируй значение document.cookie

Вставь cookies строку:
""")
    cookie_str = input().strip()

    if cookie_str:
        cookies = {}
        for part in cookie_str.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                cookies[name.strip()] = value.strip()

        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)

        print(f"[+] Saved {len(cookies)} cookies to {COOKIES_FILE}")
        return cookies

    return {}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--manual":
        manual_cookie_input()
    else:
        cookies = get_chrome_cookies()

        if cookies:
            with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
            print(f"\n[+] Saved {len(cookies)} cookies to {COOKIES_FILE}")
        else:
            print("\n[!] No cookies found, trying manual input...")
            manual_cookie_input()
