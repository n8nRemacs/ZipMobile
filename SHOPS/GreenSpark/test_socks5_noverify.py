"""Тест SOCKS5 прокси без SSL verify"""
import httpx
import json
import subprocess
import ssl

with open("cookies.json") as f:
    cookies = json.load(f)
cookies.pop("__meta__", None)
cookies["magazine"] = "290112"
cookies["global_magazine"] = "290112"

url = "https://green-spark.ru/local/api/catalog/products/?path[]=komplektuyushchie_dlya_remonta&perPage=5"
ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


def test_socks5(verify_ssl):
    out = subprocess.check_output(["curl", "-s", "http://localhost:8110/proxy/get?protocol=socks5&for_site=greenspark"])
    p = json.loads(out)
    proxy_url = f"socks5://{p['host']}:{p['port']}"
    print(f"\n=== SOCKS5 ({proxy_url}) verify={verify_ssl} ===")
    try:
        client = httpx.Client(
            timeout=20, cookies=cookies, follow_redirects=True,
            proxy=proxy_url, verify=verify_ssl,
            headers={"User-Agent": ua}
        )
        resp = client.get(url)
        ct = resp.headers.get("content-type", "")
        print(f"Status: {resp.status_code}, CT: {ct}")
        if "json" in ct:
            data = resp.json()
            products = data.get("products", {}).get("data", [])
            total = data.get("products", {}).get("meta", {}).get("total", 0)
            print(f"Products on page: {len(products)}, Total: {total}")
            print("SOCKS5 WORKS!")
        else:
            print(f"HTML (first 300): {resp.text[:300]}")
        client.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


# Тест с verify=False
for i in range(3):
    print(f"\n--- Попытка {i+1}/3 ---")
    if test_socks5(False):
        break
