import os
import sys
import asyncio
# --- ADDED: Import logging ---
import logging
# --- END ADDED ---
from logging.config import fileConfig
from sqlalchemy import create_engine # Keep sync engine import for offline mode if needed
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine, async_engine_from_config
from alembic import context

# --- ADDED: Get logger instance ---
log = logging.getLogger(__name__) # Use 'log' to avoid potential clash with logging config below
# --- END ADDED ---


# Add project source directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path: sys.path.insert(0, src_path)

# Import application's configuration and models
try:
    from agentvault_registry.config import settings
    from agentvault_registry.database import Base
    from agentvault_registry import models
except ImportError as e:
    sys.stderr.write(f"Error importing application modules: {e}\n")
    sys.stderr.write(f"Ensure 'src' is in sys.path ({src_path}) and models/config are defined.\n")
    sys.exit(1)

config = context.config
# Interpret the config file for Python logging.
# This line sets up loggers based on alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
# Note: The logger obtained above might be overridden by fileConfig if names clash.
# Using 'log' instead of 'logger' avoids this potential issue.

target_metadata = Base.metadata

def get_url():
    """Return the database URL, ensuring it specifies asyncpg."""
    db_url = config.get_main_option("sqlalchemy.url")
    if not db_url: db_url = settings.DATABASE_URL
    if not db_url: raise ValueError("DATABASE_URL environment variable must be set.")
    if not db_url.startswith("postgresql+asyncpg"):
        if db_url.startswith("postgresql"):
            db_url_adjusted = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            # --- MODIFIED: Use 'log' instead of 'logger' ---
            log.warning(f"Database URL adjusted to use asyncpg: {db_url_adjusted}")
            # --- END MODIFIED ---
            return db_url_adjusted # Return the adjusted URL
        else:
            raise ValueError(f"Database URL does not appear to be a PostgreSQL URL: {db_url}")
    return db_url # Return original if already correct

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    """Helper function to run migrations within a context."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable_cfg = config.get_section(config.config_ini_section)
    db_url = get_url() # Get potentially adjusted URL
    if connectable_cfg:
        connectable_cfg["sqlalchemy.url"] = db_url
    else:
        connectable_cfg = {"sqlalchemy.url": db_url}

    connectable = async_engine_from_config(
        connectable_cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
