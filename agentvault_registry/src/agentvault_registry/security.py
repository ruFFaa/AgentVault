import secrets
import logging
# --- ADDED: Imports for JWT and datetime ---
from datetime import datetime, timedelta, timezone
# --- MODIFIED: Added Optional, Any, List ---
from typing import Optional, Any, List
# --- END MODIFIED ---
from jose import JWTError, jwt
# --- END ADDED ---
from passlib.context import CryptContext
from typing import Optional # Added Optional

# --- FastAPI Imports ---
# --- MODIFIED: Added Header ---
from fastapi import Depends, HTTPException, status, Header
# --- END MODIFIED ---
# --- MODIFIED: Import OAuth2PasswordBearer ---
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
# --- END MODIFIED ---


# --- SQLAlchemy Imports ---
from sqlalchemy.ext.asyncio import AsyncSession
# --- ADDED: Import select and func for API key update ---
from sqlalchemy import select, update, func, and_
# --- END ADDED ---


# --- Local Imports ---
# Fix the imports to use absolute paths instead of relative
from agentvault_registry import models
from agentvault_registry.database import get_db
# --- MODIFIED: Import specific CRUD functions ---
from agentvault_registry.crud import developer as developer_crud # Use alias
# --- END MODIFIED ---
# --- ADDED: Import settings ---
from agentvault_registry.config import settings
# --- END ADDED ---


logger = logging.getLogger(__name__)

# --- Password Hashing Context ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- JWT Configuration ---
SECRET_KEY = settings.API_KEY_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# --- API Key Verification (for programmatic keys) ---
def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """Verifies a plain API key against its stored hash using passlib context."""
    try:
        return pwd_context.verify(plain_api_key, hashed_api_key)
    except Exception as e:
        logger.error(f"Error verifying API key hash: {e}", exc_info=True)
        return False

# --- API Key Hashing (for programmatic keys) ---
def hash_api_key(api_key: str) -> str:
    """Hashes an API key using the configured context (bcrypt)."""
    return pwd_context.hash(api_key)

# --- Password Verification ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against its stored hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password hash: {e}", exc_info=True)
        return False

# --- Password Hashing ---
def hash_password(password: str) -> str:
    """Hashes a password using the configured context."""
    return pwd_context.hash(password)

# --- Secure API Key Generation (for programmatic keys) ---
def generate_secure_api_key(length: int = 32) -> str:
    """Generates a cryptographically secure, URL-safe API key."""
    if length < 24:
        logger.warning(f"Requested API key length ({length}) is short; using minimum of 24 bytes.")
        length = 24
    random_part = secrets.token_urlsafe(length)
    api_key = f"avreg_{random_part}"
    logger.info(f"Generated new secure programmatic API key (prefix added).")
    return api_key

# --- Recovery Key Functions ---
def generate_recovery_keys(count: int = 3) -> List[str]:
    """Generates a list of secure, user-friendly recovery keys."""
    keys = []
    for _ in range(count):
        key = f"avrec-{secrets.token_hex(4)}-{secrets.token_hex(4)}-{secrets.token_hex(4)}"
        keys.append(key)
    logger.info(f"Generated {count} recovery keys.")
    return keys

def hash_recovery_key(recovery_key: str) -> str:
    """Hashes a single recovery key."""
    return pwd_context.hash(recovery_key)

def verify_recovery_key(plain_recovery_key: str, stored_hash: str) -> bool:
    """Verifies a plain recovery key against its stored hash."""
    try:
        return pwd_context.verify(plain_recovery_key, stored_hash)
    except Exception as e:
        logger.error(f"Error verifying recovery key hash: {e}", exc_info=True)
        return False

# --- JWT Creation ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- FastAPI Authentication Dependencies ---

# Define header scheme for programmatic API keys
api_key_header_scheme = APIKeyHeader(name="X-Api-Key", auto_error=False)

