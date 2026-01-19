"""
Database connection and utilities.
Uses asyncpg for async PostgreSQL connections.
"""

import asyncpg
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging

from .config import get_settings

logger = logging.getLogger(__name__)


class Database:
    """Async database connection manager."""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.settings = get_settings()
    
    async def connect(self):
        """Create connection pool."""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    self.settings.supabase_url,
                    min_size=2,
                    max_size=10,
                    ssl="require",
                    command_timeout=30
                )
                logger.info("Database connection pool created")
            except Exception as e:
                logger.error(f"Failed to create database pool: {e}")
                raise
    
    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute query and return all results as list of dicts."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Execute query and return single result as dict."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def execute(self, query: str, *args) -> str:
        """Execute a query (INSERT, UPDATE, DELETE)."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)


# Global database instance
db = Database()


async def get_db() -> Database:
    """Dependency to get database instance."""
    return db
