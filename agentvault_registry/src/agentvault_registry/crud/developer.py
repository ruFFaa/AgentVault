import logging
import datetime
from typing import Optional, Tuple, List
from sqlalchemy import select, update, func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Import models and security utils using absolute imports
from agentvault_registry import models
from agentvault_registry import security

logger = logging.getLogger(__name__)

# --- Developer CRUD ---

async def get_developer_by_id(db: AsyncSession, developer_id: int) -> Optional[models.Developer]:
    """Retrieves a developer by their primary key ID."""
    logger.debug(f"Fetching developer by ID: {developer_id}")
    try:
        developer = await db.get(models.Developer, developer_id, options=[selectinload(models.Developer.api_keys)])
        if developer:
            logger.debug(f"Found developer: {developer.name}")
        else:
            logger.debug(f"Developer ID {developer_id} not found.")
        return developer
    except Exception as e:
        logger.error(f"Error fetching developer by ID {developer_id}: {e}", exc_info=True)
        return None

async def get_developer_by_email(db: AsyncSession, email: str) -> Optional[models.Developer]:
    """Retrieves a developer by their email address."""
    logger.debug(f"Fetching developer by email: {email}")
    # --- MODIFIED: Implement actual query ---
    stmt = select(models.Developer).where(models.Developer.email == email)
    try:
        result = await db.execute(stmt)
        developer = result.scalar_one_or_none()
        if developer:
            logger.debug(f"Found developer by email: {developer.name} (ID: {developer.id})")
        else:
            logger.debug(f"Developer with email {email} not found.")
        return developer
    except Exception as e:
        logger.error(f"Error fetching developer by email {email}: {e}", exc_info=True)
        return None
    # --- END MODIFIED ---

async def create_developer_with_hashed_details(
    db: AsyncSession, developer_data: models.Developer
) -> Optional[models.Developer]:
    """
    Creates a new developer record from a pre-filled model instance.
    Handles commit and potential IntegrityError.

    Args:
        db: The SQLAlchemy async session.
        developer_data: A models.Developer instance containing all required fields
                        (name, email, hashed_password, hashed_recovery_key, etc.).

    Returns:
        The created and refreshed Developer object, or None if creation failed.
    """
    logger.info(f"Attempting to create developer record for email: {developer_data.email}")
    # --- MODIFIED: Implement actual DB operations ---
    db.add(developer_data)
    try:
        await db.commit()
        await db.refresh(developer_data) # Refresh to get ID, defaults, etc.
        logger.info(f"Successfully created developer '{developer_data.name}' with ID: {developer_data.id}")
        return developer_data
    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"Integrity error creating developer '{developer_data.name}': {e}")
        raise e # Re-raise for the router to catch
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error creating developer '{developer_data.name}': {e}", exc_info=True)
        raise e # Re-raise for the router to catch
    # --- END MODIFIED ---

async def get_developer_by_verification_token(db: AsyncSession, token: str) -> Optional[models.Developer]:
    """Retrieves a developer by their email verification token."""
    logger.debug(f"Fetching developer by verification token (prefix: {token[:6]}...).")
    # --- MODIFIED: Implement actual query ---
    stmt = select(models.Developer).where(models.Developer.email_verification_token == token)
    try:
        result = await db.execute(stmt)
        developer = result.scalar_one_or_none()
        if developer:
            logger.debug(f"Found developer by verification token: {developer.name} (ID: {developer.id})")
        else:
            logger.debug("Developer with matching verification token not found.")
        return developer
    except Exception as e:
        logger.error(f"Error fetching developer by verification token: {e}", exc_info=True)
        return None
    # --- END MODIFIED ---

# --- Placeholder for password reset token lookup ---
async def get_developer_by_password_reset_token(db: AsyncSession, token: str) -> Optional[models.Developer]:
    """
    Retrieves a developer by their password reset token.
    (Placeholder - Requires password reset token field in Developer model)
    """
    logger.warning("get_developer_by_password_reset_token is not fully implemented (needs DB model field).")
    return None


# --- API Key CRUD ---