# Define OAuth2 scheme for JWT Bearer tokens (still needed for login endpoint response)
# Set auto_error=True for the required dependency
oauth2_scheme_required = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)
# Keep auto_error=False for potential use elsewhere if needed, but optional verify won't use it directly
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# --- JWT Token Verification Dependencies ---
async def verify_access_token_required(token: str = Depends(oauth2_scheme_required)) -> int:
    """
    FastAPI dependency to verify JWT token (required).
    Raises HTTPException on failure. Returns developer ID (int).
    Uses OAuth2PasswordBearer with auto_error=True.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # auto_error=True in oauth2_scheme_required handles the case where token is None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        developer_id_str: Optional[str] = payload.get("sub")
        if developer_id_str is None:
            logger.warning("JWT verification failed: 'sub' claim missing.")
            raise credentials_exception

        purpose: Optional[str] = payload.get("purpose")
        if purpose == "password-set":
             logger.warning("JWT verification failed: Password set token used for regular access.")
             raise credentials_exception

        try:
            developer_id = int(developer_id_str)
        except ValueError:
            logger.warning(f"JWT verification failed: 'sub' claim '{developer_id_str}' is not an integer.")
            raise credentials_exception

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise credentials_exception from e
    except Exception as e:
         logger.error(f"Unexpected error during JWT decode/validation: {e}", exc_info=True)
         raise credentials_exception from e

    logger.debug(f"Required JWT verified successfully for developer ID: {developer_id}")
    return developer_id

# --- MODIFIED: verify_access_token_optional uses Header directly ---
async def verify_access_token_optional(authorization: Optional[str] = Header(None)) -> Optional[int]:
    """
    FastAPI dependency to optionally verify JWT token from Authorization header.
    Returns developer ID (int) if valid, None otherwise (does not raise HTTPException).
    """
    if authorization is None:
        logger.debug("Optional JWT verification: No Authorization header provided.")
        return None # No header, no user

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.debug(f"Optional JWT verification failed: Invalid Authorization header format (Scheme is not Bearer or wrong parts). Header: {authorization[:20]}...")
        return None # Invalid scheme or format

    token = parts[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        developer_id_str: Optional[str] = payload.get("sub")
        if developer_id_str is None:
            logger.debug("Optional JWT verification failed: 'sub' claim missing.")
            return None

        purpose: Optional[str] = payload.get("purpose")
        if purpose == "password-set":
             logger.debug("Optional JWT verification failed: Password set token used.")
             return None

        try:
            developer_id = int(developer_id_str)
            logger.debug(f"Optional JWT verification succeeded for developer ID: {developer_id}")
            return developer_id
        except ValueError:
            logger.debug(f"Optional JWT verification failed: 'sub' claim '{developer_id_str}' is not an integer.")
            return None

    except JWTError as e: # Catches ExpiredSignatureError, InvalidTokenError etc.
        logger.debug(f"Optional JWT verification failed: {e}")
        return None # Invalid token
    except Exception as e:
         logger.error(f"Unexpected error during optional JWT decode/validation: {e}", exc_info=True)
         return None # Treat unexpected errors as invalid token
# --- END MODIFIED ---

async def verify_temp_password_token(token: str = Depends(oauth2_scheme_required)) -> int: # Use required scheme here
    """
    FastAPI dependency specifically for verifying the temporary password set token.
    Checks for the 'password-set' purpose. Raises HTTPException on failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired password recovery token",
        headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
    )
    # auto_error=True handles missing token

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": True}) # Ensure expiry is checked
        developer_id_str: Optional[str] = payload.get("sub")
        purpose: Optional[str] = payload.get("purpose")

        if developer_id_str is None or purpose != "password-set":
            logger.warning(f"Temporary token verification failed: 'sub' missing or purpose is not 'password-set'. Purpose: {purpose}")
            raise credentials_exception
        try:
            developer_id = int(developer_id_str)
        except ValueError:
            logger.warning(f"Temporary token verification failed: 'sub' claim '{developer_id_str}' is not an integer.")
            raise credentials_exception

    except JWTError as e:
        logger.warning(f"Temporary token JWT verification failed: {e}")
        raise credentials_exception from e
    except Exception as e:
         logger.error(f"Unexpected error during temporary token decode/validation: {e}", exc_info=True)
         raise credentials_exception from e

    logger.debug(f"Temporary password set token verified successfully for developer ID: {developer_id}")
    return developer_id


# --- Developer Fetching Dependencies ---
async def get_current_developer(
    db: AsyncSession = Depends(get_db),
    developer_id: int = Depends(verify_access_token_required) # Use REQUIRED verifier
) -> models.Developer:
    """
    FastAPI dependency to get the current developer based on a verified JWT token.
    Raises HTTPException(401) if the developer ID from the token doesn't exist in DB.
    """
    developer = await developer_crud.get_developer_by_id(db=db, developer_id=developer_id)

    if developer is None:
        logger.warning(f"Authenticated developer ID {developer_id} not found in database.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"Successfully identified current developer: ID={developer.id}, Name={developer.name}")
    return developer

# --- MODIFIED: get_current_developer_optional uses OPTIONAL JWT verification ---
async def get_current_developer_optional(
    db: AsyncSession = Depends(get_db),
    developer_id: Optional[int] = Depends(verify_access_token_optional) # Use OPTIONAL verifier
) -> Optional[models.Developer]:
    """
    FastAPI dependency that attempts to get the current developer based on the
    Authorization: Bearer header, returning None if token missing/invalid or dev not found.
    """
    if developer_id is None:
        logger.debug("Optional authentication: No valid developer ID from token.")
        return None

    try:
        developer = await developer_crud.get_developer_by_id(db=db, developer_id=developer_id)
        if developer is None:
            logger.debug(f"Optional authentication: Developer ID {developer_id} from token not found.")
            return None
        logger.debug(f"Optional authentication successful for developer ID: {developer.id}")
        return developer
    except Exception as e:
        logger.error(f"Unexpected error during optional developer lookup by ID {developer_id}: {e}", exc_info=True)
        return None
# --- END MODIFIED ---

# --- Dependency for programmatic API Key Auth ---
async def verify_programmatic_api_key(
    api_key: Optional[str] = Depends(api_key_header_scheme), # Use X-Api-Key header
    db: AsyncSession = Depends(get_db)
) -> models.Developer:
    """
    FastAPI dependency to get the current developer based on the X-Api-Key header,
    checking against the new DeveloperApiKey table. Raises HTTPException on failure.
    """
    if not api_key:
        logger.warning("Programmatic API Key auth failed: X-Api-Key header missing.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated: X-Api-Key header missing or empty"
        )

    developer = await developer_crud.get_developer_by_plain_api_key(db=db, plain_key=api_key)

    if developer is None:
        logger.warning(f"Programmatic API Key auth failed: Invalid or inactive API Key provided (Key starts with: {api_key[:10]}...).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API Key"
        )

    logger.debug(f"Successfully authenticated developer ID via programmatic API key: {developer.id}")
    return developer
