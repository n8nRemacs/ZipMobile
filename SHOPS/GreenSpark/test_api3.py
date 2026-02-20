"""
Тест 3: API с правильными параметрами и куками
"""
import httpx
import json

# Куки из браузера пользователя
cookies = {
    "magazine": "16344",
    "global_magazine": "16344",
    "PHPSESSID": "28bliu9r49p107he4a17v4nghv",
    "__js_p_": "708,3600,0,0,0",
    "__jhash_": "850",
    "catalog-per-page": "100",
}

client = httpx.Client(
    timeout=30.0,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0",
        "Accept": "*/*",
        "Accept-Language": "ru,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    },
    cookies=cookies,
    follow_redirects=True,
)

BASE = "https://green-spark.ru/local/api"

# Тест 1: API товаров категории с path[]
print("=" * 60)
print("TEST 1: Products API with path[]")
print("=" * 60)

params = {
    "path[]": ["komplektuyushchie_dlya_remonta", "zapchasti_dlya_mobilnykh_ustroystv", "displei_2", "dlya_doogee"],
    "orderBy": "quantity",
    "orderDirection": "desc",
    "perPage": "100",
}

# httpx требует особого формата для path[]
url = f"{BASE}/catalog/products/"
full_url = url + "?path%5B%5D=komplektuyushchie_dlya_remonta&path%5B%5D=zapchasti_dlya_mobilnykh_ustroystv&path%5B%5D=displei_2&path%5B%5D=dlya_doogee&orderBy=quantity&orderDirection=desc&perPage=100"

r = client.get(full_url)
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}")

if r.headers.get('content-type', '').startswith('application/json'):
    data = r.json()
    print(f"\nKeys: {list(data.keys())}")

    if 'data' in data:
        products = data['data']
        print(f"Products count: {len(products)}")

        if products:
            p = products[0]
            print(f"\nFirst product keys: {list(p.keys())}")
            print(f"\nFirst product:")
            print(json.dumps(p, ensure_ascii=False, indent=2))

            # Сохраним полный ответ
            with open("data/category_products.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("\nSaved to data/category_products.json")

    if 'meta' in data:
        print(f"\nMeta: {data['meta']}")

    if 'sections' in data:
        print(f"\nSections (subcategories): {len(data.get('sections', []))} items")
        for s in data.get('sections', [])[:3]:
            print(f"  - {s}")
else:
    print(f"Response (first 500): {r.text[:500]}")

# Тест 2: Корневая категория
print("\n" + "=" * 60)
print("TEST 2: Root category")
print("=" * 60)

url2 = f"{BASE}/catalog/products/?path%5B%5D=komplektuyushchie_dlya_remonta&perPage=20"
r2 = client.get(url2)
print(f"Status: {r2.status_code}")
print(f"Content-Type: {r2.headers.get('content-type')}")

if r2.headers.get('content-type', '').startswith('application/json'):
    data2 = r2.json()
    print(f"Keys: {list(data2.keys())}")

    if 'sections' in data2:
        print(f"\nSubcategories ({len(data2['sections'])}):")
        for s in data2['sections'][:10]:
            print(f"  {s.get('code', '?')}: {s.get('name', '?')}")

        # Сохраним
        with open("data/root_category.json", "w", encoding="utf-8") as f:
            json.dump(data2, f, ensure_ascii=False, indent=2)
        print("\nSaved to data/root_category.json")
else:
    print(f"Response (first 300): {r2.text[:300]}")

# Тест 3: Карточка товара (если есть id)
print("\n" + "=" * 60)
print("TEST 3: Product card API")
print("=" * 60)

# Попробуем разные эндпоинты
product_id = 130659  # ID из предыдущего теста
endpoints = [
    f"/catalog/product/{product_id}/",
    f"/catalog/product/?id={product_id}",
    f"/product/{product_id}/",
    f"/catalog/element/{product_id}/",
]

for ep in endpoints:
    r3 = client.get(f"{BASE}{ep}")
    ct = r3.headers.get('content-type', '')
    print(f"\n{ep}")
    print(f"  Status: {r3.status_code}, Type: {ct}")
    if ct.startswith('application/json'):
        try:
            data3 = r3.json()
            print(f"  Keys: {list(data3.keys())}")
            if 'data' in data3:
                print(f"  Data keys: {list(data3['data'].keys()) if isinstance(data3['data'], dict) else 'array'}")
                # Ищем артикул
                if isinstance(data3['data'], dict):
                    for k, v in data3['data'].items():
                        if 'article' in k.lower() or 'sku' in k.lower() or 'art' in k.lower():
                            print(f"  Found article field: {k} = {v}")
        except:
            print(f"  JSON parse error")

client.close()
print("\n" + "=" * 60)
print("DONE")
