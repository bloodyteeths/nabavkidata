"""
Shared asyncpg connection pool for modules that use raw SQL.
Used by corruption.py and any future modules needing raw asyncpg access.
"""
import asyncpg
import os
import logging
from dotenv import load_dotenv
load_dotenv()


logger = logging.getLogger(__name__)

_pool: asyncpg.Pool = None


async def get_asyncpg_pool() -> asyncpg.Pool:
    """Get or create the shared asyncpg connection pool."""
    global _pool
    if _pool is None or _pool._closed:
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        # Strip SQLAlchemy dialect prefix if present
        dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(
            dsn,
            min_size=2,
            max_size=8,
            max_inactive_connection_lifetime=300,
            command_timeout=30,
        )
        logger.info("asyncpg connection pool created (min=2, max=8)")
    return _pool


async def close_asyncpg_pool():
    """Close the pool on app shutdown."""
    global _pool
    if _pool and not _pool._closed:
        await _pool.close()
        logger.info("asyncpg connection pool closed")
