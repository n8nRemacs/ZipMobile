"""
Parse Chrome cookies database and extract moba.ru cookies
"""
import sqlite3
import json

DB_PATH = "cookies.db"
OUTPUT_FILE = "moba_cookies.json"

def parse_cookies(db_path, domain_filter=None):
    cookies = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get table info
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"[*] Tables: {[t[0] for t in tables]}")

    # Get column names
    cursor.execute("PRAGMA table_info(cookies);")
    columns = cursor.fetchall()
    print(f"[*] Columns: {[c[1] for c in columns]}")

    # Query cookies
    query = "SELECT host_key, name, value, encrypted_value, path, expires_utc FROM cookies"
    if domain_filter:
        query += f" WHERE host_key LIKE '%{domain_filter}%'"

    cursor.execute(query)
    rows = cursor.fetchall()

    print(f"\n[*] Found {len(rows)} cookies for '{domain_filter}':\n")

    for row in rows:
        host, name, value, encrypted_value, path, expires = row
        # On Android, value might be in encrypted_value as plain bytes
        if value:
            cookies[name] = value
            print(f"  {name}: {value[:60]}{'...' if len(value) > 60 else ''}")
        elif encrypted_value:
            # Try to decode as plain text (Android sometimes stores unencrypted)
            try:
                decoded = encrypted_value.decode('utf-8')
                cookies[name] = decoded
                print(f"  {name}: {decoded[:60]}{'...' if len(decoded) > 60 else ''}")
            except:
                # It's actually encrypted
                print(f"  {name}: [encrypted, {len(encrypted_value)} bytes]")
        else:
            print(f"  {name}: [empty]")

    conn.close()
    return cookies


if __name__ == "__main__":
    print("[*] Parsing Chrome cookies database...\n")

    # Get all moba.ru cookies
    cookies = parse_cookies(DB_PATH, "moba")

    if cookies:
        # Save to JSON
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Saved {len(cookies)} cookies to {OUTPUT_FILE}")

        # Also create cookie string for requests
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        print(f"\n[*] Cookie string:\n{cookie_str[:200]}...")
    else:
        print("\n[!] No cookies found for moba.ru")
        print("[*] Open moba.ru in Chrome on Android first, then run this again")
