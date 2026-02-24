"""
Multi-protocol proxy checker.
Tests HTTP, HTTPS, SOCKS4, SOCKS5 for each proxy independently.
Resolves proxy country via ip-api.com.
"""
import asyncio
import time
import aiohttp
import logging
from typing import Optional, Dict, Tuple

from aiohttp_socks import ProxyConnector, ProxyType

logger = logging.getLogger(__name__)

TEST_URL_HTTP = "http://httpbin.org/ip"
TEST_URL_HTTPS = "https://httpbin.org/ip"
GEOIP_URL = "http://ip-api.com/json/{ip}?fields=countryCode"

SITE_TESTS = {
    "moba": "https://moba.ru/",
    "greenspark": "https://green-spark.ru/",
    "memstech": "https://memstech.ru/",
}

BLOCK_INDICATORS = [
    "captcha", "smartcaptcha", "blocked", "access denied",
    "403 forbidden", "challenge", "cf-browser-verification",
    "just a moment", "checking your browser",
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"


class ProxyChecker:
    def __init__(self, timeout: int = 10, concurrency: int = 100):
        self.timeout = timeout
        self.concurrency = concurrency
        self._sem = asyncio.Semaphore(concurrency)
        self._geo_sem = asyncio.Semaphore(40)  # ip-api.com: 45 req/min free tier

    async def check_proxy_protocols(self, host: str, port: int) -> Dict:
        """Check all protocols + resolve country. Returns protocol booleans + response_time + country."""
        results = await asyncio.gather(
            self._test_http(host, port),
            self._test_https(host, port),
            self._test_socks4(host, port),
            self._test_socks5(host, port),
            self._resolve_country(host),
            return_exceptions=True,
        )

        response_times = []
        protocols = {}
        for proto, res in zip(("http", "https", "socks4", "socks5"), results[:4]):
            if isinstance(res, Exception):
                protocols[proto] = False
            else:
                ok, rt = res
                protocols[proto] = ok
                if ok and rt is not None:
                    response_times.append(rt)

        country = results[4] if not isinstance(results[4], Exception) else None
        avg_rt = round(sum(response_times) / len(response_times), 2) if response_times else None
        return {**protocols, "response_time_ms": avg_rt, "country": country}

    async def quick_test(self, host: str, port: int, protocol: str) -> Tuple[bool, Optional[float]]:
        """Quick single-protocol test for pre-delivery verification."""
        # Note: _test_* methods already acquire self._sem, no need to acquire here
        if protocol == "http":
            return await self._test_http(host, port)
        elif protocol == "https":
            return await self._test_https(host, port)
        elif protocol == "socks4":
            return await self._test_socks4(host, port)
        elif protocol == "socks5":
            return await self._test_socks5(host, port)
        return False, None

    async def check_for_site(
        self, host: str, port: int, protocol: str, site_key: str
    ) -> Tuple[bool, Optional[float]]:
        """Check if proxy works for a specific site (not blocked)."""
        url = SITE_TESTS.get(site_key)
        if not url:
            return False, None

        async with self._sem:
            t0 = time.monotonic()
            try:
                connector = self._make_connector(host, port, protocol)
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.get(url, headers={"User-Agent": USER_AGENT}) as resp:
                        elapsed = round((time.monotonic() - t0) * 1000, 2)
                        if resp.status != 200:
                            return False, elapsed
                        body = (await resp.text())[:5000].lower()
                        for indicator in BLOCK_INDICATORS:
                            if indicator in body:
                                logger.debug(f"Proxy {host}:{port} blocked on {site_key}: '{indicator}'")
                                return False, elapsed
                        return True, elapsed
            except Exception as e:
                logger.debug(f"Proxy {host}:{port} failed for {site_key}: {e}")
                return False, None

    async def check_batch(self, proxies: list) -> list:
        """Check a batch of {host, port} dicts. Returns list of protocol dicts."""
        tasks = [self.check_proxy_protocols(p["host"], p["port"]) for p in proxies]
        return await asyncio.gather(*tasks, return_exceptions=True)

    # ── Internal protocol tests ──────────────────────────────

    async def _test_http(self, host: str, port: int) -> Tuple[bool, Optional[float]]:
        async with self._sem:
            t0 = time.monotonic()
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.get(
                        TEST_URL_HTTP, proxy=f"http://{host}:{port}"
                    ) as resp:
                        if resp.status == 200:
                            return True, round((time.monotonic() - t0) * 1000, 2)
            except Exception:
                pass
            return False, None

    async def _test_https(self, host: str, port: int) -> Tuple[bool, Optional[float]]:
        async with self._sem:
            t0 = time.monotonic()
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.get(
                        TEST_URL_HTTPS, proxy=f"http://{host}:{port}"
                    ) as resp:
                        if resp.status == 200:
                            return True, round((time.monotonic() - t0) * 1000, 2)
            except Exception:
                pass
            return False, None

    async def _test_socks4(self, host: str, port: int) -> Tuple[bool, Optional[float]]:
        async with self._sem:
            t0 = time.monotonic()
            try:
                connector = ProxyConnector(
                    proxy_type=ProxyType.SOCKS4,
                    host=host,
                    port=port,
                )
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.get(TEST_URL_HTTP) as resp:
                        if resp.status == 200:
                            return True, round((time.monotonic() - t0) * 1000, 2)
            except Exception:
                pass
            return False, None

    async def _test_socks5(self, host: str, port: int) -> Tuple[bool, Optional[float]]:
        async with self._sem:
            t0 = time.monotonic()
            try:
                connector = ProxyConnector(
                    proxy_type=ProxyType.SOCKS5,
                    host=host,
                    port=port,
                )
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.get(TEST_URL_HTTP) as resp:
                        if resp.status == 200:
                            return True, round((time.monotonic() - t0) * 1000, 2)
            except Exception:
                pass
            return False, None

    async def _resolve_country(self, host: str) -> Optional[str]:
        """Resolve proxy IP country via ip-api.com. Returns 2-letter code or None."""
        async with self._geo_sem:
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(GEOIP_URL.format(ip=host)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data.get("countryCode")
                        elif resp.status == 429:
                            await asyncio.sleep(2)
                            return None
            except Exception:
                pass
            return None

    @staticmethod
    def _make_connector(host: str, port: int, protocol: str):
        """Create appropriate connector for a protocol."""
        if protocol in ("http", "https"):
            return aiohttp.TCPConnector(ssl=False)
        elif protocol == "socks4":
            return ProxyConnector(proxy_type=ProxyType.SOCKS4, host=host, port=port)
        elif protocol == "socks5":
            return ProxyConnector(proxy_type=ProxyType.SOCKS5, host=host, port=port)
        return aiohttp.TCPConnector(ssl=False)
