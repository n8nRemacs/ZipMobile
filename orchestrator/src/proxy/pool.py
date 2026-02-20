"""
ProxyPool — main proxy management class.
Scrapes, checks, rotates proxies with per-site ban tracking.
"""
import asyncio
import logging
from typing import Optional

from .database import ProxyDatabase
from .scraper import ProxyScraper
from .checker import ProxyChecker

logger = logging.getLogger(__name__)


class ProxyPool:
    def __init__(self, db: ProxyDatabase = None):
        self.db = db or ProxyDatabase()
        self.scraper = ProxyScraper()
        self.checker = ProxyChecker()

    async def connect(self):
        await self.db.connect()

    async def close(self):
        await self.db.close()

    async def get_proxy(self, proxy_type: str = "http", for_site: str = None) -> Optional[str]:
        """
        Get a working proxy not banned for the given site.
        If none available — trigger refresh.
        """
        proxy = await self.db.get_working_proxy(proxy_type, for_site)
        if proxy:
            return proxy

        logger.warning(f"No working proxies for site={for_site}, refreshing...")
        await self.refresh()
        return await self.db.get_working_proxy(proxy_type, for_site)

    async def report(self, proxy: str, success: bool, response_time: float = None, banned_site: str = None):
        """Report proxy usage result."""
        if success:
            await self.db.report_success(proxy, response_time)
        else:
            await self.db.report_failure(proxy, banned_site)

    async def refresh(self):
        """Scrape new proxies, then check them."""
        logger.info("Refreshing proxy pool...")

        # 1. Scrape
        raw_proxies = await self.scraper.scrape_all()
        inserted = await self.db.upsert_proxies(raw_proxies)
        logger.info(f"Scraped {len(raw_proxies)} proxies, {inserted} new inserted")

        # 2. Check unchecked proxies
        await self._check_unchecked(limit=500)

        # 3. Cleanup old dead proxies
        await self.db.cleanup_dead()

        stats = await self.get_stats()
        logger.info(f"Pool stats after refresh: {stats}")

    async def _check_unchecked(self, limit: int = 500):
        """Check raw/unchecked proxies in batches."""
        unchecked = await self.db.get_unchecked(limit)
        if not unchecked:
            return

        logger.info(f"Checking {len(unchecked)} unchecked proxies...")
        results = await self.checker.check_batch(unchecked)

        working = 0
        for (proxy, ptype), result in zip(unchecked, results):
            if isinstance(result, Exception):
                await self.db.set_status(proxy, "dead")
                continue
            if result["working"]:
                await self.db.set_status(proxy, "working", result["response_time"], result["https_working"])
                working += 1
            else:
                await self.db.set_status(proxy, "dead")

        logger.info(f"Check complete: {working}/{len(unchecked)} working")

    async def check_for_site(self, site: str, limit: int = 50) -> int:
        """Check N working proxies against a specific site. Returns count of working ones."""
        proxies = await self.db.get_working_for_check(limit)
        if not proxies:
            logger.warning("No working proxies to check for site")
            return 0

        logger.info(f"Checking {len(proxies)} proxies for site '{site}'...")
        results = await self.checker.check_batch_for_site(proxies, site)

        working = 0
        for (proxy, ptype), result in zip(proxies, results):
            if isinstance(result, Exception):
                continue
            success, rt = result
            if success:
                working += 1
            else:
                await self.db.report_failure(proxy, banned_site=site)

        logger.info(f"Site '{site}': {working}/{len(proxies)} proxies working")
        return working

    async def get_stats(self) -> dict:
        return await self.db.get_stats()
