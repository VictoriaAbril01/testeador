"""Alembic environment for the TestLab PostgreSQL schema."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.database.base import Base
from app.database.config import get_database_url
import app.models  # noqa: F401 - register mappings with Base.metadata


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(get_database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported")
run_migrations_online()
