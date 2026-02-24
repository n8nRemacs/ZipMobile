#!/usr/bin/env python3
"""Mass proxy checker — проверяет raw прокси батчами, определяет страну."""
import asyncio
import time
import aiohttp
import asyncpg
from aiohttp_socks import ProxyConnector, ProxyType

DB = "postgresql://postgres:Mi31415926pSss!@localhost:5433/postgres"
BATCH = 2000
CONCURRENCY = 200
GEO_BATCH = "http://ip-api.com/batch?fields=query,countryCode"


async def check_one(host, port, sem):
    async with sem:
        # SOCKS5
        try:
            conn = ProxyConnector(proxy_type=ProxyType.SOCKS5, host=host, port=port)
            t0 = time.monotonic()
            async with aiohttp.ClientSession(
                connector=conn, timeout=aiohttp.ClientTimeout(total=8)
            ) as s:
                async with s.get("http://httpbin.org/ip") as r:
                    if r.status == 200:
                        rt = round((time.monotonic() - t0) * 1000, 2)
                        return {"host": host, "port": port, "ok": True, "socks5": True, "socks4": False, "http": False, "rt": rt}
        except Exception:
            pass
        # SOCKS4
        try:
            conn = ProxyConnector(proxy_type=ProxyType.SOCKS4, host=host, port=port)
            t0 = time.monotonic()
            async with aiohttp.ClientSession(
                connector=conn, timeout=aiohttp.ClientTimeout(total=8)
            ) as s:
                async with s.get("http://httpbin.org/ip") as r:
                    if r.status == 200:
                        rt = round((time.monotonic() - t0) * 1000, 2)
                        return {"host": host, "port": port, "ok": True, "socks5": False, "socks4": True, "http": False, "rt": rt}
        except Exception:
            pass
        # HTTP
        try:
            t0 = time.monotonic()
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=8),
            ) as s:
                async with s.get("http://httpbin.org/ip", proxy=f"http://{host}:{port}") as r:
                    if r.status == 200:
                        rt = round((time.monotonic() - t0) * 1000, 2)
                        return {"host": host, "port": port, "ok": True, "socks5": False, "socks4": False, "http": True, "rt": rt}
        except Exception:
            pass
        return {"host": host, "port": port, "ok": False}


async def resolve_countries(ips):
    result = {}
    for i in range(0, len(ips), 100):
        batch = list(set(ips[i:i+100]))
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
                async with s.post(GEO_BATCH, json=batch) as r:
                    if r.status == 200:
                        data = await r.json()
                        for item in data:
                            cc = item.get("countryCode")
                            if cc and len(cc) == 2:
                                result[item["query"]] = cc
            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"  GeoIP error: {e}", flush=True)
    return result


async def main():
    pool = await asyncpg.create_pool(DB, min_size=2, max_size=5)
    cycle = 0

    while True:
        cycle += 1
        rows = await pool.fetch(
            "SELECT host, port FROM proxy_pool WHERE status = $1 ORDER BY created_at ASC LIMIT $2",
            "raw", BATCH,
        )
        if not rows:
            print(f"Cycle {cycle}: no more raw proxies, done!", flush=True)
            break

        print(f"Cycle {cycle}: checking {len(rows)} raw proxies...", flush=True)
        t0 = time.time()
        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = [check_one(r["host"], r["port"], sem) for r in rows]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        working = 0
        working_ips = []
        for res in results:
            if isinstance(res, Exception):
                continue
            if not res["ok"]:
                await pool.execute(
                    "UPDATE proxy_pool SET status=$1, last_checked_at=NOW() WHERE host=$2 AND port=$3",
                    "dead", res["host"], res["port"],
                )
                continue

            working += 1
            working_ips.append(res["host"])
            await pool.execute(
                "UPDATE proxy_pool SET status=$1, socks5=$2, socks4=$3, http=$4, response_time_ms=$5, last_checked_at=NOW() WHERE host=$6 AND port=$7",
                "working", res["socks5"], res["socks4"], res["http"], res["rt"], res["host"], res["port"],
            )

        # Geo-resolve working proxies
        if working_ips:
            countries = await resolve_countries(working_ips)
            for ip, cc in countries.items():
                await pool.execute(
                    "UPDATE proxy_pool SET country=$1 WHERE host=$2 AND country IS NULL",
                    cc, ip,
                )

        elapsed = round(time.time() - t0, 1)
        ru_count = await pool.fetchval(
            "SELECT count(*) FROM proxy_pool WHERE status=$1 AND country=$2",
            "working", "RU",
        )
        total_working = await pool.fetchval(
            "SELECT count(*) FROM proxy_pool WHERE status=$1",
            "working",
        )
        raw_left = await pool.fetchval(
            "SELECT count(*) FROM proxy_pool WHERE status=$1",
            "raw",
        )
        print(
            f"Cycle {cycle}: +{working}/{len(rows)} working in {elapsed}s | "
            f"total={total_working} RU={ru_count} raw_left={raw_left}",
            flush=True,
        )

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
