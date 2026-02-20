"""
Moba.ru Full Product Parser
Парсер номенклатуры moba.ru с обходом Yandex SmartCaptcha
"""
import json
import time
import re
import os
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from urllib.parse import urljoin, urlparse, parse_qs

COOKIES_FILE = "moba_cookies.json"
OUTPUT_DIR = "moba_data"


class MobaParser:
    def __init__(self, cookies_file=COOKIES_FILE):
        self.base_url = "https://moba.ru"
        self.session = curl_requests.Session(impersonate="chrome120")
        self.cookies = {}
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?1",
            "Sec-Ch-Ua-Platform": '"Android"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Referer": "https://moba.ru/",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36",
        }

        # Load cookies
        if os.path.exists(cookies_file):
            with open(cookies_file, "r") as f:
                self.cookies = json.load(f)
            self.headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
            print(f"[+] Loaded {len(self.cookies)} cookies")

        # Create output dir
        Path(OUTPUT_DIR).mkdir(exist_ok=True)

    def get(self, url, **kwargs):
        """Make GET request with cookies"""
        full_url = urljoin(self.base_url, url)
        resp = self.session.get(full_url, headers=self.headers, **kwargs)
        return resp

    def test_access(self):
        """Test if we can access the site"""
        resp = self.get("/")
        if resp.status_code == 200 and "каталог" in resp.text.lower():
            print("[+] Access OK!")
            return True
        print(f"[!] Access failed: {resp.status_code}")
        return False

    def get_categories(self):
        """Get all product categories"""
        print("[*] Getting categories...")
        resp = self.get("/catalog/")

        if resp.status_code != 200:
            print(f"[!] Failed to get catalog: {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        categories = []

        # Find category links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.startswith("/catalog/") and href != "/catalog/" and "filter" not in href and "?" not in href:
                # Clean up the URL
                clean_url = href.split("?")[0]
                if clean_url not in [c["url"] for c in categories]:
                    name = link.get_text(strip=True)
                    if name and len(name) > 1:
                        categories.append({
                            "url": clean_url,
                            "name": name[:100]
                        })

        print(f"[+] Found {len(categories)} categories")
        return categories

    def get_category_products(self, category_url, max_pages=10):
        """Get all products from a category with pagination"""
        products = []
        page = 1

        while page <= max_pages:
            url = f"{category_url}?PAGEN_1={page}" if page > 1 else category_url
            print(f"  Page {page}: {url}")

            resp = self.get(url)
            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            page_products = self.parse_product_list(soup)

            if not page_products:
                break

            products.extend(page_products)

            # Check if there's a next page
            if not soup.find("a", class_="next") and not soup.find("a", {"rel": "next"}):
                break

            page += 1
            time.sleep(0.5)  # Rate limit

        return products

    def parse_product_list(self, soup):
        """Parse products from listing page"""
        products = []

        # Moba.ru uses table-based layout: tr.item.main_item_wrapper
        items = soup.select("tr.item.main_item_wrapper")

        # Fallback selectors for other Bitrix sites
        if not items:
            selectors = [
                "div.catalog-item",
                "div.item-card",
                "div.product-item",
                "div.catalog_item",
            ]
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    break

        for item in items:
            try:
                product = self.parse_product_item(item)
                if product:
                    products.append(product)
            except Exception as e:
                continue

        return products

    def parse_product_item(self, item):
        """Parse single product from listing (Moba.ru Bitrix structure)"""
        product = {}

        # Get product ID from URL
        product_id = None

        # Find product link - look for links to /catalog/category/ID/
        name_link = None
        for a in item.find_all("a", href=True):
            href = a.get("href", "")
            # Product URLs have pattern /catalog/category/number/
            if href.startswith("/catalog/") and href.count("/") >= 3:
                text = a.get_text(strip=True)
                if text and len(text) > 5:
                    name_link = a
                    # Extract ID from URL
                    parts = href.rstrip("/").split("/")
                    if parts and parts[-1].isdigit():
                        product_id = parts[-1]
                    break

        if name_link:
            product["name"] = name_link.get_text(strip=True)
            product["url"] = name_link.get("href", "")
            if product_id:
                product["id"] = product_id

        # Get price from .cost class (Moba-specific)
        price_elem = item.select_one(".cost") or item.find(class_="price")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            # Extract first number (current price)
            price_match = re.search(r'([\d\s]+)', price_text.replace("\xa0", " "))
            if price_match:
                product["price"] = price_match.group(1).replace(" ", "").strip()

        # Get image
        img = item.find("img")
        if img:
            src = img.get("src") or img.get("data-src", "")
            if src:
                product["image"] = src

        # Get article/SKU
        article_elem = item.find(class_="article") or item.find(class_="articul")
        if article_elem:
            product["article"] = article_elem.get_text(strip=True)

        # Get availability
        avail_elem = item.find(class_="available") or item.find(class_="presence-span")
        if avail_elem:
            product["available"] = avail_elem.get_text(strip=True)

        return product if product.get("name") else None

    def get_product_details(self, product_url):
        """Get detailed product info from product page"""
        resp = self.get(product_url)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        details = {}

        # Get title
        title = soup.find("h1")
        if title:
            details["name"] = title.get_text(strip=True)

        # Get price
        price_elem = soup.find(class_="price") or soup.find("meta", {"itemprop": "price"})
        if price_elem:
            if price_elem.name == "meta":
                details["price"] = price_elem.get("content")
            else:
                details["price"] = price_elem.get_text(strip=True)

        # Get description
        desc_elem = soup.find(class_="description") or soup.find("div", {"itemprop": "description"})
        if desc_elem:
            details["description"] = desc_elem.get_text(strip=True)[:500]

        # Get specifications
        specs = {}
        spec_table = soup.find("table", class_="props") or soup.find("table", class_="chars")
        if spec_table:
            for row in spec_table.find_all("tr"):
                cols = row.find_all(["td", "th"])
                if len(cols) >= 2:
                    key = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)
                    specs[key] = value
        details["specs"] = specs

        # Get images
        images = []
        for img in soup.select(".product-images img, .gallery img, .slides img"):
            src = img.get("src") or img.get("data-src")
            if src:
                images.append(src)
        details["images"] = images[:10]

        return details

    def parse_all(self, max_categories=None, max_pages_per_category=5):
        """Parse all products from all categories"""
        all_data = {
            "parsed_at": datetime.now().isoformat(),
            "categories": [],
            "products": []
        }

        categories = self.get_categories()
        if max_categories:
            categories = categories[:max_categories]

        for i, cat in enumerate(categories, 1):
            print(f"\n[{i}/{len(categories)}] {cat['name']}")

            products = self.get_category_products(cat["url"], max_pages=max_pages_per_category)
            print(f"  -> {len(products)} products")

            all_data["categories"].append({
                "name": cat["name"],
                "url": cat["url"],
                "product_count": len(products)
            })

            for p in products:
                p["category"] = cat["name"]
                all_data["products"].append(p)

            time.sleep(1)  # Rate limit between categories

        # Save results
        output_file = Path(OUTPUT_DIR) / f"moba_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        print(f"\n[+] Saved {len(all_data['products'])} products to {output_file}")

        # Also save as CSV
        self.save_csv(all_data["products"])

        return all_data

    def save_csv(self, products):
        """Save products as CSV"""
        import csv

        output_file = Path(OUTPUT_DIR) / f"moba_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
            if not products:
                return

            fieldnames = ["id", "name", "url", "price", "article", "category", "available", "image"]
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(products)

        print(f"[+] Saved CSV to {output_file}")


def main():
    import sys

    parser = MobaParser()

    if not parser.test_access():
        print("[!] Cannot access site. Update cookies!")
        return

    if len(sys.argv) > 1:
        if sys.argv[1] == "--categories":
            # Just list categories
            cats = parser.get_categories()
            for i, c in enumerate(cats, 1):
                print(f"{i}. {c['name']}: {c['url']}")

        elif sys.argv[1] == "--category":
            # Parse single category
            url = sys.argv[2] if len(sys.argv) > 2 else "/catalog/akkumulyatory/"
            products = parser.get_category_products(url)
            print(f"\nProducts: {len(products)}")
            for p in products[:10]:
                print(f"  - {p.get('name', '?')}: {p.get('price', '?')}")

        elif sys.argv[1] == "--full":
            # Full parse
            max_cats = int(sys.argv[2]) if len(sys.argv) > 2 else None
            parser.parse_all(max_categories=max_cats)
    else:
        print("Usage:")
        print("  python moba_full_parser.py --categories        # List categories")
        print("  python moba_full_parser.py --category /url/    # Parse one category")
        print("  python moba_full_parser.py --full [N]          # Parse all (or N categories)")


if __name__ == "__main__":
    main()
