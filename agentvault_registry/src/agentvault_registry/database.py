import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Import settings to get the database URL
from .config import settings

logger = logging.getLogger(__name__)

# --- Database Engine Setup ---
# Create an asynchronous engine instance.
# pool_pre_ping=True helps detect and handle stale connections.
# echo=True can be useful for debugging SQL statements, but disable for production.
try:
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        # echo=True, # Uncomment for debugging SQL
    )
    logger.info("SQLAlchemy async engine created successfully.")
except Exception as e:
    logger.error(f"Failed to create SQLAlchemy engine: {e}", exc_info=True)
    # Depending on application structure, you might want to exit or raise here
    raise

# --- Session Factory ---
# Create an asynchronous session factory (sessionmaker).
# expire_on_commit=False prevents attributes from being expired after commit,
# which is often useful in async contexts and FastAPI dependencies.
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
logger.info("SQLAlchemy async session maker configured.")


# --- Base Class for Declarative Models ---
# All database models will inherit from this Base.
Base = declarative_base()
logger.info("SQLAlchemy declarative base created.")


# --- Dependency for FastAPI ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an SQLAlchemy asynchronous session.

    Ensures the session is closed after the request is finished.
    """
    async with AsyncSessionLocal() as session:
        logger.debug(f"Yielding database session: {session}")
        try:
            yield session
            # Optionally commit here if you want automatic commit per request,
            # but usually commits are handled within CRUD operations.
            # await session.commit()
        except Exception:
            # Rollback in case of exceptions during the request handling
            logger.exception("Exception occurred during database session, rolling back.")
            await session.rollback()
            raise
        finally:
            # The session is automatically closed by the context manager 'async with'
            logger.debug(f"Database session closed: {session}")
