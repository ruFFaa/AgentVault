import logging
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# Import models and security utils using absolute imports
from agentvault_registry import models
from agentvault_registry import security

logger = logging.getLogger(__name__)

async def create_developer(db: AsyncSession, name: str) -> Tuple[Optional[models.Developer], Optional[str]]:
    """
    Creates a new developer record and generates their initial API key.

    Args:
        db: The SQLAlchemy async session.
        name: The desired name for the developer (must be unique).

    Returns:
        A tuple containing the created Developer object and the plain text API key,
        or (None, None) if creation failed (e.g., duplicate name).
    """
    logger.info(f"Attempting to create developer with name: {name}")

    # 1. Generate a new plain text API key
    plain_api_key = security.generate_secure_api_key()
    if not plain_api_key: # Should not happen with secrets, but safety check
        logger.error("Failed to generate a secure API key.")
        return None, None

    # 2. Hash the plain text key
    try:
        hashed_key = security.hash_api_key(plain_api_key)
    except Exception as e:
        logger.error(f"Failed to hash API key: {e}", exc_info=True)
        return None, None # Cannot proceed without a valid hash

    # 3. Create the Developer model instance
    db_developer = models.Developer(name=name, api_key_hash=hashed_key)

    # 4. Add to session and attempt to commit
    db.add(db_developer)
    try:
        await db.commit()
        await db.refresh(db_developer) # Load generated ID, timestamps etc.
        logger.info(f"Successfully created developer '{name}' with ID: {db_developer.id}")
        # Return the persisted object and the *plain* key for the caller to display once
        return db_developer, plain_api_key
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Failed to create developer '{name}': Name likely already exists. Error: {e}")
        # Optionally re-raise a custom exception or return specific error info
        # For now, returning None, None indicates failure
        return None, None
    except Exception as e:
        await db.rollback()
        logger.error(f"An unexpected error occurred creating developer '{name}': {e}", exc_info=True)
        return None, None


async def get_developer_by_plain_api_key(db: AsyncSession, plain_key: str) -> Optional[models.Developer]:
    """
    Retrieves a developer by verifying a plain text API key against stored hashes.

    NOTE: This iterates through all developers and performs hash verification for each.
          This is INEFFICIENT for large numbers of developers and should be
          revisited with a better strategy (e.g., key prefixes, dedicated key table)
          in a production system. Suitable for Phase 1 demonstration.

    Args:
        db: The SQLAlchemy async session.
        plain_key: The plain text API key provided for authentication.

    Returns:
        The matching Developer object if found and verified, otherwise None.
    """
    logger.debug("Attempting to find developer by plain API key (iterative check).")
    if not plain_key:
        return None

    all_developers: list[models.Developer] = [] # Define type hint
    try:
        stmt = select(models.Developer)
        result = await db.execute(stmt)
        # --- MODIFIED: Use async list comprehension ---
        all_developers = [dev async for dev in result.scalars()]
        # --- END MODIFIED ---
    except Exception as e:
        logger.error(f"Failed to query developers for API key check: {e}", exc_info=True)
        return None

    logger.debug(f"Checking plain key against {len(all_developers)} developer hashes.")
    for developer in all_developers:
        # --- ADDED: Ensure hash comparison happens ---
        if developer.api_key_hash and security.verify_api_key(plain_key, developer.api_key_hash):
        # --- END ADDED ---
            logger.info(f"API key verified for developer ID: {developer.id}, Name: {developer.name}")
            return developer

    logger.debug("No matching developer found for the provided API key.")
    return None

# Add other developer CRUD functions as needed (e.g., get_developer_by_id, get_developer_by_name, update, delete)
