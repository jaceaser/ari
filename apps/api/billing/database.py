"""
Async PostgreSQL connection for the metering database (ari_metering).

Uses SQLAlchemy 2.x async engine with asyncpg driver.
Targets the same server as apps/lead_agent (ari-leads-pg.postgres.database.azure.com)
but a separate database so billing data stays isolated from lead scraping data.

Required env var: METERING_DATABASE_URL
  Accepts any of:
    postgres://user:pass@host:port/ari_metering?sslmode=require
    postgresql://user:pass@host:port/ari_metering?sslmode=require
    postgresql+asyncpg://user:pass@host:port/ari_metering?ssl=require

If METERING_DATABASE_URL is not set, all operations that call get_db_session()
will raise RuntimeError. The metering_service catches this and logs — it never
crashes user-facing code.
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger("ari.billing.database")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def _get_database_url() -> str | None:
    url = os.getenv("METERING_DATABASE_URL", "").strip()
    if not url:
        return None
    # Normalise to asyncpg scheme
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_engine() -> AsyncEngine | None:
    global _engine
    if _engine is None:
        url = _get_database_url()
        if not url:
            return None
        _engine = create_async_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory() -> async_sessionmaker | None:
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        if engine is None:
            return None
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an async SQLAlchemy session. Commits on clean exit, rolls back on
    exception, and always closes the session.

    Raises RuntimeError if METERING_DATABASE_URL is not set.
    Callers in metering_service.py catch this and log rather than propagating.
    """
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError(
            "Metering database not configured — set METERING_DATABASE_URL env var "
            "to a postgresql+asyncpg:// connection string for ari_metering."
        )
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
