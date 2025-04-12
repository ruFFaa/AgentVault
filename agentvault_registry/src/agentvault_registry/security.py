import secrets
import logging
from passlib.context import CryptContext
from typing import Optional # Added Optional

# --- FastAPI Imports ---
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

# --- SQLAlchemy Imports ---
from sqlalchemy.ext.asyncio import AsyncSession

# --- Local Imports ---
# Fix the imports to use absolute paths instead of relative
from agentvault_registry import models
from agentvault_registry.database import get_db
from agentvault_registry.crud.developer import get_developer_by_plain_api_key


logger = logging.getLogger(__name__)

# --- Password Hashing Context ---
# Using bcrypt as the default hashing scheme.
# deprecated="auto" will automatically upgrade hashes if schemes change later.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- API Key Verification ---
def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """
    Verifies a plain API key against its stored hash.

    Args:
        plain_api_key: The API key provided by the user/client.
        hashed_api_key: The hash stored in the database.

    Returns:
        True if the key matches the hash, False otherwise.
    """
    try:
        return pwd_context.verify(plain_api_key, hashed_api_key)
    except Exception as e:
        # Log potential errors during verification (e.g., invalid hash format)
        logger.error(f"Error verifying API key hash: {e}", exc_info=True)
        return False

# --- API Key Hashing ---
def hash_api_key(api_key: str) -> str:
    """
    Hashes an API key using the configured context (bcrypt).

    Args:
        api_key: The plain text API key to hash.

    Returns:
        The resulting hash string.
    """
    return pwd_context.hash(api_key)

# --- Secure API Key Generation ---
def generate_secure_api_key(length: int = 32) -> str:
    """
    Generates a cryptographically secure, URL-safe API key.

    Args:
        length: The desired byte length of the random part of the key.
                The resulting string length will be longer due to URL-safe encoding.

    Returns:
        A secure API key string, prefixed with 'avreg_'.
    """
    if length < 24: # Ensure reasonable entropy
        logger.warning(f"Requested API key length ({length}) is short; using minimum of 24 bytes.")
        length = 24
    random_part = secrets.token_urlsafe(length)
    api_key = f"avreg_{random_part}"
    logger.info(f"Generated new secure API key (prefix added).")
    return api_key

# --- FastAPI API Key Authentication Dependency ---

# Define the header scheme we expect for the API key
# auto_error=False allows us to return a custom 403 if the header is missing
api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)

async def get_current_developer(
    api_key: Optional[str] = Depends(api_key_header), # Use Optional here with auto_error=False
    db: AsyncSession = Depends(get_db)
) -> models.Developer:
    """
    FastAPI dependency to get the current developer based on the X-Api-Key header.

    Raises:
        HTTPException(403) if the X-Api-Key header is missing or empty.
        HTTPException(401) if the API key is invalid.

    Returns:
        The authenticated Developer database model instance.
    """
    if not api_key:
        logger.warning("Authentication attempt failed: X-Api-Key header missing.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated: X-Api-Key header missing or empty"
        )

    # Use the CRUD function to find the developer by the plain key
    # (Remembering the inefficiency note for production)
    developer = await get_developer_by_plain_api_key(db=db, plain_key=api_key)

    if developer is None:
        logger.warning(f"Authentication attempt failed: Invalid API Key provided (Key starts with: {api_key[:6]}...).")
        # Use 401 for invalid credentials
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    logger.debug(f"Successfully authenticated developer ID: {developer.id}")
    return developer