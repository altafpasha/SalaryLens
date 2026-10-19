"""
SalaryLens AI by CodeSec — Database Engine and Session Management
"""
from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.base import Base

# Async Engine for FastAPI
async_engine_args = {
    "echo": settings.DB_ECHO,
    "future": True,
}
if "sqlite" not in settings.DATABASE_URL:
    async_engine_args.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
    })

async_engine = create_async_engine(
    settings.DATABASE_URL,
    **async_engine_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

sync_url = settings.DATABASE_SYNC_URL
if sync_url.startswith("postgresql://"):
    sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

# Synchronous Engine for Alembic & Worker Tasks
sync_engine = create_engine(
    sync_url,
    echo=settings.DB_ECHO,
    future=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Creates tables if they don't exist (primarily for tests/sqlite dev)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
