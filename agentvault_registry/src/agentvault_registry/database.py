import logging
from typing import AsyncGenerator
import os # Import os to check environment

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
# --- ADDED: Import InvalidRequestError for specific catch ---
from sqlalchemy.exc import InvalidRequestError
# --- END ADDED ---


# Import settings to get the database URL
from .config import settings

logger = logging.getLogger(__name__)

# --- Database Engine Setup ---
DATABASE_URL_TO_USE = settings.DATABASE_URL

# --- ADDED: Explicitly ensure asyncpg dialect in URL ---
if not DATABASE_URL_TO_USE.startswith("postgresql+asyncpg"):
    if DATABASE_URL_TO_USE.startswith("postgresql"):
        DATABASE_URL_TO_USE = DATABASE_URL_TO_USE.replace("postgresql://", "postgresql+asyncpg://", 1)
        logger.warning(f"Database URL adjusted to use asyncpg in database.py: {DATABASE_URL_TO_USE}")
    else:
        # Log error but allow to proceed, create_async_engine will likely fail anyway
        logger.error(f"DATABASE_URL in settings does not start with postgresql: {DATABASE_URL_TO_USE}")
# --- END ADDED ---


# Create an asynchronous engine instance.
try:
    engine = create_async_engine(
        DATABASE_URL_TO_USE, # Use the potentially adjusted URL
        pool_pre_ping=True,
        # echo=True, # Uncomment for debugging SQL
    )
    logger.info("SQLAlchemy async engine created successfully.")
# --- ADDED: Specific catch for the driver error ---
except InvalidRequestError as e:
    if "The asyncio extension requires an async driver" in str(e):
        logger.critical(
            f"FATAL: SQLAlchemy async engine creation failed! It detected the synchronous 'psycopg2' driver "
            f"instead of the required 'asyncpg', despite the URL being '{DATABASE_URL_TO_USE}'. "
            f"Ensure 'asyncpg' is installed and potentially check for conflicting SQLAlchemy/Alembic configurations or environment variables."
        )
    else:
        logger.critical(f"FATAL: SQLAlchemy InvalidRequestError during engine creation: {e}", exc_info=True)
    raise # Re-raise the original error after logging critical info
# --- END ADDED ---
except Exception as e:
    logger.critical(f"FATAL: Failed to create SQLAlchemy engine: {e}", exc_info=True)
    raise

# --- Session Factory ---
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
logger.info("SQLAlchemy async session maker configured.")


# --- Base Class for Declarative Models ---
Base = declarative_base()
logger.info("SQLAlchemy declarative base created.")


# --- Dependency for FastAPI ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an SQLAlchemy asynchronous session."""
    async with AsyncSessionLocal() as session:
        logger.debug(f"Yielding database session: {session}")
        try:
            yield session
        except Exception:
            logger.exception("Exception occurred during database session, rolling back.")
            await session.rollback()
            raise
        finally:
            logger.debug(f"Database session closed: {session}")
