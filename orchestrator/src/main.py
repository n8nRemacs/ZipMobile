"""
Orchestrator API — FastAPI server for proxy management and parser orchestration.
Port: 8100
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks

from .proxy.pool import ProxyPool
from .proxy.database import ProxyDatabase
from .supervisor import Supervisor
from .parsers.moba import MobaParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
proxy_db = ProxyDatabase()
proxy_pool = ProxyPool(proxy_db)
supervisor = Supervisor(proxy_pool)

# Parser registry
PARSERS = {
    "moba": MobaParser(),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await proxy_db.connect()
    logger.info("Orchestrator started, DB connected")
    yield
    await proxy_db.close()
    logger.info("Orchestrator stopped")


app = FastAPI(title="ZipMobile Orchestrator", version="0.1.0", lifespan=lifespan)


# === Proxy endpoints ===

@app.post("/proxy/refresh")
async def proxy_refresh(background_tasks: BackgroundTasks):
    """Scrape new proxies and check them."""
    background_tasks.add_task(proxy_pool.refresh)
    return {"status": "refresh started in background"}


@app.get("/proxy/stats")
async def proxy_stats():
    """Get proxy pool statistics."""
    return await proxy_pool.get_stats()


@app.post("/proxy/check/{site}")
async def proxy_check_for_site(site: str, limit: int = 50, background_tasks: BackgroundTasks = None):
    """Check working proxies against a specific site."""
    if background_tasks:
        background_tasks.add_task(proxy_pool.check_for_site, site, limit)
        return {"status": f"checking {limit} proxies for {site} in background"}
    count = await proxy_pool.check_for_site(site, limit)
    return {"site": site, "working": count}


@app.get("/proxy/get")
async def proxy_get(proxy_type: str = "http", for_site: str = None):
    """Get a working proxy."""
    proxy = await proxy_pool.get_proxy(proxy_type, for_site)
    if not proxy:
        raise HTTPException(404, "No working proxies available")
    return {"proxy": proxy, "for_site": for_site}


# === Parser endpoints ===

@app.post("/parse/full/{shop}")
async def parse_full(shop: str, background_tasks: BackgroundTasks):
    """Start full parsing for a shop."""
    parser = PARSERS.get(shop)
    if not parser:
        raise HTTPException(404, f"Unknown shop: {shop}. Available: {list(PARSERS.keys())}")

    background_tasks.add_task(supervisor.run_parser, parser, "full")
    return {"status": "started", "shop": shop, "needs_proxy": parser.needs_proxy}


@app.get("/parse/status")
async def parse_status():
    """Get status of all active/completed parse tasks."""
    return supervisor.get_status()


# === Health ===

@app.get("/health")
async def health():
    stats = await proxy_pool.get_stats()
    return {
        "status": "ok",
        "parsers": list(PARSERS.keys()),
        "proxy_pool": stats,
    }
