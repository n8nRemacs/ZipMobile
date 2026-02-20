"""
Test moba.ru anti-bot bypass
"""
from curl_cffi import requests as curl_requests
import json

def test_moba():
    session = curl_requests.Session(impersonate="chrome120")

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    print("[*] Testing moba.ru with curl_cffi chrome120...")

    resp = session.get("https://moba.ru/", headers=headers, allow_redirects=True)
    print(f"[*] Status: {resp.status_code}")
    print(f"[*] URL: {resp.url}")
    print(f"[*] Content length: {len(resp.text)}")

    if resp.status_code == 302:
        location = resp.headers.get("location", "")
        if "captcha" in location:
            print("[!] Captcha detected - need to bypass")
            return False
        else:
            print(f"[*] Redirect to: {location}")

    # Check content
    print(f"[+] Got {len(resp.text)} bytes")

    # Check if it's real content
    if "каталог" in resp.text.lower() or "товар" in resp.text.lower():
        print("[+] Real content received!")
        # Save for analysis
        with open("moba_main.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("[+] Saved to moba_main.html")
        return True, session
    elif "captcha" in resp.text.lower():
        print("[!] Captcha page")
        print(resp.text[:1000])
        return False, session
    else:
        print("[?] Unknown content:")
        print(resp.text[:1000])
        return False, session


def test_with_android_cookies(cookies_str):
    """Test with cookies captured from Android"""
    session = curl_requests.Session(impersonate="chrome120_android")

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Cookie": cookies_str,
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; LE2115) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }

    resp = session.get("https://moba.ru/", headers=headers)
    print(f"[*] Status: {resp.status_code}")
    return resp


if __name__ == "__main__":
    test_moba()
