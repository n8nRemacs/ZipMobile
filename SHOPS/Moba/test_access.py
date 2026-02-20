"""
Test moba.ru access with captured cookies
"""
import json
from curl_cffi import requests as curl_requests

COOKIES_FILE = "moba_cookies.json"

# Load cookies
with open(COOKIES_FILE, "r") as f:
    cookies = json.load(f)

# Create session
session = curl_requests.Session(impersonate="chrome120")

# Set cookies
for name, value in cookies.items():
    session.cookies.set(name, value, domain=".moba.ru")

# Test request
print("[*] Testing moba.ru access...")
resp = session.get("https://moba.ru/", allow_redirects=True)

print(f"[*] Status: {resp.status_code}")
print(f"[*] URL: {resp.url}")
print(f"[*] Content length: {len(resp.text)}")

if "captcha" in resp.url.lower():
    print("[!] Redirected to captcha")
elif "robots" in resp.text[:500].lower() and "noindex" in resp.text[:500].lower():
    print("[!] Still blocked - got loading page")
    print(resp.text[:500])
elif "каталог" in resp.text.lower() or "товар" in resp.text.lower():
    print("[+] SUCCESS! Access granted!")

    # Save page for analysis
    with open("moba_main.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print("[+] Saved to moba_main.html")
else:
    print("[?] Unknown response")
    print(resp.text[:1500])

    # Save for debug
    with open("moba_debug.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print("\n[*] Saved to moba_debug.html")
