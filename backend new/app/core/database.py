"""
database.py — Async SQLAlchemy 2.0 engine & session factory for Supabase/PostgreSQL.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Load .env from the backend root (two levels up from app/core/)
# ---------------------------------------------------------------------------
_backend_root = Path(__file__).resolve().parents[2]
load_dotenv(_backend_root / ".env")

# ---------------------------------------------------------------------------
# Read connection strings
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.environ["DATABASE_URL"]          # asyncpg URL  (postgresql+asyncpg://...)
SYNC_DATABASE_URL: str = os.environ["SYNC_DATABASE_URL"]  # psycopg2 URL (postgresql+psycopg2://...)

# ---------------------------------------------------------------------------
# Async engine (used by the application at runtime)
# ---------------------------------------------------------------------------
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# Declarative base (all ORM models inherit from this)
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass

# ---------------------------------------------------------------------------
# FastAPI dependency — yields a managed AsyncSession
# ---------------------------------------------------------------------------
async def get_db() -> AsyncSession:  # type: ignore[override]
    """Yield an AsyncSession and guarantee it is closed after the request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


__all__ = [
    "engine",
    "Base",
    "AsyncSessionLocal",
    "SYNC_DATABASE_URL",
    "get_db",
]
