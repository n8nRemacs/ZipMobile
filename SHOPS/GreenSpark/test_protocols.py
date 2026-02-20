"""Тест протоколов прокси для GreenSpark"""
import httpx
import json
import subprocess

with open("cookies.json") as f:
    cookies = json.load(f)
cookies.pop("__meta__", None)
cookies["magazine"] = "290112"
cookies["global_magazine"] = "290112"

url = "https://green-spark.ru/local/api/catalog/products/?path[]=komplektuyushchie_dlya_remonta&perPage=5"
ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


def test_proxy(name, proxy_url=None):
    print(f"\n=== {name} ({proxy_url or 'direct'}) ===")
    try:
        kwargs = {"timeout": 15, "cookies": cookies, "follow_redirects": True,
                  "headers": {"User-Agent": ua}}
        if proxy_url:
            kwargs["proxy"] = proxy_url
        client = httpx.Client(**kwargs)
        resp = client.get(url)
        ct = resp.headers.get("content-type", "")
        print(f"Status: {resp.status_code}, CT: {ct}")
        if "json" in ct:
            data = resp.json()
            products = data.get("products", {}).get("data", [])
            total = data.get("products", {}).get("meta", {}).get("total", 0)
            print(f"Products on page: {len(products)}, Total: {total}")
            print("OK!")
        else:
            text = resp.text[:300]
            print(f"HTML: {text}")
        client.close()
    except Exception as e:
        print(f"Error: {e}")


# 1. Direct
test_proxy("DIRECT")

# 2. SOCKS5
try:
    out = subprocess.check_output(["curl", "-s", "http://localhost:8110/proxy/get?protocol=socks5&for_site=greenspark"])
    p = json.loads(out)
    test_proxy("SOCKS5", f"socks5://{p['host']}:{p['port']}")
except Exception as e:
    print(f"\nSOCKS5: no proxy available: {e}")

# 3. HTTPS (через http:// URL формат для CONNECT)
try:
    out = subprocess.check_output(["curl", "-s", "http://localhost:8110/proxy/get?protocol=https&for_site=greenspark"])
    p = json.loads(out)
    test_proxy("HTTPS", f"http://{p['host']}:{p['port']}")
except Exception as e:
    print(f"\nHTTPS: no proxy available: {e}")

# 4. HTTP
try:
    out = subprocess.check_output(["curl", "-s", "http://localhost:8110/proxy/get?protocol=http&for_site=greenspark"])
    p = json.loads(out)
    test_proxy("HTTP", f"http://{p['host']}:{p['port']}")
except Exception as e:
    print(f"\nHTTP: no proxy available: {e}")
