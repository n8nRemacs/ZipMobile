"""
Тестовый скрипт для исследования API GreenSpark
"""
import httpx
import json

# Клиент с cookies как в основном парсере
client = httpx.Client(
    timeout=30.0,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    },
    cookies={"magazine": "15226", "global_magazine": "15226"},
    follow_redirects=True,
)

BASE = "https://green-spark.ru/local/api"

# Тест 1: Поиск (работает)
print("=" * 60)
print("TEST 1: Search API")
print("=" * 60)
try:
    r = client.get(f"{BASE}/catalog/fast-search/", params={"q": "дисплей doogee", "page": 1})
    data = r.json()
    if data.get("data"):
        product = data["data"][0]
        print(f"ID: {product.get('id')}")
        print(f"Name: {product.get('name')}")
        print(f"URL: {product.get('url')}")
        print(f"Quantity: {product.get('quantity')}")
        print(f"Prices: {json.dumps(product.get('prices', []), ensure_ascii=False, indent=2)}")
        print(f"\nВсе ключи товара: {list(product.keys())}")
        product_id = product.get('id')
except Exception as e:
    print(f"Error: {e}")
    product_id = 282980

# Тест 2: Карточка товара
print("\n" + "=" * 60)
print(f"TEST 2: Product card API (id={product_id})")
print("=" * 60)
endpoints = [
    f"/catalog/product/{product_id}/",
    f"/catalog/product/?id={product_id}",
    f"/catalog/products/{product_id}/",
    f"/product/{product_id}/",
]
for ep in endpoints:
    try:
        r = client.get(f"{BASE}{ep}")
        print(f"\n{ep}")
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  Keys: {list(data.keys()) if isinstance(data, dict) else 'array'}")
            if isinstance(data, dict) and 'data' in data:
                print(f"  Data keys: {list(data['data'].keys()) if isinstance(data['data'], dict) else 'array'}")
    except Exception as e:
        print(f"  Error: {e}")

# Тест 3: Категории
print("\n" + "=" * 60)
print("TEST 3: Categories API")
print("=" * 60)
cat_endpoints = [
    "/catalog/sections/",
    "/catalog/sections/?code=komplektuyushchie_dlya_remonta",
    "/catalog/menu/",
    "/menu/",
    "/main-menu/",
    "/catalog/categories/",
    "/sections/",
]
for ep in cat_endpoints:
    try:
        r = client.get(f"{BASE}{ep}")
        print(f"\n{ep}")
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())[:10]}")
            elif isinstance(data, list):
                print(f"  Array of {len(data)} items")
                if data:
                    print(f"  First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else data[0]}")
    except Exception as e:
        print(f"  Error: {e}")

# Тест 4: Товары в категории
print("\n" + "=" * 60)
print("TEST 4: Products in category API")
print("=" * 60)
cat_path = "komplektuyushchie_dlya_remonta/zapchasti_dlya_mobilnykh_ustroystv/displei_2/dlya_doogee"
prods_endpoints = [
    f"/catalog/products/?sectionCode={cat_path}",
    f"/catalog/products/?section={cat_path}",
    f"/catalog/section/{cat_path}/products/",
    f"/catalog/{cat_path}/",
]
for ep in prods_endpoints:
    try:
        r = client.get(f"{BASE}{ep}")
        print(f"\n{ep[:70]}...")
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())[:10]}")
                if 'data' in data and isinstance(data['data'], list):
                    print(f"  Products count: {len(data['data'])}")
    except Exception as e:
        print(f"  Error: {e}")

# Тест 5: HTML страница категории
print("\n" + "=" * 60)
print("TEST 5: Category HTML page")
print("=" * 60)
try:
    r = client.get(f"https://green-spark.ru/catalog/{cat_path}/")
    print(f"Status: {r.status_code}")
    print(f"Content length: {len(r.text)}")
    # Ищем подкатегории и хлебные крошки
    if "breadcrumb" in r.text.lower():
        print("Found: breadcrumbs")
    if "subcategory" in r.text.lower() or "subsection" in r.text.lower():
        print("Found: subcategories")
    # Ищем артикул
    if "GS-" in r.text:
        import re
        articles = re.findall(r'GS-\d+', r.text)
        print(f"Found articles: {articles[:5]}")
except Exception as e:
    print(f"Error: {e}")

# Тест 6: HTML карточка товара
print("\n" + "=" * 60)
print("TEST 6: Product HTML page")
print("=" * 60)
try:
    product_url = "https://green-spark.ru/catalog/komplektuyushchie_dlya_remonta/zapchasti_dlya_mobilnykh_ustroystv/displei_2/dlya_doogee/displey_dlya_doogee_s40_tachskrin_chernyy.html"
    r = client.get(product_url)
    print(f"Status: {r.status_code}")
    print(f"Content length: {len(r.text)}")
    if "GS-" in r.text:
        import re
        articles = re.findall(r'GS-\d+', r.text)
        print(f"Found articles: {set(articles)}")
    # Поиск хлебных крошек
    if "breadcrumb" in r.text.lower():
        print("Found: breadcrumbs in HTML")
except Exception as e:
    print(f"Error: {e}")

client.close()
print("\n" + "=" * 60)
print("DONE")
