"""
asyncpg connection pool для Profi Sandbox
"""
import asyncpg
from .config import settings

pool: asyncpg.Pool | None = None


async def init_pool():
    global pool
    pool = await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        ssl="require",
    )
    return pool


async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    return pool
