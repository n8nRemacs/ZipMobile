"""
Proxy scraper — collects free proxies from GitHub lists and websites.
"""
import re
import asyncio
import aiohttp
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# GitHub raw proxy lists
GITHUB_SOURCES = [
    {"url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", "type": "http"},
    {"url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt", "type": "socks4"},
    {"url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt", "type": "socks5"},
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", "type": "http"},
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt", "type": "socks4"},
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt", "type": "socks5"},
    {"url": "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt", "type": "socks5"},
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt", "type": "http"},
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt", "type": "socks4"},
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt", "type": "socks5"},
    {"url": "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt", "type": "http"},
    {"url": "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt", "type": "http"},
    {"url": "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt", "type": "socks4"},
    {"url": "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt", "type": "socks5"},
    {"url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt", "type": "http"},
    {"url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt", "type": "socks4"},
    {"url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt", "type": "socks5"},
    {"url": "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt", "type": "http"},
    {"url": "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks4.txt", "type": "socks4"},
    {"url": "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt", "type": "socks5"},
    {"url": "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt", "type": "http"},
    {"url": "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4.txt", "type": "socks4"},
    {"url": "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt", "type": "socks5"},
    {"url": "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt", "type": "http"},
    {"url": "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks4.txt", "type": "socks4"},
    {"url": "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt", "type": "socks5"},
]

# Website sources (plain text endpoints)
WEBSITE_SOURCES = [
    {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all", "type": "http"},
    {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=5000&country=all", "type": "socks4"},
    {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000&country=all", "type": "socks5"},
    {"url": "https://www.proxy-list.download/api/v1/get?type=http", "type": "http"},
    {"url": "https://www.proxy-list.download/api/v1/get?type=https", "type": "http"},
    {"url": "https://www.proxy-list.download/api/v1/get?type=socks4", "type": "socks4"},
    {"url": "https://www.proxy-list.download/api/v1/get?type=socks5", "type": "socks5"},
    {"url": "https://openproxylist.xyz/http.txt", "type": "http"},
]

PROXY_RE = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})")


class ProxyScraper:
    def __init__(self, timeout: int = 15):
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def _fetch(self, session: aiohttp.ClientSession, source: dict) -> List[Dict]:
        """Fetch proxies from a single source."""
        proxies = []
        try:
            async with session.get(source["url"], timeout=self.timeout) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    matches = PROXY_RE.findall(text)
                    for m in matches:
                        proxies.append({
                            "proxy": m,
                            "type": source["type"],
                            "source": source["url"].split("/")[2][:80],
                        })
        except Exception as e:
            logger.debug(f"Failed to fetch {source['url']}: {e}")
        return proxies

    async def scrape_all(self) -> List[Dict]:
        """Scrape all sources concurrently. Returns deduplicated list."""
        all_sources = GITHUB_SOURCES + WEBSITE_SOURCES
        seen = set()
        results = []

        connector = aiohttp.TCPConnector(limit=20, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._fetch(session, s) for s in all_sources]
            lists = await asyncio.gather(*tasks, return_exceptions=True)

            for lst in lists:
                if isinstance(lst, Exception):
                    continue
                for p in lst:
                    if p["proxy"] not in seen:
                        seen.add(p["proxy"])
                        results.append(p)

        logger.info(f"Scraped {len(results)} unique proxies from {len(all_sources)} sources")
        return results
