from collections.abc import AsyncIterator
from functools import cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


def create_engine(database_url: str) -> AsyncEngine:
    # pool_pre_ping: Supabase's pooler drops idle connections.
    return create_async_engine(database_url, pool_pre_ping=True)


@cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return async_sessionmaker(create_engine(database_url), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