async def get_developer_by_plain_api_key(db: AsyncSession, plain_key: str) -> Optional[models.Developer]:
    """
    Retrieves a developer by verifying a plain text API key against stored hashes
    in the DeveloperApiKey table. Updates last_used_at on success.
    """
    logger.debug(f"Attempting to find developer by plain API key (prefix: {plain_key[:10]}...).")
    if not plain_key or not plain_key.startswith("avreg_"):
        logger.debug("Invalid API key format provided.")
        return None

    key_prefix = plain_key.split("_")[0] + "_"

    stmt = (
        select(models.DeveloperApiKey)
        .options(selectinload(models.DeveloperApiKey.developer)) # Eager load developer
        .where(
            models.DeveloperApiKey.key_prefix == key_prefix,
            models.DeveloperApiKey.is_active == True
        )
    )

    try:
        result = await db.execute(stmt)
        possible_keys = result.scalars().all()
        logger.debug(f"Found {len(possible_keys)} active API keys with prefix '{key_prefix}' to check.")

        verified_developer: Optional[models.Developer] = None
        verified_key_id: Optional[int] = None

        for db_key in possible_keys:
            if security.verify_api_key(plain_key, db_key.hashed_key):
                logger.info(f"API key verified for Developer ID: {db_key.developer_id}, Key ID: {db_key.id}")
                verified_developer = db_key.developer
                verified_key_id = db_key.id
                break

        if verified_developer and verified_key_id:
            update_stmt = (
                update(models.DeveloperApiKey)
                .where(models.DeveloperApiKey.id == verified_key_id)
                .values(last_used_at=datetime.datetime.now(timezone.utc))
                .execution_options(synchronize_session=False)
            )
            try:
                await db.execute(update_stmt)
                await db.commit()
                logger.debug(f"Updated last_used_at for API key ID: {verified_key_id}")
            except Exception as update_err:
                logger.error(f"Failed to update last_used_at for API key ID {verified_key_id}: {update_err}", exc_info=True)
                await db.rollback()

            return verified_developer
        else:
            logger.debug("No matching active API key found for the provided plain key.")
            return None

    except Exception as e:
        logger.error(f"Error fetching/verifying API key: {e}", exc_info=True)
        return None

async def create_api_key(
    db: AsyncSession,
    developer_id: int,
    prefix: str,
    hashed_key: str,
    description: Optional[str] = None
) -> Optional[models.DeveloperApiKey]:
    """Creates a new programmatic API key record for a developer."""
    logger.info(f"Creating new API key for developer ID: {developer_id} with prefix: {prefix}")
    # --- MODIFIED: Implement actual DB operations ---
    db_api_key = models.DeveloperApiKey(
        developer_id=developer_id,
        key_prefix=prefix,
        hashed_key=hashed_key,
        description=description,
        is_active=True
    )
    db.add(db_api_key)
    try:
        await db.commit()
        await db.refresh(db_api_key)
        logger.info(f"Successfully created API key record ID: {db_api_key.id}")
        return db_api_key
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database integrity error creating API key for developer {developer_id}: {e}", exc_info=True)
        raise e # Let router handle
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error creating API key for developer {developer_id}: {e}", exc_info=True)
        raise e # Let router handle
    # --- END MODIFIED ---

async def get_active_api_keys_for_developer(db: AsyncSession, developer_id: int) -> List[models.DeveloperApiKey]:
    """Retrieves all active API key records for a specific developer."""
    logger.debug(f"Fetching active API keys for developer ID: {developer_id}")
    # --- MODIFIED: Implement actual query ---
    stmt = select(models.DeveloperApiKey).where(
        models.DeveloperApiKey.developer_id == developer_id,
        models.DeveloperApiKey.is_active == True
    ).order_by(models.DeveloperApiKey.created_at.desc())
    try:
        result = await db.execute(stmt)
        keys = list(result.scalars().all())
        logger.debug(f"Found {len(keys)} active API keys for developer {developer_id}")
        return keys
    except Exception as e:
        logger.error(f"Error fetching API keys for developer {developer_id}: {e}", exc_info=True)
        return []
    # --- END MODIFIED ---

async def deactivate_api_key(db: AsyncSession, developer_id: int, api_key_id: int) -> bool:
    """
    Deactivates an API key based on its ID and owning developer ID.
    Returns True if deactivated, False if not found or not owned.
    """
    logger.info(f"Attempting to deactivate API key ID '{api_key_id}' for developer ID: {developer_id}")
    # --- MODIFIED: Implement actual DB operations ---
    try:
        # Use db.get for efficient lookup by primary key
        db_key = await db.get(models.DeveloperApiKey, api_key_id)

        if not db_key:
            logger.warning(f"API key ID '{api_key_id}' not found.")
            return False

        if db_key.developer_id != developer_id:
            logger.warning(f"Developer {developer_id} attempted to deactivate API key {api_key_id} owned by {db_key.developer_id}.")
            return False # Not owned

        if not db_key.is_active:
            logger.info(f"API key ID '{api_key_id}' is already inactive.")
            return True # Idempotent

        # Deactivate the key
        db_key.is_active = False
        db.add(db_key) # Add to session to track change
        await db.commit()
        logger.info(f"Successfully deactivated API key ID: {db_key.id}")
        return True

    except Exception as e:
        await db.rollback()
        logger.error(f"Error deactivating API key ID '{api_key_id}' for developer {developer_id}: {e}", exc_info=True)
        return False
    # --- END MODIFIED ---

# Add other developer CRUD functions as needed (e.g., update profile)
