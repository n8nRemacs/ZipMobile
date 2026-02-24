"""
ProxyPool — orchestrates scrape → check → serve cycle.
"""
import asyncio
import logging
from typing import Optional

from .database import ProxyDatabase
from .scraper import ProxyScraper
from .checker import ProxyChecker
from .config import settings

logger = logging.getLogger(__name__)


class ProxyPool:
    def __init__(self):
        self.db = ProxyDatabase()
        self.scraper = ProxyScraper()
        self.checker = ProxyChecker(
            timeout=settings.check_timeout,
            concurrency=settings.check_concurrency,
        )
        self._refresh_lock = asyncio.Lock()

    async def connect(self):
        await self.db.connect()

    async def close(self):
        await self.db.close()

    async def get_proxy(
        self,
        protocol: str = "http",
        for_site: Optional[str] = None,
        country: Optional[str] = None,
        verify_timeout: int = 8,
    ) -> Optional[dict]:
        """
        Get a working proxy with pre-delivery verification.
        Tries up to 5 candidates, quick-tests each before returning.
        Failed quick-tests do NOT mark proxies as dead (non-destructive).
        """
        candidates = await self.db.get_working_proxies(
            protocol, for_site, country=country, limit=10
        )
        if not candidates:
            return None

        attempts = 0
        for candidate in candidates:
            if attempts >= 5:
                break
            attempts += 1

            host, port = candidate["host"], candidate["port"]

            # Quick verification (non-destructive — don't mark as dead on failure)
            old_timeout = self.checker.timeout
            self.checker.timeout = verify_timeout
            ok, rt = await self.checker.quick_test(host, port, protocol)
            self.checker.timeout = old_timeout

            if ok:
                await self.db.mark_used(host, port)
                return {
                    "host": host,
                    "port": port,
                    "protocol": protocol,
                    "response_time_ms": rt,
                    "country": candidate.get("country"),
                }
            else:
                # Bump last_used_at so this proxy goes to the back of LRU queue
                await self.db.mark_used(host, port)
                logger.debug(f"Pre-check failed for {host}:{port}, trying next")

        return None

    async def report(
        self,
        host: str,
        port: int,
        success: bool,
        response_time: Optional[float] = None,
        banned_site: Optional[str] = None,
    ):
        if success:
            await self.db.report_success(host, port, response_time)
        else:
            await self.db.report_failure(host, port, banned_site)

    async def refresh(self):
        """Full refresh: scrape → check raw → recheck working → cleanup."""
        if self._refresh_lock.locked():
            logger.info("Refresh already in progress, skipping")
            return {"status": "already_running"}

        async with self._refresh_lock:
            logger.info("Starting proxy pool refresh...")

            # 1. Scrape
            raw_proxies = await self.scraper.scrape_all()
            inserted = await self.db.upsert_proxies(raw_proxies)
            logger.info(f"Scraped {len(raw_proxies)} proxies, {inserted} new inserted")

            # 2. Check unchecked (raw)
            checked, working = await self._check_unchecked(limit=500)

            # 3. Recheck existing working proxies
            rechecked, still_working = await self._recheck_working(limit=500)

            # 4. Cleanup old dead
            cleaned = await self.db.cleanup_dead(hours=48)

            stats = await self.db.get_stats()
            logger.info(f"Refresh complete. Stats: {stats}")

            return {
                "status": "completed",
                "scraped": len(raw_proxies),
                "new_inserted": inserted,
                "checked": checked,
                "new_working": working,
                "rechecked": rechecked,
                "still_working": still_working,
                "cleaned_dead": cleaned,
            }

    async def _check_unchecked(self, limit: int = 500) -> tuple:
        """Check raw proxies. Returns (total_checked, working_count)."""
        unchecked = await self.db.get_unchecked(limit)
        if not unchecked:
            return 0, 0

        logger.info(f"Checking {len(unchecked)} raw proxies...")
        results = await self.checker.check_batch(unchecked)

        working = 0
        for proxy, result in zip(unchecked, results):
            if isinstance(result, Exception):
                await self.db.set_check_result(proxy["host"], proxy["port"], "dead")
                continue

            any_working = result["http"] or result["https"] or result["socks4"] or result["socks5"]
            status = "working" if any_working else "dead"
            await self.db.set_check_result(
                proxy["host"], proxy["port"], status,
                http=result["http"],
                https=result["https"],
                socks4=result["socks4"],
                socks5=result["socks5"],
                response_time_ms=result["response_time_ms"],
                country=result.get("country"),
            )
            if any_working:
                working += 1

        logger.info(f"Raw check: {working}/{len(unchecked)} working")
        return len(unchecked), working

    async def _recheck_working(self, limit: int = 500) -> tuple:
        """Recheck existing working proxies. Returns (total, still_working)."""
        proxies = await self.db.get_working_for_recheck(limit)
        if not proxies:
            return 0, 0

        logger.info(f"Rechecking {len(proxies)} working proxies...")
        results = await self.checker.check_batch(proxies)

        still_working = 0
        for proxy, result in zip(proxies, results):
            if isinstance(result, Exception):
                await self.db.set_check_result(proxy["host"], proxy["port"], "dead")
                continue

            any_working = result["http"] or result["https"] or result["socks4"] or result["socks5"]
            status = "working" if any_working else "dead"
            await self.db.set_check_result(
                proxy["host"], proxy["port"], status,
                http=result["http"],
                https=result["https"],
                socks4=result["socks4"],
                socks5=result["socks5"],
                response_time_ms=result["response_time_ms"],
                country=result.get("country"),
            )
            if any_working:
                still_working += 1

        logger.info(f"Recheck: {still_working}/{len(proxies)} still working")
        return len(proxies), still_working

    async def get_stats(self) -> dict:
        return await self.db.get_stats()
