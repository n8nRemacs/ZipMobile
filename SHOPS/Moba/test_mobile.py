"""
Test moba.ru with exact Chrome Android headers
"""
import json
from curl_cffi import requests as curl_requests

COOKIES_FILE = "moba_cookies.json"

with open(COOKIES_FILE, "r") as f:
    cookies = json.load(f)

# Use chrome120 impersonation
session = curl_requests.Session(impersonate="chrome120")

# Exact headers from Chrome Android
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?1",
    "Sec-Ch-Ua-Platform": '"Android"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
}

# Build cookie string
cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
headers["Cookie"] = cookie_str

print("[*] Testing with Chrome Android headers...")
print(f"[*] Cookie: {cookie_str[:100]}...")

resp = session.get("https://moba.ru/", headers=headers, allow_redirects=True)

print(f"\n[*] Status: {resp.status_code}")
print(f"[*] Final URL: {resp.url}")
print(f"[*] Content length: {len(resp.text)}")

# Check response headers for set-cookie
print("\n[*] Response cookies:")
for name, value in resp.cookies.items():
    print(f"  {name}: {value[:50]}...")

if "каталог" in resp.text.lower() or "корзин" in resp.text.lower() or "товар" in resp.text.lower():
    print("\n[+] SUCCESS!")
    with open("moba_main.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print("[+] Saved to moba_main.html")
elif "noindex" in resp.text[:500]:
    print("\n[!] Got Yandex SmartCaptcha page")

    # Check if we need to follow a redirect
    print("\n[*] Response headers:")
    for k, v in resp.headers.items():
        if "cookie" in k.lower() or "location" in k.lower():
            print(f"  {k}: {v}")
else:
    print("\n[?] Unknown response:")
    print(resp.text[:800])
