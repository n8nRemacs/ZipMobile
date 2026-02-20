"""
CRUD for proxy_pool and proxy_cookies tables via asyncpg (Homelab PostgreSQL).
"""
import asyncpg
import json
import logging
from typing import Optional, List, Dict

from .config import settings

logger = logging.getLogger(__name__)


class ProxyDatabase:
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self._pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        await self._ensure_table()

    async def close(self):
        if self._pool:
            await self._pool.close()

    async def _ensure_table(self):
        """Create proxy_pool table and indexes if not exist."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS proxy_pool (
                    id              SERIAL PRIMARY KEY,
                    host            VARCHAR(45) NOT NULL,
                    port            INTEGER NOT NULL,
                    http            BOOLEAN DEFAULT FALSE,
                    https           BOOLEAN DEFAULT FALSE,
                    socks4          BOOLEAN DEFAULT FALSE,
                    socks5          BOOLEAN DEFAULT FALSE,
                    response_time_ms FLOAT,
                    success_count   INTEGER DEFAULT 0,
                    fail_count      INTEGER DEFAULT 0,
                    status          VARCHAR(20) DEFAULT 'raw',
                    banned_sites    TEXT[] DEFAULT '{}',
                    source          VARCHAR(80),
                    created_at      TIMESTAMP DEFAULT NOW(),
                    last_checked_at TIMESTAMP,
                    last_used_at    TIMESTAMP,
                    UNIQUE(host, port)
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proxy_pool_status
                ON proxy_pool(status)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proxy_pool_protocols
                ON proxy_pool(http, https, socks4, socks5)
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS proxy_cookies (
                    id          SERIAL PRIMARY KEY,
                    host        VARCHAR(45) NOT NULL,
                    port        INTEGER NOT NULL,
                    site_key    VARCHAR(50) NOT NULL,
                    cookies     JSONB NOT NULL,
                    fetched_at  TIMESTAMP DEFAULT NOW(),
                    UNIQUE(host, port, site_key)
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_proxy_cookies_site
                ON proxy_cookies(site_key)
            """)

    # ── Queries ──────────────────────────────────────────────

    async def get_working_proxies(
        self,
        protocol: str = "http",
        for_site: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """Get working proxies for a protocol, not banned for site."""
        protocol_col = protocol.lower()
        if protocol_col not in ("http", "https", "socks4", "socks5"):
            protocol_col = "http"

        if for_site:
            rows = await self._pool.fetch(f"""
                SELECT host, port FROM proxy_pool
                WHERE status = 'working'
                  AND {protocol_col} = TRUE
                  AND NOT (banned_sites @> ARRAY[$1]::text[])
                ORDER BY last_used_at ASC NULLS FIRST, success_count DESC
                LIMIT $2
            """, for_site, limit)
        else:
            rows = await self._pool.fetch(f"""
                SELECT host, port FROM proxy_pool
                WHERE status = 'working' AND {protocol_col} = TRUE
                ORDER BY last_used_at ASC NULLS FIRST, success_count DESC
                LIMIT $1
            """, limit)

        return [dict(r) for r in rows]

    async def mark_used(self, host: str, port: int):
        await self._pool.execute(
            "UPDATE proxy_pool SET last_used_at = NOW() WHERE host = $1 AND port = $2",
            host, port,
        )

    async def report_success(self, host: str, port: int, response_time: Optional[float] = None):
        await self._pool.execute("""
            UPDATE proxy_pool SET
                success_count = success_count + 1,
                fail_count = 0,
                response_time_ms = COALESCE($3, response_time_ms),
                last_used_at = NOW()
            WHERE host = $1 AND port = $2
        """, host, port, response_time)

    async def report_failure(self, host: str, port: int, banned_site: Optional[str] = None):
        if banned_site:
            await self._pool.execute("""
                UPDATE proxy_pool SET
                    banned_sites = array_append(banned_sites, $3),
                    last_used_at = NOW()
                WHERE host = $1 AND port = $2
                  AND NOT (banned_sites @> ARRAY[$3]::text[])
            """, host, port, banned_site)
        else:
            await self._pool.execute("""
                UPDATE proxy_pool SET
                    fail_count = fail_count + 1,
                    last_used_at = NOW()
                WHERE host = $1 AND port = $2
            """, host, port)
            await self._pool.execute("""
                UPDATE proxy_pool SET status = 'dead'
                WHERE host = $1 AND port = $2 AND fail_count > 5
            """, host, port)

    async def upsert_proxies(self, proxies: List[Dict]) -> int:
        """Bulk upsert raw proxies. Each dict: {host, port, source, source_type}."""
        if not proxies:
            return 0

        BATCH = 500
        inserted = 0
        for i in range(0, len(proxies), BATCH):
            batch = proxies[i:i + BATCH]
            values = []
            args = []
            for j, p in enumerate(batch):
                idx = j * 3
                values.append(f"(${idx+1}, ${idx+2}, ${idx+3}, 'raw')")
                args.extend([p["host"], p["port"], p.get("source", "unknown")[:80]])

            sql = f"""
                INSERT INTO proxy_pool (host, port, source, status)
                VALUES {', '.join(values)}
                ON CONFLICT (host, port) DO NOTHING
            """
            try:
                result = await self._pool.execute(sql, *args)
                count = int(result.split()[-1]) if result else 0
                inserted += count
            except Exception:
                for p in batch:
                    try:
                        await self._pool.execute("""
                            INSERT INTO proxy_pool (host, port, source, status)
                            VALUES ($1, $2, $3, 'raw')
                            ON CONFLICT (host, port) DO NOTHING
                        """, p["host"], p["port"], p.get("source", "unknown")[:80])
                        inserted += 1
                    except Exception:
                        pass
        return inserted

    async def set_check_result(
        self,
        host: str,
        port: int,
        status: str,
        http: bool = False,
        https: bool = False,
        socks4: bool = False,
        socks5: bool = False,
        response_time_ms: Optional[float] = None,
    ):
        await self._pool.execute("""
            UPDATE proxy_pool SET
                status = $3,
                http = $4,
                https = $5,
                socks4 = $6,
                socks5 = $7,
                response_time_ms = COALESCE($8, response_time_ms),
                last_checked_at = NOW()
            WHERE host = $1 AND port = $2
        """, host, port, status, http, https, socks4, socks5, response_time_ms)

    async def get_unchecked(self, limit: int = 500) -> List[dict]:
        rows = await self._pool.fetch("""
            SELECT host, port FROM proxy_pool
            WHERE status = 'raw'
            ORDER BY created_at ASC
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]

    async def get_working_for_recheck(self, limit: int = 500) -> List[dict]:
        rows = await self._pool.fetch("""
            SELECT host, port FROM proxy_pool
            WHERE status = 'working'
            ORDER BY last_checked_at ASC NULLS FIRST
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]

    # ── Cookie CRUD ───────────────────────────────────────────

    async def save_cookies(self, host: str, port: int, site_key: str, cookies: dict):
        """UPSERT cookies for a proxy+site pair."""
        await self._pool.execute("""
            INSERT INTO proxy_cookies (host, port, site_key, cookies, fetched_at)
            VALUES ($1, $2, $3, $4::jsonb, NOW())
            ON CONFLICT (host, port, site_key) DO UPDATE SET
                cookies = EXCLUDED.cookies,
                fetched_at = NOW()
        """, host, port, site_key, json.dumps(cookies))

    async def get_cookies(self, host: str, port: int, site_key: str) -> Optional[dict]:
        """Get cookies for a proxy+site pair, or None if missing/expired."""
        row = await self._pool.fetchrow("""
            SELECT cookies FROM proxy_cookies
            WHERE host = $1 AND port = $2 AND site_key = $3
              AND fetched_at > NOW() - INTERVAL '1 hour' * $4
        """, host, port, site_key, settings.cookie_max_age_hours)
        if not row:
            return None
        val = row["cookies"]
        if not val:
            return None
        # asyncpg may return JSONB as str or as native dict depending on version/codec
        if isinstance(val, str):
            return json.loads(val)
        return dict(val)

    async def get_proxies_without_cookies(
        self,
        site_key: str,
        protocol: str = "socks5",
        limit: int = 20,
    ) -> List[dict]:
        """Get working SOCKS5 proxies that have no fresh cookies for site_key."""
        protocol_col = protocol.lower()
        if protocol_col not in ("http", "https", "socks4", "socks5"):
            protocol_col = "socks5"
        rows = await self._pool.fetch(f"""
            SELECT p.host, p.port FROM proxy_pool p
            WHERE p.status = 'working'
              AND p.{protocol_col} = TRUE
              AND NOT (p.banned_sites @> ARRAY[$1]::text[])
              AND NOT EXISTS (
                SELECT 1 FROM proxy_cookies c
                WHERE c.host = p.host AND c.port = p.port AND c.site_key = $1
                  AND c.fetched_at > NOW() - INTERVAL '1 hour' * $2
              )
            ORDER BY p.last_checked_at ASC NULLS FIRST
            LIMIT $3
        """, site_key, settings.cookie_max_age_hours, limit)
        return [dict(r) for r in rows]

    async def delete_cookies_for_proxy(self, host: str, port: int):
        """Delete all cookies for a proxy (called on ban)."""
        await self._pool.execute(
            "DELETE FROM proxy_cookies WHERE host = $1 AND port = $2",
            host, port,
        )

    # ── Stats / Maintenance ───────────────────────────────────

    async def get_stats(self) -> dict:
        rows = await self._pool.fetch(
            "SELECT status, count(*) as cnt FROM proxy_pool GROUP BY status"
        )
        stats = {r["status"]: r["cnt"] for r in rows}

        ban_rows = await self._pool.fetch("""
            SELECT unnest(banned_sites) as site, count(*) as cnt
            FROM proxy_pool
            WHERE array_length(banned_sites, 1) > 0
            GROUP BY site
        """)
        stats["banned_by_site"] = {r["site"]: r["cnt"] for r in ban_rows}

        total = sum(v for k, v in stats.items() if k != "banned_by_site")
        stats["total"] = total
        return stats

    async def cleanup_dead(self, hours: int = 48):
        """Remove dead proxies older than N hours."""
        result = await self._pool.execute(f"""
            DELETE FROM proxy_pool
            WHERE status = 'dead'
              AND last_checked_at < NOW() - INTERVAL '{hours} hours'
        """)
        count = int(result.split()[-1]) if result else 0
        logger.info(f"Cleaned up {count} dead proxies older than {hours}h")
        return count
