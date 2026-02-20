"""
CRUD for zip_proxies table via asyncpg.
"""
import asyncpg
import ssl
from typing import Optional, List, Dict
from datetime import datetime


DB_CONFIG = {
    "host": "aws-1-eu-west-3.pooler.supabase.com",
    "port": 5432,
    "user": "postgres.griexhozxrqtepcilfnu",
    "password": "Mi31415926pSss!",
    "database": "postgres",
}


class ProxyDatabase:
    def __init__(self, pool=None):
        self._pool = pool
        self._conn = None

    async def connect(self):
        if self._pool is None:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._conn = await asyncpg.connect(
                **DB_CONFIG,
                ssl=ctx,
                statement_cache_size=0,
                command_timeout=30,
            )
            # Wrap single connection to look like a pool
            self._pool = self

    async def close(self):
        if self._conn:
            await self._conn.close()

    # Pool-compatible methods
    async def execute(self, query, *args):
        return await self._conn.execute(query, *args)

    async def fetch(self, query, *args):
        return await self._conn.fetch(query, *args)

    async def fetchrow(self, query, *args):
        return await self._conn.fetchrow(query, *args)

    async def fetchval(self, query, *args):
        return await self._conn.fetchval(query, *args)

    async def get_working_proxy(self, proxy_type: str = "http", for_site: str = None) -> Optional[str]:
        """Get a working proxy not banned for the given site."""
        if for_site:
            row = await self._pool.fetchrow("""
                SELECT proxy FROM zip_proxies
                WHERE status = 'working'
                  AND type = $1
                  AND NOT (banned_sites @> ARRAY[$2]::text[])
                ORDER BY last_used_at ASC NULLS FIRST, last_checked_at ASC
                LIMIT 1
            """, proxy_type, for_site)
        else:
            row = await self._pool.fetchrow("""
                SELECT proxy FROM zip_proxies
                WHERE status = 'working' AND type = $1
                ORDER BY last_used_at ASC NULLS FIRST, last_checked_at ASC
                LIMIT 1
            """, proxy_type)
        if row:
            await self._pool.execute(
                "UPDATE zip_proxies SET last_used_at = NOW() WHERE proxy = $1",
                row["proxy"]
            )
            return row["proxy"]
        return None

    async def report_success(self, proxy: str, response_time: float = None):
        await self._pool.execute("""
            UPDATE zip_proxies SET
                success_count = success_count + 1,
                fail_count = 0,
                response_time = COALESCE($2, response_time),
                last_used_at = NOW()
            WHERE proxy = $1
        """, proxy, response_time)

    async def report_failure(self, proxy: str, banned_site: str = None):
        if banned_site:
            await self._pool.execute("""
                UPDATE zip_proxies SET
                    banned_sites = array_append(banned_sites, $2),
                    last_used_at = NOW()
                WHERE proxy = $1 AND NOT (banned_sites @> ARRAY[$2]::text[])
            """, proxy, banned_site)
        else:
            await self._pool.execute("""
                UPDATE zip_proxies SET
                    fail_count = fail_count + 1,
                    last_used_at = NOW()
                WHERE proxy = $1
            """, proxy)
            # Mark dead if too many failures
            await self._pool.execute("""
                UPDATE zip_proxies SET status = 'dead'
                WHERE proxy = $1 AND fail_count > 5
            """, proxy)

    async def upsert_proxies(self, proxies: List[Dict]):
        """Bulk upsert raw proxies in batches."""
        if not proxies:
            return 0

        BATCH = 500
        inserted = 0
        for i in range(0, len(proxies), BATCH):
            batch = proxies[i:i+BATCH]
            # Build a single VALUES clause
            values = []
            args = []
            for j, p in enumerate(batch):
                idx = j * 3
                values.append(f"(${idx+1}, ${idx+2}, ${idx+3}, 'raw')")
                args.extend([p["proxy"], p.get("type", "http"), p.get("source", "unknown")[:80]])

            sql = f"""
                INSERT INTO zip_proxies (proxy, type, source, status)
                VALUES {', '.join(values)}
                ON CONFLICT (proxy) DO NOTHING
            """
            try:
                result = await self._pool.execute(sql, *args)
                # result is like "INSERT 0 N"
                count = int(result.split()[-1]) if result else 0
                inserted += count
            except Exception as e:
                # Fallback: insert one by one for this batch
                for p in batch:
                    try:
                        await self._pool.execute("""
                            INSERT INTO zip_proxies (proxy, type, source, status)
                            VALUES ($1, $2, $3, 'raw')
                            ON CONFLICT (proxy) DO NOTHING
                        """, p["proxy"], p.get("type", "http"), p.get("source", "unknown")[:80])
                        inserted += 1
                    except Exception:
                        pass
        return inserted

    async def set_status(self, proxy: str, status: str, response_time: float = None, https_working: bool = None):
        await self._pool.execute("""
            UPDATE zip_proxies SET
                status = $2,
                response_time = COALESCE($3, response_time),
                https_working = COALESCE($4, https_working),
                last_checked_at = NOW()
            WHERE proxy = $1
        """, proxy, status, response_time, https_working)

    async def get_unchecked(self, limit: int = 100) -> List[str]:
        rows = await self._pool.fetch("""
            SELECT proxy, type FROM zip_proxies
            WHERE status = 'raw'
            ORDER BY created_at ASC
            LIMIT $1
        """, limit)
        return [(r["proxy"], r["type"]) for r in rows]

    async def get_working_for_check(self, limit: int = 50) -> List[str]:
        rows = await self._pool.fetch("""
            SELECT proxy, type FROM zip_proxies
            WHERE status = 'working'
            ORDER BY last_checked_at ASC NULLS FIRST
            LIMIT $1
        """, limit)
        return [(r["proxy"], r["type"]) for r in rows]

    async def get_stats(self) -> dict:
        rows = await self._pool.fetch(
            "SELECT status, count(*) as cnt FROM zip_proxies GROUP BY status"
        )
        stats = {r["status"]: r["cnt"] for r in rows}

        ban_rows = await self._pool.fetch("""
            SELECT unnest(banned_sites) as site, count(*) as cnt
            FROM zip_proxies
            WHERE array_length(banned_sites, 1) > 0
            GROUP BY site
        """)
        stats["banned_by_site"] = {r["site"]: r["cnt"] for r in ban_rows}

        total_working = stats.get("working", 0)
        stats["total"] = sum(v for k, v in stats.items() if k != "banned_by_site")
        stats["working"] = total_working
        return stats

    async def cleanup_dead(self):
        """Remove dead proxies older than 24h."""
        await self._pool.execute("""
            DELETE FROM zip_proxies
            WHERE status = 'dead' AND last_checked_at < NOW() - INTERVAL '24 hours'
        """)
