import secrets
import logging
from passlib.context import CryptContext

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
