"""
Supervisor — orchestrates parser execution with proxy rotation.
"""
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime

from .proxy.pool import ProxyPool
from .parsers.base import BaseParser, ProxyBannedException

logger = logging.getLogger(__name__)


class Supervisor:
    def __init__(self, proxy_pool: ProxyPool):
        self.proxy_pool = proxy_pool
        self.active_tasks: Dict[str, dict] = {}

    async def run_parser(self, parser: BaseParser, mode: str = "full") -> dict:
        """Run a parser with automatic proxy rotation on bans."""
        task_id = f"{parser.shop_code}_{datetime.now().strftime('%H%M%S')}"
        self.active_tasks[task_id] = {
            "shop": parser.shop_code,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "attempt": 0,
        }

        proxy = None
        if parser.needs_proxy:
            proxy = await self.proxy_pool.get_proxy(for_site=parser.shop_code)
            if not proxy:
                logger.error(f"No proxies available for {parser.shop_code}")
                self.active_tasks[task_id]["status"] = "failed"
                self.active_tasks[task_id]["error"] = "No proxies available"
                return self.active_tasks[task_id]

        try:
            result = await self._execute_parser(task_id, parser, proxy)
            self.active_tasks[task_id]["status"] = "completed"
            self.active_tasks[task_id]["result"] = result
        except Exception as e:
            logger.error(f"Parser {parser.shop_code} failed: {e}")
            self.active_tasks[task_id]["status"] = "failed"
            self.active_tasks[task_id]["error"] = str(e)

        return self.active_tasks[task_id]

    async def _execute_parser(self, task_id: str, parser: BaseParser, proxy: Optional[str]) -> dict:
        """Execute parser with retry logic for proxy bans."""
        max_retries = 5 if parser.needs_proxy else 1

        for attempt in range(max_retries):
            self.active_tasks[task_id]["attempt"] = attempt + 1
            self.active_tasks[task_id]["proxy"] = proxy

            try:
                logger.info(f"[{task_id}] Attempt {attempt+1}/{max_retries}, proxy={proxy}")
                products = await parser.parse_all(proxy=proxy)

                if len(products) == 0 and parser.needs_proxy:
                    raise ProxyBannedException("0 products — likely blocked")

                # Report success
                if proxy:
                    await self.proxy_pool.report(proxy, success=True)

                return {
                    "products": len(products),
                    "proxy_used": proxy,
                    "attempts": attempt + 1,
                }

            except ProxyBannedException as e:
                logger.warning(f"[{task_id}] Proxy {proxy} banned for {parser.shop_code}: {e}")
                if proxy:
                    await self.proxy_pool.report(proxy, success=False, banned_site=parser.shop_code)

                # Get new proxy
                proxy = await self.proxy_pool.get_proxy(for_site=parser.shop_code)
                if not proxy:
                    raise RuntimeError(f"No working proxies for {parser.shop_code}")
                continue

        raise RuntimeError(f"Max retries ({max_retries}) exceeded for {parser.shop_code}")

    def get_status(self) -> dict:
        return dict(self.active_tasks)
