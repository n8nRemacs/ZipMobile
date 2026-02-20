"""
Moba.ru parser adapter for Orchestrator.
Wraps the existing SHOPS/Moba/moba_full_parser.py with auto-cookie refresh.
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from .base import BaseParser, Product, ProxyBannedException

logger = logging.getLogger(__name__)

PARSER_DIR = "/mnt/projects/repos/ZipMobile/SHOPS/Moba"
PARSER_SCRIPT = "moba_full_parser.py"
AUTO_COOKIES_SCRIPT = "auto_cookies.py"
COOKIES_FILE = os.path.join(PARSER_DIR, "moba_cookies.json")


class MobaParser(BaseParser):
    shop_code = "moba"
    shop_name = "Moba.ru"
    needs_proxy = False  # uses cookies instead of proxy
    parser_dir = PARSER_DIR

    async def ensure_cookies(self, twocaptcha_key: str = None) -> bool:
        """
        Validate existing cookies; auto-refresh if expired.
        Returns True if cookies are ready.
        """
        # Quick validate
        proc = await asyncio.create_subprocess_exec(
            sys.executable, os.path.join(PARSER_DIR, AUTO_COOKIES_SCRIPT),
            "--validate",
            cwd=PARSER_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        if proc.returncode == 0:
            logger.info("Moba cookies are valid")
            return True

        # Need refresh
        logger.info("Moba cookies expired — auto-refreshing ...")
        cmd = [
            sys.executable,
            os.path.join(PARSER_DIR, AUTO_COOKIES_SCRIPT),
            "--force",
        ]
        if twocaptcha_key:
            cmd.extend(["--twocaptcha", twocaptcha_key])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=PARSER_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        if proc.returncode == 0:
            logger.info("Cookies refreshed successfully")
            return True

        logger.error(
            "Cookie refresh failed: %s",
            stderr.decode("utf-8", errors="replace")[:500],
        )
        return False

    async def parse_all(self, proxy: str = None, checkpoint=None) -> List[Product]:
        """
        Ensure cookies are valid, then run moba_full_parser.py --full.
        Proxy param is accepted for interface compat but ignored (cookies used instead).
        """
        # Step 1: cookies
        if not await self.ensure_cookies():
            raise ProxyBannedException("Cannot get valid moba.ru cookies")

        # Step 2: run parser
        cmd = ["python3", PARSER_SCRIPT, "--full"]
        logger.info("Running Moba full parser with cookies")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=PARSER_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=1800,  # 30 min max
        )

        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            logger.error(f"Moba parser failed (rc={proc.returncode}): {stderr_text[:500]}")

        # Check for captcha/block indicators
        combined = (stdout_text + stderr_text).lower()
        block_indicators = ["captcha", "smartcaptcha", "blocked", "403", "access denied"]
        for indicator in block_indicators:
            if indicator in combined:
                raise ProxyBannedException(f"Moba blocked: found '{indicator}' in output")

        # Parse JSON output from data files
        products = self._parse_data_files()
        if not products:
            products = self._parse_output(stdout_text)

        return products

    def _parse_output(self, stdout: str) -> List[Product]:
        """Parse JSON lines or JSON array from stdout."""
        products = []

        # Try to find JSON array in output
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Look for the JSON output marker
            if line.startswith("[") or line.startswith("{"):
                try:
                    data = json.loads(line)
                    if isinstance(data, list):
                        for item in data:
                            p = self._to_product(item)
                            if p:
                                products.append(p)
                    elif isinstance(data, dict):
                        if "products" in data:
                            for item in data["products"]:
                                p = self._to_product(item)
                                if p:
                                    products.append(p)
                        else:
                            p = self._to_product(data)
                            if p:
                                products.append(p)
                except json.JSONDecodeError:
                    continue

        return products

    @staticmethod
    def _to_product(item: dict) -> Optional[Product]:
        article = item.get("article", "").strip()
        name = item.get("name", "").strip()
        if not article or not name:
            return None
        return Product(
            article=article,
            name=name,
            price=float(item.get("price", 0)),
            in_stock=item.get("in_stock", True),
            category=item.get("category", ""),
            url=item.get("url", ""),
        )

    def _parse_data_files(self) -> List[Product]:
        """Read most recent output from moba_data/ directory."""
        data_dir = os.path.join(PARSER_DIR, "moba_data")
        if not os.path.isdir(data_dir):
            return []

        # Find latest JSON file
        json_files = sorted(
            [f for f in os.listdir(data_dir) if f.endswith(".json")],
            reverse=True,
        )
        if not json_files:
            return []

        latest = os.path.join(data_dir, json_files[0])
        try:
            with open(latest) as f:
                data = json.load(f)
            raw = data.get("products", []) if isinstance(data, dict) else data
            products = []
            for item in raw:
                p = self._to_product(item)
                if p:
                    products.append(p)
            logger.info("Loaded %d products from %s", len(products), latest)
            return products
        except Exception as e:
            logger.error("Failed to read %s: %s", latest, e)
            return []

    async def health_check(self, proxy: str = None) -> bool:
        """Quick check: do we have valid cookies for moba.ru?"""
        return await self.ensure_cookies()
