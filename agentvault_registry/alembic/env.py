import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add project source directory to the Python path to find models and config
# Assumes alembic command is run from the 'agentvault_registry' directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..')) # Path to agentvault_registry/
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import application's configuration and models
try:
    # Import settings to make DATABASE_URL available via environment
    from agentvault_registry.config import settings
    # Import Base from database setup
    from agentvault_registry.database import Base
    # Import all models here so Alembic autogenerate can detect changes
    import agentvault_registry.models # This imports models defined in models.py
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
    """Return the database URL from environment variable."""
    # Alembic's configuration already reads sqlalchemy.url = ${DATABASE_URL}
    # from alembic.ini, which sources it from the environment.
    # No need to explicitly read settings.DATABASE_URL here.
    return config.get_main_option("sqlalchemy.url")

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    if not url:
        raise ValueError("DATABASE_URL environment variable must be set for Alembic.")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Create engine configuration dictionary using settings from alembic.ini
    # which already includes the database URL from the environment variable.
    connectable_cfg = config.get_section(config.config_ini_section)
    if not connectable_cfg or "sqlalchemy.url" not in connectable_cfg:
         raise ValueError("Database URL not configured in alembic.ini or environment.")

    connectable = engine_from_config(
        connectable_cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
