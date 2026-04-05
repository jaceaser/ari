"""
Alembic env.py — async-aware, reads DB URL from METERING_DATABASE_URL env var.

Uses asyncpg (same driver as the app) via async_engine_from_config so there
is only one driver dependency. Alembic wraps the async calls in asyncio.run().

Run migrations:
    cd apps/api
    METERING_DATABASE_URL="postgresql+asyncpg://..." alembic upgrade head
"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from billing.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    url = os.getenv("METERING_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "METERING_DATABASE_URL is not set. "
            "Export it before running alembic, e.g.:\n"
            "  METERING_DATABASE_URL=postgresql+asyncpg://... alembic upgrade head"
        )
    # Normalise to asyncpg scheme
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL instead)."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Connect via asyncpg and run migrations in a sync callback."""
    connectable = async_engine_from_config(
        {"sqlalchemy.url": _get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
