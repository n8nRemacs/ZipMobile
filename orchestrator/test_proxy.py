"""
Test proxy pool: check 200 HTTP proxies, then check for moba.
"""
import asyncio
import logging
import time
import sys
import aiohttp

sys.path.insert(0, "/mnt/projects/repos/ZipMobile/orchestrator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test")

from src.proxy.pool import ProxyPool


async def main():
    pool = ProxyPool()
    pool.checker.timeout = aiohttp.ClientTimeout(total=5)
    pool.checker.concurrency = 100
    pool.checker._sem = asyncio.Semaphore(100)
    print("Connecting to DB...")
    await pool.connect()
    print("Connected!")

    # Step 1: Check 200 HTTP proxies
    print("=== Step 1: Checking 200 HTTP proxies ===")
    t0 = time.time()

    print("Fetching proxies from DB...")
    rows = await pool.db._pool.fetch(
        "SELECT proxy, type FROM zip_proxies WHERE status = $1 AND type = $2 ORDER BY created_at ASC LIMIT 200",
        "raw", "http"
    )
    proxies = [(r["proxy"], r["type"]) for r in rows]
    print(f"Got {len(proxies)} HTTP proxies to check")

    results = await pool.checker.check_batch(proxies)

    working = 0
    for (proxy, ptype), result in zip(proxies, results):
        if isinstance(result, Exception):
            await pool.db.set_status(proxy, "dead")
            continue
        if result["working"]:
            await pool.db.set_status(proxy, "working", result["response_time"], result["https_working"])
            working += 1
        else:
            await pool.db.set_status(proxy, "dead")

    elapsed = time.time() - t0
    print(f"Step 1 done in {elapsed:.1f}s: {working}/{len(proxies)} working")

    stats = await pool.get_stats()
    print(f"Stats: {stats}")

    if working == 0:
        print("No working proxies found in first 200, checking more...")
        # Check more batches
        for batch_num in range(2, 6):
            rows = await pool.db._pool.fetch(
                "SELECT proxy, type FROM zip_proxies WHERE status = $1 AND type = $2 ORDER BY created_at ASC LIMIT 200 OFFSET $3",
                "raw", "http", (batch_num - 1) * 200
            )
            proxies = [(r["proxy"], r["type"]) for r in rows]
            if not proxies:
                break

            print(f"\nBatch {batch_num}: checking {len(proxies)} proxies...")
            results = await pool.checker.check_batch(proxies)

            for (proxy, ptype), result in zip(proxies, results):
                if isinstance(result, Exception):
                    await pool.db.set_status(proxy, "dead")
                    continue
                if result["working"]:
                    await pool.db.set_status(proxy, "working", result["response_time"], result["https_working"])
                    working += 1
                else:
                    await pool.db.set_status(proxy, "dead")

            print(f"Total working so far: {working}")
            if working >= 10:
                break

    # Step 2: Check working proxies for moba
    print(f"\n=== Step 2: Checking working proxies for moba.ru ===")
    if working > 0:
        moba_count = await pool.check_for_site("moba", limit=min(working, 50))
        print(f"Working for moba.ru: {moba_count}")
    else:
        print("No working proxies to test against moba.ru")

    # Step 3: Get a proxy for moba
    print(f"\n=== Step 3: Get proxy for moba ===")
    proxy = await pool.get_proxy(for_site="moba")
    print(f"Got proxy: {proxy}")

    # Final stats
    stats = await pool.get_stats()
    print(f"\nFinal stats: {stats}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
