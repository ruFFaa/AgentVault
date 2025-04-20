import logging
import datetime
import uuid
from typing import Optional, List, Dict, Any, Union
import re

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from agentvault_registry import models, schemas, security

logger = logging.getLogger(__name__)

# Define constants
API_KEY_PREFIX = "avreg_"  # This was missing and causing errors

async def get_developer_by_id(db: AsyncSession, developer_id: int) -> Optional[models.Developer]:
    """Get a developer by ID, with eager loading of agent cards."""
    try:
        return await db.get(models.Developer, developer_id, options=[selectinload(models.Developer.agent_cards)])
    except Exception as e:
        logger.error(f"Error fetching developer ID {developer_id}: {e}", exc_info=True)
        return None

async def get_developer_by_email(db: AsyncSession, email: str) -> Optional[models.Developer]:
    """Get a developer by email address."""
    try:
        stmt = select(models.Developer).where(models.Developer.email == email)
        result = await db.execute(stmt)
        return await result.scalar_one_or_none()  # Fix: await the scalar_one_or_none call
    except Exception as e:
        logger.error(f"Error fetching developer by email '{email}': {e}", exc_info=True)
        return None

async def create_developer_with_hashed_details(
    db: AsyncSession, developer_data: models.Developer
) -> models.Developer:
    """
    Create a new developer record, directly taking a Developer model.
    Expects password to already be hashed.
    """
    try:
        db.add(developer_data)
        await db.commit()
        await db.refresh(developer_data)
        logger.info(f"Created new developer: {developer_data.email}")
        return developer_data
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Database constraint violated creating developer: {e}", exc_info=True)
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating developer: {e}", exc_info=True)
        raise

async def create_developer(db: AsyncSession, developer: schemas.DeveloperCreate) -> models.Developer:
    """
    Create a new developer record, hashing the provided password.
    """
    hashed_password = security.hash_password(developer.password)
    
    # Generate a verification token
    verification_token = security.generate_verification_token()
    
    # Create the Developer model instance
    db_developer = models.Developer(
        email=developer.email,
        name=developer.name,
        hashed_password=hashed_password,
        is_verified=False,
        email_verification_token=verification_token,
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    
    return await create_developer_with_hashed_details(db, db_developer)

async def get_developer_by_verification_token(db: AsyncSession, token: str) -> Optional[models.Developer]:
    """Get a developer by email verification token."""
    try:
        stmt = select(models.Developer).where(models.Developer.email_verification_token == token)
        result = await db.execute(stmt)
        return await result.scalar_one_or_none()  # Fix: await the scalar_one_or_none call
    except Exception as e:
        logger.error(f"Error fetching developer by verification token: {e}", exc_info=True)
        return None

async def verify_developer_email(db: AsyncSession, developer: models.Developer) -> bool:
    """Mark a developer's email as verified and clear the verification token."""
    try:
        developer.is_verified = True
        developer.email_verification_token = None
        developer.verified_at = datetime.datetime.now(datetime.timezone.utc)
        
        db.add(developer)
        await db.commit()
        await db.refresh(developer)
        logger.info(f"Developer email verified: {developer.email}")
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"Error verifying developer email: {e}", exc_info=True)
        return False

async def create_api_key(
    db: AsyncSession, developer_id: int, prefix: str, hashed_key: str, description: str
) -> Optional[models.DeveloperApiKey]:
    """Create a new API key for a developer."""
    try:
        api_key = models.DeveloperApiKey(
            developer_id=developer_id,
            key_prefix=prefix,
            hashed_key=hashed_key,
            description=description,
            is_active=True,
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        logger.info(f"Created new API key for developer ID {developer_id}")
        return api_key
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating API key for developer ID {developer_id}: {e}", exc_info=True)
        return None

async def get_developer_by_plain_api_key(db: AsyncSession, plain_key: str) -> Optional[models.Developer]:
    """Get a developer by plain API key, verifying the hash match."""
    if not plain_key.startswith(API_KEY_PREFIX):
        logger.warning(f"Attempted access with invalid API key format")
        return None
    
    try:
        # Get active API keys with matching prefix
        stmt = (
            select(models.DeveloperApiKey)
            .where(
                models.DeveloperApiKey.key_prefix == API_KEY_PREFIX,
                models.DeveloperApiKey.is_active == True
            )
            .options(selectinload(models.DeveloperApiKey.developer))
        )
        result = await db.execute(stmt)
        api_keys = await result.scalars().all()  # Fix: await scalars().all()
        
        # Check each key for a hash match
        for api_key in api_keys:
            if security.verify_api_key(plain_key, api_key.hashed_key):
                # Update last_used_at timestamp
                api_key.last_used_at = datetime.datetime.now(datetime.timezone.utc)
                db.add(api_key)
                await db.commit()
                return api_key.developer
        
        return None
    except Exception as e:
        logger.error(f"Error validating API key: {e}", exc_info=True)
        return None

async def get_active_api_keys_for_developer(db: AsyncSession, developer_id: int) -> List[models.DeveloperApiKey]:
    """Get all active API keys for a developer."""
    try:
        stmt = (
            select(models.DeveloperApiKey)
            .where(
                models.DeveloperApiKey.developer_id == developer_id,
                models.DeveloperApiKey.is_active == True
            )
            .order_by(models.DeveloperApiKey.created_at.desc())
        )
        result = await db.execute(stmt)
        scalars_result = await result.scalars()  # Fix: await the scalars call
        keys = list(scalars_result.all())
        return keys
    except Exception as e:
        logger.error(f"Error fetching API keys for developer {developer_id}: {e}", exc_info=True)
        return []

async def deactivate_api_key(db: AsyncSession, developer_id: int, api_key_id: int) -> bool:
    """Deactivate an API key for a developer."""
    try:
        # Get the API key
        api_key = await db.get(models.DeveloperApiKey, api_key_id)
        
        # Check if API key exists and belongs to the developer
        if not api_key:
            logger.warning(f"API key ID {api_key_id} not found for deactivation")
            return False
            
        if api_key.developer_id != developer_id:
            logger.warning(f"API key ID {api_key_id} does not belong to developer {developer_id}")
            return False
            
        # If already inactive, nothing to do
        if not api_key.is_active:
            logger.info(f"API key ID {api_key_id} is already inactive")
            return True
            
        # Deactivate the key
        api_key.is_active = False
        api_key.deactivated_at = datetime.datetime.now(datetime.timezone.utc)
        
        db.add(api_key)
        await db.commit()
        logger.info(f"Deactivated API key ID {api_key_id} for developer {developer_id}")
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deactivating API key {api_key_id}: {e}", exc_info=True)
        return False

async def get_developer_access_level(db: AsyncSession, developer_id: int) -> str:
    """
    Get a developer's access level. Currently just checks if they're verified,
    but will expand to include other levels (e.g., admin) in the future.
    
    Returns a string value: "none", "unverified", or "verified"
    """
    developer = await get_developer_by_id(db, developer_id)
    
    if not developer:
        return "none"
    
    if not developer.is_verified:
        return "unverified"
    
    # Default for verified users
    return "verified"