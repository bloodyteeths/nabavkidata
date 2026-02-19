"""
Shared Database Connection Pool for AI Module

This module provides a single connection pool shared across all AI components
to prevent connection exhaustion under load.

Usage:
    from db_pool import get_pool, get_connection

    # Option 1: Get a connection from the pool
    async with get_connection() as conn:
        result = await conn.fetch("SELECT * FROM tenders LIMIT 10")

    # Option 2: Get the pool directly
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetch("SELECT * FROM tenders LIMIT 10")
"""
import os
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager
import asyncpg
from dotenv import load_dotenv
load_dotenv()


logger = logging.getLogger(__name__)

# Global pool instance
_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()

# Pool configuration - conservative settings to share with FastAPI backend
POOL_MIN_SIZE = 2  # Minimum connections
POOL_MAX_SIZE = 10  # Maximum connections (shared across all AI operations)
POOL_MAX_INACTIVE_TIME = 300  # Close idle connections after 5 minutes
POOL_COMMAND_TIMEOUT = 60  # Query timeout


def _get_database_url() -> str:
    """Get database URL from environment and convert to asyncpg format"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    # Convert SQLAlchemy URL format to asyncpg format
    # asyncpg doesn't understand postgresql+asyncpg://
    return database_url.replace('postgresql+asyncpg://', 'postgresql://')


async def get_pool() -> asyncpg.Pool:
    """
    Get or create the shared connection pool.

    This function is thread-safe and will only create one pool instance.

    Returns:
        asyncpg.Pool: The shared connection pool
    """
    global _pool

    if _pool is not None and not _pool._closed:
        return _pool

    async with _pool_lock:
        # Double-check after acquiring lock
        if _pool is not None and not _pool._closed:
            return _pool

        database_url = _get_database_url()

        logger.info(f"Creating shared AI connection pool (min={POOL_MIN_SIZE}, max={POOL_MAX_SIZE})")

        _pool = await asyncpg.create_pool(
            database_url,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            max_inactive_connection_lifetime=POOL_MAX_INACTIVE_TIME,
            command_timeout=POOL_COMMAND_TIMEOUT,
        )

        logger.info("Shared AI connection pool created successfully")
        return _pool


async def close_pool():
    """
    Close the shared connection pool.

    Call this during application shutdown.
    """
    global _pool

    if _pool is not None:
        logger.info("Closing shared AI connection pool")
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection():
    """
    Context manager to get a connection from the shared pool.

    Usage:
        async with get_connection() as conn:
            result = await conn.fetch("SELECT 1")

    The connection is automatically returned to the pool when done.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def get_pool_stats() -> dict:
    """
    Get statistics about the connection pool.

    Returns:
        dict with pool statistics
    """
    global _pool

    if _pool is None:
        return {"status": "not_initialized"}

    if _pool._closed:
        return {"status": "closed"}

    return {
        "status": "active",
        "size": _pool.get_size(),
        "free_size": _pool.get_idle_size(),
        "used_size": _pool.get_size() - _pool.get_idle_size(),
        "min_size": _pool.get_min_size(),
        "max_size": _pool.get_max_size(),
    }
