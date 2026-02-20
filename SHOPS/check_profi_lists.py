import sys
sys.path.insert(0, "/mnt/projects/repos/ZipMobile/SHOPS/Profi")
from fetch_price_lists import fetch_price_lists
from price_lists_config import PRICE_LISTS

dynamic = fetch_price_lists()
print("=== DYNAMIC (from site): {} ===".format(len(dynamic)))
for i, pl in enumerate(dynamic):
    print("{:3d}. [{:<20}] {:<30} {}".format(
        i+1, pl.get("city", "?"), pl.get("shop", "?"), pl["url"].split("/")[-1]
    ))

print("\n=== STATIC (from config): {} ===".format(len(PRICE_LISTS)))
for i, pl in enumerate(PRICE_LISTS):
    print("{:3d}. [{:<20}] {:<30} {}".format(
        i+1, pl.get("city", "?"), pl.get("shop", "?"), pl.get("url", "?").split("/")[-1]
    ))

# Find what's in static but not in dynamic
dynamic_urls = set(pl["url"] for pl in dynamic)
static_urls = set(pl["url"] for pl in PRICE_LISTS)
print("\n=== In STATIC but not DYNAMIC: {} ===".format(len(static_urls - dynamic_urls)))
for url in sorted(static_urls - dynamic_urls):
    print("  ", url.split("/")[-1])
print("\n=== In DYNAMIC but not STATIC: {} ===".format(len(dynamic_urls - static_urls)))
for url in sorted(dynamic_urls - static_urls):
    print("  ", url.split("/")[-1])
