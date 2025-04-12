import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine # Import AsyncEngine
from alembic import context

# Add project source directory to the Python path to find models and config
# Assumes alembic command is run from the 'agentvault_registry' directory
# The path is adjusted relative to env.py location inside alembic/
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..')) # Path to agentvault_registry/
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import application's configuration and models
try:
    # Import settings to make DATABASE_URL available via environment (though alembic.ini handles it)
    from agentvault_registry.config import settings
    # Import Base from database setup
    from agentvault_registry.database import Base
    # Import all models here so Alembic autogenerate can detect changes
    # Ensure models.py defines __all__ or explicitly import each model class
    from agentvault_registry import models
except ImportError as e:
    sys.stderr.write(f"Error importing application modules: {e}\n")
    sys.stderr.write(f"Ensure 'src' is in sys.path ({src_path}) and models/config are defined.\n")
    sys.exit(1)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata for 'autogenerate' support
# Use the Base metadata from the application's models
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_url():
    """Return the database URL from environment variable via alembic config."""
    # Alembic's configuration already reads sqlalchemy.url = ${DATABASE_URL}
    # from alembic.ini, which sources it from the environment.
    db_url = config.get_main_option("sqlalchemy.url")
    if not db_url:
         # Fallback to reading directly from settings if needed, though ini should work
         db_url = settings.DATABASE_URL
    if not db_url:
        raise ValueError("DATABASE_URL environment variable must be set and accessible.")
    return db_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Create engine configuration dictionary using settings from alembic.ini
    # which already includes the database URL from the environment variable.
    connectable_cfg = config.get_section(config.config_ini_section)
    if not connectable_cfg or "sqlalchemy.url" not in connectable_cfg:
         # Try getting URL directly as fallback
         db_url = get_url()
         if not db_url:
             raise ValueError("Database URL not configured in alembic.ini or environment.")
         connectable_cfg = {"sqlalchemy.url": db_url} # Create config dict manually
    else:
        # Ensure the URL is present if section exists
        if "sqlalchemy.url" not in connectable_cfg:
             db_url = get_url()
             if not db_url:
                 raise ValueError("Database URL not configured in alembic.ini or environment.")
             connectable_cfg["sqlalchemy.url"] = db_url


    # Create an AsyncEngine instance
    connectable = AsyncEngine(
        engine_from_config(
            connectable_cfg,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            future=True, # Ensure SQLAlchemy 2.0 style engine
        )
    )

    # Connect and run migrations within an async context
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    # Dispose the engine after use
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # Run the async online migrations
    import asyncio
    asyncio.run(run_migrations_online())
