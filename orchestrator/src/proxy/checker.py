"""
Proxy checker — validates proxies against test URLs and specific sites.
"""
import asyncio
import time
import aiohttp
import logging
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)

# Generic test URL
TEST_URL = "http://httpbin.org/ip"
TEST_TIMEOUT = 10

# Site-specific tests
SITE_TESTS = {
    "moba": "https://moba.ru/",
    "greenspark": "https://green-spark.ru/",
    "memstech": "https://memstech.ru/",
}

# Indicators of being blocked
BLOCK_INDICATORS = [
    "captcha", "smartcaptcha", "blocked", "access denied",
    "403 forbidden", "challenge", "cf-browser-verification",
    "just a moment", "checking your browser",
]


class ProxyChecker:
    def __init__(self, timeout: int = TEST_TIMEOUT, concurrency: int = 50):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.concurrency = concurrency
        self._sem = asyncio.Semaphore(concurrency)

    async def check_proxy(self, proxy: str, proxy_type: str = "http") -> Dict:
        """
        Check if proxy works with httpbin.
        Returns: {working: bool, response_time: float, https_working: bool}
        """
        result = {"working": False, "response_time": None, "https_working": False}

        proxy_url = self._format_proxy(proxy, proxy_type)
        if not proxy_url:
            return result

        async with self._sem:
            # HTTP check
            t0 = time.monotonic()
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector, timeout=self.timeout) as session:
                    async with session.get(TEST_URL, proxy=proxy_url) as resp:
                        if resp.status == 200:
                            result["working"] = True
                            result["response_time"] = round((time.monotonic() - t0) * 1000, 2)
            except Exception:
                return result

            # HTTPS check (only if HTTP works)
            if result["working"]:
                try:
                    connector = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(connector=connector, timeout=self.timeout) as session:
                        async with session.get("https://httpbin.org/ip", proxy=proxy_url) as resp:
                            if resp.status == 200:
                                result["https_working"] = True
                except Exception:
                    pass

        return result

    async def check_for_site(self, proxy: str, proxy_type: str, site_key: str) -> Tuple[bool, Optional[float]]:
        """
        Check if proxy works for a specific site (not blocked/captcha'd).
        Returns: (success, response_time_ms)
        """
        url = SITE_TESTS.get(site_key)
        if not url:
            return False, None

        proxy_url = self._format_proxy(proxy, proxy_type)
        if not proxy_url:
            return False, None

        async with self._sem:
            t0 = time.monotonic()
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector, timeout=self.timeout) as session:
                    async with session.get(url, proxy=proxy_url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                    }) as resp:
                        elapsed = round((time.monotonic() - t0) * 1000, 2)
                        if resp.status != 200:
                            return False, elapsed

                        body = (await resp.text())[:5000].lower()
                        for indicator in BLOCK_INDICATORS:
                            if indicator in body:
                                logger.debug(f"Proxy {proxy} blocked on {site_key}: found '{indicator}'")
                                return False, elapsed

                        return True, elapsed
            except Exception as e:
                logger.debug(f"Proxy {proxy} failed for {site_key}: {e}")
                return False, None

    async def check_batch(self, proxies: list) -> list:
        """Check a batch of (proxy, type) tuples concurrently."""
        tasks = [self.check_proxy(p, t) for p, t in proxies]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def check_batch_for_site(self, proxies: list, site_key: str) -> list:
        """Check a batch for a specific site."""
        tasks = [self.check_for_site(p, t, site_key) for p, t in proxies]
        return await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _format_proxy(proxy: str, proxy_type: str) -> Optional[str]:
        """Format proxy string for aiohttp."""
        if proxy_type in ("http", "https"):
            return f"http://{proxy}"
        elif proxy_type == "socks4":
            return f"socks4://{proxy}"
        elif proxy_type == "socks5":
            return f"socks5://{proxy}"
        return None
