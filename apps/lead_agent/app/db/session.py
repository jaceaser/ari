"""
SQLAlchemy engine and session factory.
Provides a context-manager-style get_db() for use in repositories.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine():
    settings = get_settings()
    return create_engine(
        settings.sql_connection_string,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_pre_ping=True,
        echo=False,
    )


@lru_cache
def get_session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context-manager session. Always closes on exit."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
