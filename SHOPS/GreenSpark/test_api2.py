"""
Тест 2: Детальное исследование API
"""
import httpx
import json
import re

client = httpx.Client(
    timeout=30.0,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9",
    },
    cookies={"magazine": "15226", "global_magazine": "15226"},
    follow_redirects=True,
)

BASE = "https://green-spark.ru/local/api"

# Тест 1: Полная структура товара из поиска
print("=" * 60)
print("TEST 1: Full product structure from search")
print("=" * 60)
r = client.get(f"{BASE}/catalog/fast-search/", params={"q": "GS-00015762", "page": 1})
data = r.json()
print(f"Total found: {data.get('meta', {}).get('total', 0)}")
if data.get("data"):
    product = data["data"][0]
    # Сохраним полную структуру
    with open("data/sample_product.json", "w", encoding="utf-8") as f:
        json.dump(product, f, ensure_ascii=False, indent=2)
    print("Saved full product to data/sample_product.json")
    print(f"\nAll keys: {list(product.keys())}")
else:
    print("No products found for this article")

# Тест 2: Поиск по артикулу - может вернёт артикул в ответе?
print("\n" + "=" * 60)
print("TEST 2: Search with different queries")
print("=" * 60)
queries = ["дисплей doogee s40", "15762"]
for q in queries:
    r = client.get(f"{BASE}/catalog/fast-search/", params={"q": q, "page": 1})
    data = r.json()
    print(f"\nQuery: '{q}'")
    print(f"Found: {len(data.get('data', []))} products")
    if data.get("data"):
        p = data["data"][0]
        print(f"  ID: {p.get('id')}")
        print(f"  Name: {p.get('name')}")
        # Ищем артикул в данных
        for key, val in p.items():
            if isinstance(val, str) and "GS-" in str(val):
                print(f"  Found article in '{key}': {val}")

# Тест 3: Что в HTML ответе карточки?
print("\n" + "=" * 60)
print("TEST 3: What's in product HTML?")
print("=" * 60)
url = "https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/zapchasti_dlya_mobilnykh_ustroystv/displei_2/dlya_doogee/displey_dlya_doogee_s40_tachskrin_chernyy.html"
r = client.get(url)
html = r.text
print(f"Length: {len(html)}")

# Ищем JSON в скриптах
json_pattern = r'<script[^>]*>.*?window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;?.*?</script>'
matches = re.findall(json_pattern, html, re.DOTALL)
if matches:
    print("Found __INITIAL_STATE__")

# Ищем любой большой JSON
json_pattern2 = r'\{["\'][^"\']+["\']:[^}]{100,}\}'
matches2 = re.findall(json_pattern2, html)
print(f"Found {len(matches2)} potential JSON objects")

# Ищем артикулы
articles = re.findall(r'GS-\d+', html)
print(f"Articles found: {set(articles)}")

# Ищем breadcrumb
if "breadcrumb" in html.lower():
    print("Contains breadcrumb")

# Первые 500 символов HTML
print(f"\nFirst 500 chars:\n{html[:500]}")

# Тест 4: Что в ответе API продукта?
print("\n" + "=" * 60)
print("TEST 4: Raw API product response")
print("=" * 60)
r = client.get(f"{BASE}/catalog/product/73550/")
print(f"Status: {r.status_code}")
print(f"Headers: {dict(r.headers)}")
print(f"Content type: {r.headers.get('content-type')}")
print(f"Content length: {len(r.text)}")
print(f"First 500 chars: {r.text[:500]}")

# Тест 5: API с другими заголовками
print("\n" + "=" * 60)
print("TEST 5: API with different headers")
print("=" * 60)
client2 = httpx.Client(
    timeout=30.0,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://green-spark.ru/catalog/",
    },
    cookies={"magazine": "15226", "global_magazine": "15226"},
    follow_redirects=True,
)
r = client2.get(f"{BASE}/catalog/product/73550/")
print(f"Status: {r.status_code}")
print(f"Content: {r.text[:300]}")
client2.close()

client.close()
print("\n" + "=" * 60)
print("DONE")
