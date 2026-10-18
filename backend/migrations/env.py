import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app.config import get_settings
from app.db.session import create_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    database_url = get_settings().database_url
    if not database_url:
        raise SystemExit("set DATABASE_URL to run migrations")
    engine = create_engine(database_url)
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("offline migrations are not supported; run them against DATABASE_URL")
asyncio.run(run_async_migrations())
