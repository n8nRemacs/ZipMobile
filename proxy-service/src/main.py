"""
proxy-service — universal proxy manager.
FastAPI app with lifespan, API routes, and scheduled refresh.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .config import settings
from .pool import ProxyPool
from .scheduler import init_scheduler, shutdown_scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

pool = ProxyPool()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.connect()
    init_scheduler(pool)
    logger.info(f"proxy-service started on :{settings.port}")
    yield
    shutdown_scheduler()
    await pool.close()
    logger.info("proxy-service stopped")


app = FastAPI(title="proxy-service", version="1.0.0", lifespan=lifespan)


# ── Schemas ──────────────────────────────────────────────────

class ReportRequest(BaseModel):
    host: str
    port: int
    success: bool
    response_time: Optional[float] = None
    banned_site: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "proxy-service"}


@app.get("/proxy/get")
async def proxy_get(protocol: str = "http", for_site: Optional[str] = None):
    """
    Get a verified working proxy.
    Pre-checks the proxy before returning (up to 3 attempts).
    """
    result = await pool.get_proxy(protocol=protocol, for_site=for_site)
    if not result:
        raise HTTPException(status_code=404, detail="No working proxies available")
    return result


@app.post("/proxy/report")
async def proxy_report(req: ReportRequest):
    """Report proxy usage result from a consumer."""
    await pool.report(
        host=req.host,
        port=req.port,
        success=req.success,
        response_time=req.response_time,
        banned_site=req.banned_site,
    )
    return {"status": "ok"}


@app.post("/proxy/refresh")
async def proxy_refresh(background_tasks: BackgroundTasks):
    """Trigger scrape + check cycle (runs in background)."""
    background_tasks.add_task(_run_refresh)
    return {"status": "started", "message": "Refresh running in background"}


async def _run_refresh():
    try:
        result = await pool.refresh()
        logger.info(f"Manual refresh result: {result}")
    except Exception as e:
        logger.error(f"Manual refresh failed: {e}")


@app.get("/proxy/stats")
async def proxy_stats():
    """Pool statistics."""
    return await pool.get_stats()


# ── Entrypoint ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
